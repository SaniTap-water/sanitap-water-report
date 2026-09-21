#!/usr/bin/env bash
# Wrapper for the Windows scheduled task. Keeps the task definition to one
# line and the environment in one place, so the schedule and the logic can be
# changed independently.
set -uo pipefail
cd /home/bushp/sanitap-water-report || exit 1
export PLAYWRIGHT_BROWSERS_PATH=/home/bushp/.cache/ms-playwright
exec /home/bushp/sdws1/venv/bin/python tools/publish_waiting.py "$@"
