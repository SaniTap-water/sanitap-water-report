#!/usr/bin/env bash
# What the Windows scheduled task runs on Mondays, and what the desktop
# shortcut "Update water report now" starts on demand. The full edition is
# built here; tools/publish.sh gates and publishes it. The cloud session is
# only a watchdog.
#
#   tools/weekly_build.sh             # build, gate, publish
#   tools/weekly_build.sh --dry-run   # build, run every gate, stop before
#                                     # commit and push, roll back
set -uo pipefail
cd /home/bushp/sanitap-water-report || exit 1
export PLAYWRIGHT_BROWSERS_PATH=/home/bushp/.cache/ms-playwright
/home/bushp/sdws1/venv/bin/python tools/weekly_build.py "$@"
rc=$?
# If the local build did nothing, a candidate may still be waiting in Downloads
# from a stretch when this machine was unavailable. It publishes through
# publish.sh too, and a dry run stays a dry run.
dry=""
for a in "$@"; do [ "$a" = "--dry-run" ] && dry="--dry-run"; done
[ "$rc" -eq 0 ] && /home/bushp/sdws1/venv/bin/python tools/publish_waiting.py $dry
exit $rc
