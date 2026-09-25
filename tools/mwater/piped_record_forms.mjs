// SDWS 27 evidence for the piped systems, READ-ONLY (GET through api.mjs).
// For each record type the hand pumps have - preventive maintenance, repair,
// days not operational - find the active piped / Endur'O forms of that type
// and count their final responses that name a managed piped system or one of
// its water points. Prints JSON: {types: {...}, missing: n}, where missing is
// the number of record types with no such record yet.
//
//   node tools/mwater/piped_record_forms.mjs <code>[,<code>...]
import { apiGet } from "./api.mjs";

const codes = new Set((process.argv[2] || "").split(",").filter(Boolean));
const TYPES = {
  maintenance: /entretien|maintenance|maintien/i,
  repair: /r[ée]paration|repair|panne|breakdown/i,
  days_not_operational: /arr[êe]t|downtime|non.?op[ée]rationnel|not operational|jours? d.?arr/i,
};
const forms = await apiGet("forms", { fields: JSON.stringify({ "design.name": 1, state: 1 }), limit: 3000 });
const name = (f) => { const n = f.design && f.design.name; return typeof n === "string" ? n : (n && (n.en || n.fr || Object.values(n)[0])) || ""; };
const piped = forms.filter((f) => f.state === "active" && /piped water|endur.?o/i.test(name(f)));

function mentions(v) {
  if (v && typeof v === "object") {
    if (v.code && codes.has(String(v.code))) return true;
    return Object.values(v).some(mentions);
  }
  return false;
}
const out = {};
for (const [t, re] of Object.entries(TYPES)) {
  const hit = piped.filter((f) => re.test(name(f)));
  let records = 0;
  for (const f of hit) {
    const rs = await apiGet("responses", { filter: JSON.stringify({ form: f._id, status: "final" }), limit: 5000 });
    records += rs.filter((r) => mentions(r.data)).length;
  }
  out[t] = { forms: hit.map((f) => ({ id: f._id, name: name(f) })), records_on_managed: records };
}
console.log(JSON.stringify({ types: out, missing: Object.values(out).filter((x) => !x.records_on_managed).length }));
