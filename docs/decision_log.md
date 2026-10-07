# Decision log

Decisions that change how a figure on the report is produced or what it means. One entry per
decision, dated, with the reasoning and what followed. Analysis lives in its own file where there
is one; this is the index and the record of what was settled and when.

Nothing here is described as closed. A decision records what was decided; whether a carbon
position is closed is the Head of Carbon's call.

---

## 2026-09-22 — The rehabilitation source was a retired form, and nothing would have noticed

**What was wrong.** `tools/populations.py` read `86cf66ef…` as the single rehabilitation source
and called it “the works form”. That form has been **retired branch by branch**. Every branch
now has a live dedicated successor, and the first-rehabilitation successor `63747997…` **has
never received a response**.

Because zero is a plausible weekly count, the first rehabilitation anyone submitted on the
successor would not have entered the fleet and nothing would have failed.

**Fixed.** Both rehabilitation populations now read three sources, unioned and de-duplicated on
water point: the retired combined form (historical), `63747997…` (current) and the Marolinta
borehole form. `F_COMBINED` is renamed `F_RETIRED_COMBINED` and its rule says what it is.

**The audit found a second one.** The live water-quality forms — sampling `43c96af4…` (735
responses) and results `7b33c5d7…` (736) — were **read by no population, tool or builder**.
`S.wq_tested` was a stored 729 with no generator; the retired form's water-analysis branch
stopped taking records in July 2025. A `water_quality_tested` population now reads the live
results form and reproduces 729 exactly.

Two more successors, identification `198b016d…` and hygiene `283c5670…`, were read by nothing.
Both now have a population, so a migration onto either cannot pass unnoticed.

**The gate.** `tools/populations.py --migration` fails the build if a response arrives on a
successor form that no population reads, or if a successor is declared by no population. It is in
`publish.sh` and negative-tested: injecting one response on `63747997…` fails the build by name.
The provenance table now labels the retired form **RETIRED, superseded by the dedicated
per-branch forms** so a verifier following the link is not left guessing.

**The watch item was wrong about why.** “No first rehabilitation recorded since 1 January
2026” was written up as recording discipline. It is not: the branch was retired, the successor
was deployed to three districts, and it is empty. The instruction to the field teams is **use the
new form**, not *remember to record rehabilitations*. `act-mar-which-form` says that now.

**628 is not reproducible, and 643 was itself a paging artefact.** The retired form holds 431
repair records and the live repair form 214 — 645 naively, 642 with a linked point, 623 since
August 2024, 620 de-duplicated on point and date. None is 628. The 643 in the brief came from a
paged pull that reported 416 where a stable enumeration gives 431. The figure is shown as it
stands with that stated beside it, not forced into a derivation.

**One record appears on both forms** with the same point and the same date — a genuine
double-entry at the migration boundary, and the only one.

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

---

## 2026-09-22 — S.wq_tested was stored, not computed, for fourteen months

**What was found.** `S.wq_tested` — the count of managed points with a water-quality result —
was a literal `729` embedded in the page. No generator wrote it, nothing asserted it, and the
branch it came from stopped taking records in **July 2025**. Both live water-quality forms,
*Water Quality Sampling SDWS 3* (`43c96af4…`) and *Water Quality Testing SDWS 3 Result*
(`7b33c5d7…`), were read by **no population at all**.

**The number was right.** The population `water_quality_tested`, built from the live results form
against the managed fleet, reproduces **729** exactly. No published figure was wrong and no
external correction is needed.

**The risk was that it could never have become wrong-looking.** Had a single water-quality result
arrived — or had one point left the fleet — the page would have gone on reporting 729 and nothing
in the build could have noticed. A figure that cannot move is a figure nobody is checking. It sat
that way from **July 2025 to 22 September 2026**.

**Editions affected.** Every edition in the archive carries the stored value: `2026-09-07-wk36`,
`2026-09-10-wk37`, `2026-09-15-wk38`, `2026-09-16-wk38-ed5`, `-ed6`, `-ed7`, `-ed9`, and
`2026-09-22-wk39-ed1` through `-ed6` — thirteen editions, all reporting 729, all correct.
The archives are not rewritten.

**What followed.** This is the fifth figure of this shape, after `WPOP_C250`, `727`, `723` and
`628`, and all five were found by a person noticing rather than by a check. So the class is now
swept and gated rather than fixed case by case:

* `tools/embedded_fields.py` enumerates every field of every embedded data object — 235 of them.
* Ownership was established **by experiment, not by reading code**: every numeric and free-text
  leaf was perturbed, the whole generator chain run, and a field that came back has a generator.
  115 fields are demonstrably owned, **71 are demonstrably ungenerated**, 49 cannot be decided by
  that method (dates, ids, hashes) and are listed as untestable rather than excused.
* `data/ungenerated_fields.json` records the 69 remaining ungenerated fields, dated and
  **shrink-only**.
* `tools/check_generators.py` fails the build if any embedded field has no generator and is not on
  that list, if the list grows, or if a field declared to come from a population stops equalling it.
  `S.n` and `S.wq_tested` are the first two so declared.

The sweep's own finding is that `S` and `TTR` are the worst of it: 20 of `S`'s fields and **all 13
of `TTR`'s** are computed by nothing.

---

## 2026-09-22 — Seven extracts were outside the build, and the page stated the newest vintage

**What was found.** Seven JSON extracts — `combined_rehab`, `repair`, `wq_results`, `hygiene`,
`identification`, `marolinta_borehole`, `first_rehab_current` — were refreshed by no build step.
`tools/mwater/pull_form.mjs` was invoked by nothing: it existed, it was correct, and no script
called it. **Six of the fourteen populations are built from those files**, so they held whatever
date someone last ran that script by hand.

**Why no gate caught it.** This is the frozen-value fault one level up. The figure gates compare
figures to populations and populations to files, and all three agreed — because they were all
reading the same frozen inputs. Everything passed green while the inputs aged. A gate that checks
internal consistency cannot see an input that has stopped moving.

**What followed.**

* `tools/pull_extract.py` now pulls all seven through `pull_form.mjs`, in 30-day windows,
  de-duplicated on `_id`, and records each in `data/extract_manifest.json` beside the five CSVs.
  Twelve extracts, one manifest, one pull step.
* `tools/check_vintage.py` fails the build if any extract was pulled before the build it is
  feeding. `wp_madavance.csv` is pulled by a separate filtered export — an unfiltered
  `water_point` export walks the whole global mWater entity table — so it carries its own
  14-day limit rather than a silent exemption.
* **The page now states the vintage floor.** The caption led with `extract_newest`, the newest
  source, which claims a currency no single source has. It now leads with the OLDEST pull across
  every extract and names the file that sets it. A form's own last record is a different quantity
  and is reported separately: a quiet form has an old last record and is perfectly current.
* `tools/test_vintage.py` is the negative test — it holds one extract back a week against a copy
  of the manifest and asserts the build fails, names the file, and moves the stated vintage.

**Correction made during the work.** The first version of the check took the vintage floor from
the oldest *last record*, which reported "data to 29 August" because the Marolinta borehole form
had simply been quiet since then. That is the error in the other direction, and it was fixed
before the check was wired in: the floor is the oldest **pull**.

---

## 2026-09-23 — The register joined the build; the carbon money was withdrawn

**The register was the vintage floor.** `wp_madavance.csv` came from a hand-run export because an
*unfiltered* `water_point` export walks the whole global mWater entity table. Filtered to the
managed group it is **one bounded query returning 908 rows in 1.7 seconds** — so the reason it sat
outside the build never applied to the filtered form of the query. While it sat outside, every
population rested on an eleven-day-old file: a pump rehabilitated last week was not in the fleet,
and the page said 736 with confidence.

`tools/mwater/pull_entities.mjs` now pulls it, walking 90-day `_created_on` windows and
de-duplicating on `_id`, and refuses to write if the windowed walk and a single bounded query
disagree. **The vintage floor is now the build's own day and the spread across all 13 extracts is
zero.** The 14-day allowance in `check_vintage.py` is gone; nothing carries a longer one.

**The carbon monetary framing is withdrawn.** Every tonnage and cash figure in the gardien-calendar
section — the 2025 and 2026 emission reductions, the USD sizing at 20/t, the evidenced-versus-
unevidenced split, the two-year exposure — was computed from the SDWS 27 per-year quantification,
whose basis does not exist in this repository. **They were unreproducible, not wrong**: no error was
found in any of them and none is corrected. They return when `act-carbon-year-basis` rebuilds the
basis, which restores the whole framing at once. Logged as `carbon_money`.

**The section now states the same risk in points and days, both of which derive:** 434 of 731 active
carbon points have no readable dated 2026 sheet, each resting on the registered 347 days with
nothing on file to demonstrate it — and 347 is a ceiling a manual log may not exceed, so evidence
can only ever confirm the registered figure, never raise it.

**A correction to the count I reported.** I told Adriaan 29 figures would be withdrawn. That number
was wrong: it came from a classifier that swept in a CSS `font-size:1.45rem`, a form `_rev` of 391,
a question count of 750, water-point id fragments, and derivable counts like the 415 point-years
and the 2,348 calendar photographs. **The real withdrawal is 20**, and the derivable counts stay.
Withdrawing them would have removed true, reproducible facts.

**TTR is unfrozen.** `tools/rebuild_ttr.py` computes the eight `ttr_*` fields from
`repairs_time_measured`. The median of 1.0 days, the mean of 3.6 and the 7-day share of 91% all
reproduce exactly; `ttr_n` moves 606 → 617 and the site and year splits move with it, off the
basis that reproduced from no rule. **The five `call_*` fields are NOT computed**: no filter on the
call-centre extract reproduces their 122 / 90 / 32, and inventing one to make them fit is the
fault this whole exercise exists to stop. They stay on the backlog, named.

**Group A is wired.** `tools/rebuild_summary.py` recomputes `S.by_site`, `S.by_pump`,
`S.down_list`, `S.wq_untested`, the two duplicated `METRICS` fields, and the register columns on
`PUMPS` and `DOWN`. The site column needed care: the page's `site` is SaniTap's operational
grouping and is **not** a register column — the register calls Fort-Dauphin's district Taolagnaro.
The 1:1 mapping is declared explicitly and an unknown district fails the build, because inferring
it would have silently renamed 127 points.

**The ungenerated backlog is 69 → 43.** Nine parameters are declared in `PARAMS` with citations,
and the figure residue is 93 → 75.

---

## 2026-09-23 — The sourcing work is closed

**What it changed.** Five published figures — `WPOP_C250`, 727, 723, 628 and `S.wq_tested` — were
values computed once and frozen, and every one was found by a person noticing. That is now a class
the build catches rather than five accidents:

* **Every embedded field is accounted for.** 236 fields, each resolving to a generator, a
  population, or a dated shrink-only backlog. `check_generators.py` fails the build on anything
  else, on a backlog that grows, or on a population-backed field that stops matching its
  population.
* **Every extract is pulled by the build and carries its pull date.** Thirteen of them, including
  the register, which was outside the pipeline and set an eleven-day vintage floor. The page states
  the OLDEST pull, never the newest.
* **A failed pull can no longer look like an empty month.** `call()` returned `[]` for any failure;
  two pulls of the call-centre form minutes apart returned 2,747 and 2,826 rows because of it.
* **Withdrawn figures stay withdrawn.** The consistency checks that asserted the carbon tonnages
  were present now assert they stay absent.

**What remains, and it is meant to remain.**

* **Ungenerated fields: 37.** Five `call_*` fields that reproduce from no rule anyone has found —
  and no rule was invented to make them fit, which is the whole point; the rest of `S`, `OPENREP`,
  `WPOP`, and the genuinely hand-maintained `CORR` and the two `WPOPMETA` description fields.
* **Figure residue: 73.** 58 derivable, 13 deferred by decision, 2 explanatory references to
  withdrawn figures. The 13 are the people-served figures: capturing them is a change to what
  `sdws1_population.py` *emits*, not to the model — about half a day — and on 2026-09-23 that was
  judged not worth it for 14 prose figures. The decision is recorded per figure so it is not
  re-taken by accident.

**A correction worth keeping.** I reported 29 figures for withdrawal. Thirteen of them were not
carbon money at all: four census false positives (a CSS `font-size`, a form `_rev`, a question
count, an identifier fragment), two quoted from the Gold Standard monitoring report, six derivable
counts, and `20,827`, which is a live product of a population and two quoted per-point values.
**The real withdrawal was 20.** Withdrawing the other thirteen would have deleted true,
reproducible facts. The lesson is the one the whole exercise keeps teaching: a classifier that
matches on value alone is not evidence, and the figures have to be read in context before anything
is removed.

**The rule from here: a figure gains a source when someone next touches its section, not in a
dedicated sweep.** Both backlogs are shrink-only and gated, so they cannot quietly grow and cannot
become permanent exemption lists. Neither needs another campaign. The sweep found what a sweep can
find; what is left is work that belongs to whoever next edits the prose around it.

---

## 2026-09-23 — The carbon section moved to the right side of the line

**The scope correction.** This report tracks what the field operation must measure and whether it
is measuring it. It does not run the carbon programme: methodology interpretation, the design
review, the VPA-DD and the Gold Standard relationship are the Head of Carbon's. Where the two meet
there is one question — **can we supply the data the carbon programme needs, and if not what is
missing and who owns it** — and that is now the only carbon question this report answers.

**What replaced it.** *Data the carbon programme needs from us*: one row per parameter we must
evidence, from `data/carbon_parameters.json`. Coverage is derived from the named population over
the named relevant population; freshness from the extract manifest; **readiness falls out of both
rather than being asserted**, so a row cannot read Ready while its evidence says otherwise. The
rows filter by readiness, so "what are we not ready on" is one press rather than a read.

**What came out.** The design review section entirely — round state, Request Clarification,
CAR#1, #4, #5, #7(b), #8 and CL#2 — and the JavaScript status deck behind the old *Carbon file*
section. Four action items that were pure review-chasing went with it. **Two were kept and
restated without the review framing**, because the deliverable underneath is ours: the
installation database of households per borehole, and the SDWS 3 record correction plus the
parallel validation round.

**The version map split the same way.** Six divergences alter what the field must collect or
record and stay: the minimum sample size moving 30 → 50, mandatory confidence intervals, the
end-user non-claiming assertion, embodied emissions under SDWS 21/41, the annual stove-stacking
survey, and the stroke-count proxy under SDWS 28. Eight were interpretation and moved to the Head
of Carbon, named on the page so a reader knows where they went.

**Built to take additions.** A new requirement is a row in `data/carbon_parameters.json` — id,
plain-language measure, form, population, owner, action. Nothing else changes. The consistency
checker asserts every row names populations that exist and an owner, so a row cannot be added with
a typed coverage figure or with no one accountable for the gap.

**One thing I could not do.** `claude/sdws-parameter-map-what-must-be-evidenced.md` is in the
Claude Project and is not readable from the build machine — Claude Code sees only the local
filesystem. The **row set** is therefore reconstructed from `docs/methodology_version_map.md`,
`docs/sdws27_basis.md` and the live form snapshot, and is marked provisional in the data file and
on the page. Every row's **evidence** is derived and is not provisional. Reconciling the row set
against that map is a five-minute job for whoever can open it.

---

## 2026-09-23 — The SDWS 26 instrument already existed; no form was built

**Step 1 stopped the build, which is what it was for.** Every mWater form reachable to us was
enumerated — paged in full, and the paged and unpaged sets agree exactly, so the enumeration is
complete — and every design searched for a question asking frequency of use of the project water
point.

**It is already there.** `db0bcbf2e7ea44b280aed653a715553e`, *Clean Water || project SDWS18*,
revision 118, **state active with three active deployments** (Maroantsetra, Fort-Dauphin,
Moramanga), carries:

