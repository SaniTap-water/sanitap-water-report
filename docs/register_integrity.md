# Register integrity

What was wrong in the water-point register, how it happened, how each case was resolved, and the
checks that stop it coming back. Written 22 September 2026.

---

## 1. Nine managed points with no `admin_region`

**What was wrong.** Nine points carry complete `admin_div1`–`admin_div5` text — region, district,
commune, fokontany — but no `admin_region`, the separate field holding an id into mWater's
`admin_regions` table. Every export and every view that keys on `admin_region` therefore shows
them with no district, while the report, which reads the `admin_div` text, shows commune and
fokontany correctly. They are:

`698771103` `698771110` `698771244` `698771251` `699596004` `699596114` `742897074` `742897115`
`742897232`

**They are not ghosts and not duplicates.** Each has maintenance visits, an E. coli test, a
distinct beneficiary count and its own mWater response links. Pairs sit 137–255 m apart with
different visit dates and different populations.

**How it happened — partly confirmed, partly corrected.** `742897074`, `742897115` and
`742897232` share `_created_on` `2024-08-15T10:04:23.856Z` to the millisecond and one creator,
which no form entry can produce: those three were bulk-imported. The other six were created
singly between 2 and 9 September 2024 by two different users, so "bulk import" explains three of
the nine, not all nine.

**The brief expected the names to need fixing. They do not.** `Canzee` is the house convention
across the register — 663 of the 908 managed entities carry it and 104 carry `IndiaMark`. There
is no better name in any form response, and no name was changed.

**How each was resolved.** The value is *derived*, from two independent lines that agree
unanimously on all nine:

| point | commune / fokontany | `admin_region` | fokontany-mates agreeing | nearest 8 by GPS | closest |
|---|---|---|---|---|---|
| 698771103 | Ankofabe / Antoraka | 303143 | 14 of 14 | 8 of 8 | 156 m |
| 698771110 | Ankofabe / Antoraka | 303143 | 14 of 14 | 8 of 8 | 302 m |
| 698771244 | Voloina / Ambodipaka | 308394 | 10 of 10 | 8 of 8 | 304 m |
| 698771251 | Voloina / Ambodipaka | 308394 | 10 of 10 | 8 of 8 | 168 m |
| 699596004 | Ankofabe / Antoraka | 303143 | 14 of 14 | 8 of 8 | 490 m |
| 699596114 | Ankofabe / Manambia | 303141 | 12 of 12 | 8 of 8 | 19 m |
| 742897074 | Anjahana / Navana | 303144 | 27 of 27 | 8 of 8 | 262 m |
| 742897115 | Anjahana / Navana | 303144 | 27 of 27 | 8 of 8 | 110 m |
| 742897232 | Anjahana / Navana | 303144 | 27 of 27 | 8 of 8 | 222 m |

A third line — the region and district dropdowns on a works form — does not exist: no form export
carries a region or district column, and `premiere_rehabilitation.csv` is header-only. So *all
available* evidence agrees, which is the test that was set.

**The values are NOT in mWater, and that is a finding.** The v3 entities API accepts a `PATCH`,
bumps `_rev`, and silently discards `admin_region`. It was tried twice on `698771103`: once as a
full-document patch and once as a minimal `{_id, _rev, admin_region}` patch. Both returned 200.
Neither persisted the field. `admin_region` is a declared property of its own type
`admin_region`, so this is not a format error — the field is almost certainly derived server-side
or gated behind a route this credential does not reach. **No further writes were attempted.**

That entity's `_rev` moved 8 → 10 with no content change: every other field is byte-identical to
the pre-write backup in `data/mwater_backups/`. Before-and-after documents and the full attempt
log are in `data/mwater_backups/` and `data/register_write_log.json`.

The derived values live in `data/register_corrections.json` under `admin_region_derived`, with
the evidence for each.

### Resolved 23 September: mWater's boundary polygons stop short of these nine

**This is resolved, permanently, by the override in `data/register_corrections.json`.** Nothing is
to be set in mWater, by Lanja or anyone else, and no coordinate is to be moved.

**`admin_region` is computed by mWater, not entered.** The `water_point` entity schema describes
the property as *"Geographical divisions and subdivisions (country, state/province, region,
district, etc.); assigned automatically by mWater based on the GPS location"*. Its roles
nominally allow editing, but the two patches of 22 September show that a written value is
discarded, which is what a computed field does.

