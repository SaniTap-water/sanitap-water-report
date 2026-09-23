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

## Who owns an action, and by when — the SharePoint workbook

The page is static and rebuilt every Monday, so an owner or a date typed into the
browser would live in one person's browser and be gone by Tuesday. The two fields
that are genuinely a person's call therefore live outside the page:

**`Water report - action owners and deadlines.xlsx`** — Central Data Hub →
`Water Documents`. One row per action: `id`, `owner` (a dropdown of known owners),
`deadline` (a date column), and a read-only copy of the title. Adriaan and Jan edit
it in Excel Online.

The build reads it through the Microsoft 365 connector into
`data/action_owners.json` and renders owner and deadline from there. If that cache
is missing or older than ten days, the page falls back to the owner and deadline
written in the body row **and prints a WATCH notice above the list saying so** — it
never shows stale values silently.

**Status, the counts and closure are never read from the workbook.** They are
computed every build by `tools/eval_conditions.py` from the closing conditions in
`data/action_conditions.json`. If a person could set status in the workbook, an item
could be marked done that the data says is not — which is the failure this whole
arrangement exists to prevent.

To rebuild and republish the workbook:

```
python3 tools/make_owner_workbook.py        # builds and self-verifies
cp build/action_owners.xlsx "/mnt/c/Users/bushp/OneDrive - SaniTap/Central Data Hub - Water Documents/Water report - action owners and deadlines.xlsx"
python3 tools/verify_published_workbook.py  # reads the published copy back
```

**Copy into the synced OneDrive folder — that is the supported path.** Do not
upload this file through Microsoft Graph or the Microsoft 365 connector.

It once opened read-only because Excel repaired it, and the cause was 40 cells
carrying a type with no value. `[trash]/NNNN.dat` members are SharePoint's
property-promotion filler with illegal OPC part names, invisible to Excel and
harmless. See `docs/owner_workbook_diagnosis.md` — including two theories that
were wrong and should not be revisited.

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
5. **the owner-and-deadline workbook** — owner and deadline come from SharePoint,
   status and closure are computed, and the fallback notice appears when the cache
   cannot be read
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
   is named.
3. **The page states the OLDEST pull, never the newest.** One extract pulled today beside one left
   over from last week must not read as "data to today". A form's own last record is a different
   quantity — a quiet form has an old last record and is perfectly current — so the two are
   reported separately and neither is passed off as the other.

`tools/test_vintage.py` is the negative test. Run it after touching any of this.
