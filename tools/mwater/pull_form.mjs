// Stable enumeration of a form's responses.
//
// mWater's skip/limit paging has no sort order, so the row order shifts
// between requests: two full pulls of the same 1,688-response form returned
// the same TOTAL and 147 rows that differed. Paging cannot be trusted to
// enumerate a set. Date windows split by _id range can, and nothing pages:
// tools/mwater/enumerate.mjs (20 Oct 2026; until then a window of more than
// 500 rows was paged with skip, and the CSV pulls went through the MCP CLI,
// which cut every window at 200 rows).
//
// The file is written only when the whole form has been read, so a failed
// pull never leaves a partial file.
//
//   node tools/mwater/pull_form.mjs <form_id> <out.json> [field]
import fs from "node:fs";
import { pullResponses } from "./enumerate.mjs";

const [form, out, field = "submittedOn"] = process.argv.slice(2);
if (!form || !out) { console.error("usage: pull_form.mjs <form_id> <out.json> [dateField]"); process.exit(2); }

const rows = await pullResponses(form, field);
fs.writeFileSync(out + ".part", JSON.stringify(rows));
fs.renameSync(out + ".part", out);
console.log(`${rows.length} unique response(s) -> ${out}`);
