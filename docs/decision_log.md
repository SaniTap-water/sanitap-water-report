# Decision log

Decisions that change how a figure on the report is produced or what it means. One entry per
decision, dated, with the reasoning and what followed. Analysis lives in its own file where there
is one; this is the index and the record of what was settled and when.

Nothing here is described as closed. A decision records what was decided; whether a carbon
position is closed is the Head of Carbon's call.

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
