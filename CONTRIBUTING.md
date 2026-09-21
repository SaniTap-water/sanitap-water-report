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

There are two generated regions today — `machine-extraction`
(`tools/render_block.py`) and `form-freshness` (`tools/render_form_freshness.py`).
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

To reseed the workbook after a large change to the action set:

```
python3 tools/make_owner_workbook.py        # writes build/action_owners.xlsx
```

then upload it over the SharePoint copy, keeping the same filename.

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
python3 tools/rebuild_activity.py --write    # write the fresh activity into the page
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
   `tools/pull_extract.py --write` then `tools/rebuild_activity.py --write`
   before anything else. The build FAILS if the data on the page is more than
   three days old, so an edition cannot go out on a stale extract.

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
