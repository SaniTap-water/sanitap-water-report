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
