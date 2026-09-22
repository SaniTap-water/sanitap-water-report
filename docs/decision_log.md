# Decision log

Decisions that change how a figure on the report is produced or what it means. One entry per
decision, dated, with the reasoning and what followed. Analysis lives in its own file where there
is one; this is the index and the record of what was settled and when.

Nothing here is described as closed. A decision records what was decided; whether a carbon
position is closed is the Head of Carbon's call.

---

## 2026-09-22 — The figure gate is live, and honest artefact-checking raised the residue

**The gate is on.** Any rendered figure that is not derivable from a population, declared in
PARAMS with a citation, carried in the dated manual file, quoted from a named document, or the
output of a named script now fails the build unless it is on the dated residue list. That list
may only shrink; the gate fails if an entry on it acquires a source and is not removed.

**Two source classes were missing from the taxonomy and are now in it.**

*Quotation.* A figure inside quoted material takes its source from the document quoted. The SOP
says “646 Canzee + 77 India Mark III = 723 pumps”; that is what the SOP says, not what we
measure, and correcting it silently would destroy the point of quoting it. It expands to the
document, its version and its date.

*Computed artefact.* Output from our own scripts, with better provenance than most form answers:
a named output file, the generator, the input extract and the run date. The gardien-calendar
figures come from `data/calendar_extraction_figures.json` via `tools/read_year_ocr.py`; the
people-served allocations from the pinned WorldPop raster, with the weighting stated.

**A section-level marking is not a source, and finding that out put the number up.** Marking a
whole section as a computed artefact was too permissive: an invented figure injected into such a
section inherited the marking and the gate passed it. The rule is now that an artefact-marked
figure must either carry a value the artefact actually produced, or be marked individually.
Applying it took the residue from 34 back to 93 — the honest number, and the most useful thing
this pass established.

**The census was also counting things that are not figures.** Numbers welded into identifiers
(`M400-12`, `A6.4-AMT-009`, `EPSG:3857`, `CW-project survey_112025`), coordinate pairs and hub
dataset ids are excluded, and the exclusions are counted in the census output so the list cannot
grow quietly.

---

## 2026-09-22 — Every water-point deep link was broken; there is no such route

**The defect.** 62 anchors on the report pointed at
`https://portal.mwater.co/#/water_point/<uuid>`. That route does not exist, and neither does
`#/entities/<type>/<uuid>`, `#/entity/...` or `#/sites/<uuid>`. Every one landed on *Page not
found*. It was not an authentication problem: `#/forms/<id>` and `#/responses/<id>` resolve from
the same session.

**There is no deep link to an entity to be had.** This was settled from the portal's own route
table, read out of its JavaScript bundle rather than guessed at. The complete set of entity-ish
routes is:

| route | what `:id` is |
|---|---|
| `/entities(/:id)` | redirects to `/entity_views/:id` |
| `/entity_views(/:id)` | a saved **view** document, not a water point |
| `/water_systems/:id`, `/sanitation_systems/:id` | an **asset**, not a site |
| `/admin/archives/:table/:id` | admin only |

And the application never builds one: every `href:"#/..."` in the bundle is to a section, never
to a record. The Sites page is a browser, not an addressable record view.

**What the links point at now.** The response that references the point —
`#/responses/<id>`, which resolves, and is the better target anyway: it opens the document that
says something about the point rather than a bare record card.
`data/mwater_point_responses.json` maps 863 point codes to response ids across the works,
borehole, repair, maintenance and call forms, preferring the first-rehabilitation record.
84 anchors rewritten across `index.html`, `data/action_details.json`,
`tools/render_marolinta.py` and `tools/render_block.py`. **Zero broken routes remain**, including
in the provenance table.

A point with no record on any form gets no link — the code as plain text — rather than a link
that lands nowhere. One point qualifies: `670401842`, which has no record on any form, consistent
with everything else known about it.

**The gate.** `tools/check_links.py` extracts the portal's route table and asserts that every
mWater route the page links to exists in it. It is in `publish.sh` and negative-tested: restoring
one `#/water_point/` link fails it by name.

