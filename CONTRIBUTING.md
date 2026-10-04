# Working on this repository

The report is a single living page. Everything below exists because something
went wrong once and the fix would not have stuck on good intentions.

## The gate

`tools/check_consistency.py` must pass before anything is published, and
publishing goes through `tools/publish.sh` — never `git commit` by hand. The
checker is a gate, not a report: `publish.sh` stops before the commit if it
exits non-zero.

```
tools/publish.sh --check-only            # gate the working tree
tools/publish.sh -m "what changed"       # check, commit, push
```

## The report covers the actively managed portfolio only

Decided by Adriaan, 23 September 2026 (`docs/decision_log.md`). The page covers
the water points we maintain and that serve people, broken ones included. A
maintained pump reported down stays in the portfolio, in "reported down" and
in downtime. Records that merely sit in the MadAvance mWater group, such as
survey entries, failed or abandoned points, points handed on and rope pumps,
are not the portfolio. **The count of the whole group never appears in
rendered text.** `tools/render_check.py` fails the build if it does, on any
scope.

The group is still read every week, inside the build.
`tools/classify_register.py` classifies every record: in the fleet; joins (a
successful first rehabilitation, not excluded, with a site, a coordinate and a
pump model, appended to PUMPS automatically); excluded by decision; a
rehabilitation that did not succeed; no first rehabilitation; or review.
Anything it cannot place goes to `logs/publisher.log` for a person to look at,
and nowhere on the page. Its full result is `data/register_classification.json`.

### "How this is worked out" footnotes

Six collapsed footnotes sit beside the figures they govern: the data date, the
scope line, the fleet count, the water-quality tile, people served, and the
register corrections. Every number in them (the pump models, the E. coli
threshold, the WorldPop release and checksum, the service and neighbourhood
radii, the caps and the roof-count factors) renders from
`data/build_config.json`. The tools read the same file (`tools/build_config.py`).
`check_consistency.py` fails if a footnote carries a typed number, or if the
configuration differs from what the tools, the SDWS1 pipeline, the run of
record, the per-pump caps or `PARAMS` actually applied. Change a rule in the
configuration, not in a footnote.

## Every number on the page has exactly one home

An audit in September 2026 counted 191 live figures typed into the body prose
and nothing asserting any of them: `736` appeared in fifty-four sentences,
`127` in twenty-seven, `84` in fifteen. The only protection was a blacklist of
withdrawn phrases, which can only ever catch a number somebody already knew
was wrong. Had the register moved to 737, fifty-four sentences would have
become false and every gate would still have passed.

**The rule. A figure with an mWater source is interpolated. A parameter is
declared in `PARAMS` with its citation. A hand-entered figure lives in a dated
manual file with an owner. Nothing else may appear as a number on the page.**

### Tier 1 — live

Anything derivable from an extract. Never type it.

* In JavaScript, interpolate: `${fmt(S.n)}`.
* In body prose — static HTML, which cannot interpolate — write
  `<span data-fig="S.n"></span>`. `fillFigures()` evaluates the expression
  against the page's own data on every render, so a sentence is on exactly the
  same footing as a tile. The span carries no digits, which is what makes the
  prose gate below exact.
* The same span works inside `data/action_details.json`, inside the `TRACE`
  array and anywhere else whose text reaches the page through `innerHTML`.

Do not store a figure that can be computed. `SUCC_CORRECTED`, `WPOP_IM500` and
`WPOP_C250` were stored constants sitting beside the data they duplicated;
`WPOP_C250` had drifted 8,478 people out of date before anyone noticed. They
are computed now, from `CORR` and from `WPOP`.

### Tier 2 — declared constants, in `PARAMS`

Registered or chosen values that must **not** become live: the capacity
ceilings, the Type 3 annual cap, the registered per-point emission reductions,
the 347-day SDWS 27 cap, the mWater group id. Each entry carries:

```js
im_cap:{v:300,unit:'people per pump',
 source:'Rural Water Supply Network and Akvopedia design service population. '+
  'Still unsettled between the WorldPop methodology note, which used 500, and '+
  'the technical note, which argues 300; this page uses the lower of the two. '+
  'Open as act-indiamark-premises.',
 set:'2026-09-16, with the WorldPop R2025A run'},
```

Render it with `${pp('im_cap')}` in JavaScript, or
`<span data-param="im_cap"></span>` in prose; both show the citation on hover.
A constant with a citation is correct. A constant without one is
indistinguishable from a typo, and `check_consistency.py` fails the build if
any `PARAMS` entry has no `source` or no `set`.

### Tier 3 — hand-entered, in a dated manual file

Endur'O is not on mWater, so its figures cannot be derived. That is a fact
about the programme. Them ageing silently is not acceptable. They live in
`data/enduro_manual.json` with an `as_at` date, the person who supplied them
and the document they came from, and `tools/render_enduro.py` writes them into
the page. `enduroAsAt()` prints *"as at 2026-09-18, supplied by …"* wherever
one of them appears. Past `max_age_days` (60) the page says so in red and
`act-enduro-refresh` reopens on its own.

A figure whose source is recorded as "not recorded" is not sourced, however
long it has been carried: `enduro_figures_unattributed` counts them and
`act-enduro-people-source` stays open until it reaches zero.

### The two gates

Both run in `publish.sh` and both must pass.

```
python3 tools/figure_census.py --gate    # the rendered page: does each figure have a source?
python3 tools/prose_figures.py --gate    # the source: was it typed rather than rendered?
```

They ask different questions and neither can answer the other's. The census
walks all five scope buttons and asks of every rendered literal whether its
value is reachable from the live data, declared in `PARAMS`, or in the manual
file. It cannot tell a typed figure from an interpolated one — they are
identical in the DOM. The prose gate can, because a `data-fig` span contains no
digits: every digit left in the body prose is typed by hand.

The blacklist of withdrawn figures stays. A positive rule and a negative one
catch different things.

**What the prose gate does not count** (since 23 September 2026): digits inside
a generated region, and digits in a span its own element marks as
`data-quote`, `data-retired`, `data-withdrawn` or `data-artefact`. A generated
region is its generator's output, rewritten every build and checked with
`--check`. Counting it made the gate fail whenever a metric readout in the
action list moved, so the automated build could never pass. A marked span is
typed by design, and the census holds it to its registry. The census still
checks every one of these values.

