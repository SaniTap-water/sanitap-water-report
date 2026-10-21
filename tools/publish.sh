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
#   tools/publish.sh --reuse-extracts DIR ...     # the build reused the extract set
#                                                 # in DIR (tools/weekly_build.py
#                                                 # --reuse-extracts): verified first
#
# Each gate's result is printed and appended to logs/gates.log the moment it
# finishes (20 Oct 2026), not only in the summary at the end.
#
# Note on shell style: the gate is deliberately NOT part of an && chain. A
# `cmd && git commit` chain hides the distinction between "check failed" and
# "check could not run", and a zero-match grep inside such a chain silently
# skips the commit while reporting success. Every step below is a separate
# statement with its exit status tested explicitly.

set -u                      # not -e: we test each status ourselves
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 2

NEW_INDEX=""; NEW_PORTFOLIO=""; MSG=""; CHECK_ONLY=0; REUSE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --check-only) CHECK_ONLY=1; shift ;;
    -m) MSG="${2:-}"; shift 2 ;;
    --reuse-extracts) REUSE="${2:-}"; shift 2 ;;
    *) if [ -z "$NEW_INDEX" ]; then NEW_INDEX="$1"; elif [ -z "$NEW_PORTFOLIO" ]; then NEW_PORTFOLIO="$1"; fi; shift ;;
  esac
done

say() { printf '  %s\n' "$*"; }