Pattern-matching the URL is what let this through — the 62 matched their regex perfectly and none
worked. A hash fragment never reaches the server, so fetching the URL proves nothing; rendering
it unauthenticated proves nothing either, because valid and invalid routes both bounce to login.
The route table is the thing that can actually be tested.

**Archived editions are NOT corrected.** Three carry the defect and keep it:

| edition | issued | broken links |
|---|---|---|
| `2026-09-22-wk39-ed1.html` | Tue 22 September 2026 | 62 |
| `2026-09-22-wk39-ed2.html` | Tue 22 September 2026 | 62 |
| `2026-09-22-wk39-ed3.html` | Tue 22 September 2026 | 62 |

Earlier editions carry none: the links were introduced with the water-point detail tables on
22 September and the defect lasted one day.

---

## 2026-09-22 — 723 withdrawn; the chain reconciles; the 48 repeated points never existed

**Decision.** `723` is **withdrawn** as a live figure, as `727` was, rather than carried with a
caveat. It cannot be reproduced from anything held. `REG.succ` is now the derived point count
**730**; `REG.succ_withdrawn` keeps 723 so the change is auditable.

**The counts, from a stable enumeration.** 773 first-rehabilitation **records** on 773 distinct
**points** — one record each. 731 successful **records**. 730 successful **points** in the
register. 730 is exactly what the page's own register-chain note has always claimed, so that note
was right and is now derived rather than asserted.

**The 48 points with two records do not exist.** They were mWater's paging. A paged pull of the
1,688-response works form returned 1,688 rows carrying only **1,586 distinct `_id`s** — 102
records twice, 102 missed. De-duplicated it gives zero repeats.
`tools/mwater/pull_form.mjs` walks 30-day windows; no window exceeds 221 rows, so paging never
engages. Nothing to classify, and no form guard proposed: the fault a guard would prevent is not
happening. Recorded in `docs/first_rehabilitation_records.md`.

**The chain now reconciles except at one step.** `742896839` is in mWater but its `_managed_by`
is `all`, not the MadAvance group, so the register export excludes it correctly by its own
definition. That is a decision for a person — belongs in the group or leaves the fleet — not an
investigation. The six fleet points with no successful rehabilitation are the five Marolinta
boreholes, whose works are on a different form, plus `782134540`, which is recorded.

**Records are not points.** 731 successful **records** equals 731 carbon-fleet **points** by
coincidence this week. Every population now declares its unit, every chain step names which unit
it relates, and the checker refuses to let the two be set beside each other. That confusion
produced 727, the 723/731 gap and a "46 unexplained points" finding that was the paging fault.

---

## 2026-09-22 — The register chain does not reconcile, and the definitions now say so

**Decision.** `tools/populations.py` is the single definition of every population the report
counts. Each is a **set of records** with a predicate, never a stored count and never a
subtraction. The reconciliation is produced by that file and rendered on the page; where a step
does not hold it is reported, not closed.

**Two steps do not hold.**

**1. One managed point is not in the register export.** `742896839`. Already tracked as
`act-742896839`; the chain rediscovered it independently, which is the point of having a chain.

**2. The first-rehabilitation figures cannot be reproduced from the form the page cites.**
The page carries 773 first-rehabilitation records and 723 successful, sourced to
`86cf66efdd3749dd8a121314bab3675a`. Read today, that form yields **725** distinct points with a
first-rehabilitation record and **686** recorded successful — a gap of 48 and 37.

The register-chain note also says the fleet is the successfully rehabilitated points plus a
handful never rehabilitated. On the records there are **46** managed non-Marolinta points with no
successful first-rehabilitation record, not one.

**Nothing was adjusted to close either gap.** Both are rendered on the page under *Does the chain
reconcile?* and both `REG.total_first_rehab` and `REG.succ` expand to a caveat saying the figure
does not reconcile with the form it cites.

**What does reconcile.** register ⊇ first-rehabilitated ⊇ successful holds; managed ⊇ Marolinta
holds; **carbon_fleet + marolinta = managed_fleet exactly** (731 + 5 = 736); calendar-evidenced ⊆
carbon_fleet holds (297 of 731).

---

## 2026-09-22 — A published sensitivity figure was wrong by 8,478 people for six days

