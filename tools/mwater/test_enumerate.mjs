// Offline proof for tools/mwater/enumerate.mjs (20 Oct 2026): no network.
// A fake server answers bounded queries in a shuffled order and caps every
// answer at one page, as mWater does. The enumerator must return every row
// exactly once - including a day of 1,300 rows, ids that are not lower-case
// hex, and rows with no date - and must fail loudly, never cut, when a range
// that cannot be split is full.
//   node tools/mwater/test_enumerate.mjs
import { pullResponses, children, PAGE } from "./enumerate.mjs";

let fails = 0;
const check = (name, ok, got) => { console.log(`  ${ok ? "PASS" : "FAIL !"}  ${name}${ok ? "" : `: ${got}`}`); if (!ok) fails++; };

// the children of a prefix cover each string exactly once
const strs = ["", "0", "00", "0f", "1", "9z", ":", "A1", "Zz", "a", "af", "f", "fz", "g", "zz", "~"];
for (const p of ["", "a", "9f"]) {
  const kids = children(p);
  for (const x of strs.map((t) => p + t)) {
    const n = kids.filter((k) => (k.lo === null || x >= k.lo) && (k.hi === null || x < k.hi)).length;
    check(`children(${JSON.stringify(p)}) cover ${JSON.stringify(x)} once`, n === 1, n);
  }
}

const hex = (i) => (i * 2654435761 >>> 0).toString(16).padStart(8, "0") + i.toString(16).padStart(24, "0");
function server(rows) {
  return async (f) => {
    const m = rows.filter((r) => {
      if (f.form !== r.form) return false;
      const d = f.submittedOn;
      if (d === null) { if (r.submittedOn != null) return false; }
      else if (!(r.submittedOn >= d.$gte && r.submittedOn < d.$lt)) return false;
      const id = f._id || {};
      return (id.$gte === undefined || r._id >= id.$gte) && (id.$lt === undefined || r._id < id.$lt);
    });
    return m.sort(() => Math.random() - 0.5).slice(0, PAGE);        // no order, one page
  };
}
const rows = [];
for (let i = 0; i < 1300; i++) rows.push({ _id: hex(i), form: "F", submittedOn: "2026-02-04T08:00:00Z" });
for (let i = 1300; i < 1900; i++) rows.push({ _id: hex(i), form: "F", submittedOn: `2025-${String(1 + i % 12).padStart(2, "0")}-15T00:00:00Z` });
rows.push({ _id: "ABCDEF", form: "F", submittedOn: "2026-02-04T09:00:00Z" });
rows.push({ _id: "zz-odd", form: "F", submittedOn: "2026-02-04T09:00:00Z" });
for (let i = 0; i < 3; i++) rows.push({ _id: "nodate" + i, form: "F", submittedOn: null });
rows.push({ _id: "other", form: "G", submittedOn: "2026-02-04T09:00:00Z" });

const quiet = process.stderr.write.bind(process.stderr);
process.stderr.write = () => true;
const got = await pullResponses("F", "submittedOn", "2025-01-01", server(rows));
process.stderr.write = quiet;
const want = rows.filter((r) => r.form === "F").map((r) => r._id).sort();
const ids = got.map((r) => r._id).sort();
check("every row of the form comes back exactly once", JSON.stringify(ids) === JSON.stringify(want), `${ids.length} of ${want.length}`);

// a full range that cannot be split is an error, never a silent cut
const many = Array.from({ length: PAGE }, (_, i) => ({ _id: "ZZ" + i, form: "F", submittedOn: "2026-03-01T00:00:00Z" }));
let threw = "";
process.stderr.write = () => true;
try { await pullResponses("F", "submittedOn", "2026-03-01", server(many)); } catch (e) { threw = e.message; }
process.stderr.write = quiet;
check("a full range that cannot be split fails loudly", /cannot be split/.test(threw), threw || "no error");

console.log(fails ? `${fails} FAILED` : "every assertion holds");
process.exit(fails ? 1 : 0);
