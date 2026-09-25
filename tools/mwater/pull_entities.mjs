// Stable enumeration of the MadAvance water-point register.
//
// The register was pulled by a separate hand-run export because an UNFILTERED
// water_point export walks the whole global mWater entity table. Filtered to
// the managed group it is one bounded query that returns in about two seconds
// - so the reason it sat outside the build never applied to the filtered form
// of the query. The row count is live: each pull records it in
// data/extract_manifest.json (wp_madavance.csv); no count is fixed here.
//
// It still walks _created_on windows and de-duplicates on _id rather than
// trusting one request. A single request that comes back short looks exactly
// like a complete one, which is the fault that has now produced four artefacts
// in this repository. The windowed total and the single-shot total are both
// reported; they must agree.
//
//   node tools/mwater/pull_entities.mjs <out.csv> [entity_type] [group]
import fs from "node:fs";
import { apiGet } from "./api.mjs";

const [out,
       type = "water_point",
       group = "group:aaaf0a14e4ce44eaa7a2bcfd1c74aa56"] = process.argv.slice(2);
if (!out) { console.error("usage: pull_entities.mjs <out.csv> [type] [group]"); process.exit(2); }

const base = { _managed_by: group };

// one bounded query, for comparison only
const single = await apiGet(`entities/${type}`, { filter: JSON.stringify(base), limit: 5000 });

const seen = new Map();
const start = new Date("2015-01-01T00:00:00Z");
const end = new Date(Date.now() + 86400000);
const STEP = 90 * 86400000;                    // 90-day windows

for (let t = start.getTime(); t < end.getTime(); t += STEP) {
  const a = new Date(t).toISOString(), b = new Date(Math.min(t + STEP, end.getTime())).toISOString();
  const filter = { ...base, _created_on: { $gte: a, $lt: b } };
  let got = 0;
  for (let skip = 0; ; skip += 500) {
    const p = await apiGet(`entities/${type}`, { filter: JSON.stringify(filter), limit: 500, skip });
    for (const r of p) seen.set(r._id, r);
    got += p.length;
    if (p.length < 500) break;
  }
  if (got) process.stderr.write(`  ${a.slice(0, 10)} .. ${b.slice(0, 10)}  ${got} row(s), ${seen.size} unique\n`);
}
// anything with no creation date at all
for (let skip = 0; ; skip += 500) {
  const p = await apiGet(`entities/${type}`, { filter: JSON.stringify({ ...base, _created_on: null }), limit: 500, skip });
  for (const r of p) seen.set(r._id, r);
  if (p.length < 500) break;
}

const rows = [...seen.values()];
if (rows.length !== single.length) {
  console.error(`MISMATCH: windowed walk found ${rows.length}, one bounded query found ` +
                `${single.length}. One of them is short; refusing to write ${out}.`);
  process.exit(1);
}

const cols = [];
for (const r of rows) for (const k of Object.keys(r)) if (!cols.includes(k)) cols.push(k);
const cell = (v) => {
  if (v === null || v === undefined) return "";
  const s = typeof v === "object" ? JSON.stringify(v) : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};
fs.writeFileSync(out, [cols.join(","),
  ...rows.map((r) => cols.map((c) => cell(r[c])).join(","))].join("\n") + "\n");
console.log(`${rows.length} ${type} record(s) -> ${out} (windowed and single-query agree)`);
