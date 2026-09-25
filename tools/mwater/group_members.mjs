// Members of one mWater group, READ-ONLY: one GET through api.mjs, which
// refuses anything but GET and the login. Prints {"group": id, "members": n}.
//
//   node tools/mwater/group_members.mjs <group_id>
import { apiGet } from "./api.mjs";

const [group] = process.argv.slice(2);
if (!group) { console.error("usage: group_members.mjs <group_id>"); process.exit(2); }
const rows = await apiGet("group_members", { filter: JSON.stringify({ group }) });
if (!Array.isArray(rows)) { console.error("unexpected reply from group_members"); process.exit(1); }
console.log(JSON.stringify({ group, members: new Set(rows.map((r) => r.member)).size }));