* **A9** — *"In the past year, how often did this household take drinking water from this water
  point?"*, whose own hint reads *"Parameter SDWS 26 — only premises reporting use at least every
  two days may be counted as served"*. Its choices are **exactly** the specification: Every day /
  At least every two days / Two or three times a week / About once a week / Less often / Never.
  The every-two-days threshold evaluates without interpretation.
* **A10** — people per premises, SDWS 25.
* Consent, GPS, the water-point link and photographs, on the house conventions.
* **All three languages on all 100 questions**, so the Malagasy translation task the goal
  anticipated is not needed for this instrument.

A second instrument asks the same thing differently: `2eeb8682`, *Clean Water || Project
Cbn&Gender*, questions WS1.18 and WS1.39, with day-by-day choices (Every 2 days / Every 3 days / …).
Two live forms asking one parameter two ways is worth a decision before round one.

**What the instrument does not carry**, against the VPA-DD commitment (B.7.1, B.7.3): SDWS 22
boiling, the JMP core questions for drinking water and hygiene (SDWS 20), the enumerator's
identity, and the household-versus-institution distinction with a population figure for
institutions. **Each is an addition to a live form, not a new survey** — which is why building a
parallel instrument would have been the wrong move even before the duplicate question was found.

**What was built instead.** `tools/draw_usage_sample.py` draws the sample to the VPA-DD design
(B.7.2) — 90% confidence, 10% margin of error, ≥100 households and ≥8 clusters per scenario, Anosy
and Maroantsetra separate — recording the seed, the extract date and the register checksum so it
redraws identically. It does; a different seed gives a different draw, and the floors cannot be
argued below. **Five managed points in Androy fall in neither named scenario** and are reported
for a decision rather than assigned: they are the Marolinta boreholes, outside the carbon fleet.

Maroantsetra is tight: **9 communes exist and 8 are required**, so the cluster draw there is close
to a census of communes. That is a fact about the design meeting the estate, and it should be said
before the round rather than discovered during it.

`tools/export_form_review.py` writes the review copy at
`docs/review/sdws26_usage_instrument_db0bcbf2.md` — every question in all three languages, choices,
skip logic in plain words, and the parameter each question serves **where the form itself states
it**, never inferred.

---

## 2026-09-23 — SDWS 26 was already measured, from the November 2025 round

**The parameter has an answer, and it did before any new instrument was proposed.** The annual
monitoring survey (`2eeb8682`, *Clean Water || Project Cbn&Gender*) asks how often a household
draws drinking water from the project water point, once for the dry season (WS1.18) and once for
the rainy (WS1.39). It was run **11–21 November 2025**, and 410 responses answered both.

**Served is matched by choice id, never by position.** The declared scale is *not* monotonic —
*"More than 1 time per day"* sits **second**, after *"Every day"* — so anything mapping it by
position is wrong. The served set is the three ids meaning every day, more than once a day, and
every two days.

**The result is 99.5% of premises served** on the conservative reading, and **the seasonal rule
does not move it**: served-in-both and served-in-either differ by **one record out of 410**. The
choice of rule was the open question; it turns out not to matter, and that is worth knowing before
anyone spends time settling it.

**The denominator excludes four responses as a stated rule.** They answered neither usage question,
and between 2 and 21 of the form's 92 questions — abandoned part-entries, three of them marked
final on questions the form declares required. Counting a part-entry as a non-response understates
the proportion; counting it as served overstates it. Neither is honest, so they are excluded and
the exclusion is written into the population's rule rather than applied silently.

**The limits are rendered from the same data as the result**, because they are what a verifier will
test: the round evidences **2025 only** and cannot be carried into 2026; **Maroantsetra reached 6
village or commune clusters against the VPA-DD B.7.3 minimum of 8** while Fort-Dauphin met it at 8;
and **not one of the 414 responses carries an approval**.

**SDWS 25 in passing:** mean household size in this round is 4.47 in Fort-Dauphin and 3.66 in
Maroantsetra, which still round to the registered 4.5 and 3.7. Derived from the same round,
question WS1.12; the registered values are untouched.

**Two actions were closed, not deleted.** `act-run-sdws-26-premises` rested on the premise that the
parameter had no field instrument and no data until a new round ran — both false. `act-sdws26-
instrument-review` was scoped to sign an instrument off *before* round one, and round one had
already happened, on a different form. Both are recorded in `data/decisions.json` with the reason
and the date, so the audit trail shows why they went rather than showing a gap. Their substance —
which form is the standing instrument, and whether it must also carry SDWS 22, the JMP core
questions, the enumerator's identity and the household-versus-institution split — is carried into
the replacement.

**Replaced by two.** `act-sdws26-annual-round`, recurring annually with Angelo owning it and the
condition that Maroantsetra must draw at least 8 clusters; and `act-sdws26-approve-2025`, because
an unapproved response is weaker evidence in front of a VVB than an approved one, and approving
them is a review the team can do now rather than during a verification.

**What was deliberately not built:** the sample-size calculator and the draw publication. At 99.5%
the precision question is not live, and the next round is months away.


## 23 September 2026 — the 44-pump comparison removed from the page

The block headed *"Open issue — 44 pumps reported down that read as fully
operational"* and the matching passage in `act-transcription-round` are
removed. Their premise, 44 points whose latest call-centre answer says the pump
is down with no repair since, cannot be rebuilt from any extract: a stable
enumeration with the call and repair mappings of `tools/build_call_tables.py`
gives 26 to 33 points, at cut-offs of 20, 21 and 23 September. The comparison
that followed (353.0 against 353.4 days, reduced on 23 September to "read like
the rest of the fleet") rests on that list, and so do the two readings built on
it: stale tickets, or gardiens not marking outage days. None of it is shown until the
list is derivable; `tools/check_consistency.py` keeps it off the page. The
transcription round stands on its own purpose, measuring the reader's accuracy.


## 23 September 2026 — the report covers the actively managed portfolio only

**Decided by Adriaan Mol.** The report covers only water points that are
actively managed: maintained by us and serving people. Records that merely sit
in the MadAvance mWater group - abandoned points, survey and identification
records, points handed on, rope pumps, anything not in the maintained fleet -
are not the portfolio and are not on the page.

**Removed from the page:** every statement of the whole group's record count
(then 909): the *"Why the scope figure is 867 while the mWater register record
count still reads 909"* block, the register tile and its derivation, the
register count in the evidence-trail table, the sampling-frame and
cookstove-overlap sentences that started from it, the scope-line sentence,
the *"What the register holds beyond the portfolio"* paragraph, the two
register rows of the definitions table and the two chain steps that relate a
population to the whole group, and `act-read-district-commune-water`, which
counted unclassified group records (119). `REG.register_total`,
`register_classified`, `register_unclassified` and `missing_from_register`
are gone from the page's data.

**Kept:** every maintained pump whatever its state. A pump reported down is in
the portfolio, in "reported down" and in downtime. The retired-points and
reconciliation tables stay, because each includes maintained pumps. Marolinta's
points are maintained, so they stay in the portfolio and its scope, and stay out
of every carbon figure.

**Inside the build, silently:** `tools/classify_register.py` classifies every
group record each week. A record with a successful first rehabilitation that
is not excluded, has a district that maps to a site, a coordinate and a pump
model joins PUMPS on its own. Anything it cannot place is written to
`logs/publisher.log` for review and nowhere else. On the day of the decision
one record was logged: `742894057`, with a successful first rehabilitation and
newly in the group, but its register name, *"IndiaMark- changée en canzee"*, is
not a pump model. Set the name in mWater and it joins on the next build.

**Enforced:** `tools/render_check.py` fails the build if the current group
count appears anywhere in the rendered text, on any scope.

## 23 September 2026 — 742894057 named Canzee in mWater; the first pump to join automatically

Water point `742894057` (`_id 5d185c0f-7bf6-495b-9a7f-b4e0f85a7e82`) carried the
name *"IndiaMark- changée en canzee"*, set 27 October 2025: the India Mark was
replaced by a Canzee. Its name was set to **Canzee** and its description to
*"Pompe à main — India Mark remplacée par une Canzee (nom corrigé le
2026-09-23)"*, so the history stays on the record. `_rev` 7 → 8, verified by
re-reading, no other field changed; before and after are in
`data/mwater_backups/` and the write is logged in `data/register_write_log.json`.
Requested by Adriaan Mol.

On the next build `tools/classify_register.py` joined it to the portfolio: a
successful first rehabilitation (April 2024), not excluded, Fort-Dauphin, a
coordinate and now a pump model. The managed fleet went 736 → 737 and the carbon
fleet 731 → 732. The join is recorded in `data/register_classification.json`
(`joined`), which the fleet-churn check reads as its explanation. It is a record
correction, not new work, and the page says so. It has no WorldPop allocation
until the population run is repeated (`act-population-rerun`), and its
roof-count and water-quality columns are among the page columns no generator
fills yet, so it shows as untested on the page though the extract holds a result.

## 23 September 2026 — a joining pump gets its per-pump inputs in the same build

742894057 joined with a blank WorldPop allocation, water-quality result and roof
count, because those values were written once and never recomputed. Fort-Dauphin's
people per pump fell 323 → 320 and the pump read as untested although mWater held
a passing result. Now, every build:

- `tools/rebuild_pump_inputs.py` recomputes the water-quality result (the latest
  SDWS 3 result, Pass when E. coli is 0) and the roof count (roofs ÷ 2.5 × 4.5
  from the roof-count form, now pulled as `roof_count.json`) for every portfolio
  pump, and sets `wq_status` tested / not tested on every row. The rules
  reproduced 729 of 729 and 724 of 724 stored values before replacing them.
- `tools/rerun_wpop.py` reruns the SDWS 1 allocation when a pump joins or
  leaves, on the run of record's own inputs plus the change. Every pump more
  than 2 km from a change must reproduce exactly, or the build fails. Reusing the
  run's inputs matters: rerunning on the page's re-rounded coordinates (about
  0.1 m) alone moved 90 capped allocations. If the raster, its checksum or the
  SDWS1 workspace is unavailable, the build fails with an OUTCOME sentence.
- `tools/render_portfolio.py` keeps the map page's figures and marker list in
  step with the report.
- `tools/check_consistency.py` fails if any portfolio pump lacks an allocation
  or a water-quality status.

Result for 742894057: 529 allocated, 500 after the Canzee cap; roof count 106;
E. coli Pass on 25 April 2025. Three neighbours within 2 km shared cells with it
(742894071 973 → 602, 742894181 1,264 → 1,116, 742894552 432 → 429 allocated),
all India Marks at their 300 cap before and after. People served 128,221 →
128,721 (carbon portfolio 126,780 → 127,280); run `r2025a_barriers_20260923`.

## 23 September 2026 — James Walker's rulings: SDWS 26 seasonal rule and scale mapping; a piped usage survey

**From:** James Walker, Carbon Lead · **Sent:** 23 September 2026, 14:48 UTC ·
**Subject:** "Re: Water program dashboard & actions" · a reply to Adriaan Mol's two questions of
the same morning, plus the piped-systems point.

1. **Seasonal rule.** *"We could average or lower of the two. Let's average it to prevent
   unnecessarily losing credits."* The SDWS 26 served share is the **average** of the dry-season
   (WS1.18) and rainy-season (WS1.39) served shares, over the premises that answered both. It is
   no longer the both-seasons reading this report headlined on 23 September.
2. **Scale mapping.** *"Correct."* Served = *Every day*, *More than 1 time per day*, *Every 2 days*,
   matched by choice id (`J1qZUqA`, `6wqmK16`, `h4uZZBz`). Confirmed, not provisional.
3. **Piped systems.** *"We will do the annual survey for the piped systems, and it will be a
   separate project to the hand pumps. We are obliged to ask the JMP questions, HH size, usage,
   SDGs etc."* and *"do not need to do so for some time (within 1 year of start date)"*. This
   overturns the assumption in Adriaan's email that metered systems would not need the survey.

**Applied to the report:**

- `#sdws26` headlines the seasonal average, per scenario and across both scenarios (pooled), live
  from new `SDWS26` fields `served_dry` and `served_rain` (`tools/rebuild_sdws26.py`) and new
  populations `usage_served_dry_season` and `usage_served_rainy_season`. On the November 2025 round:
  Fort-Dauphin 99.5%, Maroantsetra 99.8%, both scenarios 99.6% (was 99.5% on the both-seasons
  reading).
- The both-seasons and either-season readings survive **only in the derivation panel** under each
  average, as a sensitivity. Their populations are now build-internal, so they are not a figure or
  a definitions row.
- The section's "How this is worked out" footnote states the rule, the served set and this email as
  the source. `act-sdws26-annual-round` no longer calls the rule "settled in practice".
- New action `act-piped-usage-survey`, owner James Walker, due within one year of the piped
  programme's start date (not yet fixed; the piped VPA-DD is not registered).
  `act-mor-households-people-served-per` no longer says smart taps answer SDWS 26 directly.

## 23 September 2026 — James Walker's ruling: days operational on multi-outlet sites

**From:** James Walker, Carbon Lead · **Sent:** 23 September 2026, 13:57 UTC ·
**Subject:** "Re: Days operational: we are applying a hand-pump rule to multi-tap sites"

- *"Uptime / functionality is at a per system level."* Days operational on piped systems and kiosks
  is assessed per system, not per tap or device.
- Distance basis: *"1km. Easier to define radius on a map and less subjective."* Outlets within
  1 km of one another form one service unit. Declared on the page as the parameter
  `service_unit_radius_km`, citing this email.
- *"equation 4 takes the minimum of Qpop … and Qm … I imagine Qm will generally be smaller"*. On
  metered sites the metered volume is expected to be the binding term in Q_y = min(Q_m, Q_pop).
- The piped VPA-DD is not yet registered, so the method is ours to define and need not be fixed
  until verification. **Hand pumps are unchanged.**

**Applied to the report:** the smart-meter panel, `act-enduro-move-register-fully` and the Endur'O
indicator row now state the per-system rule, the 1 km service unit and the binding metered term.

## 23 September 2026 — James Walker's ruling: the Moramanga baseline

**From:** James Walker, Carbon Lead · **Sent:** 23 September 2026, 08:44 UTC ·
**Subject:** "Re: Moramanga carbon baseline: 331 households, and the boiling numbers"

- *"The meth does not measure baseline fuel consumption. It works out the ERs based on the
  theoretical amount of energy required to boil 1 litre of water for 5 mins based on the efficiency
  of the cooking device."* Baseline fuel quantity does not need to be measured.
- *"the presence of actually boiling does not increase the value of the credits"*. An
  actual-boiling baseline does not raise credit value.

**Applied to the report:** nothing had to change. The page carries no action or open question on
measuring baseline fuel quantity, and nowhere says an actual-boiling baseline raises credit value.
Both points were raised only in email. Checked on 25 September 2026.

