#!/usr/bin/env bash
# What the Windows scheduled task runs on Mondays, and what the desktop
# shortcut "Update water report now" starts on demand. The full edition is
# built here; tools/publish.sh gates and publishes it.
#
#   tools/weekly_build.sh             # build, gate, publish
#   tools/weekly_build.sh --dry-run   # build, run every gate, stop before
#                                     # commit and push, roll back
#
# IT RUNS IN ITS OWN CLONE, ~/sanitap-water-report-build. The scheduled run on
# 21 September refused to build because the working tree was dirty: the task
# shared ~/sanitap-water-report with interactive sessions, so anyone's
# uncommitted work stopped the Monday edition. The build clone is never
# worked in. Every run starts by fetching and resetting it to origin/main, so
# it builds from what is published and from nothing else. Run from any other
# clone, this script hands over to the build clone.
#
# The last line of logs/publisher.log in the build clone is always one plain
# sentence starting "OUTCOME:", so the Monday watchdog can quote why a run did
# or did not publish.
#
# Everything is inside main(), so bash has read the whole file before the
# reset below replaces it on disk.
main() {
  set -uo pipefail
  local here build log py
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  build=/home/bushp/sanitap-water-report-build
  py=/home/bushp/sdws1/venv/bin/python
  export PLAYWRIGHT_BROWSERS_PATH=/home/bushp/.cache/ms-playwright
  # wsl.exe from Task Scheduler starts a non-login shell, so ~/.local/bin -
  # where node lives - is not on PATH, and every extract pull failed with
  # "No such file or directory: 'node'". Found by the rehearsal of 23 September.
  export PATH="/home/bushp/.local/bin:$PATH"

  if [ "$here" != "$build" ]; then
    if [ ! -x "$build/tools/weekly_build.sh" ]; then
      echo "OUTCOME: nothing was built, because the build clone $build does not exist."
      return 1
    fi
    exec bash "$build/tools/weekly_build.sh" "$@"
  fi

  cd "$build" || return 1
  log="$build/logs/publisher.log"
  outcome() {   # the one sentence the watchdog quotes, always the last line
    mkdir -p "$build/logs"
    printf '%s  OUTCOME: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%S+00:00)" "$1" >> "$log"
    echo "OUTCOME: $1"
  }

  # AT LEAST 60 MINUTES BETWEEN RUNS (25 September 2026). A run pulls every
  # form from mWater; two runs close together only double the load. The start
  # of the last real run is recorded outside git; a run inside the window
  # stops here, before any fetch or pull, and says so. A dry run is exempt.
  local isdry="" x
  for x in "$@"; do [ "$x" = "--dry-run" ] && isdry=1; done
  if [ -z "${SANITAP_SYNCED:-}" ] && [ -z "$isdry" ]; then
    local stamp="$build/logs/last_run_started" now last mins
    now=$(date +%s)
    if [ -f "$stamp" ]; then
      last=$(cat "$stamp" 2>/dev/null || echo 0)
      mins=$(( (now - last) / 60 ))
      if [ "$mins" -ge 0 ] && [ "$mins" -lt 60 ]; then
        outcome "Skipped: the last run started $mins minute(s) ago, and runs are at least 60 minutes apart."
        return 0
      fi
    fi
    mkdir -p "$build/logs" && echo "$now" > "$stamp"
  fi

  if [ -z "${SANITAP_SYNCED:-}" ]; then
    # logs/publisher.log is untracked (23 September), so neither this reset
    # nor a rollback can touch it. The copy below covers the one reset that
    # moves from a commit where it was tracked to one where it is not.
    local keep; keep="$(mktemp /tmp/sanitap-publisher-log.XXXXXX)" || keep=""
    # outside the tree, so neither the reset nor git clean can remove it
    if [ -n "$keep" ]; then
      if [ -f "$log" ]; then cp "$log" "$keep"; else rm -f "$keep"; fi
    fi
    local from="${SANITAP_BUILD_FROM:-origin}" branch="${SANITAP_BUILD_BRANCH:-main}"
    if ! git fetch -q "$from" "$branch"; then
      outcome "Not published: the build could not fetch $from/$branch from GitHub, so nothing was built."
      return 1
    fi
    if ! git reset -q --hard "$from/$branch" || ! git clean -qfd; then
      outcome "Not published: the build clone could not be reset to $from/$branch, so nothing was built."
      return 1
    fi
    if [ -n "$keep" ] && [ -f "$keep" ]; then
      if [ -f "$log" ]; then
        # a tracked log (before 23 September): published lines first, then
        # any local line the published log lacks
        grep -vxF -f "$log" "$keep" >> "$log" 2>/dev/null
        rm -f "$keep"
      else
        # the log is untracked since 23 September; the reset that stopped
        # tracking it deleted the file, so put this clone's history back
        mkdir -p "$(dirname "$log")" && mv "$keep" "$log"
      fi
    fi
    SANITAP_SYNCED=1 exec bash "$build/tools/weekly_build.sh" "$@"
  fi

  rm -f "$build/logs/last_outcome.txt"
  "$py" tools/weekly_build.py "$@"
  local rc=$?
  # If the local build did nothing, a candidate may still be waiting in
  # Downloads from a stretch when this machine was unavailable. It publishes
  # through publish.sh too, and a dry run stays a dry run.
  local dry="" a
  for a in "$@"; do [ "$a" = "--dry-run" ] && dry="--dry-run"; done
  [ "$rc" -eq 0 ] && "$py" tools/publish_waiting.py $dry
  if [ -s "$build/logs/last_outcome.txt" ]; then
    outcome "$(cat "$build/logs/last_outcome.txt")"
  else
    outcome "Not published: tools/weekly_build.py stopped (exit $rc) without saying why; see the lines above."
  fi
  return $rc
}
main "$@"
exit $?