**The census classes.** Beyond live, `PARAMS` and manual there are four marked
classes, each sourced by what it is: a quotation (`data-quote`, registered in
`QUOTES`); a computed artefact (`data-artefact`, registered in `ARTEFACTS`
with its generator, input, run date and seed, and its value must be reachable
in the artefact's inlined data, not merely marked); a figure named only to
record its withdrawal (`data-withdrawn`); and **a retired value quoted as
history** (`<span class="retired" data-retired="DATE" data-was="…">628</span>`).
A retired value renders struck through and labelled *retired*, so it cannot be
read as current. Use it where a sentence records what changed ("changed from
727 to …"). In a population's `decided` text, list the value under `retired=`
in `tools/populations.py` and the definitions generator marks it.

A figure JavaScript writes goes through `figSpan(expr, value)`. That writes the
same `data-fig` contract as the prose, so the census sees it as rendered and a
click opens `DERIV[expr]`. Every such expression needs an entry in
`tools/render_derivations.py`.

**The backlogs.** `data/figure_backlog.json` (134 rendered figures with no
source) and `data/prose_figure_backlog.json` (354 still typed) recorded what was
outstanding on 22 September 2026. On 23 September the figure backlog reached
**zero**. Its `cleared_note` says how each group was resolved and what stopped
rendering. `data/unsourced_figures.json`, an older worklist no gate reads, was
emptied with it. Anything not on them fails the gate
immediately, so no new unsourced figure can land. **They may only shrink**: a
value that acquires a source must be removed from the file, and the gate fails
if it is not. They are a worklist with a date on it, never an exemption list.

To clear one: convert the figure, run `--gate`, and it will tell you which
entry to delete.

**Two layout rules the render check enforces.** In the headline tile row, no
single tile may set the row's height (tallest within 6 px of the next
tallest), and every number is one line at one size. The row sizes each tile by
its number, not its label. At phone width (390 px) the page never scrolls
sideways: a wide table scrolls inside its own container (`wrapTables()` gives
one to any table without it), and grid children may shrink.

**The generator audit** (`tools/check_generators.py`) holds every field of
every embedded data object to a generator, a population, or the dated,
shrink-only `data/ungenerated_fields.json`. It finds objects by a `const NAME=`
at the start of a line, so **declare every data object on its own line**.
`REG` was declared after `COAST` on the same line and was invisible to the
audit until 23 September. Its nine population fields are now written each
build by `tools/sync_reg_populations.py`; the other twelve are group D of the
backlog, each classed *declared* or *neither*.

## Every number means what its label says

Standing rule, Adriaan Mol, 28 September 2026 (`docs/decision_log.md`). It was written after
"Pumps reported down or reduced: 5" sat beside "21 hand pumps reported down": the 5 was the
call-centre contact count, copied into another key (`breakdown_reports = calls`) and rendered under
a meaning it did not have.

* **No figure is copied or aliased from another.** Each figure is computed from its own records.
  `check_consistency.py` (block 7bd) fails the build if a build tool assigns one stored figure to
  another key, or if the page's own script does; the handful of assignments that are not figures
  are named there with their reason. A value typed into prose must never be bound to a live figure
  because the numbers happened to match (a "732 chemical test results" was once bound to the
  corrected rehabilitation count that way).
* **A windowed count and a current total are labelled as such.** A tile that counts events in a
  window says so and names the window; a current total says what state it counts ("down now, by
  the last record on each pump"). Where both sit together, the page reconciles them in words.
* **Say which set a figure counts.** Records or points; submitted or final; this form or both
  forms; the carbon fleet or the maintained fleet; per image or per pump-period; on file in mWater
  or in the backup. Two figures over different sets that could be read as the same thing carry the
  distinction beside them.
* **A dated figure stays dated.** A figure measured on a day (an overlap, a reconciliation, a
  census) is shown with its date or as a retired value, never re-bound to today's live count.
* **Parts add up to their total, or the page says why not.** A table's rows sum to its total row;
  a split names every part, including "not classified" and "not in the managed register".
* **Nothing stored stands in for something computable.** A figure the build can compute is
  computed every build; a stored one goes on the dated, shrink-only backlog and says so on the page.
* **Checked by a reader.** Before a release that changes figures, the rendered page is read by a
  reviewer with no build context, looking for unexplained contradictions; what they find is fixed
  or explained on the page.

## Formatting and readability

Standing rule, Adriaan Mol, 28 September 2026 (`docs/decision_log.md`). It applies to every
table on the page, and `tools/test_readability.py` fails the publish if any part of it breaks.

* **Fixed, content-sized columns.** Every table is `table-layout: fixed` with a `<colgroup>`
  sized to what the columns hold. `layoutTables()` in the page measures each table and writes
  the colgroup; a table whose source already carries one sets `data-cols="set"` and keeps its
  own widths (`#popstbl`).
* **Numbers** are right-aligned and never wrap (`td.num`).
* **No text column narrower than about 110 px at 1366 px width.** A table that cannot fit at
  that width scrolls inside its own box.
* **Long ids, mono strings and links** use `overflow-wrap: anywhere`, so they cannot force odd
  widths on their neighbours.
* **Any table over 12 rows sits in a scroll box**: at most 60vh high, sticky header, and the
  line "N lignes — faites défiler" above it. It must not push the rest of the report down.
* **No horizontal page scroll** at 1366 px or at 390 px. Wide tables scroll inside their own box.
* **Both themes are checked on real screenshots.** The test renders every table in the light
  and the dark theme, writes a screenshot of each (`--shots DIR`), and fails if header or body
  text falls below a 4.5:1 contrast.
* The test prints every table on the page with its narrowest text column, so a regression names
  itself.
* **Print** (`@media print`): every scroll box opens to its full height (no max-height, no
  overflow), headers stop being sticky and repeat at the top of each printed page, the filter
  boxes and the "faites défiler" lines are hidden, and the light theme is forced. Column widths
  are percentages, so a table fills the paper width in its screen proportions; a filter is
  cleared before printing and restored after. The test emulates print at A4 width, starting
  from the dark theme with a filter set, and fails unless every table prints all its rows.

```
~/sdws1/venv/bin/python tools/test_readability.py --shots /tmp/readability
```

A new table needs nothing extra: it is laid out and checked like the others. A table that
needs particular proportions carries its own `<colgroup>` and `data-cols="set"`, and is still
checked.

## Transcription photographs are served upright

Every calendar on the transcription page has a reviewed orientation in
`data/transcription_orientation_review.csv` (degrees clockwise to upright, who looked).
`tools/bundle_new_sheets.py --orientation` writes the upright copy into `transcription/img/`
from the original kept in `transcription/img_original/`, never from an already-turned file, and
records both SHA-256s in `data/transcription_orientation.csv`. The checker fails if a calendar
has no review, or if the served file, its size or its kept original differs from that record, so
an image cannot be served sideways or un-reviewed. Aspect ratio is not the test: an upright
sheet can be photographed in portrait, and an upside-down one is still landscape.

## The two-copies rule

**Every generated artefact is edited only at its generator, and no script
exists at two paths.** This is the rule that most needs to survive a context
reset, because breaking it produces a failure that looks exactly like success.

It has caused two regressions:

* A stale `bundle_new_sheets.py` lived in `sdws1/calendar_extract/` as well as
  in `tools/`. The repo copy was fixed; the other copy was the one actually
  run. The fix appeared to do nothing, twice, before the second copy was
  found — sixteen selection rows were left without sheet numbers.
* The machine-extraction block of `index.html` was edited directly, twice. Both
  edits were correct, both were committed, and both were silently reverted the
  next time `render_block.py` ran.

### One home per script

A script name may appear at exactly one path across this repository and the
extraction workspaces it shares code with (`sdws1/`, `sdws1/calendar_extract/`).
Where a second copy used to live, a **tombstone** remains: a short file whose
whole body is `sys.exit(__doc__)` and whose docstring names the one real home.
Tombstones are not counted as copies — that is the point of them. Previous
contents are kept in `sdws1/.attic/`.

If you need to run a repo tool against the extraction workspace, run the repo
copy and pass it paths. Do not copy it there.

### One source per generated region

Generated regions of `index.html` are delimited:

```html
<!-- BEGIN GENERATED machine-extraction :: tools/render_block.py :: do not edit between these markers -->
...
<!-- END GENERATED machine-extraction -->
```

Everything between the markers is **output**. To change a word of it, edit
`tools/render_block.py` and re-run it:

```
python3 tools/render_block.py --write    # splice into index.html
python3 tools/render_block.py --check    # exit 1 if index.html has drifted
```

The generated regions include `machine-extraction` (`tools/render_block.py`),
`form-freshness` (`tools/render_form_freshness.py`), `ttr-table`
(`tools/render_ttr_table.py`, the time-to-repair table, typed by hand until 23
September), `marolinta-table` and `definitions`.
`tools/publish.sh` runs every one of them with `--write` before it gates, so the gate sees
current output; the checker then fails the build if any region and its generator disagree.
Adding a third means writing a generator with `--write`/`--check`, putting its markers in
`index.html`, and adding it to the loop in `publish.sh`. Nothing else needs changing — the
checker discovers regions from the markers.

The marker names its own generator, so the rule is readable from the page.

`data/mwater_form_snapshot.json` follows the same rule without markers: it is output, written
only by `tools/refresh_form_snapshot.py`, and never hand-edited. It is what block 7ai asserts
the live form structure against, because the checker cannot call mWater on every build. `publish.sh` runs it on every build (`--if-possible`), so in practice the snapshot is refreshed
from mWater each time the report is published. That path never fails the build for being
offline: with no network or credentials it falls back on the committed snapshot and prints its
age. What is not tolerated is staleness — the checker fails outright once the snapshot is more
than seven days old, and the page states the date the forms were last read.
A generator added later must support `--check` and `--write` and be named in
its marker the same way; the checker discovers regions from the markers, so
nothing else needs updating.

### What enforces this

`tools/check_consistency.py`, block 7af:

* **no script filename exists at two paths** — walks this repo and the
  declared sibling workspaces, skipping caches, virtualenvs and tombstones,
  and fails naming both paths;
* **index.html declares its generated regions**, and the markers are balanced;
* **the generator named in each marker exists**;
* **each region matches its generator** — the checker runs the generator's
  `--check` and fails with a diff if the published region has drifted;
* **this file records the rule**.

## Actions: one list, three states, and how an item closes

**Every action in the report has exactly one detailed row**, in the section that explains it,
and appears once more in the consolidated list at the top of the page. The list is *generated*
from those rows by `tools/render_actions.py`, so the two cannot drift: the detailed row is the
source, the summary table is output.

**Three states and no more.**

| | | was |
|---|---|---|
| **ACT** | bright red — work outstanding | DUE, OVERDUE |
| **WATCH** | orange — standing, monitored, no end date | STANDING |
| **OK** | green — done, or decided | DONE, DECIDED |

`DECIDED` survives as a small label inside OK, because a decision taken is not the same as work
completed and a reader should be able to tell them apart.

**OVERDUE is not a stored state.** It is a badge rendered beside ACT in the generated list,
computed from the deadline against the build date. It was previously typed by hand, and eleven
rows carried an OVERDUE label against a date that had not yet arrived. `check_consistency.py`
fails the build if an OVERDUE label appears anywhere outside the generated region.

**Closing discipline.** When an item is resolved:

1. set its detailed row to **OK**;
2. **update the text that raised it in the same pass** — the prose that described the problem
   must stop describing it as open;
3. the generated list moves it out of the live table into the collapsed *closed this period*
   block on its own.

The checker enforces the parts it can see: that nothing marked OK is still described as open,
that every detailed row carries an up-link to the list, that no action-shaped text hides inside
a collapsed block without a row, and that the status vocabulary is exactly these three.

## Generated regions are siblings, never nested

A generated region is delimited by its BEGIN/END markers and is rewritten wholesale by its
generator. **Never place one region, or any hand-written content you intend to keep, inside
another region's markers.** The outer generator will delete it on its next `--write`, silently,
and the only evidence will be that something stopped appearing.

This has now cost three separate faults:

* the `downtbl` opening tag eaten while wrapping a table, leaving a stray `>` — markup still
  parsed, table simply gone;
* a `</table>` match that truncated at the wrong closing tag;
* the definitions section, anchored on `<section id="actions">` which sits *inside* the
  action-list region — written successfully, then deleted by the next `render_actions --write`
  with no error anywhere.

Anchor on the region's BEGIN marker, not on markup inside it:

```python
anchor = "<!-- BEGIN GENERATED action-list"      # correct: a sibling boundary
anchor = '<section id="actions">'                # wrong: that tag is inside the region
```

`tools/check_consistency.py` asserts the definitions region sits before the action-list region.
Extend that assertion when you add a region; the check is cheap and the fault is invisible.

## A figure's source is never a working document, plan or deck

A figure's source is **a form response, a registered methodology parameter, or a named
decision.** Never a plan, deck, proposal or working document. Numbers in those were written to
make a point, not to be accurate, and they do not become accurate by being quoted.

This was applied on 22 September to the StrokeMeter Technical Development Plan v1.2, whose
illustrative counts had been carried into the report as though they were the register: 770 units,
688 and 82 by variant, a fleet of 723, 646 Canzee and 77 India Mark II, and 10 pods plus 2 spares.
All removed. The substantive quotation — that the Stroke Logger is *"permanently mounted to a
static part of every metered pump"* — stays, because it is a commitment, not a measurement.

Quoting a document in order to correct it is allowed, and must be visibly a quotation: the SOP
item says the SOP's own words are *"646 Canzee + 77 India Mark III = 723 pumps"* and then gives
the managed fleet from the register.

## Tracing whether a figure left the building: check the attachment, not the folder

When establishing whether a figure reached an external artefact, check **the file actually
attached to the email**, not the similarly named file sitting in the folder. They are routinely
different: a deck is revised after it is sent, or sent from a copy, and the folder holds the
version nobody received. A file named for the date of a meeting is not evidence it is the file
that went to the meeting.

Where the attachment cannot be recovered, say so and give the folder evidence for what it is —
an indication, not a finding.

## Waiting for a background job: never `pgrep -f` on its own pattern

On 22 September a session was ending every report with "18 shells still running". Nothing in
this repository was leaking them. `publish.sh`, `weekly_build.sh` and `weekly_build.py` have no
backgrounded step, and the render gate closes its browser on every path — there were zero stray
Chromium processes. The orphans were wait loops of this shape:

```bash
until ! pgrep -f "weekly_build.py" >/dev/null; do sleep 60; done   # never exits
```

`pgrep -f` matches against the full command line, and the waiting shell's own command line
contains the pattern it is searching for. So the loop matches itself, `pgrep` never returns
empty, and the shell waits for ever. Twenty-two of them had accumulated, the oldest three days
old, several polling for a script that had finished days earlier.

Wait on something that cannot match the waiter:

```bash
until ! pgrep -f "[w]eekly_build.py" >/dev/null; do sleep 60; done   # bracket breaks self-match
until ! pgrep -x python3 >/dev/null; do sleep 60; done               # match the process, not the line
wait "$PID"                                                          # best: wait on the job itself
```

Check before reporting a run finished: `pgrep -f "[u]ntil ! pgrep"` should return nothing.

## Other standing rules

* Clone and patch the live files. Never rebuild a page from sources elsewhere.
* Every number carries its source, and no number appears twice with two values.
* Correct published numbers visibly. Do not narrate changing understanding to
  readers.
* Where a conclusion turns on what a registered document says, quote the
  parameter box or the clause, not a reviewer's summary of it.
* The words "disinfect", "disinfection" and "désinfection" do not appear.
* Deadlines are proposals, marked for Jan to confirm or move.
* Nothing is described as closed — that is the Head of Carbon's call.
* Archive an edition into `editions/` only when locking one for a VVB.

## Disk, and the documents that live on OneDrive

**C: is the drive under pressure, not the Linux disk.** Measured 21 September 2026: the WSL
filesystem was 15% full with 810 GB free, while C: was 98% full with 22 GB free. Deleting files
inside WSL does not give C: a byte back on its own — the WSL disk is one 161.8 GB file on C:
(`ext4.vhdx`) that grows and never shrinks by itself. It takes a compaction, and a compaction
needs `wsl --shutdown`.

Two tools exist for this and neither deletes anything in a sync folder, ever — deleting from
OneDrive, Dropbox or Proton Drive deletes from the cloud, which is the opposite of freeing a
cache:

* `tools/require_local.py` — fails the build when a document it reads from OneDrive is
  **cloud-only** rather than present. Storage Sense dehydrates synced files when C: fills; a
  dehydrated file shows a normal size in a listing and then stalls or throws an unexplained I/O
  error on open. Detection is `st_size > 0 and st_blocks == 0`, verified by dehydrating a
  disposable file and watching blocks go 360 → 0 → 360. Wired into `check_consistency.py` so it
  fails first, names the file, and says how to restore it.
* `tools/disk_retention.py` — reports both disks and the VHDX slack, and enforces retention on
  the three stores this project owns. **Report-only by default**; `--apply` enforces,
  `--caches` also clears package caches.

**The retention rule.**

| Store | Rule |
|---|---|
| `~/mwater-mcp/backups` | keep **30 days**. Older files are deleted only if a byte-identical copy exists in SharePoint, or if they are `*_proposed.json` plan artefacts. Anything else is kept and reported — a file whose only copy is local is never deleted. |
| `~/mwater-exports` | keep **14 days**; regenerable by re-exporting. |
| `~/.cache/pip`, `~/.cache/uv`, `~/.cache/go-build` | pure download caches, clearable on request. |
| `ext4.vhdx` | compaction is flagged once the allocated-minus-used gap passes **20 GB**. The script prints the command and never runs it. |

Virtual environments are **not** in scope: none of them has a requirements file, so none can be
demonstrably rebuilt, so none may be deleted.

To schedule the report weekly:

```
0 8 * * 1  cd ~/sanitap-water-report && python3 tools/disk_retention.py >> ~/disk_retention.log 2>&1
```

## Controlled documents outside the repo

The gardien calendar SOP, its template and its generator live in SharePoint at
`Water Documents/SOPs/`. The SOP is at **v1.5**; the template and generator are at **v1.4**
(v1.5 changed the procedure and the mWater form, not the sheet). Superseded versions go to
`SOPs/Archive/`. The generator there is the source
of record for the template; `sdws1/calendar_extract/make_calendar.py` is a
tombstone pointing at it.

## Who owns an action, and by when — `data/action_owners.json`

The page is static and rebuilt every Monday, so an owner or a date typed into the
browser would live in one person's browser and be gone by Tuesday. The two fields
that are genuinely a person's call therefore live in one file in this repository:

**`data/action_owners.json`, block `owners`, is the source of record** for owner and
deadline: one entry per action id, `owner` and `deadline` (an ISO date or `null`), and
nothing else. It is edited only here, in a commit that goes through `publish.sh`.
`tools/render_actions.py` renders owner and deadline from it, and refuses to render
if the file is missing — there is no silent fallback to the owners typed in the
detail rows.

A row naming an action that no longer exists renders nothing. Such rows are held in
`orphan_rows` in the same file, dated and **shrink-only**: the checker fails on a new
one, and on a listed one that has since been removed. Removing a row is Adriaan's call.

**Status, the counts and closure are never stored there.** They are computed every
build by `tools/eval_conditions.py` from the closing conditions in
`data/action_conditions.json`. If a person could set status by hand, an item could be
marked done that the data says is not — which is the failure this whole arrangement
exists to prevent.

### The SharePoint workbook is retired

Until 28 September 2026 owner and deadline were read from
**`Water report - action owners and deadlines.xlsx`** (Central Data Hub → `Water
Documents`) through the Microsoft 365 connector. That workbook is retired (decision of
28 September 2026, confirming a verbal decision of 26 September; `docs/decision_log.md`).
It was last read on 21 September and last modified on 22 September. The build does not
read it, does not report it as a to-do, and does not rebuild it. Its location is kept
under `retired_source` in `data/action_owners.json`.
`tools/make_owner_workbook.py`, `tools/verify_published_workbook.py`,
`tools/synthesise_sharepoint_roundtrip.py`, `tools/xlsx_invariants.py`,
`build/action_owners.xlsx` and `docs/owner_workbook_diagnosis.md` are no longer part of
the build; the checker asserts that nothing in the build path calls them.

## Self-closing actions

| file | what it holds |
|---|---|
| `data/action_conditions.json` | one closing condition per action — `data`, `form`, `artefact`, `decision`, or an explicit `none` with the reason |
| `data/action_metrics.json` | the recounted value of every stored query, written by `tools/action_metrics.py` |
| `data/action_state.json` | what the build worked out this run: satisfied, evidence, `closed_since`, `reopened_on` |
| `data/decisions.json` | the only thing that closes a `decision` item: answer, date, source |
| `data/decision_candidates.json` | possible answers found in the mail thread — **surfaced for confirmation, never closing anything** |
| `data/sharepoint_listing.json` | folder listings behind the `artefact` conditions |

Rebuild order, every Monday:

```
python3 tools/pull_extract.py --write        # FIRST: pull, or everything below is stale
python3 tools/rebuild_activity.py --write    # visits and repairs into the page
python3 tools/build_call_tables.py --write   # status, down, partially working
python3 tools/check_freshness.py --write     # how far behind mWater the extract is
python3 tools/marolinta_admin.py --write     # district/commune from the register
python3 tools/action_metrics.py --write      # recount every stored query
python3 tools/eval_conditions.py --write     # decide what is open
python3 tools/render_masthead.py --write
python3 tools/render_freshness.py --write
python3 tools/render_marolinta.py --write
python3 tools/render_block.py --write
python3 tools/render_form_freshness.py --write
python3 tools/render_actions.py --write      # last: it reads the state the others wrote
```

## What the weekly task must preserve

Carried forward every edition. `tools/check_consistency.py` asserts each of them:

1. the five scope buttons
2. the maintenance clock rule
3. the Marolinta exclusion
4. the collapsed "Management notes — internal, remove before sharing with a VVB" block
5. **the owners record** — owner and deadline come from `data/action_owners.json`,
   the source of record, edited only in this repository; status and closure are
   computed; a missing record stops the build
6. **one to-do list** — the consolidated action list is the only one on the page
7. **the extract is pulled and the page rebuilt from it, every edition** — run
   `tools/pull_extract.py --write`, then `tools/rebuild_activity.py --write`
   and `tools/build_call_tables.py --write`, before anything else. The build
   FAILS if any rebuildable source is more than two days behind mWater, so an
   edition cannot go out on a stale extract.
8. **the call-centre status rule** — stated in `tools/build_call_tables.py`,
   printed on the page, and asserted identical by the checker. It was
   recovered once by comparison; it must never again be something only one
   process knows.

## The extract, and why it went stale for a fortnight

On 21 September the page reported the week to 7 September. Three separate
faults had to line up, and each of them passed every check:

1. **The build ran, and published nothing.** ~~There was no scheduled build.~~
   *Corrected 21 September:* the weekly build runs in a **cloud session**, not
   on this computer, which is why no cron entry, systemd timer or Windows task
   exists here — looking for one locally proved nothing. It fired at 05:09 UTC
   and finished at 06:01. Its push was refused, so it did what its instructions
   say: wrote `index.html` and `routes.html` into `C:\Users\bushp\Downloads`
   at 05:59 UTC, archived week 38 into `Downloads\sanitap-wk39\editions\`,
   and asked for a manual push. **Nobody pushed it.** The built edition — week
   39, edition 11, 735 points, records to 14 September — sat in Downloads while
   the published page kept its 7 September data, and every staleness check
   passed because the published page was internally consistent with its own
   stale extract.
2. **The pull ran, onto a filename nothing reads.** The cloud build reaches
   mWater through this computer, and it did: `repairs.csv` was written here at
   04:54 UTC, fifteen minutes before the build started, holding records to
   14 September — and the built page carries exactly that date, so only that
   pull can have supplied it. But `repairs.csv` is not a canonical name. The
   canonical `reparation_apres_panne.csv` stayed at 7 September, which is what
   any later investigation finds. The pull was also not code in this
   repository; `tools/pull_extract.py` is that step, now written down, and it
   writes canonical names only.
3. **The exporter silently lost the newest rows.** `mwater_export_csv` pages
   with `skip`/`limit` and no sort order. mWater's row order shifts between
   requests, so a long export duplicates some rows and drops others, then
   stops on a short page and reports success. The 21 September export of the
   preventive-maintenance form wrote 755 rows of which only **547 were
   distinct**, and the four most recent responses — 3, 4, 10 and 11
   September — were not among them.

`tools/pull_extract.py` does not page. It walks fixed date windows, splits a
window that comes back full, and de-duplicates on `_id`. The same form now
pulls 755 rows, all distinct, newest 11 September.

### What fails the build now

| check | fails when |
|---|---|
| the extract behind the page is not stale | the newest record on the page is more than **3 days** older than the build date |
| the page was rebuilt from the extract that was pulled | the files are newer than the page — pulled, never rebuilt from |
| the extract carries no duplicated records | any response file has fewer distinct `_id`s than rows, or no distinct count at all |
| no extract sits under a filename the build never reads | anything but the canonical names is in `~/mwater-exports` |

The masthead carries the extract date beside the issue date, and turns the gap
into a red badge past the same three days, so a reader sees it without opening
anything.

### Canonical extract filenames

`pm.csv`, `reparation_apres_panne.csv`, `appel_signalement_pannes.csv`,
`premiere_rehabilitation.csv`, `forage_moramanga.csv`, `wp_madavance.csv`.
Nothing else is read. A pull that writes `repairs.csv` is a pull that did
nothing.

### What the refresh moved, and what it deliberately did not

The 21 September refresh rebuilt the visit- and repair-derived fields:
`last_pm`, `last_repair`, `last_visit`, `days` on every pump, `S.over6` and
the week counters. Preventive maintenance and repairs are now level with
mWater (lag 0).

It did **not** rebuild the call-centre-derived tables — pump status, the down
list, the partially-working list, time out of service. That builder is not in
this repository, and the rule it applies is not written down anywhere. A
reconstruction from the page's own description of the rule agreed on 463 of
640 pumps and would have restated 177 — 168 of them from `partial` to `ok` —
so it was not applied. `data/data_freshness.json` carries `call-centre` as a
named gap with a reason, a date and the action that closes it
(`act-call-tables-builder`), and `check_consistency.py` fails if a named gap
ever loses its action row.

`S.never` is left alone for the same reason: it counts points with no works
record of any kind, including rehabilitation and construction, and this pull
covers neither.

### "Succeeded" is not "published"

The scheduled task reporting success means **the build completed**, not that
anything reached the site. When its push is refused it writes the built pages
into `C:\Users\bushp\Downloads` and asks for a manual push — and if nobody
acts, the site keeps last week's page while the task's own log says success.

`tools/check_build_drop.py` reads that folder and records what is waiting.
`check_consistency.py` then **fails** when a completed build carries a later
issue date than the published page, so an edition cannot be built, dropped and
forgotten. Run it before every publish:

```
python3 tools/check_build_drop.py --write
```

Check the Downloads folder whenever the task reports success and the site has
not moved.

## The scheduled publisher

The cloud build pushes if it can. When it cannot it writes the edition into
`C:\Users\bushp\Downloads` and asks for a manual push — and on 21 September
nobody pushed, so a complete edition sat there all day. `SaniTapWeeklyPublish`
removes the person from that loop.

**Mechanism: Windows Task Scheduler invoking WSL.** Not a systemd timer inside
WSL: WSL is not a persistent machine, it shuts down when its last process
exits, so a timer inside it only fires when something else has already started
it. Task Scheduler runs whenever Windows is on and *starts* WSL itself.

```
wsl.exe -d Ubuntu -- /home/bushp/sanitap-water-report/tools/publish_waiting.sh
```

**Schedule:** Mondays 11:00 local (07:00 UTC), one hour after the cloud build's
06:01 UTC finish, then every 2 hours for 12 hours — 11:00, 13:00, 15:00, 17:00,
19:00, 21:00, 23:00 — in case the build ran late or the machine was asleep. A
run with nothing waiting costs a few seconds and logs one line, so retrying is
cheap.

**If the machine is off at the scheduled time:** `StartWhenAvailable` is set,
so Windows runs the task as soon as it next boots. If the machine stays off all
week the edition simply waits in Downloads; the next Monday's run publishes
whichever candidate is there, provided it is newer than the published page and
passes both gates.

**What it will not do.** It refuses, publishes nothing and logs the reason
when: the working tree is dirty (someone's uncommitted work would be swept
into the edition); the candidate has no readable issue date; the candidate is
not newer than the published page; or either gate fails. It verifies the
candidate **where it lies** before copying — copying first and checking after
leaves the repository half-written — re-verifies in the repository after
copying, and `git reset --hard` + `git clean` the working tree if anything
after the first copied byte fails.

Every run appends one line to `logs/publisher.log`, success or not, so a later
run and a later reader can both see what happened.

```
tools/publish_waiting.sh              # what the task runs
tools/publish_waiting.sh --dry-run    # verify and report, never write
SANITAP_DROP=/some/fixture tools/publish_waiting.sh   # proof runs
```

## The call-centre tables, and the rule behind them

`tools/build_call_tables.py` builds the status split, the down list and the
partially-working list. Until 21 September these were the only part of the page
nothing here could rebuild: the builder was not in the repository and the rule
was written down nowhere, so when the extract went stale they quietly kept
10 September values while everything around them moved on.

The rule was recovered by comparing candidate rules against the published
tables pump by pump. It is stated in full at the top of that file, printed on
the page, and the checker asserts the two are identical.

**Reproduction is the test.** `--reproduce <date>` rebuilds from the extract
truncated to that date and compares against the published tables:

```
python3 tools/build_call_tables.py --reproduce 2026-09-07   # 736/736, exact
```

A change to the rule that breaks reproduction is a wrong change.

**Holds.** 39 pumps cannot be reproduced and are listed in
`data/call_status_holds.json` with the reason on each, left on their published
value rather than restated on a guess. Most are days on which a call and a
visit share the last date: across the 193 pumps in that position the original
build followed the call on 168 and the works record on 25, and the submitted-on
timestamps do not separate them — in 171 of the 193 the published value
contradicts timestamp order. A hold applies only while the rule still
disagrees; the next answered record on that pump settles it and the hold falls
away. Two fell away on the first run against current data.

**Not recovered:** the split of "partially working" into a service request and
a reduced-performance report. On the 55 pumps the published table calls reduced
performance, the selected response's issue question is empty, so that split
comes from somewhere the extract does not reach. It is carried forward for
pumps that already had one and left unclassified for new entries.

## The weekly edition is built here now

Until 21 September the edition was built in a cloud session that could not
publish. It wrote its output into `C:\Users\bushp\Downloads` and asked for a
manual push; when nobody pushed, the site kept last week's page and every
check passed. Every piece the edition needs now lives in this repository, so
the build runs here and the cloud session is a watchdog rather than the
builder.

**`SaniTapWeeklyPublish`** → `wsl.exe -d Ubuntu -- /home/bushp/sanitap-water-report-build/tools/weekly_build.sh`
Mondays **07:00 local (03:00 UTC)**, repeating every 2 hours for 14 hours —
07:00 through 21:00. It no longer waits an hour for a cloud build to finish,
so it runs as early as the machine is likely to be on.

`tools/weekly_build.py` **builds**; `tools/publish.sh` **gates and publishes**.
There is one gate list, and it is in `publish.sh`. Until 23 September the weekly
build carried its own shorter list, only the render gate and the consistency
checker, and committed and pushed itself. So the automated edition skipped the
figure census, the prose gate, the link check and the migration check that
every manual publish runs. `tools/publish_waiting.py`, the Downloads path, did
the same. Both now publish only through `publish.sh`.

In order:

1. refuse if the working tree is dirty, and remember `HEAD`
2. do nothing if today's edition is already out, unless an update was asked
   for (below), `--force`, or `--dry-run`
3. pull the mWater extracts
4. rebuild the activity fields, the call tables, the Marolinta admin data,
   the freshness record, the metrics and the condition evaluation, and
   re-render every generated region
5. hand over to `publish.sh`, which archives the outgoing edition, refreshes
   the form snapshot and runs **every** gate: `--check-only` on a dry run,
   `-m` otherwise
6. if `publish.sh` refuses, `git reset --hard` to the remembered `HEAD`

A `--dry-run` stops before commit and push and always rolls back.

### The build has its own clone: `~/sanitap-water-report-build`

The scheduled run of 21 September refused to build because the working tree
was dirty. The task shared `~/sanitap-water-report` with interactive sessions,
so anyone's uncommitted work stopped the Monday edition, and it would have
happened again. **The build clone is never worked in.** Every run of
`tools/weekly_build.sh` in it starts with `git fetch` and
`git reset --hard origin/main` plus `git clean -fd`, then re-runs the freshly
reset copy of itself. So it builds from what is published and from nothing
else. Run from any other clone, `tools/weekly_build.sh` hands over to the
build clone. `~/sanitap-water-report` is for interactive work only.

`logs/publisher.log` is not tracked by git (since 23 September), so no reset
or rollback can erase it. A refused run is never pushed, so its reason exists
only in the build clone's log. **The last line of
`~/sanitap-water-report-build/logs/publisher.log` is always one plain sentence
beginning `OUTCOME:`**, for example *"OUTCOME: Not published: publish.sh
refused the edition because a figure renders on the page with no source
(first: 339 x4 in …)."* That is the line the Monday watchdog quotes.

What it needs from outside the repository, all by absolute or `~` path, so any
clone resolves them: `/home/bushp/sdws1/venv` (Python and Playwright),
`~/.cache/ms-playwright`, `node` in `~/.local/bin` (the wrapper puts it on
`PATH` itself: a scheduled `wsl.exe` shell does not load the profile, so it was
missing there), `~/mwater-mcp` (mWater credentials and CLI),
`~/mwater-exports` (shared with interactive sessions) and push credentials
through `gh auth git-credential` in `~/.gitconfig`. The untracked edition
ledger `logs/editions_issued.tsv` is the clone's own.

A rehearsal against unpublished work: add the interactive clone as a remote in
the build clone, then run with `SANITAP_BUILD_FROM=<remote>
SANITAP_BUILD_BRANCH=<branch>`.

### The mWater tooling is read-only (since 25 September 2026)

mWater allows writes only through the portal or MCP proposals. Nothing in this
repository or in `~/mwater-mcp` writes to it. Both HTTP clients
(`tools/mwater/api.mjs` and the MCP server's `mwaterFetch`) throw on any
request other than a GET, except the login `POST /v3/clients`. The old write
scripts are in `tools/mwater/retired/` and cannot run; their writes stay on
record in `data/register_write_log.json`. `check_consistency.py` fails the
build if anything the build runs calls a retired script, or if `api.mjs` grows
a write path again. A correction to a register record is made in the portal
and arrives with the next pull.

**The build runs only the pinned `~/mwater-mcp`.** That checkout has no
remote and its `dist/` is untracked build output, so neither a commit here nor
one there fixes what executes. `data/mwater_mcp_pin.json` records the commit
and the SHA-256 of `dist/index.js` and `cli_call.mjs`; `weekly_build.py`
refuses to pull if the checkout is at another commit, has uncommitted changes
to tracked files, or either file differs. To move the pin: commit in
`~/mwater-mcp`, `npm run build`, `npm test`, record the new values.

**Runs are at least 60 minutes apart.** A real run of `weekly_build.sh`
records its start in `logs/last_run_started` (untracked). A run that starts
within 60 minutes of the last one stops before any fetch or pull, with the
`OUTCOME:` line "Skipped, not built: the last run started N minute(s) ago…",
and **exits 75**, so the task's Last Result shows it did not build. The retry
is not triggered by the exit code: the task's trigger repeats every 2 hours
from 07:00 to 21:00 whatever the last result was. A skip consumes nothing, so
a pending `logs/update_requested` is honoured by the next run. Dry runs are
exempt.

*A manual update in the hour before Monday 07:00* cannot lose the Monday
edition. It builds the new ISO week's edition itself; the 07:00 run is either
ignored by Task Scheduler (`IgnoreNew`, while the manual run is still going)
or skipped by the guard; the 09:00 run then finds today's edition published
and does nothing, or, if the manual run did not publish, builds it.

### Updating mid-week

A second run in the same ISO week pulls live mWater again and republishes
**over** the current edition. The week and edition number stay the same, and
the issue date becomes today's (`render_masthead.edition()` keeps the number
of the edition at `HEAD` when it is this week's). `tools/archive_edition.py`
archives the outgoing edition only across a week boundary, so a mid-week
update adds nothing to `editions/` and cannot duplicate an entry. The week's
last version is frozen when the next week's edition replaces it.

**The desktop shortcut "Update water report now"** (on the Windows desktop)
runs `tools/update_now.cmd` in the build clone. It drops `logs/update_requested`, runs
`schtasks /run /tn SaniTapWeeklyPublish`, waits for the task, and leaves the
window open with the result and the tail of `logs/publisher.log`. The request
file is how the build tells a click from a scheduled retry: a retry after
today's edition is out does nothing, a click rebuilds.

### The Downloads path is still live, and secondary

A candidate in Downloads is still considered and gated identically. It is
preferred over the local build **only when its data is genuinely newer** —
compared on the newest record each carries, not on its issue date. That keeps
a route open if this machine is unavailable for a long stretch. If the local
build did nothing at all, `tools/publish_waiting.py` still runs on its own, so
a waiting candidate is never stranded.

### What the local build cannot do that the cloud build could

- **It needs this machine.** The cloud build ran whether or not the laptop was
  on. `StartWhenAvailable` catches up at the next boot, and the retries cover
  a machine that was merely asleep, but a machine off all week publishes
  nothing that week — where the cloud build would at least have produced a
  candidate. The Downloads path is the mitigation.
- **It cannot rebuild the page's narrative.** The cloud session could rewrite
  prose; this build regenerates only what has a generator. Structural and
  wording changes are still hand work.
- **It is slow where the cloud build was not.** `tools/pull_extract.py` walks
  date windows per form, spawning a process per window, and takes roughly a
  quarter of an hour. That is the price of a correct pull — the server's own
  paging silently drops rows — but it means a run is minutes, not seconds.
  `SANITAP_SKIP_PULL=1` exercises every other step against the extracts
  already on disk; the schedule never sets it.

### The cloud build is now a watchdog

Leave it scheduled. It no longer builds the edition that gets published: its
candidate is gated like any other and is taken only if its data is genuinely
newer than the local build's. What it still does usefully is notice — if it
runs and this machine has not published, its output lands in Downloads and
`tools/check_build_drop.py` turns that into a failing check.

## Extracts: one puller, one manifest, one vintage

Every extract the build reads is pulled by `tools/pull_extract.py --write` and recorded in
`data/extract_manifest.json`. There are twelve: five response CSVs, the seven JSON extracts the
populations read, and the register, which is pulled separately.

**Never add an extract without adding it to the puller.** Seven JSON extracts spent months
outside the build because `tools/mwater/pull_form.mjs` was correct and invoked by nothing. Six
populations read them; nothing refreshed them; every gate passed, because the figures agreed with
the populations and the populations agreed with the files. An input that has stopped moving is
invisible to any check that only compares the build to itself.

Three rules follow:

1. **Enumerate in bounded windows, never by paging.** mWater's `skip`/`limit` has no sort order,
   so a paged pull duplicates some rows and drops others, and stops on a short page either way.
   Both pullers walk date windows and de-duplicate on `_id`. `tools/check_extracts.py` reads the
   files themselves and fails on any repeated `_id`.
2. **Every extract carries its pull date, and no extract may predate the build it feeds.**
   `tools/check_vintage.py` enforces it. A file left over from a previous week fails the build and
   is named. The day rule alone cannot see a file from yesterday or from an earlier run the same
   day, so a build that pulls (`weekly_build.py`) sets `SANITAP_RUN_STARTED`, and every extract
   must then have been written after that moment; one written before it fails and is named.
   `tools/test_vintage.py` proves both rules fail.
3. **The page states the OLDEST pull, never the newest.** One extract pulled today beside one left
   over from last week must not read as "data to today". A form's own last record is a different
   quantity — a quiet form has an old last record and is perfectly current — so the two are
   reported separately and neither is passed off as the other.

`tools/test_vintage.py` is the negative test. Run it after touching any of this.

## Layout and status gates (30 Sep 2026)

Two gates run inside `publish.sh`, and both must pass:

* **`tools/check_layout.py`** loads the built page in Chromium at 1522 px and
  506 px with every `<details>` open. It fails on an inline pixel width on a
  table; a `.num` column over 25% while a text column is under 160 px; action
  list shares more than 2 points off 50/12/6/8/24; an empty `<h2>` (also one
  that renders no text as loaded, inside a collapsed `<details>`); the withdrawn
  section wording; a stat tile whose surface, border or radius differs from the
  partner cards; and a section box narrower than 90% of the content column,
  including a grid with an empty column track. `--url` runs it against the live
  page; `--shots DIR --tag NAME` saves screenshots.
* **`tools/status_actions.py --write --check`**: every status cell in a table
  marked `statusgate` is complete ("applied", "in place", "sourced and
  evidenced") or names an OPEN action in `data/status_actions.json`, and links
  to it. Closing that action while the status is unchanged fails the build.
  A new requirements table (Requirement/Input column, then Status or Evidence
  status) fails until it is marked `statusgate`.

Tables are sized by `layoutTable()` in `index.html` only once they render,
never with an inline width; `.num` columns are capped at 25% on a table of
900 px or more (a capped one wraps, class `numwrap`), and text columns share
the rest by content, never under 160 px there. Retired action ids live in
`data/action_redirects.json`; the surviving row carries an anchor with the old id.

### Laptops only, both themes, tinted surfaces (30 Sep 2026, second pass)

Every render check runs at 1280x800, 1440x900 and 1920x1080 only; the narrow-screen CSS stays but is
not tested. `check_layout.py` runs in the light and the dark scheme and adds: tinted surfaces at
1.25:1 or more on the page background (`--tint`, `--tint-line` in `:root` for each theme), all text
at 4.5:1 (3:1 at 24 px and larger) against its composited background, and partner cards logo-left and
no taller than 220 px (Endur'O excepted). Status colours hold 4.5:1 on the page and on `--tint` in both
themes. The header carries an Auto / Light / Dark switch (`localStorage` key `sanitap-theme`, applied
in `<head>` before first paint).

## Machine-read downtime is published only from a validated reader (1 Oct 2026)

Transcription round 1 compared two human readers and the calendar machine reader on the same 68
calendars and days. The reader detected **0 of the 40 days both humans marked X** (sensitivity 0%,
specificity 99.6%, κ about 0 against either human). Its high "agreement" was blank days agreeing.
Every figure computed from its marks was withdrawn the same day, from the page and from the data
files the page inlines: the stratum days-operational averages (363.9 and the district and year rows),
"1.1 days not operational", the observed-cell marked rate and the impossible-cell error floor, the
count of days not operational, the implied uptime, and the 2027-sheet marked rates. Earlier editions
carried older values of the same kind (2.41%, 4.25%, 1.84%, 8.8 days, 356.2 days, "98% of days",
97.6%, and the 2,787 t / 3,015 t / 25,121 t "supported by evidence / resting on the estimate" split);
the archived editions are left as issued.

**The rule.** `tools/reader_gate.py` names the machine-downtime fields and the withdrawn phrasings.
`tools/check_consistency.py` fails the build if any of them is on `index.html` or `portfolio.html`
(as a `data-fig`, an inlined dataset field or text), or in `data/calendar_extraction_figures.json` or
`data/calendar_stratum_figures.json`, unless `data/reader_validation.json` shows the reader of record
validated: sensitivity ≥ 0.90 and specificity ≥ 0.99 against the days both human readers mark X, on
all round-1 calendars **and** on the held-out (even-numbered) ones. `tools/recompute_figures.py` and
`tools/calendar_stratum.py` omit the fields themselves while the gate is shut.

`tools/reader_validation.py` writes the validation file (slow: it OCRs every round-1 photograph; the
registrations are cached in `~/sdws1/calendar_extract/v3_cache`). It is not in the build loop; rerun
it when the reader or the transcriptions change. Days operational stand at the registered 347 days
either way; the only operational evidence shown is the human transcription, labelled as a sample.

## Provenance panels follow the scope buttons, and open at full width (1 Oct 2026)

**Scope.** Every "How this figure is produced" panel says which scope it is in. A figure that adds
Endur'O's hand-entered figure to the hand pumps (`agg(HP).x + (SCOPES[SCOPE].enduro ? ENDURO.y : 0)`)
is split into its parts by the page (`scopeComposite`): MadAvance alone, the Endur'O manual file alone,
or *MadAvance + Endur'O = total* with each source and date, according to what the scope covers. The
Endur'O manual-file derivation is never chosen in a scope without Endur'O. Partner-specific blocks
carry their own `data-scopes` (the partner cards, the smart-meter panel, the Endur'O sentence in the
estate note), which `applyScope` now honours on any element. Sections that are the same in every
scope (the action list, the register trace, the carbon data gaps, the data-quality notes) are marked
`data-programme-wide`, and their panels say "programme-wide" instead of pretending to follow the
buttons. Every panel's arithmetic arrives at the value its own expression gives.

`tools/check_provenance.py` builds the panel of every live figure in all five scopes and fails on a
panel whose arithmetic does not arrive at the figure, one that names a source its scope does not use,
a composite without the sum in a scope with both partners, or a panel with no scope row.

**Layout.** A panel opens at full width beneath its card or card row and pushes the content down: a
figure in a table cell opens in a full-width row under that row (after any row-spanning cell, pinned to
the visible width of a sideways-scrolling table); a figure inside a grid or a row of flex cards opens
after the outermost such row (`derivAnchor`). A row expanded inside a long table's 60vh scroll box (the
readability rule) scrolls that box so it starts in view; the rest is reached by scrolling the box. `tools/check_panels.py` opens every panel and every
`<details>` at 1280, 1440 and 1920 px and fails on a panel that is narrow, overlapped, clipped or that
does not push what follows down. Both run in `publish.sh`.

**One box at a time (4 Oct 2026).** Clicking a figure shows one box, for that figure only; clicking another
figure replaces it; clicking the same figure again closes it (`toggleDeriv`, `closeDeriv`, `DERIV_CUR`). The
active figure is outlined, and the box's first line names what it explains (`derivLabel`: a tile's or card's
caption, a donut's legend and title, a table cell's column and row, or the rest of the sentence), e.g.
"Explains: 745 water points in scope". A box whose figure is re-rendered away (a scope change) is dropped.
`check_panels.py` clicks a tile, a sentence and a table cell and fails if any of this does not hold.

## Actions: Asana is the list, the repo is the evidence (2 Oct 2026)

Owner, deadline and completion of every action are edited in Asana (project "H2O4CO2 - CLEAN WATER",
section "Weekly report actions"), not in the repo. Each build runs `tools/asana_pull.py` (read-only) and
renders from `data/asana_pull.json`. `tools/asana_setup.py` is the only script that writes to Asana — run
it after adding an action to `data/action_details.json`, with `--complete <act-id>` to complete a task.
The token lives in `~/.config/sanitap/asana_token`; never print or commit it.

Completing a task in Asana does not close the action: the page shows "done in Asana, evidence pending"
until the evidence its closes-when names is recorded under `evidence` in `data/action_owners.json` (or a
build condition is satisfied). `tools/check_asana.py` fails the publish on an open action without exactly
one task, an owner or deadline differing from Asana, or an action closed without evidence.

Tasks are matched by gid (`data/asana_map.json`), never by name. Each action's name is a plain
title in `data/action_owners.json` ("title"): a verb first, about twelve words, codes only in brackets
after plain words. Asana names a task "<plain title> [act-id]"; if an owner renames it, the build takes
the new wording as the title.
