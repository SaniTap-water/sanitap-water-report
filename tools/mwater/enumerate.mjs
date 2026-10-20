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
const succ = (s) => s.slice(0, -1) + String.fromCharCode(s.charCodeAt(s.length - 1) + 1);

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

/** The children of the _id prefix p, covering exactly the strings in
 * [p, succ(p)) - every string when p is "": the strings below p+"0" (p
 * itself included), one prefix per hex digit, the gap between "9" and "a"
 * (upper case, punctuation), and the strings above p+"f". Only the hex
 * prefixes can be split again; a gap that is full is an error, never a cut. */
export function children(p) {
  const out = [{ lo: p || null, hi: p + "0", prefix: null }];
  for (const c of HEX) {
    out.push({ lo: p + c, hi: succ(p + c), prefix: p + c });
    if (c === "9") out.push({ lo: succ(p + "9"), hi: p + "a", prefix: null });
  }
  out.push({ lo: succ(p + "f"), hi: p ? succ(p) : null, prefix: null });
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
