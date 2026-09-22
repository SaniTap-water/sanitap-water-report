// Stable enumeration of a form's responses.
//
// mWater's skip/limit paging has no sort order, so the row order shifts
// between requests: two full pulls of the same 1,688-response form returned
// the same TOTAL and 147 rows that differed. Paging cannot be trusted to
// enumerate a set. Walking fixed date windows and de-duplicating on _id can:
// each window is a bounded query whose answer does not depend on where a
// previous page stopped.
//
//   node tools/mwater/pull_form.mjs <form_id> <out.json> [field]
import fs from "node:fs";
import { apiGet } from "./api.mjs";

const [form, out, field = "submittedOn"] = process.argv.slice(2);
if (!form || !out) { console.error("usage: pull_form.mjs <form_id> <out.json> [dateField]"); process.exit(2); }

const seen = new Map();
const start = new Date("2019-01-01T00:00:00Z");
const end = new Date(Date.now() + 86400000);
const STEP = 30 * 86400000;             // 30-day windows

for (let t = start.getTime(); t < end.getTime(); t += STEP) {
  const a = new Date(t).toISOString(), b = new Date(Math.min(t + STEP, end.getTime())).toISOString();
  const filter = { form, [field]: { $gte: a, $lt: b } };
  let got = 0;
  for (let skip = 0; ; skip += 500) {
    const p = await apiGet("responses", { filter: JSON.stringify(filter), limit: 500, skip });
    for (const r of p) seen.set(r._id, r);
    got += p.length;
    if (p.length < 500) break;
  }
  if (got) process.stderr.write(`  ${a.slice(0,10)} .. ${b.slice(0,10)}  ${got} row(s), ${seen.size} unique\n`);
}
// anything with no date at all
for (let skip = 0; ; skip += 500) {
  const p = await apiGet("responses", { filter: JSON.stringify({ form, [field]: null }), limit: 500, skip });
  for (const r of p) seen.set(r._id, r);
  if (p.length < 500) break;
}
const rows = [...seen.values()];
fs.writeFileSync(out, JSON.stringify(rows));
console.log(`${rows.length} unique response(s) -> ${out}`);