**What was wrong.** The people-served sensitivity note read: *"On the earlier basis of Canzee 250
and India Mark 500 it gives **115,074**."* The correct figure for that basis is **123,552**.
115,074 understated it by **8,478 people**.

**What 115,074 actually was.** It is exactly the total computed with **India Mark capped at 300**
— the *applied* ceiling — and Canzee at 250. The second scenario was computed with the India Mark
cap left at its applied value instead of the alternative the sentence named. The figure was
right for a basis nobody stated and wrong for the basis printed beside it.

**When it went wrong, and when it did not.** The figure was introduced on 12 September
(`cbce482`) as **126,058**, and on the data of that day 126,058 is exactly Canzee 250 / India
Mark 500 — correct for its caption. The fault was introduced at the **WorldPop R2025A rebase on
16 September** (`01eb3bf`), which recomputed it to 115,074 on the wrong cap while leaving the
caption alone. So this was not drift and not staleness: it was recomputed, and recomputed wrong.

**Where it was published — the exposure.** It was never emailed to anyone; it stayed inside the
report. The exposure is four archived editions and six days live:

| edition | issued | live until |
|---|---|---|
| `2026-09-16-wk38-ed5.html` | Wed 16 Sep 2026 | superseded same day |
| `2026-09-16-wk38-ed6.html` | Wed 16 Sep 2026 | superseded same day |
| `2026-09-16-wk38-ed7.html` | Wed 16 Sep 2026 | superseded 18 Sep |
| `2026-09-16-wk38-ed9.html` | Wed 16 Sep 2026, archived 18 Sep | on the live site until 22 Sep 07:28 |

**The archives are not corrected.** They are the record. A corrected archive is a worse artefact
than a wrong one with a correction attached, so all four keep the figure they were issued with
and this entry is the correction attached to them.

**Why nothing caught it.** It was a stored constant, `WPOP_C250`, sitting beside the data it
duplicated, with no assertion anywhere and no computation to check it against. A wrong figure of
the right order of magnitude is invisible to a checker that was never told what the figure means.

**What was done.** `WPOP_C250` and `WPOP_IM500` are deleted. Both figures are now computed at
render time by `wpopAt(imCap, czCap)`, from `WPOP` and the pump type, so the caption and the
computation take their caps from the same place and cannot disagree again. `wpopAt` reproduces
the published applied total (128,221) exactly, which is the test that it is reconstructing the
same quantity.

**One detail worth recording.** `WPOP[wp]` is `[raw, capped, cap]`, and raw and capped were each
rounded from the same float, so on 32 points they differ by 1. A naive `min(raw, newCap)` misses
the published total by 8. `wpopAt` uses the published `capped` for any point below its ceiling
and the raw only for a point at its ceiling, which is the only reconstruction that reproduces
128,221. The old stored constants used the naive form, so they were a further 8 out on top of
the cap error.

---

## 2026-09-22 — Exposure trace for 727, which did leave the building

**Why this is separate.** 115,074 stayed inside the report. 727 did not: it was sent to James
Walker on Monday 21 September, four times — as the 2026 active carbon count, as the denominator
of "293 of those 727", as "roughly 127,000 people at 727 points", and as "zero of 727 points" in
the Annexe B individual-consent argument. The correction to him is drafted separately. This is
the trace of everywhere else it reached.

**When it existed at all.** 727 was created on **Sunday 20 September 2026 at 07:09** in commit
`8b33228`, the SDWS 27 basis work. It did not exist before that date. That one fact clears most
of the field.

**The live report.** Present from 20 Sep 07:09 until 22 Sep 07:46 (`70447c7`) — two days:

| commit | time | 727 rendered |
|---|---|---|
| `8b33228` | Sun 20 Sep 07:09 | 3 |
| `e9bd885` | Sun 20 Sep 14:28 | 8 |
| `8a606a8` | Mon 21 Sep 18:53 | 13 |
| `d513e1a` | Mon 21 Sep 22:00 | 13 |
| `41e7e0c` | Tue 22 Sep 07:28 | 13 |
| `70447c7` | Tue 22 Sep 07:46 | 0 as a denominator |

