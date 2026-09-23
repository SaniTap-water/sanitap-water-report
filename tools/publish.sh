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

# ---- 0. freeze the outgoing edition ----------------------------------------
# Archiving used to live only in weekly_build.py, so every edition published
# through this script - which is every edition since 18 September - was never
# archived. Week 39 had no archive at all, which is also how the edition
# counter came to reset. The outgoing edition is frozen here, BEFORE anything
# is overwritten, and the publish refuses to continue if it is not on disk.
if [ -z "${SANITAP_SKIP_ARCHIVE:-}" ]; then
  say ""
  say "archiving the outgoing edition ..."
  python3 tools/archive_edition.py || true
  python3 tools/archive_edition.py --assert
  if [ $? -ne 0 ]; then
    say "ABORT: the outgoing edition is not archived; nothing overwritten."
    exit 1
  fi
fi

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

# ---- 1b. refresh what is generated, before gating it -----------------------
# The page makes claims about live mWater forms. Those are only as good as the
# last time anyone read the forms, so the build reads them itself where it can.
# This step NEVER fails the build for being offline - a machine with no network
# or no credentials publishes from the committed snapshot and says so. It is
# the consistency checker, below, that refuses a snapshot older than a week.
say ""
say "refreshing the mWater form snapshot ..."
python3 tools/refresh_form_snapshot.py --if-possible
RC=$?
if [ "$RC" -ne 0 ]; then
  say "ABORT: the snapshot refresh failed for a reason other than being offline (exit $RC)."
  exit 2
fi

# Regenerate every generated region of index.html from its own generator, so
# the gate sees current output rather than yesterday's. Each generator is
# named in its own marker in index.html; block 7af of the checker fails the
# build if a region and its generator disagree.
for gen in tools/render_block.py tools/render_form_freshness.py tools/render_ttr_table.py \
           tools/render_datasets.py tools/render_actions.py tools/render_portfolio.py; do
  python3 "$gen" --write
  RC=$?
  if [ "$RC" -ne 0 ]; then
    say "ABORT: $gen failed (exit $RC). Nothing committed."
    exit 2
  fi
done

# ---- 1c. the render gate ---------------------------------------------------
# Markup checks cannot see a page that parses but no longer shows what it
# should. This loads the page in headless Chromium and asserts against the
# rendered DOM. It is skipped, loudly, where Chromium is not available - a
# machine without it can still publish, but it publishes without this cover.
say ""
say "running the render check ..."
PW="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"
PYBIN="$HOME/sdws1/venv/bin/python"
if [ -x "$PYBIN" ] && PLAYWRIGHT_BROWSERS_PATH="$PW" "$PYBIN" -c "import playwright" 2>/dev/null; then
  PLAYWRIGHT_BROWSERS_PATH="$PW" "$PYBIN" tools/render_check.py
  RC=$?
  if [ "$RC" -ne 0 ]; then
    say "ABORT: the rendered page does not match the manifest (exit $RC)."
    say "Nothing committed. Inspect, fix, or re-record with --manifest if intended."
    exit 1
  fi

  # Every number on the page must be live, declared in PARAMS with its
  # citation, or from a dated manual file. These two gates enforce it from
  # both sides: the census reads the rendered page and asks whether each
  # figure has a source; the prose gate reads the source and asks whether it
  # was typed. Each holds a dated backlog of what is not yet converted, and
  # that backlog may only shrink - so neither can quietly become an
  # exemption list.
  # Every mWater route the page links to must exist in the portal's own route
  # table. 56 anchors once matched their regex perfectly and every one of them
  # landed on "Page not found"; a shape check cannot catch that.
  say ""
  # A response arriving on a successor form that no population reads is a
  # migration completing silently. The first-rehabilitation successor has zero
  # responses, and zero is a plausible weekly count.
  say ""
  say "checking for a silent form migration ..."
  "$PYBIN" tools/populations.py --migration | tail -8
  RC=${PIPESTATUS[0]}
  if [ "$RC" -ne 0 ]; then
    say "ABORT: a successor form carries a response no population reads."
    exit 1
  fi

  say "checking the mWater links ..."
  python3 tools/check_links.py | tail -8
  RC=${PIPESTATUS[0]}
  if [ "$RC" -ne 0 ]; then
    say "ABORT: the page links to an mWater route that does not exist."
    exit 1
  fi

  say ""
  say "running the figure gates (LIVE: nothing unsourced may be added) ..."
  # THE FIGURE GATE IS LIVE. Anything not on the dated residue list fails
  # the build. The list may only shrink - see act-figure-residue.
  PLAYWRIGHT_BROWSERS_PATH="$PW" "$PYBIN" tools/figure_census.py --gate | tail -22
  RC=${PIPESTATUS[0]}
  if [ "$RC" -ne 0 ]; then
    say "ABORT: a figure renders on the page with no source (exit $RC)."
    exit 1
  fi
  "$PYBIN" tools/prose_figures.py --gate | tail -22
  RC=${PIPESTATUS[0]}
  if [ "$RC" -ne 0 ]; then
    say "ABORT: a figure is typed into the prose (exit $RC)."
    say "Make it a data-fig span, a PARAMS entry, or a dated manual figure."
    exit 1
  fi
else
  say "  SKIPPED: playwright/chromium not available here."
  say "  The markup checks below still run, but nothing is verifying what renders."
fi

# ---- 2. THE GATE -----------------------------------------------------------
# Run it, capture the status on its own line, then branch. Nothing is chained.
say ""
say "checking extract vintages ..."
python3 tools/check_vintage.py | tail -8
RC=${PIPESTATUS[0]}
if [ "$RC" -ne 0 ]; then
  say "ABORT: an extract is older than the build it is feeding."
  say "A stale edition that looks current is worse than no edition. Nothing committed."
  exit 1
fi

say ""
say "checking WPOPMETA against the allocation run's own summary ..."
python3 tools/check_wpopmeta.py | tail -4
RC=${PIPESTATUS[0]}
if [ "$RC" -ne 0 ]; then
  say "ABORT: a WPOPMETA field disagrees with the run that produced it."
  exit 1
fi

say ""
say "checking that every embedded figure has a generator ..."
python3 tools/check_generators.py
RC=$?
if [ "$RC" -ne 0 ]; then
  say "ABORT: an embedded field has no generator, or a generator disagrees with what is stored."
  say "A field nothing can move is a field nobody is checking. Nothing committed."
  exit 1
fi

say ""
say "checking the extracts for the paging fault ..."
python3 tools/check_extracts.py | tail -12
RC=${PIPESTATUS[0]}
if [ "$RC" -ne 0 ]; then
  say "ABORT: an extract the build reads carries a repeated _id."
  exit 1
fi

say ""
say "recomputing the corrections-log distances ..."
python3 tools/check_distances.py | tail -4
RC=${PIPESTATUS[0]}
if [ "$RC" -ne 0 ]; then
  say "ABORT: a stated distance no longer reproduces from located_register_points."
  exit 1
fi

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
