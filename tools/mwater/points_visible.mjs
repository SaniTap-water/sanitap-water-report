// Which of these water points this account can see, READ-ONLY: one GET of
// entities/water_point through api.mjs (GET and the login only). Prints
// {"asked": [...], "got": [{code, name, _managed_by}]}. A point that is not
// returned is not visible to this account (deleted, or in a group it cannot
// read); a control point that does come back shows the read itself worked.
//
//   node tools/mwater/points_visible.mjs <code> [<code> ...]
import { apiGet } from "./api.mjs";

const codes = process.argv.slice(2);
if (!codes.length) { console.error("usage: points_visible.mjs <code> ..."); process.exit(2); }
const rows = await apiGet("entities/water_point",
  { filter: JSON.stringify({ code: { $in: codes } }), limit: codes.length + 5 });
if (!Array.isArray(rows)) { console.error("unexpected reply from entities/water_point"); process.exit(1); }
console.log(JSON.stringify({ asked: codes,
  got: rows.map((e) => ({ code: e.code, name: e.name, _managed_by: e._managed_by })) }));