**Archived editions: none.** No archived edition carries 727 as a figure. The last archive is
`wk38-ed9` of 18 September, two days before 727 was created, and week 39 was never archived. The
`routes.html` and `portfolio.html` companions carry none either.

**The UNICEF deck of 17 September: clear.** `SaniTap UNICEF 2026-09-17 v_02.pptx` was last
written on **15 September**, five days before 727 existed, and contains no 727, 731, 293, 434,
736 or 723 on any of its twenty slides. It cannot have carried the figure.

**Two SOPs in SharePoint do carry it,** both written 20 September, and both in the rhetorical
sense rather than as a carbon claim — *"727 variantes propres à chaque point"*, the argument for
why a per-year calendar grid beats a per-pump one:

* `SOPs/SOP-MAD-SDWS27-CalendrierGardien-v1.5-2026.docx` (current), 20 Sep 22:43
* `SOPs/Archive/SOP-MAD-SDWS27-CalendrierGardien-v1.4-2026.docx` (archived), 20 Sep 21:48

They are SOPs a VVB may be shown. The number is wrong there for the same reason it was wrong on
the page — it should be the derivable 731 — though nothing in either document divides by it.

**No monitoring report or VPA-DD extract carries it.** Nothing under
`Central Data Hub - Water Documents` or `MadAvance` modified since 19 September contains 727
apart from those two SOPs; the Marolinta interim report of 20 September does not.

**Analysis documents.** `docs/sdws27_basis.md`, `docs/enduser_consent_position.md` and
`docs/decommissioning_rule_question.md` each carry it and each now carries a dated correction
note at the top. Their bodies are left as written, for the same reason the archives are.

**Still on the page, deliberately.** Six occurrences remain: the SDWS 27 per-year table cell,
which is shown as entered and visibly marked unsourced, and the text explaining the change.

---

## 2026-09-22 — The carbon denominator changed from 727 to 731, because 727 could not be derived

**Decision.** The denominator for "active carbon points" on the report is now **731** — the
actively managed register less Marolinta — computed from the register every build by
`tools/carbon_denominator.py`. It replaces **727**, which was carried in eleven places including
under carbon claims, and which nothing in this repository can reproduce.

**From 727 to 731. The figures that changed with it:**

| figure | was | is | basis |
|---|---|---|---|
| active carbon points | 727 | **731** | `PUMPS` less Marolinta, computed |
| carbon points with a dated 2026 calendar sheet | 293 | **297** | `data/calendar_year_coverage.csv` ∩ the carbon fleet |
| carbon points with none | 434 | **434** | 731 − 297, unchanged |
| 2026 calendar coverage | 40.3% | **40.6%** | 297 ÷ 731 |

**434 was right all along, and that is what settles it.** The count of carbon points with no dated
2026 sheet reproduces *exactly* on the 731 basis. The page's own arithmetic was internally
consistent — 727 − 434 = 293 — but the denominator was wrong by four, so the covered count was
wrong by four in the other direction.

**Why 727 could not be kept.** Four candidate derivations were tested against the data. All four
reach 727 arithmetically and none is a set operation:

* **732 corrected successful first rehabilitations − 5 Marolinta.** `SUCC_CORRECTED` counts
  corrected *records*, two of which are not in the maintained fleet, so subtracting Marolinta from
  it is not an operation over the fleet.
* **731 − 4**, **736 − 9**, **751 − 24**, **738 − 11.** None of the subtrahends corresponds to any
  identified set in `CORR`, `REG` or the extracts.
* The nearest principled reading — successfully rehabilitated, not Marolinta, less the points
  flagged *"refer to James Walker before this point is counted in a monitoring report"* — gives
  **728**, not 727, because one of those three (`742895010`) is not in the fleet to begin with.

And it cannot be checked here at all: `premiere_rehabilitation.csv` is header-only and
`wp_madavance.csv` carries no rehabilitation, eligibility or commissioning column, so no per-point
successful-rehabilitation set and no per-year activity set exists locally.

**Where it came from.** 727 arrived already formed in commit `8b33228` (20 September 2026, the
SDWS 27 basis work), with no computation beside it. It was never derived in this repository.

