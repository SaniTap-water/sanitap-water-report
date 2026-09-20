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

The marker names its own generator, so the rule is readable from the page.

`data/mwater_form_snapshot.json` follows the same rule without markers: it is output, written
only by `tools/refresh_form_snapshot.py`, and never hand-edited. It is what block 7ai asserts
the live form structure against, because the checker cannot call mWater on every build. Run the
refresh whenever an mWater form is changed — a form edit is caught the next time it runs, and
the failing check names what moved.
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

## Controlled documents outside the repo

The gardien calendar SOP, its template and its generator live in SharePoint at
`Water Documents/SOPs/`. The SOP is at **v1.5**; the template and generator are at **v1.4**
(v1.5 changed the procedure and the mWater form, not the sheet). Superseded versions go to
`SOPs/Archive/`. The generator there is the source
of record for the template; `sdws1/calendar_extract/make_calendar.py` is a
tombstone pointing at it.
