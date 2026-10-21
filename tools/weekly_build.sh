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
  build="${SANITAP_BUILD_DIR:-/home/bushp/sanitap-water-report-build}"   # tools/test_repeat_skip.py points it at a worktree
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
    # a run that did not publish puts one line on the week's approval task
    # (Adriaan Mol, 21 Oct 2026); Asana unreachable never changes the result
    case "$1" in
      "Not published"*|"Dry run failed"*)
        if [ -f "$build/tools/asana_setup.py" ] && [ -f "$build/tools/limit.py" ]; then
          python3 "$build/tools/limit.py" 120 "approval-task line" -- \
            python3 "$build/tools/asana_setup.py" --run-failed "$1" 2>&1 | tail -2 \
            | sed 's/^/  /' | tee -a "$log" >/dev/null || true
        fi ;;
    esac
  }

  # AT LEAST 60 MINUTES BETWEEN RUNS (25 September 2026). A run pulls every
  # form from mWater; two runs close together only double the load. The start
  # of the last real run is recorded outside git; a run inside the window
  # stops here, before any fetch or pull, and says so. A dry run is exempt.
  # A run on a kept extract set (--reuse-extracts) makes no mWater call at
  # all (20 Oct 2026), so it is exempt too, and does not move the stamp.
  local isdry="" x
  for x in "$@"; do [ "$x" = "--dry-run" ] || [ "$x" = "--reuse-extracts" ] && isdry=1; done
  if [ -z "${SANITAP_SYNCED:-}" ] && [ -z "$isdry" ]; then
    local stamp="$build/logs/last_run_started" now last mins
    now=$(date +%s)
    if [ -f "$stamp" ]; then
      last=$(cat "$stamp" 2>/dev/null || echo 0)
      mins=$(( (now - last) / 60 ))
      if [ "$mins" -ge 0 ] && [ "$mins" -lt 60 ]; then
        # Non-zero (75, "try again later"), so the task's Last Result shows
        # the run did not build. The retry is the next 2-hourly repetition of
        # the trigger, which fires whatever this returned; nothing here is
        # consumed, so a pending logs/update_requested waits for that run.
        outcome "Skipped, not built: the last run started $mins minute(s) ago, and runs are at least 60 minutes apart; the next scheduled run will build."
        return 75
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

  rm -f "$build/logs/last_outcome.txt" "$build/logs/current_step"

  # NO SLEEP WHILE A RUN IS GOING (21 Oct 2026). Modern Standby suspended a
  # pre-flight run for 12 hours on 20 Oct. tools/keepawake.ps1 holds a
  # system-required power request while logs/keepawake.hold exists, at most
  # 125 minutes; the trap removes the file however the run ends.
  local hold="$build/logs/keepawake.hold"
  local psh=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
  mkdir -p "$build/logs" && : > "$hold"
  trap 'rm -f "'"$hold"'"' EXIT
  if [ -x "$psh" ]; then
    ( setsid "$psh" -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w "$build/tools/keepawake.ps1")" \
        -HoldFile "$(wslpath -w "$hold")" -Minutes 125 >/dev/null 2>&1 & )
    printf '%s  sleep held off for this run (tools/keepawake.ps1)\n' "$(date -u +%Y-%m-%dT%H:%M:%S+00:00)" >> "$log"
  else
    printf '%s  WARNING: powershell.exe not found, so the laptop may sleep during this run\n' "$(date -u +%Y-%m-%dT%H:%M:%S+00:00)" >> "$log"
  fi

  # THE WHOLE RUN HAS 2 HOURS (21 Oct 2026). tools/limit.py stops the run's
  # whole process tree at the limit; the tree and the extracts are then rolled
  # back here, as weekly_build.py would have, and the outcome names the step
  # that was running (logs/current_step).
  local head; head=$(git rev-parse HEAD)
  python3 tools/limit.py "${SANITAP_RUN_LIMIT:-7200}" "the whole run" -- "$py" tools/weekly_build.py "$@"
  local rc=$?
  if [ "$rc" -eq 124 ]; then
    local step; step=$(cat "$build/logs/current_step" 2>/dev/null || echo "an unrecorded step")
    local lim=$(( ${SANITAP_RUN_LIMIT:-7200} / 60 ))
    case "$step" in
      published*)
        echo "Published, but the run ran longer than $lim min and was stopped afterwards, during: ${step#published: }" \
          > "$build/logs/last_outcome.txt" ;;
      *)
        git reset -q --hard "$head"; git clean -qfd editions data
        "$py" -c "import sys; sys.path.insert(0, 'tools'); import pull_extract as P; b = P.restore_previous(); print(f'~/mwater-exports restored ({len(b)} files)' if b else '')" >> "$log" 2>&1
        echo "Not published: the run timed out: it ran longer than $lim min and was stopped during $step; the tree and the extracts were rolled back to $(echo "$head" | cut -c1-8)" \
          > "$build/logs/last_outcome.txt" ;;
    esac
  fi
  # If the local build did nothing, a candidate may still be waiting in
  # Downloads from a stretch when this machine was unavailable. It publishes
  # through publish.sh too, and a dry run stays a dry run.
  local dry="" a
  for a in "$@"; do [ "$a" = "--dry-run" ] && dry="--dry-run"; done
  # Not on a repeat that found this week's edition already out (21 Oct 2026):
  # that run does nothing else - no pull, no Downloads candidate, no Asana.
  if [ "$rc" -eq 0 ] && ! grep -q '^Nothing to do' "$build/logs/last_outcome.txt" 2>/dev/null; then
    "$py" tools/publish_waiting.py $dry
  fi
  if [ -s "$build/logs/last_outcome.txt" ]; then
    outcome "$(cat "$build/logs/last_outcome.txt")"
  else
    outcome "Not published: tools/weekly_build.py stopped (exit $rc) without saying why; see the lines above."
  fi
  return $rc
}
main "$@"
exit $?
