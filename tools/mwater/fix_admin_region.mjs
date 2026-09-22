// Write admin_region to the nine register entities that have none.
//
// EVIDENCE REQUIRED BEFORE ANY WRITE, per point:
//   1. every coded point sharing its commune AND fokontany carries ONE
//      admin_region value, and
//   2. the eight nearest coded points by GPS all carry that same value.
// Both must agree. A point where they do not is skipped and reported.
//
// Only admin_region is written. Names are NOT touched: "Canzee" is the house
// convention for 663 of the 908 managed entities, not an import defect.
//
//   node tools/mwater/fix_admin_region.mjs            # dry run
//   node tools/mwater/fix_admin_region.mjs --write [code ...]
import fs from "node:fs";
import { apiGet, apiWrite, backup } from "./api.mjs";

const NINE = ["698771103","698771110","698771244","698771251","699596004",
              "699596114","742897074","742897115","742897232"];
const WRITE = process.argv.includes("--write");
const ONLY = process.argv.slice(2).filter(a => /^\d{9}$/.test(a));
const LOG = "/home/bushp/sanitap-water-report/data/register_write_log.json";

const hav = (a, b) => {
  const R = 6371000, r = Math.PI / 180;
  const dLat = (b[1]-a[1])*r, dLon = (b[0]-a[0])*r;
  const s = Math.sin(dLat/2)**2 + Math.cos(a[1]*r)*Math.cos(b[1]*r)*Math.sin(dLon/2)**2;
  return 2*R*Math.asin(Math.sqrt(s));
};

const all = [];
for (let skip = 0; ; skip += 500) {
  const r = await apiGet("entities/water_point", {
    filter: JSON.stringify({ _managed_by: "group:aaaf0a14e4ce44eaa7a2bcfd1c74aa56" }),
    limit: 500, skip });
  if (!r.length) break; all.push(...r); if (r.length < 500) break;
}
const coded = all.filter(e => e.admin_region != null);
console.log(`${all.length} managed entities, ${coded.length} carry admin_region\n`);

const log = fs.existsSync(LOG) ? JSON.parse(fs.readFileSync(LOG, "utf8")) : [];
const targets = (ONLY.length ? ONLY : NINE);

for (const code of targets) {
  const e = all.find(x => x.code === code);
  if (!e) { console.log(`  ${code}  NOT FOUND — skipped`); continue; }
  if (e.admin_region != null) { console.log(`  ${code}  already has ${e.admin_region} — skipped`); continue; }

  // evidence 1: fokontany-mates
  const mates = coded.filter(o => o.admin_div3 === e.admin_div3 && o.admin_div4 === e.admin_div4);
  const mateVals = [...new Set(mates.map(o => String(o.admin_region)))];
  // evidence 2: eight nearest coded points
  const near = coded.filter(o => o.location?.coordinates)
    .map(o => ({ ar: String(o.admin_region), d: hav(e.location.coordinates, o.location.coordinates) }))
    .sort((a,b) => a.d - b.d).slice(0, 8);
  const nearVals = [...new Set(near.map(n => n.ar))];

  const agree = mateVals.length === 1 && nearVals.length === 1 && mateVals[0] === nearVals[0];
  const value = mateVals[0];
  const ev = {
    fokontany: `${e.admin_div3}/${e.admin_div4}`,
    fokontany_mates: mates.length, fokontany_values: mateVals,
    nearest8_values: nearVals, nearest_m: Math.round(near[0].d),
  };
  if (!agree) {
    console.log(`  ${code}  REFUSED — evidence disagrees: fokontany ${JSON.stringify(mateVals)}, GPS ${JSON.stringify(nearVals)}`);
    log.push({ code, action: "refused", when: new Date().toISOString(), evidence: ev });
    continue;
  }
  console.log(`  ${code}  ${ev.fokontany.padEnd(24)} -> ${value}   (${mates.length} fokontany-mates, 8/8 nearest, closest ${ev.nearest_m} m)`);
  if (!WRITE) continue;

  const before = backup("before", code, e);
  const doc = { ...e, admin_region: Number(value) };
  await apiWrite("PATCH", "entities/water_point", { doc, base: e });
  const re = await apiGet("entities/water_point", { filter: JSON.stringify({ code }) });
  const after = re[0];
  const okNow = String(after?.admin_region) === value;
  const afterPath = backup("after", code, after);
  console.log(`      written: rev ${e._rev} -> ${after?._rev}  admin_region=${after?.admin_region}  verified=${okNow}`);
  log.push({ code, action: okNow ? "written" : "WRITE NOT VERIFIED",
             when: new Date().toISOString(),
             before: { admin_region: e.admin_region ?? null, _rev: e._rev },
             after: { admin_region: after?.admin_region ?? null, _rev: after?._rev },
             evidence: ev, backups: { before, after: afterPath } });
}
fs.writeFileSync(LOG, JSON.stringify(log, null, 1), "utf8");
console.log(`\nlog: ${LOG} (${log.length} entr${log.length===1?"y":"ies"})`);
