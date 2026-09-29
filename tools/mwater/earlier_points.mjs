// Earlier-project water points (other organisations' historical records):
// code, name, owning group and GPS, for the Moramanga crosswalk. GET only
// (api.mjs refuses anything else); nothing is written to mWater.
//
//   node tools/mwater/earlier_points.mjs <code,code,...>
import { apiGet } from "./api.mjs";

const codes = (process.argv[2] || "").split(",").filter(Boolean);
if (!codes.length) { console.error("usage: earlier_points.mjs <code,...>"); process.exit(2); }
const pts = await apiGet("entities/water_point", { filter: JSON.stringify({ code: { $in: codes } }),
  limit: 1000, fields: JSON.stringify({ code: 1, name: 1, desc: 1, location: 1, _managed_by: 1, _created_on: 1, water_system: 1 }) });
const groups = {};
for (const g of new Set(pts.map(p => p._managed_by).filter(x => x?.startsWith("group:")))) {
  try { groups[g] = (await apiGet(`groups/${g.slice(6)}`, {})).name; } catch { groups[g] = g; }
}
console.log(JSON.stringify({ read_on: new Date().toISOString(), points: pts.map(p => ({
  code: p.code, name: (p.name || "").trim() || null, owner: groups[p._managed_by] || p._managed_by,
  created_on: (p._created_on || "").slice(0, 10) || null,
  location: p.location?.coordinates ? [p.location.coordinates[1], p.location.coordinates[0]] : null })) }));