**The cause: every one of the nine lies outside mWater's boundary polygons.**
`tools/mwater/admin_polygon_test.mjs` asks mWater's own `admin_regions` table, through `jsonql`,
which polygons contain each location, and how far each point is from the nearest. The output is
in `data/admin_polygon_test.json`. Not one of the nine falls inside any polygon at any level, not
even the country, so the geocoder has nothing to assign. Each lies 1–91 m outside, and the nearest
fokontany polygon is in every case the value derived above. As a control, the nearest coded
neighbour of each lies inside all five levels (country to fokontany).

| point | lat, lon | polygons containing it | outside by | nearest fokontany | control |
|---|---|---|---|---|---|
| 698771103 | -15.48309, 49.66520 | none | 13 m | 303143 Antoraka | 699595979, 156 m away: inside all five |
| 698771251 | -15.54294, 49.62024 | none | 1 m | 308394 Ambodipaka | 698771268, 168 m away: inside all five |
| 699596004 | -15.48634, 49.66262 | none | 69 m | 303143 Antoraka | 699596011, 490 m away: inside all five |
| 698771244 | -15.54182, 49.62080 | none | 9 m | 308394 Ambodipaka | 698771268, 304 m away: inside all five |
| 742897232 | -15.41320, 49.86123 | none | 91 m | 303144 Navana | 742897081, 222 m away: inside all five |
| 698771110 | -15.48470, 49.66430 | none | 71 m | 303143 Antoraka | 699596011, 302 m away: inside all five |
| 742897115 | -15.41309, 49.86319 | none | 9 m | 303144 Navana | 742897108, 110 m away: inside all five |
| 699596114 | -15.51995, 49.63347 | none | 12 m | 303141 Manambia | 699596121, 19 m away: inside all five |
| 742897074 | -15.41295, 49.85926 | none | 37 m | 303144 Navana | 742897081, 262 m away: inside all five |

Distances are Mercator distance × cos(latitude). All nine are on the Maroantsetra shore of Antongil
Bay, so the Madagascar boundary data appears to clip the shoreline. A note to mWater support is
drafted in `docs/mwater_support_admin_region_note.md` (not sent). It is a courtesy to them. The
report does not depend on it.

### The geocoder hypothesis, tested 22 September

The likeliest explanation was that mWater derives `admin_region` server-side from `location`
against its boundary set. That was tested on `698771103` by patching the entity with the
**identical** coordinates it already holds. The server treated the identical document as a no-op
(`_rev` did not move), so no geocoder was invoked and `admin_region` stayed null. The polygon test
above answers what that test could not: the geocoder does run from location, and for these nine
locations it finds no polygon.

### Phantom revisions on 698771103 — not edits

`698771103` now carries `_rev` **8 → 10**: two revisions whose content is byte-identical to the
pre-write backup in `data/mwater_backups/`. They are the two discarded `admin_region` patches of
22 September. **Nobody should later read them as edits.** No field changed; only `_rev` and
`_modified_on` moved. A third attempt on the same day — the identical-coordinates test above —
was a no-op and did not create a revision.

No other entity was written to at any point.

---

## 2. `670401842` "Morafeno"

**It never left the fleet, because it was never in it.** It appears in no archived edition's
`PUMPS`, including the 751-point fleet of 7 September. Its entity `type` is `other`, not a pump
type.

**What actually happened.** It was on the portfolio **map**, which until commit `d439714` drew
every entity in the MadAvance group. `d439714` changed the map to draw the actively managed
portfolio only, and that is what removed it. The departure is explained by that commit.

**Name and `admin_region` were never set, not cleared.** `_rev` is 1 and `_modified_on` is
absent: the record has never been modified since it was created on 2024-09-03. The September map
displayed "Morafeno" because it reads `desc`, which is set; `name` is null and always has been.
Its `admin_region` 306666 resolves to no row in `admin_regions`.

Recorded in `data/register_corrections.json` under `excluded_from_map`.

---

## 3. Points entering or leaving the fleet without a recorded decision

**Size of the fault class: zero.**

Across all eight archived editions and the live page, fleet membership changes exactly once:
751 → 736 on 15 September 2026, fifteen points leaving and none joining. Those fifteen are
*exactly* the fifteen in `register_corrections.json` → `excluded`, matching in both directions
with no residue. No point has ever joined the fleet unexplained.

---

## The checks that stop this returning

In `tools/check_consistency.py`:

* every point with no `admin_region` has a derived value on file, and every derived value carries
  its evidence;
* the mWater write attempt is recorded either way — the API accepting a patch and discarding the
  field is a finding, not a silence;
* **no point enters or leaves the fleet unexplained**: every archived edition is compared against
  its predecessor and the live page, and any departure must appear in
  `register_corrections.json`.