**What is NOT changed, and is now marked unsourced on the page.** The SDWS 27 per-year
quantification table reports carbon points active and point-years per year — 0 / 722 / 727 and
0 / 356.7 / 726.6 — and computes every tonnage and USD figure from them. Those are *per-year*
counts: a point counts in a year from the date it entered the programme. That basis does not
exist in this repository, so the tonnages cannot be recomputed on 731 either. Changing one cell
and leaving its row would have been worse than saying so. All thirteen cells carry a visible
mark and the table carries a stated caveat naming what is missing. `act-carbon-year-basis` is
open against it.

**Consequence.** No figure on the page divides by 727 any more. The per-year table is the only
place it still appears, shown as entered and marked as such.

---

## 2026-09-21 — The gardien calendar is the official record of days operational

**Decision.** The gardien calendar is the official record of days operational for `SDWS 27`. The
call centre is an operational dispatch device: it exists to send a technician to a pump. **A
ticket that remains open means the report-back did not arrive, not that the pump is still
broken.** Call-centre data does not evidence downtime and is used in no carbon figure.

**Why.** The registered basis names the instrument. `SDWS 27` option 2 is *"demonstrate from log
of operation and maintenance system"*, and the calendar is that log — a daily record kept at the
point by the person who is there. A call-centre ticket is a dispatch artefact: it is opened when
somebody telephones and closed when somebody reports back, and neither event is an observation
of the pump. Treating ticket age as downtime measures the reporting process, not the asset.

**What followed.**

* **A published figure was withdrawn.** The edition of 21 September 2026 valued the open-ticket
  backlog at **297 tCO₂e** of days operational, and valued a day cleared across the 44 affected
  points at 3.5 tCO₂e. Both were computed by treating an open ticket as a day not operational.
  Both are withdrawn and not replaced. The correction is visible on the page rather than silent.
* The 44 points remain on the report as an **operational signal** — tickets open a median 84
  days — under the maintenance section, with no carbon quantity attached.
* `tools/check_consistency.py` asserts that no call-centre-derived quantity appears in tonnes
  anywhere on the page.
* Where a ticket and a calendar disagree, the calendar governs.

**What this does not settle.** See the open question below. Deciding which instrument governs
says nothing about whether that instrument is being filled in.

### Open, and turning on the transcription round

The 44 points with open tickets show a mean implied days operational of **353.0** against
**353.4** for the fleet — indistinguishable, where a pump reported broken for a median 84 days
should not be. Two explanations remain:

1. **The tickets are stale and the pumps were repaired.** The repair form is created only when
   work is finished, and 143 of 187 records carry a completion date equal to the submission date,
   so a repair done without the form filled in leaves a ticket open for ever. The calendars are
   right; report-back discipline is what is broken. Benign.
2. **The gardiens are not marking outage days.** The pumps really were down and the calendar does
   not record it. That is not a coverage gap but a defect in the instrument, applying to every
   point rather than these 44 — and it would undermine the record this decision has just made
   official.

**The 50-sheet transcription round distinguishes them and nothing else on file can.** A human
transcriber reading the same photographs will show whether marks are present that the extraction
missed — fault in the reader, calendars sound — or whether the sheets are genuinely unmarked,
which is explanation two. Both produce identical extraction output, which is why the round is
the only test. Tracked as `act-transcription-round`.

---

## 2026-09-21 — No decommissioning or retirement for inactivity

**Decision.** SaniTap will not decommission or retire water points for inactivity. A pump that
stays broken remains in the portfolio and is reported at its honest days operational.

**Why.** Conservatism. Removing under-performing points takes them out of the denominator and
flatters the fleet average — the worst points leave the register and reported availability rises
without a single pump working better. It is also what the methodology assumes: neither version
has any provision for a retired supply, because `DO_p,y` is days operational and a pump that
stops working simply contributes fewer of them.

**What followed.** The 95% pause rule in `SOP-Suppression_Points d'Eau` is not applied and that
SOP needs amending to say so. The permanent-deletion criteria are untouched. No writable status
property is needed in the register. Repair speed becomes the only lever on days operational,
which is why time to repair became a headline metric.

Full analysis and the options as they stood: [`decommissioning_rule_question.md`](decommissioning_rule_question.md).
