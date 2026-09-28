// Every water_system record within a radius of each given system, in any
// mWater group, with what is attached to it: its creator, the water points
// that name it as their system, and the form responses that reference it.
// GET only (api.mjs refuses anything else); nothing is written to mWater.
//
// Slow: mWater answers a response lookup by entity in about two minutes, so
// a run over the Moramanga systems takes ten minutes or more. It is not a
// weekly build step; tools/moramanga_dedupe.py --history runs it and stores
// the dated result in data/moramanga_system_history.json.
//
//   node tools/mwater/system_history.mjs <code,code,...> [radius_m]
//
// Prints JSON: { radius_m, systems: { <centre code>: [record, ...] } }
import { apiGet } from "./api.mjs";

const [codesArg, radiusArg] = process.argv.slice(2);
if (!codesArg) { console.error("usage: system_history.mjs <code,...> [radius_m]"); process.exit(2); }
const codes = codesArg.split(",").filter(Boolean);
const radius = Number(radiusArg || 3000);

const users = new Map();          // user id -> username, learnt from responses
const groups = new Map();
async function groupName(id) {
  if (!id || !id.startsWith("group:")) return id || null;
  if (!groups.has(id)) {
    try { const g = await apiGet(`groups/${id.slice(6)}`, {}); groups.set(id, g?.name || id); }
    catch { groups.set(id, id); }
  }
  return groups.get(id);
}

const seen = new Map();           // record code -> detail, fetched once
const t0 = Date.now();
const lap = (what) => process.stderr.write(`  ${((Date.now() - t0) / 1000).toFixed(0)}s ${what}\n`);
async function detail(e) {
  if (seen.has(e.code)) return seen.get(e.code);
  lap(`record ${e.code}`);
  const resp = await apiGet("responses", {
    filter: JSON.stringify({ "entities.entityType": "water_system", "entities.value": e.code }),
    limit: 1000, fields: JSON.stringify({ form: 1, status: 1, user: 1, username: 1, submittedOn: 1 }) });
  if (resp.length >= 1000) throw new Error(`${e.code}: 1000 or more responses; page the lookup`);
  for (const r of resp) if (r.user && r.username) users.set(r.user, r.username);
  const byForm = {};
  for (const r of resp) byForm[r.form] = (byForm[r.form] || 0) + 1;
  lap(`  ${resp.length} responses`);
  const pts = await apiGet("entities/water_point", {
    filter: JSON.stringify({ water_system: e._id }), limit: 1000,
    fields: JSON.stringify({ code: 1, name: 1 }) });
  const d = {
    code: e.code, name: (e.name || "").trim() || null,
    managed_by: e._managed_by || null, managed_by_name: await groupName(e._managed_by),
    created_on: e._created_on || null, created_by: e._created_by || null,
    location: e.location?.coordinates ? [e.location.coordinates[1], e.location.coordinates[0]] : null,
    responses: resp.length,
    responses_final: resp.filter(r => r.status === "final").length,
    responses_by_form: byForm,
    last_response: resp.map(r => r.submittedOn).filter(Boolean).sort().pop() || null,
    points: pts.map(p => ({ code: p.code, name: (p.name || "").trim() || null })),
  };
  seen.set(e.code, d);
  return d;
}

const out = { radius_m: radius, read_on: new Date().toISOString(), systems: {} };
const found = {};
for (const code of codes) {
  const [centre] = await apiGet("entities/water_system", { filter: JSON.stringify({ code }), limit: 1 });
  if (!centre?.location?.coordinates) { found[code] = null; continue; }
  found[code] = await apiGet("entities/water_system", {
    filter: JSON.stringify({ location: { $near: { $geometry: { type: "Point",
      coordinates: centre.location.coordinates.slice(0, 2) }, $maxDistance: radius } } }),
    limit: 500 });
}
// four lookups at a time: each is slow on mWater's side, not ours
const unique = [...new Map(Object.values(found).flat().filter(Boolean).map(e => [e.code, e])).values()];
for (let i = 0; i < unique.length; i += 4)
  await Promise.all(unique.slice(i, i + 4).map(detail));
for (const [code, list] of Object.entries(found))
  out.systems[code] = list ? list.map(e => seen.get(e.code)) : null;
// usernames are only known where the creator filed a response we read
for (const list of Object.values(out.systems))
  for (const d of list || []) d.created_by_name = users.get(d.created_by) || null;
console.log(JSON.stringify(out));
