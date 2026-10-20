#!/usr/bin/env bash
# Pre-flight (20 Oct 2026): the full gate suite, offline, on a kept extract set.
#
# Builds the commit the scheduled build would build (same SANITAP_BUILD_FROM /
# SANITAP_BUILD_BRANCH, in the build clone) on an extract set already pulled -
# by default the newest ~/mwater-exports.pull-* or ~/mwater-exports.refused -
# and runs every gate in publish.sh --check-only. No mWater call is made
# (--reuse-extracts sets SANITAP_NO_MWATER=1, which tools/mwater/api.mjs
# enforces), so there is no hour guard. Nothing is published; the tree is
# rolled back as after any dry run. The verdict - every gate, its class, and
# PUBLISHABLE or not - is in logs/gates.log, and the result is recorded in
# logs/preflight.json against the commit it ran on.
#
#   tools/preflight.sh                       # newest kept set
#   tools/preflight.sh ~/mwater-exports.pull-2026-10-20T1148
set -u
BUILD="${SANITAP_BUILD_DIR:-$HOME/sanitap-water-report-build}"
SET="${1:-}"
if [ -z "$SET" ]; then
  SET=$(ls -dt "$HOME"/mwater-exports.pull-* "$HOME"/mwater-exports.refused 2>/dev/null | head -1)
fi
if [ -z "$SET" ] || [ ! -d "$SET" ]; then
  echo "preflight: no kept extract set (give a directory, or keep a pull in ~/mwater-exports.pull-*)"
  exit 2
fi
SET="$(cd "$SET" && pwd)"
echo "preflight: gating ${SANITAP_BUILD_FROM:-origin}/${SANITAP_BUILD_BRANCH:-main} on $SET (no mWater call)"
bash "$BUILD/tools/weekly_build.sh" --dry-run --reuse-extracts "$SET"
RC=$?
COMMIT=$(git -C "$BUILD" rev-parse HEAD)
VERDICT=$(grep "==== " "$BUILD/logs/gates.log" | tail -1 | sed 's/.*==== //')
python3 - "$BUILD/logs/preflight.json" "$COMMIT" "$SET" "$RC" "$VERDICT" <<'E'
import json, sys, datetime
path, commit, s, rc, verdict = sys.argv[1:6]
json.dump({"commit": commit, "extracts": s, "exit": int(rc), "verdict": verdict,
           "passed": int(rc) == 0,
           "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
          open(path, "w"), indent=1)
E
echo "preflight: $([ "$RC" -eq 0 ] && echo PASSED || echo FAILED) on $COMMIT - $VERDICT"
exit $RC