# ---- every gate runs, every result is kept (20 Oct 2026) --------------------
# No gate stops the run. Each records its result the moment it finishes - in
# logs/gates.log, and for this run in logs/gates_run.tsv with the file holding
# its output - and tools/gate_decide.py decides at the end from
# data/gate_classes.json: a BLOCKING failure publishes nothing; REVIEW failures
# publish, PROVISIONAL on the page and on the week's approval task.
mkdir -p "$REPO/logs/gate_out"
GATELOG="$REPO/logs/gates.log"
RESULTS="$REPO/logs/gates_run.tsv"
RUNLOG="$REPO/logs/publish_run.log"
: > "$RESULTS"; : > "$RUNLOG"; rm -f "$REPO"/logs/gate_out/*.txt
exec > >(tee -a "$RUNLOG") 2>&1
LASTOFF=0
# Every gate runs under a time limit (Adriaan Mol, 21 Oct 2026): 10 minutes,
# then its whole process tree is stopped (tools/limit.py, exit 124) and the
# timeout counts as that gate's failure - BLOCKING unless the gate is REVIEW.
GATE_LIMIT="${SANITAP_GATE_LIMIT:-600}"
LIM() {                  # LIM ID COMMAND...
  local id="$1"; shift
  echo "publish.sh gate $id" > "$REPO/logs/current_step"
  python3 "$REPO/tools/limit.py" "$GATE_LIMIT" "gate $id" -- "$@"
}
gate_result() {          # gate_result ID STATUS MESSAGE
  local id="$1" rc="$2" msg="${3:-}" now off out
  if [ "$rc" -eq 124 ]; then
    msg="timed out: ran longer than $((GATE_LIMIT / 60)) min and was stopped (process tree killed)."
  fi
  sleep 0.3              # let tee catch up, so the gate's output is in the log
  off=$(stat -c %s "$RUNLOG" 2>/dev/null || echo 0)
  out="$REPO/logs/gate_out/${id//[^A-Za-z0-9_.-]/_}.txt"
  tail -c +$((LASTOFF + 1)) "$RUNLOG" | head -c $((off - LASTOFF)) > "$out"
  LASTOFF=$off
  now=$(date -u +%FT%TZ)
  if [ "$rc" -eq 0 ]; then
    printf '  %s  GATE PASS  %s\n' "$now" "$id"
    printf '%s  GATE PASS  %s\n' "$now" "$id" >> "$GATELOG"
  else
    printf '  %s  GATE FAIL (exit %s)  %s: %s\n' "$now" "$rc" "$id" "$msg"
    printf '%s  GATE FAIL (exit %s)  %s: %s\n' "$now" "$rc" "$id" "$msg" >> "$GATELOG"
  fi
  printf '%s\t%s\t%s\t%s\n' "$id" "$rc" "$msg" "$out" >> "$RESULTS"
}
# A layout-type gate that fails is run once more on the same built page, and
# the second result counts (data/gate_classes.json rerun_once).
rerun_once() {           # rerun_once ID STATUS COMMAND...  -> sets RC
  local id="$1"; RC="$2"; shift 2
  if [ "$RC" -ne 0 ]; then
    say "failed (exit $RC); running it once more on the same page ..."
    LIM "$id" "$@"
    RC=$?
  fi
}
printf '%s  ---- publish.sh %s\n' "$(date -u +%FT%TZ)" "$([ "$CHECK_ONLY" -eq 1 ] && echo --check-only || echo -m)${REUSE:+ --reuse-extracts $REUSE}" >> "$GATELOG"

# ---- reused extracts: the gates must run on exactly that set ----------------
if [ -n "$REUSE" ]; then
  say ""
  say "verifying the reused extract set ..."
  LIM verify_reuse python3 tools/pull_extract.py --verify-reuse "$REUSE"
  RC=$?
  gate_result verify_reuse "$RC" "~/mwater-exports is not the reused set $REUSE. Nothing committed."
fi

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
# every build starts with no provisional items: the list is this run's alone
python3 tools/provisional.py --clear

say ""
say "refreshing the mWater form snapshot ..."
LIM form_snapshot python3 tools/refresh_form_snapshot.py --from-extract
RC=$?
gate_result form_snapshot "$RC" "the snapshot refresh failed for a reason other than being offline (exit $RC)."

# Regenerate every generated region of index.html from its own generator, so
# the gate sees current output rather than yesterday's. Each generator is
# named in its own marker in index.html; block 7af of the checker fails the
# build if a region and its generator disagree.
for gen in tools/render_block.py tools/render_form_freshness.py tools/render_ttr_table.py \
           tools/india_mark_cap.py tools/transcription_round1.py tools/render_transcription_round1.py tools/render_reader_diagnosis.py \
           tools/call_followup.py tools/render_call_followup.py tools/rebuild_hygiene.py tools/render_hygiene.py \
           tools/rebuild_enduro_registry.py tools/render_enduro_registry.py \
           tools/rebuild_eligibility.py tools/render_eligibility.py \
           tools/kiosk_people.py tools/repeat_breakdowns.py tools/call_outcomes.py \
           tools/render_datasets.py tools/asana_pull.py tools/render_actions.py tools/render_portfolio.py \
           tools/render_piped_pairing.py tools/render_sdws18.py tools/iron_manganese.py; do
  LIM "generator:$gen" python3 "$gen" --write
  RC=$?
  gate_result "generator:$gen" "$RC" "$gen failed (exit $RC). Nothing committed."
  # owners (7 Oct 2026): Asana is the single source. The pull has taken in
  # reassignments made in Asana; an owner changed in the repository is pushed
  # to its task now, in the same run, before the action list is rendered.
  if [ "$gen" = "tools/asana_pull.py" ]; then
    LIM asana_push_owners python3 tools/asana_setup.py --push-owners
    RC=$?
    gate_result asana_push_owners "$RC" "pushing owners to Asana failed (exit $RC). Nothing committed."
  fi
done

# ---- 1b. Asana gate (2 Oct 2026) ---------------------------------------------
# Every open action has exactly one Asana task, owner and deadline on the page
# equal Asana's, and nothing is closed without recorded evidence. The Asana
# read above is read-only; tools/asana_setup.py is the only writer.
LIM asana python3 tools/check_asana.py
RC=$?
gate_result asana "$RC" "the action list disagrees with Asana or closes an action without evidence (exit $RC)."

# ---- 1b. status -> action gate (30 Sep 2026) ---------------------------------
# Every non-complete status in a requirements/evidence table names an OPEN
# action (data/status_actions.json) and links to it. The links are written
# after the action list, then checked; a failure stops the build here.
LIM status_actions python3 tools/status_actions.py --write --check
RC=$?
gate_result status_actions "$RC" "a non-complete status has no open action, or an action closed while its status is still open (exit $RC)."

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
  # Every figure's value is written into the static HTML, so a reader without
  # JavaScript never sees an empty span. The generators above write their
  # regions with empty spans; this fills them, after them and before any gate.
  # Changes this week (rule of 7 Oct 2026): headline figures against last week's
  # edition, every moved point traced to its mWater records; major changes
  # (edited upward, deleted, or a large move carried by edits) wait for Adriaan
  # or Jan in one Asana approval task per week. tools/change_review.py.
  say "reviewing this week's changes to the headline figures ..."
  LIM change_review env PLAYWRIGHT_BROWSERS_PATH="$PW" "$PYBIN" tools/change_review.py --compute \
    && LIM change_review python3 tools/asana_setup.py --approval \
    && LIM change_review python3 tools/render_datasets.py --write \
    && LIM change_review python3 tools/change_review.py --write
  RC=$?
  gate_result change_review "$RC" "the change review could not run (exit $RC). Nothing committed."
  # act-cal-working-day-ticks (7 Oct 2026): Angelo's answers in the checklist
  # workbook are copied into docs/transcription_round_notes.md every build.
  LIM calendar_check "$PYBIN" tools/calendar_check.py --write && LIM calendar_check "$PYBIN" tools/calendar_check.py --check
  RC=$?
  gate_result calendar_check "$RC" "the calendar checklist answers could not be copied (exit $RC). Nothing committed."
  say "prerendering every figure into the static HTML ..."
  LIM prerender_write env PLAYWRIGHT_BROWSERS_PATH="$PW" "$PYBIN" tools/prerender_figures.py --write
  RC=$?
  gate_result prerender_write "$RC" "a figure could not be prerendered into the static HTML (exit $RC)."
  LIM render_check env PLAYWRIGHT_BROWSERS_PATH="$PW" "$PYBIN" tools/render_check.py
  RC=$?
  rerun_once render_check "$RC" env PLAYWRIGHT_BROWSERS_PATH="$PW" "$PYBIN" tools/render_check.py
  gate_result render_check "$RC" "the rendered page does not match the manifest (exit $RC)."
  LIM static_figures env PLAYWRIGHT_BROWSERS_PATH="$PW" "$PYBIN" tools/prerender_figures.py --check
  RC=$?
  gate_result static_figures "$RC" "a static figure value differs from what the page computes (exit $RC)."

  # The transcription page is where the human round is done. On 28 Sep 2026 a
  # full pass exported 22 of 83 calendars because an empty calendar was never
  # recorded as checked. This drives the page and fails the build if an
  # answered calendar can again go missing from the export.
  say ""
  say "checking the formatting and readability rule on every table ..."
  LIM readability env PLAYWRIGHT_BROWSERS_PATH="$PW" "$PYBIN" tools/test_readability.py --no-shots | tail -12
  RC=${PIPESTATUS[0]}
  gate_result readability "$RC" "a table breaks the formatting and readability rule (exit $RC)."
  say ""
  say "checking the layout acceptance test (1522 px and 506 px, every <details> open) ..."
  LIM layout env PLAYWRIGHT_BROWSERS_PATH="$PW" "$PYBIN" tools/check_layout.py | tail -12
  RC=${PIPESTATUS[0]}
  rerun_once layout "$RC" bash -o pipefail -c "PLAYWRIGHT_BROWSERS_PATH='$PW' '$PYBIN' tools/check_layout.py | tail -12"
  gate_result layout "$RC" "the layout acceptance test failed (exit $RC)."
  say ""
  say "checking that every provenance panel follows the scope buttons ..."
  LIM provenance env PLAYWRIGHT_BROWSERS_PATH="$PW" "$PYBIN" tools/check_provenance.py | tail -12
  RC=${PIPESTATUS[0]}
  gate_result provenance "$RC" "a provenance panel does not match its figure, or names a source its scope does not use (exit $RC)."
  say ""
  say "opening every panel and expanding block at 1280, 1440 and 1920 px ..."
  LIM panels env PLAYWRIGHT_BROWSERS_PATH="$PW" "$PYBIN" tools/check_panels.py | tail -12
  RC=${PIPESTATUS[0]}
  rerun_once panels "$RC" bash -o pipefail -c "PLAYWRIGHT_BROWSERS_PATH='$PW' '$PYBIN' tools/check_panels.py | tail -12"
  gate_result panels "$RC" "a panel or expanding block overlaps, is clipped or does not push the content down (exit $RC)."
  say ""
  say "testing the transcription page in the browser ..."
  # every failing assertion is printed, not only the last lines (7 Oct 2026)
  LIM transcription_page env PLAYWRIGHT_BROWSERS_PATH="$PW" "$PYBIN" tools/test_transcription_page.py | grep -v "^  PASS" | tail -12
  RC=${PIPESTATUS[0]}
  gate_result transcription_page "$RC" "the transcription page fails its browser test (exit $RC)."
  # The route page's exports (16 Oct 2026): the CSV per site holds exactly
  # its routed pumps, and the day sheets print with their map and stop table,
  # one page per day, with nothing on the console.
  say ""
  say "testing the route page's CSV and print exports in the browser ..."
  LIM routes_page env PLAYWRIGHT_BROWSERS_PATH="$PW" "$PYBIN" tools/test_routes_page.py | grep -v "^  PASS" | tail -12
  RC=${PIPESTATUS[0]}
  gate_result routes_page "$RC" "the route page's exports fail their browser test (exit $RC)."

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
  LIM migration "$PYBIN" tools/populations.py --migration | tail -8
  RC=${PIPESTATUS[0]}
  gate_result migration "$RC" "a successor form carries a response no population reads."

  say "checking the mWater links ..."
  LIM links python3 tools/check_links.py | tail -8
  RC=${PIPESTATUS[0]}
  gate_result links "$RC" "the page links to an mWater route that does not exist."

  say ""
  say "running the figure gates (LIVE: nothing unsourced may be added) ..."
  # THE FIGURE GATE IS LIVE. Anything not on the dated residue list fails
  # the build. The list may only shrink - see act-figure-residue.
  LIM figure_census env PLAYWRIGHT_BROWSERS_PATH="$PW" "$PYBIN" tools/figure_census.py --gate | tail -22
  RC=${PIPESTATUS[0]}
  gate_result figure_census "$RC" "a figure renders on the page with no source (exit $RC)."
  LIM prose_figures "$PYBIN" tools/prose_figures.py --gate | tail -22
  RC=${PIPESTATUS[0]}
  gate_result prose_figures "$RC" "a figure is typed into the prose (exit $RC)."
else
  say "  SKIPPED: playwright/chromium not available here."
  say "  The markup checks below still run, but nothing is verifying what renders."
fi

# ---- 2. THE GATE -----------------------------------------------------------
# Run it, capture the status on its own line, then branch. Nothing is chained.
# No browser needed, so this runs even where the render gate is skipped: a
# figure that is empty in the static HTML fails the build.
say ""
say "checking that no figure is empty without JavaScript ..."
LIM empty_figures python3 tools/prerender_figures.py --gate
RC=$?
gate_result empty_figures "$RC" "a figure renders empty in the static HTML (exit $RC)."

say ""
say "checking extract vintages ..."
LIM vintage_pull python3 tools/check_vintage.py --part pull | tail -8
RC=${PIPESTATUS[0]}
gate_result vintage_pull "$RC" "an extract is missing, failed, older than the build or from another pull."
LIM vintage_shrink python3 tools/check_vintage.py --part shrink | tail -6
RC=${PIPESTATUS[0]}
gate_result vintage_shrink "$RC" "an extract has fewer rows than at the last passing build, with no recorded acceptance."

say ""
say "checking WPOPMETA against the allocation run's own summary ..."
LIM wpopmeta python3 tools/check_wpopmeta.py | tail -4
RC=${PIPESTATUS[0]}
gate_result wpopmeta "$RC" "a WPOPMETA field disagrees with the run that produced it."

say ""
say "checking that every embedded figure has a generator ..."
LIM change_review_check python3 tools/change_review.py --check
RC=$?
gate_result change_review_check "$RC" "the change review failed: a repository move without a decision, an approval not by Adriaan or Jan, or a stale review (exit $RC)."
LIM generators python3 tools/check_generators.py
RC=$?
gate_result generators "$RC" "an embedded field has no generator, or a generator disagrees with what is stored."

# The catch-up route plans (16 Oct 2026). tools/build_routes.py draws them in
# weekly_build.py from that build's overdue list; this refuses an edition whose
# plans were not drawn on its issue date (routes_fresh) or whose routed pumps
# are not exactly the overdue pumps at every site (routes_cover_overdue), and
# checks that index.html, routes.html, itinerary.csv and data/routes.json are
# what the generator gives. No network: it rebuilds from the OSRM cache.
say ""
say "checking the catch-up route plans against this edition's overdue list ..."
LIM routes_plans python3 tools/check_routes.py
RC=$?
gate_result routes_plans "$RC" "the route plans are not this build's, or do not cover the overdue pumps (exit $RC)."

say ""
say "checking the extracts for the paging fault ..."
LIM paging python3 tools/check_extracts.py | tail -12
RC=${PIPESTATUS[0]}
gate_result paging "$RC" "an extract the build reads carries a repeated _id."

# Piped results paired with their samples (Adriaan Mol, 28 Sep 2026). A
# readout, not a pass/fail: what did not pair is listed with its response
# codes for Cathy to pair by hand and never stops the build. It stops only if
# the pairing could not be computed at all (exit 2).
say ""
say "pairing piped water-quality results with their samples (counted, never failing) ..."
LIM piped_pairing python3 tools/rebuild_piped_wq.py --pairing | head -40
RC=${PIPESTATUS[0]}
gate_result piped_pairing "$RC" "the piped pairing could not be computed (exit $RC)."

# A new Moramanga point hung on a duplicate system record instead of the
# record of record (Adriaan Mol, 29 Sep 2026). A readout, never failing.
say ""
say "checking Moramanga points for a duplicate parent (counted, never failing) ..."
LIM moramanga_parent python3 tools/moramanga_dedupe.py --wrong-parent | head -20
RC=${PIPESTATUS[0]}
gate_result moramanga_parent "$RC" "the wrong-parent check could not run (exit $RC)."

say ""
say "recomputing the corrections-log distances ..."
LIM distances python3 tools/check_distances.py | tail -4
RC=${PIPESTATUS[0]}
gate_result distances "$RC" "a stated distance no longer reproduces from located_register_points."

say ""
say "running consistency checker ..."
# Under the venv where it exists: the checker imports check_managed, whose
# rendered check needs Playwright, and system python3 has none (10 Oct 2026).
CPY=python3; [ -x "$PYBIN" ] && CPY="$PYBIN"
LIM consistency env PLAYWRIGHT_BROWSERS_PATH="$PW" "$CPY" tools/check_consistency.py index.html portfolio.html
GATE=$?
case "$GATE" in
  0) gate_result consistency 0 "" ;;
  2) gate_result consistency 2 "the consistency checker could not run (exit 2)." ;;
  *) gate_result consistency "$GATE" "consistency checks FAILED (exit $GATE)." ;;
esac

# ---- 2b. decide, from every result ------------------------------------------
say ""
say "deciding from every gate's result (data/gate_classes.json) ..."
python3 tools/gate_decide.py
DECIDE=$?
# this run's REVIEW failures, PROVISIONAL at the top of the page
python3 tools/provisional.py --write
if [ "$DECIDE" -ne 0 ]; then
  say "Nothing was committed and nothing was pushed: a BLOCKING gate failed (listed above and in logs/gates.log)."
  exit 1
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  say "--check-only: stopping before commit as asked."
  exit 0
fi

# and on the week's approval task (the one task for the week; never a second)
if python3 -c "import json,sys; sys.exit(0 if json.load(open('data/provisional.json'))['items'] else 1)"; then
  python3 tools/asana_setup.py --approval
  RC=$?
  if [ "$RC" -ne 0 ]; then say "ABORT: the approval task could not be updated with the provisional items (exit $RC). Nothing committed."; exit 1; fi
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
