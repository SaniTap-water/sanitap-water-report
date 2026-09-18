#!/usr/bin/env bash
# Publish the weekly report.
#
# The consistency checker is a GATE, not a report: if it exits non-zero this
# script stops before `git commit`, so a build whose figures disagree with each
# other cannot reach the live site.
#
# Usage:
#   tools/publish.sh <new-index.html> [<new-portfolio.html>] -m "commit message"
#   tools/publish.sh --check-only                 # gate the working tree as-is
#
# Note on shell style: the gate is deliberately NOT part of an && chain. A
# `cmd && git commit` chain hides the distinction between "check failed" and
# "check could not run", and a zero-match grep inside such a chain silently
# skips the commit while reporting success. Every step below is a separate
# statement with its exit status tested explicitly.

set -u                      # not -e: we test each status ourselves
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 2

NEW_INDEX=""; NEW_PORTFOLIO=""; MSG=""; CHECK_ONLY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --check-only) CHECK_ONLY=1; shift ;;
    -m) MSG="${2:-}"; shift 2 ;;
    *) if [ -z "$NEW_INDEX" ]; then NEW_INDEX="$1"; elif [ -z "$NEW_PORTFOLIO" ]; then NEW_PORTFOLIO="$1"; fi; shift ;;
  esac
done

say() { printf '  %s\n' "$*"; }

# ---- 1. stage the new files ------------------------------------------------
if [ -n "$NEW_INDEX" ]; then
  if [ ! -f "$NEW_INDEX" ]; then say "ABORT: $NEW_INDEX does not exist"; exit 2; fi
  if [ "$NEW_INDEX" -ef index.html ]; then
    say "index.html already in place (source is the file itself)"
  else
    cp "$NEW_INDEX" index.html
    say "installed index.html      <- $NEW_INDEX"
  fi
fi
if [ -n "$NEW_PORTFOLIO" ]; then
  if [ ! -f "$NEW_PORTFOLIO" ]; then say "ABORT: $NEW_PORTFOLIO does not exist"; exit 2; fi
  if [ "$NEW_PORTFOLIO" -ef portfolio.html ]; then
    say "portfolio.html already in place (source is the file itself)"
  else
    cp "$NEW_PORTFOLIO" portfolio.html
    say "installed portfolio.html  <- $NEW_PORTFOLIO"
  fi
fi

# ---- 2. THE GATE -----------------------------------------------------------
# Run it, capture the status on its own line, then branch. Nothing is chained.
say ""
say "running consistency checker ..."
python3 tools/check_consistency.py index.html portfolio.html
GATE=$?
say ""

if [ "$GATE" -eq 2 ]; then
  say "ABORT: the consistency checker could not run (exit 2)."
  say "Nothing was committed. Fix the checker's inputs and try again."
  exit 2
fi
if [ "$GATE" -ne 0 ]; then
  say "ABORT: consistency checks FAILED (exit $GATE)."
  say "Nothing was committed and nothing was pushed."
  say "The working tree still holds the new files - inspect, fix, re-run."
  exit 1
fi
say "consistency checks passed."

if [ "$CHECK_ONLY" -eq 1 ]; then
  say "--check-only: stopping before commit as asked."
  exit 0
fi

# ---- 3. commit and push ----------------------------------------------------
if [ -z "$MSG" ]; then say "ABORT: no commit message (-m). Nothing committed."; exit 2; fi

git add -A

# "nothing staged" is not a failure - it means the build is identical to what is
# already published. Distinguish it from a real commit error, which exits 1 too.
git diff --cached --quiet
if [ $? -eq 0 ]; then
  say "nothing to commit - the working tree already matches HEAD."
  say "Checks passed; there is simply nothing new to publish."
  exit 0
fi

git commit -m "$MSG"
RC=$?
if [ "$RC" -ne 0 ]; then say "ABORT: git commit failed (exit $RC). Nothing pushed."; exit "$RC"; fi

git push
RC=$?
if [ "$RC" -ne 0 ]; then say "git push FAILED (exit $RC). The commit exists locally."; exit "$RC"; fi

say "published: $(git rev-parse HEAD)"
exit 0
