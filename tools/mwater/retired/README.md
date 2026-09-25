# Retired mWater write scripts

retired 25 Sep 2026: mWater allows writes only via portal or MCP proposals

Kept for the record of what was written and how; none of these can run. The
write helper they imported (`apiWrite` in `tools/mwater/api.mjs`) is gone, and
that client now refuses every request other than a GET or the login. The
writes they made are logged in `data/register_write_log.json`, with before and
after documents in `data/mwater_backups/`. Nothing in the weekly build or in
`tools/publish.sh` calls anything in this folder, and
`tools/check_consistency.py` fails the build if something does.

- `fix_admin_region.mjs` — wrote `admin_region` to nine register entities on
  22 September 2026. mWater discarded the field (it computes it from location).
