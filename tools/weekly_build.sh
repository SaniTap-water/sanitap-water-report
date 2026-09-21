#!/usr/bin/env bash
# What the Windows scheduled task runs on Mondays. The full edition is built
# here now; the cloud session is only a watchdog.
set -uo pipefail
cd /home/bushp/sanitap-water-report || exit 1
export PLAYWRIGHT_BROWSERS_PATH=/home/bushp/.cache/ms-playwright
/home/bushp/sdws1/venv/bin/python tools/weekly_build.py "$@"
rc=$?
# If the local build did nothing, a candidate may still be waiting in Downloads
# from a stretch when this machine was unavailable.
[ "$rc" -eq 0 ] && /home/bushp/sdws1/venv/bin/python tools/publish_waiting.py
exit $rc
