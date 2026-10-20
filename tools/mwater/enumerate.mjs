// Every response of a form, enumerated without skip paging (20 Oct 2026).
//
// mWater's skip/limit has no sort order, so paging a set duplicates some rows
// and drops others. Date windows are stable whatever order the server answers
// in, but a window can hold more than one page: 4 Feb 2026 holds 522
// call-centre responses. Until today the CSV pulls went through the MCP CLI,
// which prints at most 200 rows, and a one-day window cannot be split by
// date - so that day came back as exactly 200 and the extract was 322 rows
// short with no error anywhere. Inside this file nothing pages:
//
//   * fixed calendar-month windows on the date field;
//   * a window that comes back full (a whole page) is split by _id range
//     into sixteen hex-prefix ranges plus the gaps between them, recursively,
//     so every query is bounded and its answer does not depend on where a
//     previous page stopped; the ranges cover every string, so nothing is
//     lost if an _id is not lower-case hex;
//   * every row is de-duplicated on _id.
//
// Every request has a timeout and is retried with backoff. The pull of
// 20 Oct 2026 failed on "Error: fetch" (a network-level failure: no HTTP
// status) after three tries five seconds apart, and the error's cause was cut
// from the log. One diagnostic run the same morning replayed the request
// pattern - 47 windows, a login per window - with every request HTTP 200 and
// none slower than 4.7 s, so the failure was transient. Five tries over three
// minutes ride out a short outage, and a failure now logs its cause. One login
// per process: the CLI logged in once per window, about 150 times a run.
//
// READ-ONLY: through tools/mwater/api.mjs, which refuses anything but GET and
// the login POST /v3/clients.
import { apiGet } from "./api.mjs";

export const PAGE = 500;
const BACKOFF = [5, 15, 45, 90];             // seconds between the five tries
const TIMEOUT_MS = 120000;
const HEX = "0123456789abcdef";
const sleep = (s) => new Promise((r) => setTimeout(r, s * 1000));
// the whole _id space; a full answer splits it into children("")
const TOP = { lo: null, hi: null, prefix: "" };
// the hex string that follows every string with prefix p, in hex order
// ("3f" -> "4", "9" -> "a"); null when p is "" or all "f"
const nextHex = (p) => !p ? null : p.endsWith("f") ? nextHex(p.slice(0, -1)) : p.slice(0, -1) + HEX[HEX.indexOf(p.at(-1)) + 1];

function why(e) {
  const c = e?.cause;
  return String(e?.message || e) + (c ? ` (cause: ${c.code || c.name || ""} ${c.syscall || ""} ${c.message || ""})`.replace(/\s+/g, " ") : "");
}

/** One bounded query, retried with backoff; throws with the cause after the last try. */
export async function query(filter, label) {
  for (let i = 0; ; i++) {
    try {
      let timer;
      const p = await Promise.race([
        apiGet("responses", { filter: JSON.stringify(filter), limit: PAGE, skip: 0 }),
        new Promise((_, no) => { timer = setTimeout(() => no(new Error(`no answer within ${TIMEOUT_MS / 1000} s`)), TIMEOUT_MS); }),
      ]).finally(() => clearTimeout(timer));
      if (!Array.isArray(p)) throw new Error(`expected an array, got ${JSON.stringify(p).slice(0, 120)}`);
      return p;
    } catch (e) {
      if (i >= BACKOFF.length) throw new Error(`${label}: ${i + 1} tries failed; last: ${why(e)}`);
      process.stderr.write(`  ${label}: try ${i + 1} failed (${why(e)}); retrying in ${BACKOFF[i]} s\n`);
      await sleep(BACKOFF[i]);
    }
  }
}

/** The children of the _id prefix p, covering [p, nextHex(p)) - every
 * string when p is "": the strings below p+"0" (p itself), then one range per
 * hex digit, [p+c, p+next c), the last ending at nextHex(p). Every boundary is
 * a hex string, never punctuation: mWater compares _id in a locale collation,
 * not byte order, and the first version's gap [":", "a") between "9" and "a"
 * held every id that starts with a digit (build of 20 Oct 2026, 09:46 UTC).
 * Hex strings sort the same in byte order and in any collation that puts
 * digits before letters, so the boundaries are in order under either, and a
 * chain of ranges between ordered boundaries covers each string exactly once,
 * hex or not. Only the hex ranges can be split again; the range below p+"0"
 * holds at most p itself. */
export function children(p) {
  const out = [{ lo: p || null, hi: p + "0", prefix: null }];
  for (let i = 0; i < HEX.length; i++)
    out.push({ lo: p + HEX[i], hi: i + 1 < HEX.length ? p + HEX[i + 1] : nextHex(p), prefix: p + HEX[i] });
  return out;
}

async function range(base, node, label, out, q) {
  const f = { ...base };
  if (node.lo !== null || node.hi !== null)
    f._id = { ...(node.lo !== null ? { $gte: node.lo } : {}), ...(node.hi !== null ? { $lt: node.hi } : {}) };
  const p = await q(f, label);
  if (p.length < PAGE) { out.push(...p); return; }
  if (node.prefix === null) throw new Error(`${label}: _id range [${node.lo}, ${node.hi}) holds a full page and cannot be split`);
  if (node.prefix.length >= 8) throw new Error(`${label}: still full at _id prefix ${node.prefix}`);
  for (const c of children(node.prefix))
    await range(base, c, `${label.split(" _id ")[0]} _id ${c.lo ?? ""}..${c.hi ?? ""}`, out, q);
}

/** Every response of `form`, by month windows on `field` and _id ranges.
 * `q` is the bounded query (tests pass a fake one; tools/mwater/test_enumerate.mjs). */
export async function pullResponses(form, field = "submittedOn", first = "2019-01-01", q = query) {
  const seen = new Map();
  const end = new Date(Date.now() + 2 * 86400000);
  for (let d = new Date(first + "T00:00:00Z"); d < end; d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1))) {
    const a = d.toISOString().slice(0, 10);
    const b = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1)).toISOString().slice(0, 10);
    const got = [];
    await range({ form, [field]: { $gte: a, $lt: b } }, TOP, `${form.slice(0, 8)} ${a}..${b}`, got, q);
    for (const r of got) seen.set(r._id, r);
    if (got.length) process.stderr.write(`  ${a} .. ${b}  ${got.length} row(s), ${seen.size} unique\n`);
  }
  // responses with no date at all never fall in a window
  const none = [];
  await range({ form, [field]: null }, TOP, `${form.slice(0, 8)} no ${field}`, none, q);
  for (const r of none) seen.set(r._id, r);
  return [...seen.values()];
}