Re-checked on 25 September 2026 against the repository, every archived edition, git history and the
live page: no published text ever referred to form `3ef4385a619244c7ad129169ac1ec71f` ("Piped Water
|| Baseline Cbn"), called actual boiling a stronger baseline or "the core of the emission reduction
case", or carried an action on Moramanga fuel quantity. Nothing to remove and no action to close.
The ruling is now stated on the page as the collapsed footnote `piped-baseline-ruling` in the
Endur'O smart-meter panel, quoted from the email (QUOTES `jw_2026_09_23_moramanga_baseline`). The
boiling and stove counts from the survey are not on the page: the build does not pull that form.

## 25 September 2026 — Adriaan Mol: when a piped system joins the managed portfolio

**From:** Adriaan Mol, COO SaniTap · 25 September 2026.

- The 43 results on the piped SDWS 3 result form (`0ac68d82`) for Amboasary gara, March to
  August 2026, are **pre-project baseline** tests: they establish the starting situation so the
  system qualifies for the carbon work. Works are not complete and post-rehabilitation tests have
  not happened.
- The four Deichmann-funded Moramanga piped systems are therefore **in process**, not part of the
  managed portfolio.
- **Rule:** a piped system joins the managed portfolio only when its rehabilitation works are
  complete **and** its post-rehabilitation water-quality tests are done.

**Applied to the report:** `data/piped_systems_status.json` gives every Endur'O water system a
status. The four Moramanga systems were identified from mWater, not assumed: the Moramanga carbon
baseline survey (`3ef4385a`, 331 households) and the Moramanga piped water-point identification
(`a34cb66b`) both name exactly 1108783583 Amboasary gara, 1108783624 Ambohibola, 1108783648
Amboanjo and 1108783662 Andilanatoby. mWater records no funder for any of them (the donor form
`8c9f8dc1` has no Moramanga entry; the one system registration is the Antananarivo kiosk), so
"Deichmann-funded" rests on this ruling. The other 21 systems are not managed; 17 of those statuses
are inferred (duplicates or sub-records near the four, or Antananarivo records named "Amboasary
gara") and marked `confirmed: false` for Endur'O to confirm. `tools/rebuild_piped_wq.py` applies
the rule by date: a result after a recorded works-completion date is post-rehabilitation and
counts; one on or before it is baseline and never counts. The build fails on any Endur'O system
missing from the status file. The earlier 30 km-from-Antananarivo proxy is withdrawn.

## 25 September 2026 — Adriaan Mol: the first Antananarivo smart-tap kiosk joins the managed portfolio

**From:** Adriaan Mol, COO SaniTap · 25 September 2026.

- The first Antananarivo smart-tap kiosk is in the managed portfolio. It is operational with
  SaniTap/Curtech meters and its data is in Zoho.
- The join rule for piped systems (works complete AND post-rehabilitation water-quality test)
  stays; this kiosk is admitted by decision.

**Applied to the report:** the kiosk was identified from mWater, not assumed: water system
1125843376 "Kiosk" (Endur'O group; -18.89313, 47.47879; Antsahakely, Fiombonana, Antananarivo
Avaradrano), registered on the Endur'O System form (44044e27, response b0b01aa0) with one
Distribution Point (8a3af50c, response 840ae830): water point 1125843383 "SmarTap", a public tap
stand in a built kiosk, one outlet fitted with a smart tap, installed 7 Sep 2026, commissioned
14 Sep 2026. Both registrations are still drafts. In `data/piped_systems_status.json` it is
`managed` with `admitted_by_decision`, operational from 14 September 2026 (the commissioning date
on the registration). The first real dispense in Zoho could not be read: the Curtech endpoints are
not reachable from this build. No water-quality test is on record for the kiosk; that is an
onboarding step. Every statement that the Antananarivo kiosks are "not under management" was
reworded: only Antananarivo sites not yet onboarded are outside.

The umbrella action act-enduro-move-register-fully became a parent of seven onboarding steps,
each with an owner, a date and a condition the build evaluates; the parent closes only when all
have (condition kind `children`). act-enduro-feed ("Obtain a feed or scheduled export from
Endur'O for the smart-meter figures") was merged into the dispensing-events step, keeping its id.
The enumerator-team step was already done: the team Enduro › EndurO Tana › Enumerators has three
members and is the enumerator group on both registration forms.

## 18, 21 and 23 September 2026 — James Walker's written replies, applied 26 September 2026

**From:** James Walker, Carbon Lead · email thread "Re: Water program dashboard & actions",
replies of 18 Sep (09:45 UTC), 21 Sep (09:22 UTC) and 23 Sep (14:48 UTC). Each answer is recorded
per action in `data/action_owners.json` (`sources`) and in the action's collapsed detail.

- **fNRB, Maroantsetra** (21 Sep): *"It should be 36, so it is inline with what we have applied for
  FD (sub national rather than commune). I will update that in the verification as a 'correction'."*
  Registered 34% (VPA-DD SDWS 21, p.76) stays shown; 36% is applied. Every figure built on it is
  recomputed from the registered EF_b inputs (VPA-DD pp.78-80): at 34% Equation 1 reproduces the
  registered 0.00018 tCO2e/L; at 36% it gives 0.000189, and the per-CWS ER moves from 27.9 to 29.2.
- **Version** (21 Sep): v2.0 from 1 Jan 2026 with some grandfathering; alignment at the verification
  submission (Q1 2027), full alignment at renewal; v2.0 to be tried for 2025 via the design-change pathway.
- **Sampling** (21 Sep): 50 per stratum, to be safe. **Days operational** (21 Sep): capped at 347
  without a sensor; actual days only for sensor pumps (50 per stratum), cap on the rest; a lost or
  damaged calendar is acceptable given the SOP, visits and call log; "premises p" should read
  "CWS / CWT p". **Contracts** (21 Sep): "we are fine here". **Embodied emissions** (21 Sep): accounted
  for at verification. **Machine reading** (21 Sep): fine, with a spot check.
- **Stove adjustment** (18 Sep): ex post figures adjusted by the ICS share from the annual
  monitoring; Fort-Dauphin 2025: 81%. **Stacking** (18 Sep): Impact Statements only, not credits.
  **TOOL30** (18 Sep): James corrects it on the hub. **Stroke test** (18, 21 Sep): SDWS 28 is the
  published ID and the 5-minute test the standard one; the quarterly validation is expected to be
  withdrawn by Gold Standard. **Piped fNRB** (18 Sep): national 36% proposed, rather than Tana 26%.

**Applied:** 7 actions closed on these answers (act-v2-nonclaiming converted from a data condition
to the ruling); act-put-current-methodology-vpa and act-update-sops-portfolio-figures closed on files
filed in the Central Data Hub; 7 annotated and kept open; 4 added; the ICS reporting item merged
into act-re-run-improved-cookstove. The India Mark question of 26 Sep is a **draft**, not yet sent.
SOPs: calendar v1.7 and stroke-test v2.1 (French and English), each beside its original. The VPA-DD
was copied into Methodology of record with its SHA-256, and that folder's README rewritten, on
Adriaan Mol's instruction (it had deliberately held no VPA-DD).

## 26 September 2026 — Adriaan Mol: sign-off of the new SOP versions; the Curtech briefing is still a draft

- **Calendar SOP v1.7** gets its own sign-off action, `act-sop-calendar-v17-signoff` (Angelo Nahavitatsara /
  MadAvance, proposed 10 Oct 2026): approve v1.7, brief every field team in French on the changes (347-day
  cap, sensor pumps only above it, lost-calendar handling, photograph before replacing), then retire v1.6.
  Evidence: the signed v1.7 filed in SOPs and a dated briefing note. No existing action was equivalent:
  `act-adopt-consolidated-gardien-calendar` closed on 21 Sep on v1.5, and `act-calendar-custody` issues
  one rule of the briefing, not the SOP.
- **Stroke-test SOP v2.1** sign-off (proposed id `act-sop-stroke-test-v21-signoff`) is merged into
  `act-move-stroke-test-sop`: same owner (Jan), same date (31 Oct 2026), same ask. It now covers v2.1 in
  French and English, moving the French version from Work in Progress to SOPs, and retiring v2.0. Its
  condition changes from a file matching "StrokeTest" in SOPs to a logged decision, because moving an
  unsigned file would have closed it.
- **`act-sensor-sample` stays open.** The email "StrokeMeter: how many units, and how many for
  calibration" to ralf@curtech.nl is in Drafts (isDraft true, 26 Sep 2026 05:59 UTC), not Sent Items.
  Noted as "briefing drafted 26 Sep, awaiting send"; it closes, citing that email, once sent.

## 26 September 2026 — Adriaan Mol: the calibration sample is 50 pump calibrations a year, not 50 per stratum

The StrokeMeter calibration sample of 50 is **50 pump calibrations a year**: each a timed 5-minute discharge
test (SDWS 28) against the meter installed on the pump, carried out with a small set of **about 5 portable
calibration pods** (one of them a spare) moved from pump to pump. It is separate from the **at least 100
permanently installed stroke meters** (50 per stratum, James Walker 21 Sep). Declared as `calib_pumps_per_year`
and `calib_pods` in the page parameters.

- Stroke-test SOP v2.1, French (`Work in Progress/SOP_SDWS27_StrokeTest_v2.1_Revise_2026.docx`) and English
  (`SOPs/COP_STROKE TEST — STROKE COUNTING FLOW TEST v2.1.docx`), edited in place as unsigned drafts: the
  revision note read "30 to 50 pumps per stratum" and chapter 10's calibration sample size read "at least 50
  pumps per stratum"; both now say 50 pump calibrations a year, with the pods and the separation from the
  installed meters. A change-log line was added under each revision note. The English chapter 10 calibration
  frequency still read "at least 1 time per quarter" and is corrected to annual re-verification, as the French
  text and the revision note already said.
- On the page: `act-sensor-sample`, the stroke-test open question on quarterly calibration, and
  `act-resolve-sdws-27-sdws` say the same.

## 28 September 2026 — James Walker, 21 Sep 2026: the SDWS 27 / SDWS 28 numbering and the calibration requirement

Source: James Walker, Carbon Lead, email "Re: Water program dashboard & actions", 21 September 2026.
Logged in `data/decisions.json` on Adriaan Mol's instruction.

- **Numbering.** *"27 was the parameter ID in the consultation version, 28 is the published. So 28 is
  correct."* The v2.0 stroke-test parameter is SDWS 28 (Option 3). v1.0 SDWS 27, days operational, is a
  different parameter and is untouched.
- **Calibration.** *"I believe they are removing the validation requirement all together, but this won't
  be confirmed until later this year"* and *"Apparently this will published in error and they will update
  later this year."* The quarterly validation attaches to the Option 3 proxy only; the StrokeMeter annual
  re-verification stands.
- **Applied:** `act-resolve-sdws-27-sdws` closes on the logged decision (status computed OK; the row is
  kept, not deleted). Gold Standard's confirmation is not yet in writing, so
  `act-gs-validation-withdrawal-watch` (James Walker, proposed 31 Dec 2026, evidence) stays open until
  Gold Standard publishes a correction or answers in writing.
- **Stroke-test SOP v2.2** (French and English), unsigned drafts, each beside its v2.1: cites SDWS 28
  Option 3 where v2.1 cited SDWS 27 Option 3, with a change-log line giving both points above. The
  document reference `SOP-MAD-SDWS27-StrokeTest` and the file-name pattern are kept, as identifiers.
  v2.0 and v2.1 are unchanged.
- **Stays open, noted:** `act-v2-confidence-intervals` — James's 21 Sep reply gave the sample size only
  ("50 in each to be safe"), not the confidence-interval instruction. `act-enduro-onboard-5-calibration` —
  Ralf van Veenendaal's 22 Sep reply ("RE: Zoho endpoint: works, and what else we need alongside it")
  covers device identity (EEPROM id), not calibration; no certificate.
- **Added:** `act-mwater-backup-restore-check` (Adriaan Mol, proposed 2 Oct 2026, manual): identify by id
  and revision the form Lanja restored from backup (mWater support replies of 26 and 27 Sep, the
  "Fer > 0.2 mg/l" calculation) and confirm that the later edits are present: the Malagasy locale on
  Entretien préventif, and the SDWS 3 operating-status question if it had already been added.

## 28 September 2026 — Adriaan Mol: the owner workbook is retired; `data/action_owners.json` is the record

Recorded in the words given (it had not been written down before):

> Adriaan Mol, 28 Sep 2026 (confirming a verbal decision of 26 Sep 2026): data/action_owners.json
> 'owners' is the source of record for action owners and deadlines, edited only in the repo. The
> SharePoint workbook 'Water report - action owners and deadlines.xlsx' is retired; it was last read
> on 21 Sep and last modified on 22 Sep. The build no longer reads it.

- **Applied.** `tools/render_actions.py` reads owners from the record and refuses to render without
  it. The ten-day staleness notice and the publisher.log line asking for rows to be deleted from the
  shared workbook are gone. The workbook's location moved to `retired_source` in
  `data/action_owners.json`. Its one row naming no action on the page,
  `act-read-district-commune-water`, is listed under `orphan_rows` (dated, shrink-only) and not
  removed: that is Adriaan's call. The workbook itself was neither edited nor deleted.
- **Checks.** The eleven workbook checks in `tools/check_consistency.py` block 7bb were replaced
  one for one by assertions on the record (list in the commit message). The boundary is unchanged:
  status and closure are computed, never set by hand.
- **Archived and renamed, 28 Sep 2026.** The workbook was moved to `Water Documents/Archive` and renamed
  "RETIRED 2026-09-28 - Water report - action owners and deadlines (see decision_log.md).xlsx" (item id
  unchanged, 01LKVHFNETFSNHGAJ2X5D27LFSAVL72ZF5); `retired_source` in `data/action_owners.json` carries the
  new name, folder and link.
- **Differences not applied.** Before retiring it, the SharePoint copy was compared with
  `owners`. Owner differences on `act-adopt-consolidated-gardien-calendar` and `act-calendar-v13`,
  and four rows for the §4.15/§4.16 CAR items that are not actions on the page, were reported for
  decision. The record was not changed to match.

## 28 September 2026 — Adriaan Mol: the stroke-test SOP actions after v2.2

- **`act-move-stroke-test-sop`** now asks for the **v2.2** drafts to be signed:
  `Work in Progress/SOP_SDWS27_StrokeTest_v2.2_Revise_2026.docx` (French) and
  `SOPs/COP_STROKE TEST — STROKE COUNTING FLOW TEST v2.2.docx` (English). v2.1 is superseded and is
  retired together with v2.0 on sign-off. Its logged-decision condition now names v2.2.
- **`act-v2-stroke-test` merged into it.** The reconciliation with methodology v2.0 is done in the
  v2.2 drafts (SDWS 28 / Option 3, 50 calibrations a year, annual re-verification, the 5-minute
  test). The item keeps its id and row and becomes a child of `act-move-stroke-test-sop` (condition
  kind `children`), so it closes when the signed v2.2 is logged there and not before. Owner and
  proposed date aligned to that item: Jan, 31 Oct 2026 (were James Walker, 10 Oct 2026). The merge
  is recorded under `merges` in `data/decisions.json`; a merge closes nothing on its own.
- **Both v2.1 files**, unsigned drafts, edited in place: a change-log line "superseded by v2.2"
  under the v2.1 notes. Their content is otherwise unchanged.

## 28 September 2026 — Adriaan Mol, 28 Sep 2026, workbook reconciliation

The differences found between the retired SharePoint workbook and `data/action_owners.json`, settled:

- **`act-adopt-consolidated-gardien-calendar`**: owner Jan → **Angelo Nahavitatsara / MadAvance**
  (as the workbook had it). Deadline unchanged, 31 Oct 2026.
- **`act-calendar-v13`**: no change. The instruction was to close it as superseded if
  `act-calendar-print-v14` covered its scope. No such action exists, in the data or in the git history:
  `act-calendar-v13` is itself the v1.4 print-and-distribute item (its title is "Print and distribute
  calendar template v1.4 …"). It stays open, and its owner stays Adriaan Mol, which the record already
  held; the workbook's Angelo Nahavitatsara / MadAvance is not applied.
- **`act-chase-s4-16-car`, `act-close-s4-15-car`, `act-close-s4-16-car`, `act-resolve-s4-16-car`**:
  **not restored.** They are Gold Standard design-review items (§4.16 CAR#8, §4.15 CAR#1, §4.16 CAR#5,
  §4.16 CAR#4), removed on 23 September with the design review section ("The carbon section moved to
  the right side of the line", above): the review is the Head of Carbon's. That scope, and consistency
  check 7p, stand. Their workbook rows are left as they are, in the retired workbook.
- **`act-mar-missing-rehabs`, `act-mar-new-construction-gap`, `act-mor-submit-drafts`**: found only in
  the local OneDrive copy of the workbook; shown to Adriaan, not added.
- **`act-read-district-commune-water`**: its owner row (Adriaan, no deadline) is deleted; it named no
  action on the page. `orphan_rows` in `data/action_owners.json` is now empty.

### Adriaan Mol, 28 Sep 2026, workbook reconciliation (continued)

The three rows found only in the local copy of the workbook are **already actions on the page**; each
lacked only a row in `owners`.

- **`act-mar-new-construction-gap`**: merged into `act-mar-missing-boreholes`. Both track the same
  Marolinta new-borehole gap and both close automatically at ten records (now six). The survivor is
  `act-mar-missing-boreholes`, whose count is a register population recomputed every build; the merged
  item read `data/marolinta_works.json`, which the build had not refreshed since 21 Sep. The merged item
  keeps its id and row as a child and closes with the survivor; the merge is under `merges` in
  `data/decisions.json`. The survivor already had its owners row: Angelo Nahavitatsara / MadAvance, no
  deadline.
- **`act-mar-missing-rehabs`**: kept. `act-no-works-record` does **not** cover it: that item's figure is
  a stored count of register points with no works record (57), with no list of points behind it, and it
  can close by removing points from the register; the three rehabilitations have no record anywhere, so
  nothing ties them to any point. Owners row added: Angelo Nahavitatsara / MadAvance, no deadline.
- **`act-mor-submit-drafts`**: kept. mWater, read live on 28 Sep, holds 4 drafts and 1 final on the
  Moramanga deployment (e8bbe3b1…) of the borehole-progress form; the item already closes automatically
  when no drafts remain. Owners row added: Jan / Endur'O team, 17 Oct 2026.
- **Marolinta drafts.** mWater also holds 2 drafts on the Marolinta deployment (2b408dd5…), both new
  constructions, started 23 Sep: 1052525253 (Angelo Madavance) and 1052525284 (FRANTZ-EL MADAVANCE,
  edited 25 Sep; that point already has a final record). The report showed none because
  `data/marolinta_works.json` was stale (written 21 Sep, never refreshed), not because the build dropped
  drafts. Refreshed; `tools/marolinta_works.py` is now a weekly build step and stops on a failed mWater
  call instead of writing zeros; the Marolinta section states drafts apart from finals; two consistency
  checks hold the file to one day and require finals + drafts = responses. Noted on
  `act-rehab-recording`; its closing condition is unchanged.

## 28 September 2026 — Adriaan Mol: transcription page, first pass exported 22 of 83

- **Root cause.** A calendar viewed and left empty was neither counted nor exported. The page now has
  an explicit status per calendar — *Vérifié — aucune croix* by a button or by answering Oui when
  *Suivant* asks — and exports every answered calendar with `statut` (`marque`, `exclu`,
  `vide_verifie`, and `vu_sans_confirmation` for a calendar only seen). The header reads
  "vérifiés N / 83". Storage key and format unchanged; fields added only. A browser test
  (`tools/test_transcription_page.py`) runs in `publish.sh`; the export-header check now includes
  `statut`.
- **Recovery.** Calendars with time recorded but no answer are exported as `vu_sans_confirmation`,
  never as checked-empty, and a review mode walks them for confirmation. A JSON backup button was
  added; the number seen but never confirmed is not known until Adriaan sends that backup.
- **Comparison tool corrected.** `tools/compare_transcriptions.py` joined the machine on water
  point; 15 of the 22 first-pass sheets have several photographs on their water point in the machine
  file. It now joins on the image via `transcription/validation_selection.csv`. First-pass results
  (11 machine-comparable calendars; not the validation round) are in
  `docs/transcription_round_notes.md` and nowhere on the page.
- **Two open items added**, owner Adriaan Mol, no date: `act-cal-working-day-ticks` (sheets where
  the gardien may have ticked working days) and `act-cal-handwritten-year` (a sheet year written by
  hand, which the year reader cannot see).

## 28 September 2026 — Adriaan Mol: v2.1 stroke-test SOP traceability not pursued

"Adriaan Mol, 28 Sep 2026: not pursued. v2.1 was never signed and is superseded by v2.2; the unedited
originals remain in SharePoint version history for both files."

## 28 September 2026 — Adriaan Mol: standing formatting and readability rule

Every table: fixed column widths (table-layout fixed plus a colgroup) sized to their content;
numbers right-aligned and never wrapped; no text column narrower than about 110 px at 1366 px;
long ids, mono strings and links break anywhere. Any table over 12 rows sits in a scroll box
(about 60vh, sticky header, "N lignes — faites défiler"). No horizontal page scroll at 1366 px or
390 px. Light and dark themes checked on real screenshots. Written into `CONTRIBUTING.md`
("Formatting and readability") and enforced by `tools/test_readability.py` in `publish.sh`.

- **Applied.** `layoutTables()` lays out every table on the page; `#popstbl` ("What every figure is
  over") carries its own widths — Population 18%, Records 8%, The rule 29%, What it reads 15%, The
  decision that set it 19%, Derives from 11% (the suggested 8% for Derives from fell below 110 px)
  — sits in the scroll box and has a filter on population names. Table headers moved from the
  lightest grey to the secondary ink: at 3.66:1 they failed the contrast check.

## 28 September 2026 — Adriaan Mol: the sheet year on the transcription page

- An editable **Année de la feuille** per calendar, prefilled from the reader. It rebuilds the grid
  (month lengths, leap years, the observable window) and is exported as `annee_feuille` with a new
  column `annee_source` (`lecteur` / `transcripteur`). Storage: one field added per calendar.
- **Sheet 6 (742895508)** is not hard-coded: the handwritten 2024 becomes a transcriber correction only
  when Adriaan confirms it on the page.
- **Weekday-layout fallback** built in `tools/read_year_ocr.py`. Its result is a deduction, kept apart
  in `data/calendar_sheet_year_deduced.csv`, never written into `sheet_year`, and shown on the page as
  "année déduite du calendrier — à confirmer". Six of the twelve undated transcription sheets have an
  accepted deduction; details in `docs/transcription_round_notes.md`.

## 28 September 2026 — Adriaan Mol: print styles under the readability rule

On paper every scroll box expands to full height, headers repeat on each printed page instead of
sticking, filter boxes and the "faites défiler" lines are hidden, and the light theme is forced.
Column widths became percentages so a table fits the page width; a filter is cleared for printing and
restored after. `tools/test_readability.py` emulates print and fails unless every table prints all its
rows; run against the page before this change, it failed on filtered rows, printed chrome and tables
wider than the page.

## 28 September 2026 — Adriaan Mol: transcription photographs upright, sheet years set

Before Angelo's team starts, every calendar shows upright and carries a year, with no action from the
transcriber. 26 photographs turned (reviewed by Claude: OCR in four orientations, each result checked
by eye), originals kept, rotation and hashes recorded, a check in `check_consistency.py` holding the
served files to that record. Eleven sheet years set with their source; sheet 84 left for the
transcriber. Adriaan's full pass keeps every mark on its cell. Calendar 89 prints 2026 but carries
late-2025 marks: kept at 2026 as printed, the conflict noted for `act-printed-year-meaning`.
Detail in `docs/transcription_round_notes.md`.

## 28 September 2026 — Adriaan Mol: piped results paired with their samples automatically

The laboratory no longer copies the sampling code and GPS onto a piped result by hand. The build
pairs each result on the piped result form (`0ac68d82`) with its record on the piped sampling form
(`ef8cf735`). The key is the same water point (1.1b) or, for a system-level sample, the same water
system (1.1), **and** the same sampling day (result 1.2.2 = the Madagascar day of sampling 1.4).
The pair takes its GPS, sample type and photo from the sampling record. Result 1.2.1 (sampling
code) is a cross-check only, and 1.2.3 (GPS) is ignored.

- **Flagged, never failing the build:** a result with no sample, a sample with no result after 7
  days, and a site and day with more than one sample or result. Response codes are listed in a
  collapsed block in the piped panel, so Cathy can pair them by hand; `publish.sh` prints them as a
  gate readout.
- **The form change** (1.2.1 not required and disabled, 1.2.3 disabled) is written up in
  `docs/mwater_form_change_0ac68d82.md` for the portal designer. The build does not change mWater.
- **On the existing data:** 0 of the 45 results pair automatically. None carries 1.2.2 or a water
  point, because all were filed before those questions existed. Every sampling round from March to
  August 2026 was recorded against the system, 8 to 11 samples on one day, so the rounds are
  flagged too. The samples from the week before each unpaired result are listed beside it.
- **Coordinates are not published.** Some samples are household connections. The pairs with their
  GPS are written to `~/mwater-exports/piped_wq_pairs.json`, beside the extracts; the page shows
  only whether a pair has a GPS fix and a photo.
- The piped sampling form is a new extract (`wq_sampling_piped.json`). It stays out of the form
  snapshot until its duplicated code 1.7 is fixed in the portal, because the snapshot check fails
  on a reused code. The fix is in the same form-change document.

## 28 September 2026 — Adriaan Mol: bottle IDs by hand; Endur'O system links and Moramanga duplicates

- **Cathy writes the water point ID on each bottle by hand.** Pre-printed stickers are hard to get
  in Antananarivo, so the bottle-label sheet is optional. The tap plate, or the ID painted or
  stencilled on the tap, is the reference she copies from. A wrong ID is caught by the pairing:
  the result is left unpaired and flagged (`docs/labels/README.md`). The tap plates, the list and
  the README are also in OneDrive, `Clean Water - Documents/General/Water Technical/Water Quality
  Testing/Piped WQ labels/`; the bottle-label PDF is not.
- **Two new actions, owner Endur'O with MadAvance IT (Lanja) for the mWater edits.** Both close on
  a count read each build, so their closure type is *auto*:
  - `act-enduro-link-wp-systems` closes when every water point in Endur'O's mWater group has its
    parent system set, read live from mWater;
  - `act-moramanga-system-dedupe` closes when every same-name duplicate system record beside the
    four Moramanga systems has left mWater or carries a note under `resolutions` in
    `data/moramanga_system_dedupe.json` (`tools/moramanga_dedupe.py`).
- Nothing in mWater was changed.
## 28 September 2026 — Adriaan Mol: every number means what its label says

Trigger: "Pumps reported down or reduced: 5" beside "21 hand pumps reported down". The 5 was the
call-centre contact count, copied by `rebuild_activity.py` into another key and shown under a
different meaning; the 21 is a current total. Rule written into `CONTRIBUTING.md`; a check in
`check_consistency.py` (7bd) fails the build on a figure copied into another key, and was shown
failing on the published build tool (`rebuild_activity.py:119`).

A reader's pass on the rendered page by a reviewer with no build context found 37 apparent
contradictions. Fixed or explained on the page, at the generator or data file where there is one:

- **The tile**: now distinct pumps a call reported not working in the window (split down /
  partially), reconciled in words with the pumps down now. Weekly and monthly visit and repair
  counts are submitted records (final or pending) and say so; the time-to-repair table counts final
  records and says so.
- **Stored figures that no step computed, now computed every build**: `S.never` (a frozen 57; the
  page's own count is 6), `S.pm_month` and `S.rep_month`, `S.oos` and `S.oos_site` (a histogram of
  607 beside tiles over 619), the open down-reports list and its "32 of 122" (no rule reproduced
  them; 31 of 113 now, the carried values shown as retired), the visit and water-quality links.
- **Wrong or double-counting formulas**: `SUCC_CORRECTED` added corrections already written back
  to mWater (740; now 732); the calendar stratum counted points with no photograph twice and dropped
  the points outside the register; the route-plan metric counted a site with no overdue pumps.
- **A figure bound to the wrong quantity by an old value match**: "732 chemical test results" had
  been bound to the corrected rehabilitation count; now the water-quality population, worded as
  what it counts. The footprint "128 of 128" used today's count for a 22-September measurement.
- **Labels and dates**: the reconciliation audit trail, the carbon versus maintained fleet, the
  calendar headline (stratum average versus pooled cells), per-image versus per-pump-period cells,
  dated versus day-call sheet counts, the WorldPop run dates, carbon-district people served, the
  Maroantsetra fNRB (registered 34%, applied 36%), Endur'O systems in its register versus mWater,
  the UNICEF list reconciliation, the methodology divergences, the SOP sweep, photographs on file
  versus in the backup, the SDWS 26 share (99.5%, not 100%), the Marolinta records and dates, the
  unclassified partially-working pumps, and a status definition that said "in 2026".

A second reader's pass on the fixed page found 23 more. Fixed or explained on the page:

- **Labels and bases**:
  - Status is the last record in any year, not "in 2026". The "No status record" count includes 9 pumps held on their published "unknown", and the page now says so.
  - The 731 successful rehabilitations all sit inside the fleet; the page used to say they were neither a subset nor a superset of it.
  - 731 is today's count, and 723 was the count on 17 July.
  - The Marolinta points are new boreholes, not "works on the borehole form".
  - 127,280 covers the two carbon districts, not MadAvance.
  - "385 with nothing in six months" now reads "last photographed over six months ago", with the 62 never photographed stated beside it.
  - Calendar figures over the register of 19 September (736) are dated.
  - The "never" bar is relabelled "No works record".
  - Routes carry the pumps overdue on the day they were drawn, shown beside the count overdue today.
  - The time-to-repair "other" row is points outside the managed register.
  - The SDWS 26 parameter row is the both-seasons reading.
  - The functionality-report table is described as retirement records, not the only record of a breakdown.
  - Managed pumps that appear on that table are named.
  - The Endur'O southern sites are distinguished from the managed piped systems.
  - Marolinta's maintenance wording is reconciled.
  - The Type 3 ceiling check is distinguished from the withdrawn tonnage.
- **Computation**:
  - The down table's People column was empty on every row; its rows never carried the allocation.
  - The carbon-parameter shares now round like every other share, so one fraction no longer shows two values.
- **Explained**:
  - The contact and reported-not-working tiles match because every contact in the window reported a different pump down; the repairs figure matching them is a coincidence.
  - A repair recorded on the day of a down-report closes it on the open list, while the call still sets the status.
- **Markup**: a figure span was printed as text. A new check (7be) fails the build on any escaped figure span.

A third reader's pass found 13 more, all fixed or explained on the page:

- **Open tickets**: the 21 September backlog of 44 and today's open list count by different rules, and the page now says so.
- **Held statuses**: the 17 pumps with no dated record are split into the 12 counted as "No status record" and 5 held on a published status.
- **Endur'O water-quality cell**: now names the pre-project baseline results.
- **SDWS 25 row**: no longer says the survey form is not pulled.
- **Marolinta flagged codes**: the statement about how they relate to the table rows is corrected.
- **Partially working**:
  - The open list says "partially working", not "reduced".
  - The partial table says its class is carried forward and can disagree with the latest reason.
- **Calendar tables and statistics**:
  - The representativeness table counts points, not point-years.
  - The year statistics state the first-pass basis (749 sheets) against the later run (1,014).
  - The 2024 sheet count is labelled as the day-call subset.
- **SDWS 2 freshness date**: labelled as the newest response of any kind on the form.
- **Endur'O's 131**: called sites throughout.
- **The 6-point dashboard gap**: accounted for.
- **Retired-points table**: its row note now matches its rows.
- **189**: the equal field-day and timed-repair counts are marked as a coincidence.

A fourth reader's pass found 12 more, all fixed or explained on the page:

- **Successful rehabilitations and Marolinta**:
  - The successful-rehabilitation population declared that it read the Marolinta form, but it does not (that form has no success answer). The declaration and the register-chain wording now say so.
  - The 787 is labelled as including Marolinta new constructions.
- **Map**: the map draws Endur'O's own mWater points, not the 131 reconciled sites. Both pages now say where the 131 comes from.
- **Carbon points**: "active carbon points" is renamed to carbon points, because the denominator is the register less Marolinta, not the SDWS 3 "active" rule.
- **Operator rule**: the one pump counted despite its "all" tag is stated with the rule.
- **Calendar reading**: the stratum average is the reading everywhere, and the pooled figure is labelled as pooled.
- **fNRB**: the 36% called "national" (18 Sep) and "sub-national" (21 Sep) is shown to be one value.
- **Time to repair**: the 145 repaired points are no longer described as all carbon points.
- **Freshness cell**: a form with no records is no longer read as all of its sources.
- **Household size**: INSTAT versus the registered household sizes is explained.
- **2027 sheets**: sheets are tied to point-years.
- **ER inputs**:
  - Mq,y is partly evidenced.
  - EFb's row shows its fNRB input, and is labelled as such.
- **Smaller wording**:
  - The partially-working tile basis.
  - All 39 holds accounted for.
  - The photo-pool count.
  - A stale divergence number.

A fifth reader's pass found 9 more (2 material), all fixed or explained on the page:

- **Material**:
  - The Qpop,y input quoted the people figure with Marolinta included; it now quotes the carbon points only.
  - "People with safe water" is relabelled "people served": it is an allocation, not a count of people whose water has passed a test.
- **Minor**:
  - The 42 pumps with no visit or repair are on any form, not "the current forms".
  - The 385 barrier sensitivity is tied to its own run.
  - Functionality reports are not all on managed points.
  - The withdrawn Endur'O 111 is distinguished from the UNICEF list of the same size.
  - "Eight green rows" is conditioned on all four open inputs.
  - The partner note no longer says every figure is a carbon figure.
  - The two 145s are marked as a coincidence.

A sixth reader's pass found nothing material and 7 minor points, all fixed:

- A wrongly worded barrier-sensitivity sentence.
- The overdue table's note on never-visited pumps.
- The cookstove overlap's two dates, and the unchecked pump in its people share.
- C_b's evidence status.
- Carbon gap 8's wording.
- The stored tables named in the "no hand-entered number" claim.
- The joined pump in the 297-of-732 calendar share.

## 28 September 2026 — Adriaan Mol: the piped system model, standposts only, and the 72-hour pairing rule

- **What a Moramanga system is:** a spring augmented by solar-pumped boreholes, header tank(s),
  chlorination, and piped distribution to public standposts and private connections. Some of the
  four systems are existing systems being upgraded (their taps exist and are in use); some are
  built from scratch. On the page their status reads **"upgrade or new build under way"** wherever
  it said "in process" (the status key stays `in_process`). They stay out of every carbon and
  portfolio figure until complete. See `docs/piped_system_model.md`.
- **Sampling scope, for now:** public standposts and kiosks only, what comes out of the tap. No
  source, tank or household samples.
- **Pairing, replacing the same-day rule of the morning:**
  - A result pairs with the most recent unpaired sample at the same water point taken within
    72 h before the result was submitted, and each sample pairs once.
  - 1.2.2 is a cross-check only: a difference of more than 1 day adds a date-mismatch note.
  - A sample at system level or at a household is flagged outside protocol.
  - Samples on systems under way are pre-completion tests.
  - Results and samples submitted before the protocol went live (22 Sep 2026 15:58 UTC,
    sampling form revision 75) are baseline, not paired. Applying the cutoff to samples as well
    as results is ours: the brief named results only.
- **Actions:**
  - `act-moramanga-system-dedupe` now lists every system record within 3 km in any group, with
    history, from a dated snapshot (`tools/moramanga_dedupe.py --history`). It recommends a
    record of record per scheme and names WaterAid's `441839342` "AEPG AMBOASARY GARA" (19
    linked kiosks) as a duplicate.
  - `act-moramanga-register-standposts` is new and depends on the dedupe action.
- Nothing in mWater was changed.

## 29 September 2026 — Adriaan Mol: 1108783583 is Amboasary gara's record of record; the WaterAid kiosks

- **`1108783583` stays the record of record for Amboasary gara.** WaterAid's 2023 record
  `441839342` "AEPG AMBOASARY GARA" is a duplicate. This is recorded under `decisions` in
  `data/moramanga_system_dedupe.json`.
- **The 19 "KIOSQUE … AMBOASARY GARA" water points linked to `441839342`** are recorded under
  `interim_points` as belonging to `1108783583`. The mapping is used only for piped water-quality
  classification: a sample at one of these kiosks pairs by water point and is a pre-completion
  test on Amboasary gara. It does **not** count toward closing
  `act-moramanga-register-standposts`. That action now counts only a Distribution Point
  registration whose parent is the record of record itself; a registration on a duplicate no
  longer counts.
- **Permissions, read only, 29 Sep 2026:**
  - WaterAid owns `441839342` and 18 of the kiosks; MGMERL owns `378659084`.
  - Each record gives admin to its owning group only and view to everyone.
  - The Enduro and MadAvance groups are members of no other group, so neither can edit these
    records.
  - Steps added to the action: ask WaterAid Madagascar to transfer or share edit rights on its
    18 kiosks and on `441839342`, and ask the MG MERL coordination team the same for
    `378659084`.
- `441839342` is not marked resolved: it still holds the kiosks. Nothing in mWater was changed.

## 29 September 2026 — Adriaan Mol: other organisations' records are history; Endur'O registers its own

- The management contract for the Moramanga systems is with Endur'O/NatuRano. Endur'O registers
  its own new water points under its own system records (`1108783583`, `1108783624`,
  `1108783648`, `1108783662`).
- Other organisations' records (WaterAid, MG MERL and others) are historical: never edited,
  relinked, deleted or asked to be transferred. This **replaces** the steps added earlier today:
  asking WaterAid and MG MERL for edit rights, and relinking the 19 kiosks.
- `441839342` (WaterAid) and `378659084` (MG MERL) carry the resolution note "superseded – other
  organisation's historical record; Endur'O record of record used" and count as resolved.
  Endur'O's own duplicates stay open: `1108783569`, `1108783631`, `1108783655` and the three
  records `928471757`, `929469223`, `929469247`. The last three are in Endur'O's group and were
  created on 30 June 2026 by the same account as the boreholes.
- New: `data/moramanga_wp_crosswalk.json` (old ID → new Endur'O ID), filled every build by
  `tools/moramanga_dedupe.py`. The pairing uses it, and a sample at an old kiosk is flagged "use
  the Endur'O point". There is a new extract of Endur'O's water points, `enduro_points.csv`, for
  the descriptions and GPS.
- Nothing in mWater was changed.

## 29 September 2026 — Adriaan Mol: the six open Moramanga duplicates

- **Kept as history, resolved:** `928471757` AEPP AMBOHIBOLA, `929469223` AEPP AMBOASARY GARE and
  `929469247` Forage Amboasary gare. Note: "kept as history – holds existing borehole links;
  sources not in sampling scope; new boreholes and all standposts go under the Endur'O record of
  record".
- **Open:** the three accidental duplicates `1108783569`, `1108783631` and `1108783655`, for
  Endur'O to retire in mWater so they don't appear in the pick list. Owner of
  `act-moramanga-system-dedupe`: Coddy (Endur'O), with Lanja (MadAvance IT). Each closes on its
  own once it is gone from the extract or its `status` is decommissioned or disposed.
- **Wrong-parent check** (`tools/moramanga_dedupe.py --wrong-parent`, a `publish.sh` readout that
  never fails the build): any Distribution Point registration with a duplicate as parent, and any
  Endur'O water point created from 29 Sep 2026 whose system is a duplicate. The borehole links
  from before the decision are history and are not flagged.
- Nothing in mWater was changed.

## 29 September 2026 — Adriaan Mol: India Mark cap rule proposed to James Walker, not applied

**Proposed** (email to James Walker, 28 Sep 2026): 500 people per India Mark pump where the water
depth is 20 m or less, or a measured discharge test shows at least 16.6 l/min; otherwise 300.
Evidence: the Sphere Handbook (500 people per hand pump at 16.6 l/min, about 8 hours a day) and
the India Mark II rated-flow table (30 l/min at 10 m, 21.7 at 15 m, 16.7 at 20 m, 15.0 at 25 m).

**Status: proposed, awaiting James's confirmation.** The applied cap stays at 300 (`PARAMS.im_cap`)
in every carbon figure until his written reply is logged against `act-india-mark-cap-james`
(owner Adriaan, closure: evidence). `check_consistency.py` 7bf enforces this. It also requires
every figure under the proposed cap to be labelled as proposed.

**Before this, the rule did not exist.** The build carried 300 as applied and 500 as a
whole-fleet sensitivity (`im_cap_alt`), with the open question `act-indiamark-premises`. Neither
used depth or discharge.

**How the records meet the rule** (`tools/india_mark_cap.py`, run every build):
- No form records the water depth itself.
- The retired works form records the pump installation depth (question `ea5221c7`). The pump
  sits below the water, so a pump installed at 20 m or less decides the depth side.
- A deeper or unrecorded pump stays at 300 until a depth or discharge is measured.
- The form's "Débit" carries no unit and is not a timed hand-pump test, so no pump qualifies on
  flow.

On the current extract, 38 of the 84 India Mark pumps qualify on depth, and 27 of them have an
allocation above 300. The page shows current and proposed side by side in the people-served
section (people served overall, carbon points, per site, per pump, the Fort-Dauphin share, the
people-weighted fNRB). It also shows the proposed figure beside the headline, the partner table
and the Qpop,y input.

## 29 September 2026 — Adriaan Mol: owners workbook, reconfirmed

The repo action list is the record of owner and deadline, and Adriaan and Claude update it. This
confirms the entry of 28 September. That entry already stopped the workbook sync and removed the
workbook from the build. It also moved the workbook to Central Data Hub › Water Documents › Archive
as "RETIRED 2026-09-28 - Water report - action owners and deadlines (see decision_log.md).xlsx".
Nothing further changed on 29 September.

## 29 September 2026 — Adriaan Mol: the 2025 household water-quality round (SDWS 18) is on the report

**The round was run.** The page said the point-of-use round had not been run. Form `db0bcbf2`
("Clean Water || project SDWS18") holds 140 final household samples:
- Fort-Dauphin: 70 samples, 5–14 Nov 2025.
- Maroantsetra: 70 samples, 2–11 Dec 2025.
- Each district: 10 water points, 7 households each, all 20 points in the managed register.

The build now pulls the form (`pou_survey.json`). `tools/rebuild_sdws18.py` computes the round
every build (`data/sdws18.json`), and the populations `sdws18_pou_samples` and
`sdws18_pou_passing` carry it into the carbon-parameters table.

**Pass rule** (Water Quality Protocol v2.1 §5.1; methodology v2.0 §3.2.3.2):
- A household (point-of-use) sample passes at fewer than 10 *E. coli* per 100 ml, the WHO low-risk
  band.
- A pump or tap sample passes only at 0.
- All 140 are household samples.

**Results:**
- Both districts pass 100% (exact 90% CI 95.8–100).
- The stricter no-*E. coli* rate is shown as information only: Fort-Dauphin 100%, Maroantsetra 95.7%.
- The three Maroantsetra positives (2, 4 and 7 per 100 ml) are kept, with the enumerator's comment
  ("contamination probably between sampling and analysis"). They pass, so nothing is triggered.
  There are no field blanks or duplicates to check the comment against.
- Two Maroantsetra households are recorded 2.45 km and 15.9 km from their pump. They are flagged as
  a probable GPS or linking error and kept.

**Open with James Walker** (asked 29 Sep 2026; `act-sdws18-james-rulings`):
- (a) The six-month start date. Per pump, 0 of 10 Maroantsetra and 8 of 10 Fort-Dauphin pumps reach
  six months; from the programme start of 11 Apr 2025, both districts do.
- (b) Whether a note covers the kit, method, sample source and paired pump sample the 2025 records
  lack.

**Corrected:**
- The three places that said the round had not been run.
- The section, labelled SDWS 18 (share of samples passing).
- `act-point-use-round-one`, now the 2026 round with field blanks, duplicates and a paired pump
  sample.
- New: `act-pou-form-threshold` (Lanja). The form's pass field still checks against 0.

## 29 September 2026 — Adriaan Mol: a point enters the fleet only through a works record

**Statement** (Angelo Nahavitatsara, 29 Sep 2026): the records of 21–24 Aug 2025 on form `86cf66ef`
(account fitahianawilliam) are an identification survey, not managed water points. Of the 20 points:
- **Excluded:** four were counted in the managed fleet with no works record of any kind —
  987623115, 987623256, 987623270 and 987623517.
- **Kept:** 987623555, on its final 26 Aug 2026 rehabilitation (borehole-progress form).
- **Already outside:** 987623304 was excluded on 15 Sep; the other 14 were never in the fleet.

**The rule:** a point enters the managed fleet only through a programme works record, never through a
survey record. That means a successful rehabilitation, a new construction, or a recorded correction
to one. Enforcement:
- `tools/classify_register.py` removes an excluded point from the fleet.
- `check_consistency.py` 7bg fails the build on any fleet point without a works record.
- Logged in `data/decisions.json` (`register-fleet-entry-rule`).

**Consequences:**
- The fleet is 733: Marolinta 1, the carbon fleet unchanged at 732.
- The WorldPop allocation was rerun for the four leaving points. Only 987623555 moved, and it stays at
  its cap of 300; every other pump reproduced exactly.
- The rerun first refused to publish because `rerun_wpop.py` read the run of record's input from the
  pipeline root instead of the run folder. Fixed.

**Removed:** `act-marolita-spelling` (19 records spelling the village "Marolita"). It is not needed:
those are survey records, not managed water points.

## 29 September 2026 — Adriaan Mol: every SDWS 18 figure traced to mWater; two survey-point actions closed

**Traced to mWater.** The SDWS 18 section now opens with its source:
- the form "Clean Water || project SDWS18 || Survey || Active" (`db0bcbf2…`) and both deployments;
- the population rule (final records only, drafts excluded);
- the date of the mWater extract;
- a plain statement that the Excel workbook of the round is not a source.

Each figure carries its own derivation, a count over the population `sdws18_pou_samples` (or
`sdws18_pou_passing`). A record table (`tools/render_sdws18.py`) lists all 140 records:
- one row each, with district, water point, household, date, *E. coli*, result and comment;
- each row linked to its mWater response;
- the three samples with *E. coli* and the two households far from their pump are marked.

`check_consistency.py` 7bh fails the build if the table's rows differ from the tests tile, or if
any row lacks its mWater link.

**Closed:** `act-resolve-water-point-type` (987623517) and `act-visit-three-marolinta-points`
(987623517, 987623256, 987623115). Reason: "point excluded from the managed fleet: survey record only
(decision 29 Sep 2026, Angelo Nahavitatsara)". Both are logged in `data/decisions.json` and stay in
the closed list.
- The visit action named only excluded points, so it closes whole rather than dropping one point.
- The type action also carried a misfiled photograph on 742896114. That photograph is one of those
  tracked by `act-photo-misfiled`, which stays open.

## 29 September 2026 — Adriaan Mol: the fleet is the successfully rehabilitated plus completed new constructions

**Checked before changing.** Two fleet points had no successful rehabilitation (not six: four had
been excluded as survey records earlier the same day).
- **782134540** (Maroantsetra, Canzee) has a repair (28 Jun 2025), an *E. coli* pass (11 Jul 2025) and
  call-centre records, and no rehabilitation or new-construction record. It was in the fleet under
  the correction of 15 Sep 2026.
- **987623555** (Marolinta) has a final rehabilitation on the borehole-progress form, 26 Aug 2026.

The Marolinta borehole-progress form holds 13 final works records, but only 987623555 was in the
fleet; the other 12 carry no district in mWater and fell out of the join.
- **6 new constructions** (29 Jul–3 Aug 2026): 893673000, 893673127, 893673158, 1052525198,
  1052525260, 1052525284.
- **7 rehabilitations marked "Fonctionnel"** (5–29 Aug 2026), including 987623555 and 987623304.
- **Pump model:** every one records Canzee. The register names 987623555 "IndiaMark"; it is left as
  it is, and flagged.
- **Elsewhere:** Fort-Dauphin and Maroantsetra have no new-construction record on any works form, and
  the retired combined form has no new-construction type.

**Applied** (rule of 29 Sep 2026; decisions `register-marolinta-works-join`,
`register-987623304-exclusion-superseded`, `register-782134540-exception`):
- **The 12 join the fleet.** District (Beloha → Marolinta) and pump model (Canzee, from the works
  record) are set in the repository only (`register_corrections.attributes_assigned`), not in
  mWater. None is within 30 m of a fleet point or of another joiner.
- **987623304's exclusion is superseded.** It was excluded on 15 Sep 2026 as a rope-pump survey entry.
  Its rehabilitation photographs show a Canzee-type PVC direct-action pump, so it is confirmed by
  photo.
- **782134540 stays as the one recorded exception** until 31 Oct 2026
  (`act-782134540-rehab-record`, Angelo). If no final rehabilitation record for it has appeared by
  then, `classify_register.py` removes it and the carbon fleet goes from 732 to 731.
- **New action** `act-marolinta-drilling-result` (Angelo): answer the drilling-result question on
  the six new-construction records.

**Resulting counts:**

| | Maroantsetra | Fort-Dauphin | Marolinta | Total | Carbon fleet |
|---|---|---|---|---|---|
| Before | 604 | 128 | 1 | 733 | 732 |
| After | 604 | 128 | 13 | 745 | 732 (unchanged) |

- The WorldPop allocation was rerun: only the 13 Marolinta pumps changed.
- The joiners' maintenance clocks start from their works dates, so they are no longer counted as
  "no works record".
- The chain step now reads "the fleet is the successfully rehabilitated plus completed new
  constructions".

## 29 September 2026 — Adriaan Mol: action list and calendar SOP

**Wording and layout:**
- The old section title (which set every figure ranges over) is renamed "What each figure counts", with a one-line explanation.
  The rest of the section is collapsed by default; it had been fully open.
- The action list has fixed column widths: Item 40%, Owner 15%, Status 10%, Deadline 10%, "What would
  close it" 25%. The owner tables use 47/11/12/30. One action text typed in capitals is now in
  sentence case.

**"proposed — Jan to confirm or move" removed from all 68 actions.** It dates from 18 Sep 2026
(commit 2a410b3), when every deadline was a proposal awaiting Jan's confirmation. Since 28 Sep,
deadlines live in `data/action_owners.json`. It marked no open question about an owner.

**Calendar SOP v1.7:**
- **Approved** by Adriaan: its status line in SharePoint now reads "Statut: Approuvée — Adriaan Mol,
  COO SaniTap, 29 septembre 2026".
- **Moved unchanged to SOPs/Archive:** v1.0, v1.1, v1.2, v1.5 and v1.6, and Template v1.0 and v1.1
  (pdf and svg).
- **Kept in SOPs:** v1.7 and Template-v1.4-2027.pdf. Template-v1.4-2026 (pdf/svg), the v1.4-2027 svg
  and Generators v1.0/v1.4 are also still there, left for a decision.

**Actions:**

| Action | Change |
|---|---|
| `act-sop-calendar-v17-signoff` | Now "Brief every field team in French on SOP v1.7" (Angelo); closes on his written confirmation per team |
| `act-calendar-v13` | Owner Angelo; links to the template and v1.7 |
| `act-route-plans` | Owner Angelo |
| `act-sensor-sample` (the Curtech brief) | Closed: done by WhatsApp |
| `act-complete-accuracy-assessment-calendar` | Closed on the measured accuracy (below) |

**Accuracy of the calendar extraction.** Adriaan's transcription of all 83 calendars (series 1, 28 Sep
2026) is copied into `data/transcriptions/` and compared with the machine
(`tools/compare_transcriptions.py --summary-json` → `data/transcription_accuracy.json`).
- **Coverage:** the machine reads 50 of the 83 sheets; 42 have overlapping cells.
- **Agreement:** 92.1% mean over calendars, 93.8% over 9,780 days.
- **False X:** 394, of which 366 fall on days 1–5.
- **Missed X:** 18.
- **Machine unreadable:** 191 days.

This is published in the calendar section. The independent validation round stays open.

## 30 Sep 2026 — report layout and consistency fixes (Adriaan Mol)

**Table widths, root cause.** The sizer measured tables inside a closed `<details>` (Chromium keeps
their `offsetParent`, so the guard let them through) and gave a `.num` column its full unwrapped width
with no cap, then wrote the total back as an inline pixel width (`#chaintbl` 1,496 px wide, Step
110 px). Rewritten: measured only when rendered, no inline width (`--tmin` where floors need it),
`.num` capped at 25% on wide tables, text columns by content with a 160 px floor.

**Action list.** Columns 50/12/6/8/24; small centred status badges; 1000 px minimum in CSS.
`act-establish-renewal-dates-current` merged into `act-establish-renewal-dates-four` (the older id on
the page of 18 Sep); the retired id redirects (`data/action_redirects.json`, logged under merges in
`data/decisions.json`). No other near-duplicates found (titles and details compared).

**Page.** One stat-tile component with the partner-card treatment; "This week" says period, its
explanation collapsed; partner cards logo-left; Marolinta out of its one-child two-column grid (tiles
4/2/1); SDWS 18 record table collapsed; "What each figure counts" merged into "Where each figure comes
from and what it counts" at the end of the page; the five carbon-panel headings are h3 under the
panel's h2, so no heading renders empty as loaded.

**Status → action gate.** `data/status_actions.json`; two actions created with owner unassigned:
`act-usage-survey-inside-radius`, `act-usage-survey-random-selection`.

## 30 Sep 2026 (b) — visible surface tint, light-theme contrast, theme switch (Adriaan Mol)

- `--tint` / `--tint-line`: light #cbdded / #9fbfd8 (1.28:1 on the page), dark #20323f / #36546a
  (1.37:1); on tiles, donut cards, partner cards, table headers and panel summary bars.
- Light theme: `--ink3` #566169, `--warn` #8a5300, `--crit` #b3261e, `--good` #1a6e1a; dark `--ink3`
  #9aa19d, `--good` #2fbf2f, `--crit` #f07c7c. Light-theme text under threshold: 4,455 nodes before
  (5 colour/background pairs, incl. the 13 amber numbers at 1.79:1), 0 after.
- Laptop-only render checks (1280, 1440, 1920); Auto / Light / Dark switch.
- Held 29 Sep edits applied: 987623304 "Canzee (record f21f3cbd and photos agree)"; OPSTATUS closing check.

## 30 Sep 2026 (c) — Antananarivo kiosk baseline, Curtech endpoints, usage-survey SOP and Sampler mode (Adriaan Mol)

Eight open actions added (owner and deadline in `data/action_owners.json`, closing conditions in
`data/action_conditions.json`, detail in `data/action_details.json`). Actions carry no scope field (scopes
are per section), so the Endur'O ones sit under their Endur'O owner; "depends on" is in the detail text.

| Action | Owner | Deadline | Closure | Source |
|---|---|---|---|---|
| `act-tana-baseline-form` | Adriaan Mol | 2026-10-09 | manual | Adriaan's reply to Jan de Graaf, "RE: Endur'O registration forms are live: please test them at the prototype smart tap site", 30 Sep 2026 |
| `act-tana-baseline-sample-size` | James Walker | 2026-10-09 | evidence (decision, with a `households` figure) | as above |
| `act-tana-baseline-survey` | Endur'O (Coddy Velonizy, Ntsoa Ranaivoson) | 2026-10-31 | auto: `tana_baseline_households_short` = 0 | Jan de Graaf, "Fw: Endur'O registration forms are live...", 30 Sep 2026; Adriaan's reply |
| `act-tana-jirama-licence-filed` | Endur'O (Coddy Velonizy) | 2026-10-16 | evidence (SharePoint Water Documents) | Adriaan's reply-all to Jan and Coddy, 30 Sep 2026 |
| `act-ralf-shopkeeper-waterpoint-link` | Ralf van Veenendaal (Curtech) | 2026-10-31 | evidence | Adriaan to Ralf, "RE: Zoho endpoint: works, and what else we need alongside it", 30 Sep 2026 |
| `act-ralf-meter-install-register` | Ralf van Veenendaal (Curtech) | 2026-10-31 | evidence | as above, sent 30 Sep 2026 11:38 |
| `act-usage-survey-sop` | Adriaan Mol; sign-off James Walker | 2026-10-16 | evidence (SOP v1.0 in SOPs) | chat, 30 Sep 2026 |
| `act-sampler-usage-survey-mode` | Adriaan Mol (built with Claude Code) | 2026-10-23 | evidence | chat, 30 Sep 2026 |

- `tana_baseline_households_short` (tools/action_metrics.py): final responses on any deployment of form
  3ef4385a other than Moramanga's, each with both randomisation photographs, against James Walker's
  logged sample size; no value until that is logged, so the action cannot close early.
- `act-enduro-onboard-3-bind-taps` (the action the instruction called act-enduro-smart-taps-bind) closed as
  superseded by `act-ralf-meter-install-register` (logged in data/decisions.json); the new action is a step
  of `act-enduro-move-register-fully`.
- `act-usage-survey-random-selection` and `act-usage-survey-inside-radius`: owner Adriaan Mol, deadline
  2026-10-16, closing on the signed SOP v1.0; status mappings unchanged.
- `act-sdws26-annual-round`: deadline 2026-11-30 for the 2026 round, run to SOP-MAD-SDWS26 using the Sampler
  usage-survey mode; owner and recurring rule unchanged.

## 30 Sep 2026 (d) — calendar reader row alignment fixed (Adriaan Mol)

Approved by Adriaan Mol, 30 Sep 2026 (chat), after the fix was held on 29 Sep because missed X rose by two.
Measured against his transcription of 42 calendars (9,780 days): agreement over days 93.8% → 98.9%
(mean over calendars 92.1% → 97.5%); false X 394 → 27 (days 1–5: 366 → 5); missed X 18 → 20
(new misses: sheet 42, 3 February; sheet 18, 7 January).

- Cause: the day rows were fitted over the tint bounding box, which ran up through the header photographs,
  title and logos, so days 1–5 were read off the header and every lower row shifted. Rows are now registered
  on the printed weekend shading, or on the 2026/27 sheets on the month-name band above day 1, per month
  column (`caltools.fit_day_rows`).
- The reader of record moves into this repository: `tools/caltools.py`, `tools/run_extract2.py` (the copies in
  `~/sdws1/calendar_extract` now point here; the pre-fix outputs are kept in `.attic/pre-rowfix-20260929`).
- Coverage test: the fixed row finder replaces the old row test for sheets that test rejected, and such a
  sheet is admitted only if listed in `data/calendar_row_admissions.csv` with agreement of 0.97 or better
  against the transcription. 17 of the 25 transcribed sheets the old test rejected are admitted; 30 (0.967),
  33 (0.62) and 92 (0.75) fall below; 7 and 23 had no elapsed day to compare; 3, 86 and 93 have no anchor.
  Sheets nobody has transcribed cannot be measured and are not admitted. Photographs with day calls
  593 → 608. The published agreement figure stays on the 42 calendars flagged comparable in the export.
- Implied uptime stays withheld (it would read 367.2 days): the page states the observed and floor rates
  only, and `check_consistency.py` now requires the withheld statement instead of the implied rate.
- Days not operational on the page move with the reader (these figures are internal; DO_p,y and the carbon
  figures stay on the registered 347 days).
- Follow-up the same day: four more places still rendered the pooled implied figure (a stat tile, three
  sentences). All now say it is withheld, and `check_consistency.py` fails if any `CALX.implied_*` or
  `GEN.calendar.implied_*` figure is rendered.

## 30 Sep 2026 (e) — barrier split fixed in the SDWS 1 pipeline (Adriaan Mol)

Approved by Adriaan Mol, 30 Sep 2026 (chat). `~/sdws1/sdws1_population.py` clipped each barrier line to the
1 km circle and cut the circle with shapely `split()`. The clipped ends missed the circle's boundary by
rounding, so the lines were often not noded with it and `split()` returned the whole circle: a river crossing
the circle cut nothing. Found by the Sampler parity check (Sampler commit 71c5cca, README "Barrier clip parity").

- Fix: lines are clipped to the circle grown by 50 m, the circle is polygonised with them, and the pieces
  must tile the circle (a failure is counted in the run summary as `split_failures` and fails adoption).
  A closed coastline way (an island) loaded as a polygon is cut along its outline; the first rerun found two
  Fort-Dauphin points where this also used to fail silently. Rules unchanged: coastline, river, canal
  (streams off); 40 m opening at bridge=yes|viaduct|boardwalk and ford=yes|stepping_stones|boat; keep the
  fragment holding the pump. The same cut is used by barrier_overexclusion.py, barrier_check_maps.py and
  sdws1_barrier_clip.py; verify/recompute_population.py fixes it by a different route (lines clipped to a
  square well past the circle, then split()).
- Regression test `~/sdws1/tests/test_split_fix.py`: 771703469 78.1 %, 742896798 64.9 %, 772741428 54.1 %
  kept (each within 1 point), plus synthetic cases.
- Rerun on the run of record's own input (745 pumps) and the pinned R2025A raster: runs/r2025a_barriers_20260930
  (equal, idw, nearest, and the people-behind-a-barrier pass), r2025a_nobarriers_20260930, sens_c_20260930
  (no river a barrier). Adopted with `tools/rerun_wpop.py --adopt` (new: a full rerun after a method change,
  refused unless the input is the run of record's, the raster is pinned, the pipeline sha256 is the current
  script's and there are no split failures). 337 pumps changed.

| | Fort-Dauphin | Maroantsetra | Marolinta | Total |
|---|---|---|---|---|
| Allocated (after overlap split) | 78,081 → 75,989 | 86,743 → 84,356 | 1,355 → 1,355 | 166,178 → 161,699 |
| Reported after cap | 41,462 → 40,639 | 85,818 → 83,717 | 1,354 → 1,354 | 128,634 → 125,710 |
| Points at the cap | 79 → 74 | 3 → 3 | 0 → 0 | 82 → 77 |
| Points cut > 10 % | 9 → 40 | 113 → 326 | 0 → 0 | 122 → 366 |
| People behind a barrier | 658 → 7,623 | 26,801 → 78,359 | 0 → 0 | 27,459 → 85,982 |

- The "no river a barrier" sensitivity (the figure keyed `streams_as_barriers` in data/wpop_pipeline_figures.json;
  it is variant c of barrier_sensitivity.py, not streams) is now 128,939 against 125,710: +3,229 (2.57 %),
  was +385 (0.3 %) with the split failing.
- `wpop_pipeline_figures.py` now reads the 30 Sep folders; the 16 Sep folders are kept. The pipeline sha256
  is in the run summary, WPOPMETA and the provenance paragraph; check_consistency fails if the run of record
  was made by another version of the pipeline.

## 1 Oct 2026 — one SDWS 1 method for the report and the UNICEF tool (Adriaan Mol)

Instruction of Adriaan Mol, 1 Oct 2026 (chat).

- The method lives in the private repository **SaniTap-water/sdws1-method** (`~/sdws1` under git),
  pinned in `data/build_config.json` (`worldpop.pipeline`: commit f2e2004, script sha256 2319f3e0…).
  Rasters, OSM extracts, point files, renders and run outputs stay out (`.gitignore`); `MANIFEST.md`
  records their sha256 and sources. The pre-fix script is not kept anywhere. Stale copies replaced by a
  pointer file (`POINTER-sdws1-method.md`): `Downloads\sdws1-inputs\`, `Downloads\sdws1-2026-09-15\`,
  `Downloads\Claude outputs\` and the evidence library's `SDWS1_Population Count\World-Pop\` (whose
  16 Sep pre-fix outputs and renders were removed; its methodology documents stay).
- `tools/rerun_wpop.py` runs the pipeline only at the pinned commit with the script unmodified, and has
  `--repin` (a rerun at a newly pinned commit must reproduce every per-point figure). Fleet check at the
  pinned commit: all 745 per-point figures identical, 125,710 after caps; run of record now
  `~/sdws1/runs/fleet_20261001/barriers`.
- check_consistency fails unless the script sha256 is the same on the page, in the build config pin,
  in the repository at the pinned commit, in the evidence-folder copy and in its `.sha256` file, and unless
  the page names the commit and links the evidence folder.
- The sensitivity keyed `streams_as_barriers` was always the no-river run (barrier_sensitivity.py
  variant c); renamed `no_river_barriers` in data/wpop_pipeline_figures.json, its generator, the
  registry and the page. The pipeline's own `streams_as_barriers` flag (--include-streams) is unchanged.
- UNICEF tool: `unicef/build_points.py` writes the point rule down (latest monitoring type; valid GPS in
  Madagascar or within 0.05° of its coast; monitoring-flagged duplicates out; 5+ points on one 5-decimal
  coordinate out): 33,016 points against the tool's 32,996 (its 23 Sep filter was not recorded). With the
  fixed method: 12,583,744 people within 1 km after the clip; 5,267,349 after caps; restoration pool
  650,282 (5,022 of its 5,024 points in the set).
- Evidence folder "SDWS1 people served (current method)" (Central Data Hub > Water Documents > Evidence):
  README, script + sha256, MANIFEST, per-point outputs for the fleet and the UNICEF point set, summaries,
  sensitivity runs, and `unicef-tool-data-note.md`. Linked from the provenance and the mapping rules.

## 1 Oct 2026 (b) — managed points without a valid mWater region: documented exception (Adriaan Mol)

Ten managed points carry no valid `admin_region`: 698771103, 698771110, 699596004, 699596114, 698771244,
698771251, 742897074, 742897115, 742897232 (empty) and 670401842 Morafeno (306666, not a row of mWater's
admin_regions table). Reason, as decided: "mWater's boundaries leave these points unassigned (gaps between
polygons). mWater will not set regions by hand, and we will not ask for a platform-wide boundary change
(decision 1 Oct 2026). Commune and fokontany for the 9 Maroantsetra points come from their works records;
Morafeno is placed in Anosy by its GPS."

- Read from mWater (read-only, 1 Oct 2026) before applying: all ten still empty or unresolvable, so none
  left the exception. Of the managed group's 136 distinct region ids, 135 resolve; only 306666 does not.
- `data/admin_region_exceptions.json` holds the ten, the reason and the 135 valid ids. New check in
  check_consistency: no managed point (wp_madavance.csv) with a missing or invalid admin_region outside the
  list, and no listed point that has since gained a valid one. Verified by removing 742897232 from the list:
  the check failed ("1: 742897232 (empty)"); restored.
- The ten are shown in the data-quality notes with the reason. No write to mWater.

## 1 Oct 2026 (c) — transcription check, round 1: Dieu Donné's results ingested (Adriaan Mol)

Dieu Donné Razafimahatratra (MadAvance MERV) transcribed the 83 calendars of series 1 (export 1 Oct 2026). Cleaning
rules, as decided: (a) a mark after the photo date is void, each checked against the year before; (b) calendar 43's
X are the gardien's margin notes, out of grid accuracy; (c) an X whose note calls the sign doubtful counts as ?;
(d) the nine 2027 sheets with no observed day are held out until MadAvance confirms which side was marked;
(e) calendar 3 stays excluded. Applied in `tools/transcription_round1.py`, never in the raw file. Results in
`data/transcriptions/round1_resume.md`; the page carries the block "Transcription check, round 1". No action
status changed; read-only on mWater.

## 1 Oct 2026 (d) — calendar reader: record corrected, machine-read downtime withdrawn (Adriaan Mol)

Transcription round 1: the reader detected 0 of the 40 days both human readers marked X (sensitivity
0%, specificity 99.6%, κ ≈ 0 against either human). Decided: its counts are not evidence of downtime.

- Page: "rarely misses a marked day" replaced with the round-1 result. Withdrawn: the 363.9-day header
  count and tile; "1.1 days not operational" (three paragraphs); the stratum days-operational table
  (portfolio, districts, sheet years, before/after the floor) and its footnote; the visit-frequency
  averages (364.6 / 363.6 / 364.8); the observed-cell marked rate 0.61% and impossible-cell floor 1.22%;
  559 days not operational and 460 unobserved cells called marked; the 2027-sheet marked rates and the
  "in service" argument built on them. Shown instead: the registered 347-day cap as the carbon basis and
  "operational evidence: human transcription only" — X days per observed day for each human and for
  both, labelled a sample of 68 calendars.
- Data: the same fields omitted from data/calendar_extraction_figures.json and
  data/calendar_stratum_figures.json by their generators (tools/reader_gate.py).
- Gate: check_consistency fails on any machine-downtime field or withdrawn figure on either page or in
  those files unless data/reader_validation.json shows sensitivity ≥ 0.90 and specificity ≥ 0.99
  against both-human X days, on all and held-out calendars.
- Older values of the same kind (2.41%, 4.25%, 1.84%, 8.8 days, 356.2 days, "98% of days", 97.6%,
  2,787 t / 3,015 t / 25,121 t) survive only in archived editions, which are left as issued.
- Reader diagnosed and partly fixed (v3); validation does not pass; no full re-run, nothing published
  from it. Detail in docs/transcription_round_notes.md. Read-only on mWater.

## 2 Oct 2026 — provenance follows the scope; panels at full width; calls and what followed; hygiene and gender (Adriaan Mol)

- **Provenance.** Panels split hand-pump + Endur'O figures by scope (MadAvance alone; the Endur'O manual file
  alone; MadAvance + Endur'O = total, each with source and date). Before the fix, 6 tile × scope pairs were wrong:
  "water points in scope" and "people served" under MadAvance — all and MadAvance excl. Marolinta described the
  Endur'O manual file ("covers both: 125,710"), and under All SaniTap showed no MadAvance + Endur'O sum. Across the
  whole page, 648 panel failures in the first check (tools/check_provenance.py) → 0. Partner cards, the smart
  meter, the estate note's Endur'O sentence and the stove-overlap section now carry their own scopes; the action
  list, register trace, carbon data gaps and data-quality notes are marked programme-wide. Gate shown failing by
  making the composite arithmetic print total + 1 (8 failures), then restored.
- **Layout.** Panels open beneath their card row at full width (derivAnchor); table-cell panels open in a
  full-width row (after row spans, pinned to the visible width of a scrolling table); a row expanded inside a long
  table's 60vh scroll box scrolls that box to bring itself into view (the readability rule keeps the box). tools/check_panels.py at 1280/1440/1920: 983 distinct failures on the old
  placement → 0.
- **Calls and what followed** (tools/call_followup.py, data/call_followup.json): table under the activity tiles.
- **Hygiene promotion and gender** (tools/rebuild_hygiene.py, data/hygiene.json): new section; the Hygiene&San
  survey (209cc5fc…) is now pulled (hygiene_san.json). Obligation quoted from ERSDWS v1.0 SDWS 20, the VPA-DD and
  v2.0 SDWS 24. No actions added; gaps listed for Adriaan to decide.
- Extracts re-pulled 2 Oct (read-only) and the weekly rebuild steps run on them; act-moramanga-system-dedupe now
  satisfied from mWater data (duplicates resolved).

## 2 Oct 2026 (b) — Asana is the editable action list; nothing closes without recorded evidence (Adriaan Mol)

- **Asana holds owner, deadline and completion.** Project "H2O4CO2 - CLEAN WATER" (1209455787942089), section
  "Weekly report actions" (1219100994717113): one task per open action, named "<act-id> — <title>", plus the
  completed act-sdws18-james-rulings (121 tasks). Angelo NAHAVITATSARA added as a project member. Owners not in
  Asana (Ralf, Endur'O, Gold Standard, MadAvance, Coddy, Ntsoa — the last two have workspace accounts but were
  treated as not in Asana as instructed) are assigned to Adriaan with a first line "Owner: <name> (not in Asana)";
  15 actions. Map in data/asana_map.json; tools/asana_setup.py is the only script that writes to Asana, and
  re-running it creates nothing twice.
- **The build reads Asana read-only** (tools/asana_pull.py → data/asana_pull.json) and renders owner, deadline and
  completion from it; data/action_owners.json keeps closes-when, type, sources and the new `evidence` record.
  A hand-added task without an act-id gets one from its name and is logged as "new from Asana".
- **Evidence rule.** An action is closed on the page only when a build condition is satisfied this run (data, form,
  children, artefact) or an `evidence` entry is recorded. A task completed in Asana without one shows "done in
  Asana, evidence pending"; an author-closed action without one is reopened. Backfilled from the existing record:
  17 decision-closed actions (data/decisions.json) and 3 hub artefacts. act-mor-re-take-gps-fix was closed with no
  evidence ("supersedes the original action") and is reopened.
- **Gate** tools/check_asana.py (in publish.sh): every open act-id has exactly one task; owner and deadline on the
  page equal Asana; no action closed without evidence. Shown failing by setting act-call-no-followup's due date to
  2026-10-30 in the local copy of the pull (1 failure), then restored (0).
- **Reconciliation** of the 45 earlier open tasks in the project (untouched): data/asana_reconcile.csv —
  1 duplicates, 24 overlap, 20 no match.
- **SDWS 18.** James Walker ruled 1 Oct 2026 09:33 UTC ("Re: Water program dashboard & actions"): six months per
  pump from installation or rehabilitation, every annual round; kit and SOP on file; no paired pump sample under
  v1.0. The section now shows each 2025 pump's works date against its sample date (Fort-Dauphin 10 inside, 0
  outside; Maroantsetra 10 inside, 0 outside; 0 without a works date). The "first passing test / 11 April 2025"
  alternatives are removed. Mq,y's remaining gap moves to act-sdws18-2025-kit-sop.
- New actions: act-sdws18-2025-kit-sop, act-call-no-followup, act-hygiene-campaign-2026, act-jmp-survey-2026,
  act-calendar-human-sample-annual. Weekly call counts are kept in data/call_followup_history.json; the
  two-edition closure metric is uncounted until a second week is on record.

## 2 Oct 2026 (c) — Coddy Velonizy and Ntsoa Ranaivoson own their Endur'O actions in Asana (Adriaan Mol)

- tools/asana_setup.py owner map: Coddy Velonizy (1209012876322233, "IT Assistant") and Ntsoa Ranaivoson
  (1211301105253477, Endur'O director) added, and both made project members. "Endur'O (<person>)" is that
  person (the first named when two are); "Endur'O" with no person named is assigned to Coddy and keeps
  "Owner: Endur'O" as the first description line. The build reads the same map (tools/asana_pull.py imports it).
- Reassigned from Adriaan to Coddy, "Owner: … (not in Asana)" line removed and the owner as written kept
  lower in the description: act-enduro-link-wp-systems (Endur'O, no person: keeps "Owner: Endur'O"),
  act-enduro-onboard-2-register-sites, act-enduro-onboard-7-piped-sdws27, act-moramanga-register-standposts,
  act-tana-baseline-survey (Coddy and Ntsoa both named; Coddy first), act-tana-jirama-licence-filed.
- Still with Adriaan (owner not in Asana): MadAvance, 6 (act-close-eight-2-2, act-confirm-india-mark-capacity,
  act-identify-count-institutional-premises, act-point-use-round-one, act-sdws26-approve-2025,
  act-transcription-round); Ralf van Veenendaal (Curtech), 3 (act-enduro-onboard-5-calibration,
  act-ralf-meter-install-register, act-ralf-shopkeeper-waterpoint-link).

## 2 Oct 2026 (d) — plain titles; tasks matched by gid; MadAvance owners to Angelo and Cathy (Adriaan Mol)

- **Matched by gid.** tools/asana_pull.py places each task by its gid in data/asana_map.json, so tasks can be
  renamed freely. A task added by hand is placed by an unused "[act-id]" tag, or gets an act-id generated from
  its name; either way it joins the map and is logged "new from Asana".
- **Plain titles.** Every action has a "title" in data/action_owners.json (20 rows added for actions that had
  none): what has to happen, starting with a verb, about twelve words at most, codes only in brackets after the
  plain words. Asana task name = "<plain title> [act-id]" (121 tasks renamed from "<act-id> — <old heading>").
  The page shows the plain title as the action's name, with the act-id small and grey after it; the old
  descriptive heading stays as the first sentence of the detail. A task its owner renames gives the action its
  title (copied into the record at the next build). Review list: data/action_titles_review.csv. Gate
  (tools/check_asana.py): every action has a title equal to its task's wording, with no act-id and no code
  outside brackets.
- **Owners.** "MadAvance", "MadAvance field teams" and "MadAvance — transcriber to be named" map to Angelo
  Nahavitatsara; "MadAvance / Cathy" to Cathy Andriambololonirina. Reassigned from Adriaan: act-close-eight-2-2,
  act-confirm-india-mark-capacity, act-identify-count-institutional-premises, act-sdws26-approve-2025,
  act-transcription-round (Angelo); act-point-use-round-one (Cathy). Still with Adriaan: Ralf van Veenendaal's
  three (act-enduro-onboard-5-calibration, act-ralf-meter-install-register, act-ralf-shopkeeper-waterpoint-link).
- **act-transcription-round closed.** Its closes-when is "50 calendars have been transcribed". Round 1 (Dieu
  Donné, 1 Oct 2026; commit 8abf684; data/transcriptions/) transcribed 83, 73 confirmed after cleaning. Evidence
  recorded; Asana task completed. The metric transcription_sheets_done read only the transcription page's own
  store (0) and now also counts round 1.

## 2 Oct 2026 (e) — section first in Asana; household pass rule closed; installation database retitled (Adriaan Mol)

- "Weekly report actions" moved above "Suivi des recommandations/Mision Maro/10-2025" (sections/insert,
  via `tools/asana_setup.py --section-top`); nothing else in the project changed.
- act-pou-form-threshold closed on evidence: Lanja Randriamanantena, "RE: PoU form updated again (piped
  water)…", 1 Oct 2026 14:44 UTC — J1 already applies the protocol rule (a household sample with 5 E. coli per
  100 ml shows "Pass – PoU", a source sample with 5 "Fail – PoC"); only the disabled old question 8 checked
  against 0; the 2025 records stay as entered. The action had assumed the live field checked against 0.
- act-produce-s4-19-cl retitled "Produce the database of all installed boreholes, with households served by
  each" (was "Produce the list of households served by each borehole"), on Gold Standard's clarification
  request CL#2: "Full installation database (till date) with number of households under each specific
  borehole/system shall be uploaded on GS Assurance Platform." Closes-when and detail now say the same.


## 3 Oct 2026 — Endur'O's registered water points read live; Cathy's samples matched to the smart taps (Adriaan Mol)

- **Read.** The Endur'O group (c305b9b85f41417387b553d9a33c795b, named "Enduro" in mWater) was already pulled
  (`enduro_points.csv`, `piped_systems.csv`); tools/rebuild_enduro_registry.py now reads both at every build into
  data/enduro_registry.json (ENDUROREG). The 19 Amboasary gara smart taps are readable: SMARTAP 2–20, codes
  1255186538–1255186727, all typed kiosk, all linked to 1108783583 "Amboasary gara", deviceID in every description.
- **Registered in mWater** (Endur'O card, tools/render_enduro_registry.py): 25 water systems and 203
  water points (203 with GPS, 122 with a photo, 180 with no water system
  set), per scheme with type, GPS and photo. The hand-entered headline (data/enduro_manual.json) stays the headline,
  labelled as such, with the difference shown: systems 131 hand-entered against 25
  registered; register-snapshot points 181 (as at 2026-09-16) against 203.
- **Map.** portfolio.html's Endur'O layer (EDREG) and Moramanga sampling points (MORA) were typed by hand; both are
  now written by tools/render_portfolio.py from the registry. Every registered point with GPS is drawn once. Cathy's
  59 final samples (49 with GPS) form 26 sampling points (samples within
  15 m); 11 lie within 25 m of a registered tap and are drawn on it
  (two taps carry two points each: SMARTAP 7 and SMARTAP 5); 15 stay as sampling points and are listed.
  No sample yet carries a tap code or deviceID.
- **Results stay per system.** Result-form records name only the water system until question 1.2b is used, and their
  timestamps cannot tie a result to a sample, so a tap shows its samples beside its system's results, never results
  of its own.
- **Data quality notes:** SMARTAP 1 missing; all 19 typed kiosk pending Coddy's confirmation they are public tap
  stands; water points without a photo (none of the 19 smart taps has one).

## 3 Oct 2026 (b) — Pre-project eligibility section and gate: 2.2.1(d) and SDWS 12 (Adriaan Mol)

- **Section** "Pre-project eligibility: non-functional or non-potable before the project" (tools/rebuild_eligibility.py
  -> data/eligibility.json, ELIG; tools/render_eligibility.py), scope-aware, before Register corrections.
- **Hand pumps:** every managed pump's first-rehabilitation record — control ea3e342a (out of order > 3 months),
  photographs a4d23938, works date, response link. 728 of 745 carry the control answered Yes (693 with
  photographs, 35 without); Fort-Dauphin 2 answered No; Maroantsetra 1 blank and 1 with no first-rehabilitation
  record (782134540, the recorded exception); Marolinta 13 on the borehole-progress form, which has no such control.
  The eight 2.2.1(d) flags (3 No, 5 blank) are listed as gaps; 3 of those pumps are in the managed fleet.
- **Piped systems:** per system in data/piped_systems_status.json, results dated before the protocol went live
  (22 Sep 2026 15:58 UTC) or before works completion. Amboasary gara: 43 pre-project results, 38 with E. coli above
  0 per 100 ml — eligible: non-potable shown; framed as pre-project evidence of need, not a failure of a managed
  system. Ambohibola, Amboanjo, Andilanatoby and the managed Tana kiosk (1125843376): no pre-project test. The kiosk
  has no water-quality test at all; it stands in the managed figures as a listed exception (admitted by decision
  25 Sep 2026).
- **Gate** (check_consistency.py): every managed and carbon pump needs the control answered Yes, a listed exception
  (data/eligibility_exceptions.json) or a 2.2.1(d) flag; every managed piped system needs a failing pre-project
  result or a listed exception. Shown failing by emptying the exceptions list (782134540 and 1125843376 fail),
  then restored.
- Not done: the Asana tasks act-piped-baseline-other-systems and act-amboasary-post-works-retest — the project
  inbox files with their titles and owners were not found on this machine.

## 4 Oct 2026 — Adriaan Mol: eligibility Yes without a photo, the Tana kiosk exception, one explanation box at a time

- **Yes without a photo passes the eligibility gate.** A Yes on the 3-month out-of-order control (2.2.1(d)) without
  a photograph counts as eligibility evidence. The 35 pumps stay visible in the eligibility section as their own
  status, "Yes, no photo", with their own count in the summary line (data/decisions.json `elig-yes-no-photo`).
- **Tana kiosk (1125843376) approved as a listed exception** in data/eligibility_exceptions.json, with the reason
  exactly as given: "Commissioned 14 Sep 2026 with no pre-project water quality test; admitted by Adriaan's
  decision of 25 Sep 2026; post-works test tracked under act-enduro-onboard-6-kiosk-wq."
- **Two actions added, with Asana tasks** in "Weekly report actions": act-piped-baseline-other-systems (Coddy,
  Cathy collaborating; due 24 Oct 2026 and in any case before each system's works completion) and
  act-amboasary-post-works-retest (Cathy, Coddy collaborating and confirming the completion date; due completion
  date + 30 days, no date in Asana until Coddy gives it). Both close on evidence. This completes the item left
  open on 3 Oct.
- **Explanation boxes:** one "How this figure is produced" box at a time, for the figure last clicked; a click on
  another figure replaces it, a second click on the same figure closes it. The active figure is outlined and the
  box opens with "Explains: <figure and its label>". Gated in tools/check_panels.py.

## 5 Oct 2026 — Adriaan Mol: managed figures count only the managed portfolio

- **Found** (investigation, 5 Oct): at All SaniTap the tiles read 876 water points and 271,710 people served —
  745 managed hand pumps + 131 Endur'O programme sites from data/enduro_manual.json, and the SDWS 1 run's 125,710 +
  146,000 hand-entered people whose source is "not recorded". None of the 131 has a status in
  data/piped_systems_status.json, so the 25 Sep join rule never saw them; the gates checked only that the 131 was
  carried consistently, and check_provenance passed the composite because its arithmetic added up.
- **Decided:** "water points in scope" and every managed figure add only managed hand pumps plus systems with status
  "managed" in data/piped_systems_status.json; people served come only from the SDWS 1 method at its pinned commit.
  The 131 and 146,000 stand on the Endur'O card only, labelled "Endur'O programme sites, not in the managed
  portfolio", with their sources as recorded (146,000: source not recorded). data/decisions.json
  `managed-figures-2026-10-05`.
- **Figures, before → after:** All SaniTap 876 → 746 points, 271,710 → 125,710 people (+ the kiosk, not yet
  allocated); MadAvance — all 745 / 125,710 and excl. Marolinta 732 / 124,356 unchanged; Marolinta only unchanged
  (works basis: 13 points, 3,130 people, a field count); Endur'O 131 → 1 point, 146,000 → not yet allocated.
- **Gate:** tools/check_managed.py, run inside check_consistency.py — no ENDURO.systems / ENDURO.people / MF in page
  code; in every scope no programme figure outside the Endur'O card, water-points figures = managed hand pumps in
  scope + managed piped systems, people-served figures = the SDWS 1 allocation (WPOP) over the points in scope or
  "not yet allocated", and no managed input whose source is "not recorded". check_provenance.py fails a managed
  figure whose composite names the hand-entered file. Shown failing on the page as published (6 of the new
  checks; 13 provenance failures), passing after the fix.
- **Open:** act-enduro-people-source stays open; act-kiosk-sdws1-run (Adriaan, 17 Oct 2026) added. The Marolinta
  scope's people figure is a field count from the works records, not an SDWS 1 allocation; the gate checks its
  source only and leaves the counts to a decision.

## 5 Oct 2026 (b) — Adriaan Mol: people served from the SDWS 1 run in every scope, Marolinta included

- **Decided:** the Marolinta-only scope shows the SDWS 1 allocation as people served, like every other scope. The
  works-record field count stays as a secondary line, "field count from works records, not the people-served
  method" (data/decisions.json `people-served-sdws1-every-scope-2026-10-05`).
- **Figure:** Marolinta only, people served 3,130 (field count) → 1,354, the SDWS 1 allocation over its 13 points
  (the run's per-point file, ~/sdws1/runs/fleet_20261001/barriers/sdws1_population_equal.csv, and WPOP on the page
  agree: 13 points, 1,354 of 125,710; 125,710 − 124,356 = 1,354). The 3,130 is shown beside it as the field count.
  Tile, partner table, impact line and the box updated.
- **Gate:** tools/check_managed.py now applies the people-served check in the Marolinta-only scope and checks the
  tiles add up (MadAvance — all = excl. Marolinta + Marolinta only; All SaniTap = MadAvance — all while the kiosk
  is not yet allocated). On the published page it failed (Marolinta only 3,130 against 1,354 in the tile, partner
  table and impact line; 124,356 + 3,130 ≠ 125,710); after the fix it passes.

## 5 Oct 2026 (c) — Adriaan Mol: an Asana tick closes nothing without evidence

- **Decided:** a task counts as closed only if it is completed **and** carries evidence — a comment starting
  "Evidence:" or an attached file (data/decisions.json `asana-evidence-2026-10-05`).
- **Built:** tools/asana_pull.py reads each completed task's history, comments and attachments; the evidence (text
  or file name, author, date, task link) goes into data/action_owners.json `evidence`, marked `from: asana`, never
  over a repository entry. A tick without evidence shows in amber, "ticked in Asana, no evidence yet — by <who>,
  <date>", stays open in every count, and after 7 days (build_config `actions.ticked_no_evidence_days`) is listed
  under "Ticked without evidence" for Adriaan. Every closed action shows an evidence line linked to its task.
  tools/check_asana.py fails a closed action without an evidence source (Asana comment or file, repository entry, or
  build condition) or without its evidence line, and a tick shown as closed or without the amber mark.
- **Tested:** act-deichmann-ar-send (completed 5 Oct, Evidence comment by Adriaan Mol) closes on that comment; it was
  added to the report as an action, mirrored from its Asana task. act-sdws18-james-rulings, act-pou-form-threshold
  and act-transcription-round are completed in Asana with no Evidence comment or file; each keeps the evidence
  recorded in the repository on 2 Oct (and the first and last a satisfied build condition), so each stays closed,
  now with its evidence line. In a scratch copy, the Deichmann task stripped of its comment stayed open in amber and
  entered the 7-day list; forcing it closed failed the check four ways; removing an evidence line failed it.
- New Asana tasks' descriptions say how to give evidence; existing task descriptions were not edited.

## 6 Oct 2026 — Adriaan Mol: the non-calendar photographs stay where they are

- **Decided:** the 193 photographs filed on a calendar question that are not calendars stay where they are in
  mWater; nobody moves them. The report keeps excluding them using the reviewed list,
  data/calendar_not_calendar.csv (new `review` column). No "left to fix" count is kept
  (data/decisions.json `act-photo-misfiled`).
- **Restored:** 13 of the 206 flagged photographs are real calendars (by eye, 6 Oct 2026). They are marked
  "confirmed calendar (by eye, 6 Oct 2026)" and count in every calendar figure again; the other 193 are marked
  "reviewed: not a calendar, left in place by decision 6 Oct 2026".
- **Cause fixed instead:** hints in English and French added on 6 Oct to the calendar photo questions
  (preventive maintenance de26d89a: 2.15.5, 2.15.6; repair 958b4763: 1.3.1.3); Angelo briefs the teams
  (act-calendar-photo-briefing, Asana 1219205037087065, due 23 Oct).
- **Closed:** act-photo-misfiled, now a decision-kind action closing on this entry; the photographs_misfiled
  metric is retired. Reviewed list: Central Data Hub - Water Documents/Evidence/mWater/misfiled-photos-2026-10-06.xlsx.

## 6 Oct 2026 (b) — Adriaan Mol: form 0ac68d82 (piped water quality result) changed in the designer

- Made by hand in the mWater designer: 1.2.2 sampling date required again; arsenic and fluoride accept 0 (≥ 0);
  manganese calculation threshold 0.05 instead of 0.5 (data/decisions.json `form-0ac68d82-designer-2026-10-06`).

## 7 Oct 2026 — Adriaan Mol: Coddy Velonizy's Asana tasks move to coddy.velonizy@enduro.mg

- Coddy cannot use the old MadAvance account "IT Assistant" (coddy@madavance.org, 1209012876322233). He is now
  coddy.velonizy@enduro.mg (1219154315843358), a guest in the sanitap.org workspace and an editor on
  H2O4CO2 - CLEAN WATER. tools/asana_setup.py `CODDY` is the new gid; `CODDY_OLD` is kept in NAME_OF only, so
  the completed tasks left on the old account still read as Coddy Velonizy.
- Moved, all open: act-enduro-link-wp-systems, act-enduro-onboard-2-register-sites,
  act-enduro-onboard-7-piped-sdws27, act-moramanga-register-standposts, act-tana-baseline-survey,
  act-tana-jirama-licence-filed, act-naturano-import-failing, act-enduro-mwater-import-integration,
  act-coddy-slack-days-card-price, act-piped-baseline-other-systems, act-smartap-register-complete,
  act-enduro-nanisana-firmware. Follower added: act-amboasary-post-works-retest, "Sous-activité 3.2 Gestion de
  stock", "Préparer un courte note … roof count". Completed tasks and work outside the project stay on the old
  account (data/decisions.json `asana-coddy-account-2026-10-07`).

## 7 Oct 2026 (b) — Adriaan Mol: repair records are not a days-operational source; the form consolidation was settled on 22 Sep

- **act-define-maintenance-record-becomes — retired.** Days operational (SDWS 27) is evidenced by the gardien
  calendars (the operation-and-maintenance log) and the annual human transcription sample
  (act-calendar-human-sample-annual), not by converting repair records. Reconciling the two would double-count travel
  and repair days in remote areas for no gain. Repair and call-centre records stay operational records (repair time,
  dispatch). The SDWS 27 note under the calendar dimensions table no longer says days are computed from "the
  maintenance history" or that "the repair records show the days deducted".
- **act-form-consolidation — settled 22 Sep 2026.** The merge rested on a wrong premise: 86cf66ef is the retired
  combined form, not the standard works form, and every branch has its own live form. The Marolinta borehole form
  8764843c was rebuilt in place (revision 261 to 268); wording and validations finished 30 Sep 2026.
- Both closed in Asana by Adriaan Mol with an Evidence comment (7 Oct 2026, 08:20 UTC); data/decisions.json carries
  both answers, and data/action_conditions.json states each closing rule as the logged decision, so the build keeps
  them closed.
- Evidence recorded in the repository for two tasks Adriaan ticked on 7 Oct with the evidence in an ordinary comment
  (not starting "Evidence:"): act-coddy-naturano-card-spec and act-enduro-nanisana-sellthrough, both on Coddy's
  email "Re: Nanisana (R129)...", 6 Oct 2026. Angelo's tick on act-deichmann-ar-marolinta-photos (7 Oct, 02:30 UTC)
  has no comment or file and is left without evidence.

## 7 Oct 2026 (c) — Adriaan Mol: the SDWS 25 annual independent cross-check is INSTAT RGPH-3

- **Source.** INSTAT RGPH-3, census of June 2018, the most recent official household size by region. Anosy 4.3
  (Tome 1, Tableau 26, p.41), Taolagnaro district 4.3 (Tome 2, Tableau 14, p.160), urban commune of Fort Dauphin
  4.0 (Tome 2, Tableau 16, p.213); Analanjirofo 3.6 (Tableau 26, p.41), Maroantsetra district 3.6 (Tableau 14,
  p.159), urban commune of Maroantsetra 3.3 (Tableau 16, p.195).
- **Checked first, in the order asked.** INSTAT TBSE December 2025: the Analanjirofo edition (Tableau 4, PDF p.20)
  reprints the 2018 census sizes and prints 3,5 for the region, where the census counts round to 3.6; no Anosy
  edition exists. EDS-V 2021 (household composition table) gives national 4.3, urban 4.0 and rural 4.4 only. MICS6 not needed.
- **Comparison with the November 2025 survey** (people per premises): Fort-Dauphin 4.47 is +0.17 (+4%) above Anosy
  and Taolagnaro and +0.47 (+12%) above the town; Maroantsetra 3.66 is +0.06 (+2%) above Analanjirofo and the
  district and +0.36 (+11%) above the town. The census counts people per ordinary household, the survey people per
  premises. No census figure is scaled for growth: growth changes the number of households, not their size.
- Added to the SDWS 25 section (`#sdws25-crosscheck`), with the official figures declared in PARAMS. The PDFs are in
  Central Data Hub - Water Documents/Evidence/SDWS25 household size/. act-find-source-annual-independent closed;
  Evidence comment on Asana task 1219101058285868.
- **Not changed:** the SDWS 25 section still says people per premises is taken from RGPH-3 national rural 4.3 (the
  hh_size_rural parameter, confirmed with James Walker on 18 Sep 2026), while the model's registered values (4.5 /
  3.7) come from the project survey. Which one is the value of record is left for Adriaan and James.
