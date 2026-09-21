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
