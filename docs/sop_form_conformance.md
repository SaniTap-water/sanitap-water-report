# SOP statements against the live mWater forms

**Swept 20 September 2026.** Every current SOP in `Water Documents/SOPs/` was read for
statements about what an mWater form captures or requires, and each statement that makes a
checkable claim was compared against the live form design fetched the same day.

This exists because of a specific failure. `SOP-MAD-SDWS27-CalendrierGardien` chapter 11 stated
that the calendar photograph field was mandatory in mWater. It never was: `2.15.6` on the
preventive-maintenance form carried `required: false` from the day it was written until it was
changed on 20 September 2026. Nothing detected the gap, because nothing had ever compared a
sentence in a procedure with the form it describes. The question this file answers is whether
that was one mistake or a pattern.

**It was a pattern.** Nine discrepancies, five of them touching carbon evidence. **Five are now resolved** — D1, D2, D5, D6 and D7 — and the three that remain are decisions, not form edits.

## What was swept

| | |
|---|---|
| SOP documents swept | **15** (current versions; superseded `CalendrierGardien` v1.0–v1.2 and tracked-change copies excluded) |
| Live mWater forms compared | **12** (the SaniTap *Clean Water* operational family) |
| Questions across those forms | **748** |
| Paragraphs mentioning a form, field, question or requirement | **233** |
| Statements making a checkable claim | **77** |
| Statements resolvable to a specific form, field or requirement | **25** |
| — conform | **16** |
| — discrepancy | **9** |
| — resolved since the sweep | **5** |

The remaining 52 checkable statements name no specific field — *"compléter exhaustivement le
questionnaire mWater"* and similar. They are instructions to staff, not claims about a design,
and there is nothing in a form to compare them against.

## Live forms as fetched

| form | id | `_rev` | state | deployments | questions |
|---|---|---|---|---|---|
| preventive-maintenance | `de26d89a5c8a4452b42158c622be20d0` | 501 | active | 4 | 83 |
| repair-after-breakdown | `958b4763788348d699e7d8c5821f92ee` | 389 | active | 4 | |
| old-combined-works | `86cf66efdd3749dd8a121314bab3675a` | 1022 | active | 4 | |
| point-of-use-survey (SDWS 18) | `db0bcbf2e7ea44b280aed653a715553e` | 118 | active | 4 | |
| water-quality-result-sdws3 | `7b33c5d7e5074808a94915939a5a0783` | 121 | active | 2 | |
| water-quality-sampling-sdws3 | `43c96af4bc4240c0b5c4402383b9c539` | 184 | active | 2 | |
| stroke-meter | `8be8e0384709433795d2d0197e98275f` | 191 | active | 3 | |
| call-centre | `c08b3fe26d0f42c084074701f29eb75e` | 473 | active | 4 | |
| hygiene-promotion | `283c5670de82489d833e986cb76a67d8` | 224 | active | 4 | |
| beneficiary-roof-count | `8aa2dd78eb1f460f8f43db7935955846` | 28 | active | 2 | |
| marolinta-borehole-progress | `8764843c94484f5b984078c68f13b2ca` | 261 | active | 2 | |
| *première réhabilitation* | `63747997e70e478fbb2ebf71581ceeb0` | 298 | active | 3 | |

## Statements that conform

| # | SOP | statement | live form |
|---|---|---|---|
| C1 | CalendrierGardien v1.4 §8 | the calendar photograph belongs on field `2.15.6` of the preventive-maintenance form | exists, `ImagesQuestion` |
| C2 | CalendrierGardien v1.4 §8 | `2.15.5` is the supplementary calendar-photograph field | exists, `ImagesQuestion` |
| C3 | CalendrierGardien v1.4 §8 | `2.15.7` records the year the sheet documents, as a whole number | exists, `NumberQuestion`, `decimal: false` |
| C4 | CalendrierGardien v1.4 §8 | all three sit in question group `d5233b2b` | confirmed |
| C5 | CalendrierGardien v1.4 §8 | the form is `de26d89a5c8a4452b42158c622be20d0` | confirmed |
| C6 | CalendrierGardien v1.4 §11 | `2.15.6` is mandatory | **now true** — `required: true`, conditional on `2.15.5bis = Oui` (changed 20 Sep 2026; this is the statement that was false) |
| C7 | CalendrierGardien v1.4 §11 | `1.3.1.3` on repair-after-breakdown is mandatory | `required: true` |
| C8 | PMH_112025 | form *"Clean Water \|\| Appel maintenance préventive et signalement des pannes"* exists | active, 4 deployments |
| C9 | PMH_112025 | form *"Clean Water \|\| Réparation après panne \|\| Survey \|\| Actif"* exists | active, 4 deployments |
| C10 | PMH_112025 | form *"Clean Water \|\| Maintenance préventive régulière \|\| Survey \|\| Actif"* exists | active, 4 deployments |
| C11 | Techniciens_réhabilitation | a questionnaire *« Première Réhabilitation »* is available | active, 3 deployments |
| C12 | SOP pour les Socio-Orga | module *« Formation/suivi promotion hygiène »* exists | active, 4 deployments |
| C13 | WQ Protocol v2.3 Annex B | `A1` test type is required | `required: true` |
| C14 | WQ Protocol v2.3 Annex B | `A8` supply type is required and drives later questions | `required: true`, conditional |
| C15 | SOP Compteur_Canzee | a photograph of the meter is mandatory | `3.4.1` `required: true` |
| C16 | SOP Compteur_Canzee | a photograph of the displayed index is mandatory | `3.4.2` `required: true` |

## Discrepancies

### D1 — the calendar group holds five fields, the SOP describes three
**Carbon evidence: yes.** `CalendrierGardien` v1.4 §8 says *"Trois champs distincts y
concourent"*. After the 20 September change the group holds five: `2.15.5`, `2.15.5bis`
(calendar present?), `2.15.5ter` (why absent?), `2.15.6`, `2.15.7`.
**Resolved in this pass** — SOP reissued as v1.5.

### D2 — `2.15.7` is described as mandatory and is optional
**Carbon evidence: yes.** `CalendrierGardien` v1.4 §8 says the year field is *"Obligatoire dès
qu'une photographie est déposée au champ 2.15.6"*. Live: `required: false`, no condition. The
optional setting is deliberate — stock already hanging carries no handwritten year, and a
required field would force an invented one — but the SOP asserted the end state as though it
were the current one. That is exactly the defect this sweep exists to find.
**Resolved in this pass** — SOP v1.5 states the field is optional until
[`act-mwater-year-required`](../index.html#act-mwater-year-required) lands.

### D3 — the decommissioning SOPs describe an mWater field that does not exist
**Carbon evidence: yes.** `SOP-Suppression_Points_d'Eau` and `SOP for Decommissioning Water
Points` both describe *"App mobile mWater (formulaire de suivi personnalisé avec champ « jours
d'inactivité »)"*. No question matching *inactivit* / *days of inactivity* exists on any of the
eleven live forms. Retirement decides which points are in the register, and the register is the
denominator of every carbon figure on the report, so a retirement rule that runs on a field
nobody can fill is a gap in the population, not a clerical one.
→ [`act-decommission-inactivity-field`](../index.html#act-decommission-inactivity-field)

### D4 — household consent is a protocol step and an optional, unanswered field
**Carbon evidence: yes.** The Water Quality Testing Protocol v2.3 makes consent a numbered step:
*"explain the test to an adult member of the household, obtain consent on the mWater form"*. On
the point-of-use form the field exists — `A4`, *"Household consent obtained?"* — but it is
`required: false` **and** conditional, and it carries **0 answers in 142 responses**. The form
cannot produce consent evidence even when staff follow the protocol exactly.
→ recorded on [`act-v2-nonclaiming`](../index.html#act-v2-nonclaiming), which already carries the
individual-level consent gap; this is the mechanism behind it.

### D5 — the calendar photograph is unconditionally mandatory on repair-after-breakdown
**RESOLVED 21 September 2026.** `1.3.1.2bis` (presence, required) and `1.3.1.2ter` (reason,
optional, shown on *No*) were added immediately before `1.3.1.3`, and `1.3.1.3` is now required
conditional on presence = *Yes*. Form `_rev` 389 → 390.
**Carbon evidence: yes.** `1.3.1.3` is `required: true` with no condition. A repair visit to a
point that has no calendar on the wall cannot be closed without a calendar photograph, so the
technician photographs something — and **206 of the calendar photographs on file are not
calendars**, of which a share sits on `1.3.1.3`. This is the same trap that `2.15.6` was in
until 20 September, one form across.
→ [`act-photo-conditional-on-presence`](../index.html#act-photo-conditional-on-presence)

### D6 — `2.15.5` is unconditionally mandatory on preventive-maintenance
**RESOLVED 21 September 2026.** `2.15.5bis` and `2.15.5ter` were moved ahead of `2.15.5` — a
question whose answer gates another has to be asked first — and `2.15.5` is now required
conditional on presence = *Yes*. Form `_rev` 501 → 502.
**Carbon evidence: yes.** Same shape, one field earlier: the supplementary calendar-photograph
field is `required: true` with no condition, so a visit to a point with no calendar still demands
*"photos illustrating the calendar"*. Folded into the same action as D5.

### D7 — six more duplicated codes, on three other forms
**RESOLVED 21 September 2026.** All six reassigned, codes only: `1.6.3.1`→`1.6.3.5`,
`1.6.3.2`→`1.6.3.6`, `2.2.3`→`2.3.2` on premiere-rehabilitation (`_rev` 298 → 299);
`2.1.11.2`→`2.1.11.3`, `2.4.2.2`→`2.4.1.2` on repair-after-breakdown (`_rev` 390 → 391);
`5.4`→`5.5` on stroke-meter (`_rev` 191 → 192). No question code is now reused within any of the
twelve forms, and `tools/check_consistency.py` asserts that on every build.
**Carbon evidence: yes, on one.** Export column headers collide wherever a code is reused. Six
codes are duplicated across three forms, twelve questions in all:

| form | codes | questions affected |
|---|---|---|
| `premiere-rehabilitation` | `1.6.3.1`, `1.6.3.2`, `2.2.3` | 6 |
| `repair-after-breakdown` | `2.1.11.2`, `2.4.2.2` | 4 |
| `stroke-meter` | `5.4` | 2 |

Two of these are the same defect as the one cleared on the preventive-maintenance form on
20 September: a Canzee and an India-Mark variant of the same question sharing one code
(`1.6.3.1` is *"water leaks or cracks"* on one pump type and *"fasteners in good condition"* on
the other). repair-after-breakdown carries `1.3.1.3`, a calendar evidence field, so its exports
feed the evidence pack. None of the six is cleared.
→ [`act-duplicate-codes-sweep`](../index.html#act-duplicate-codes-sweep)

### D8 — meter photographs are required more broadly than the SOP says
**Carbon evidence: no.** `SOP Compteur_Canzee` makes the meter and index photographs mandatory
*"pour les compteurs non calibrés ou nouvellement installés"*. Live, `3.4.2`, `5.2` and `5.6` are
`required: true` with no condition — mandatory on every response. The form is stricter than the
procedure, which costs technician time but loses no evidence. Recorded, no action.

### D9 — the emergency-event SOP names a form that does not exist
**Carbon evidence: no, but SDWS 3 evidence: yes.** `SOP Emergency_event_SDWS3` states that a
questionnaire *« Emergency event SDWS3 »* is available in mWater and that the team leader records
all cleaning and bacteriological-analysis information in it.

This was the one row the first sweep could not verify, because the form listing appeared to
return only 200 forms. **It does not.** The listing returns **741** forms; the 200 was a display
cap inside the reporting tool, not a limit on the fetch, and the note saying so was being
discarded. Paged to exhaustion and searched:

| search | forms found |
|---|---|
| `emergency` | **0** |
| `nettoyage` | **0** |
| `chloration` | **0** |
| `sdws` | 5 — two *Piped Water* SDWS 3 forms, two *Clean Water* SDWS 3 forms, one *Clean Water* SDWS 18 form. None is an emergency-event form. |
| `urgence` | 1 — *"Urgence: Evaluation et Suivi des reparations des infrastructures - SAEP"*, a piped-scheme repair assessment, unrelated |

**The form does not exist.** An SOP that routes emergency cleaning and bacteriological results
into a form nobody can open means those results are either recorded somewhere unmanaged or not
recorded at all, and SDWS 3 emergency events are exactly the situation where evidence is most
likely to be needed later.
→ [`act-emergency-event-form`](../index.html#act-emergency-event-form)

<span id="paging-note"></span>**A note on the earlier claim.** The first version of this file
said the listing was "demonstrably partial" and that its silence proved nothing. That was wrong,
and it was wrong in the direction that let a gap stay open: the tool was reporting the truncation
plainly in a line that was being stripped before it was read.

## How to re-run this

The sweep is not yet automated end to end; the extraction is, the judgement is not. What **is**
enforced on every build, in `tools/check_consistency.py` block 7ai:

* the calendar presence question, the absence-reason question and the required-when-present
  condition are still on **both** forms as described here;
* no question code is reused within any of the twelve forms;
* every snapshot form is still active and preventive-maintenance is still deployed to all four
  districts;
* **the snapshot is no more than seven days old**, and the page says the date it was read.

`tools/publish.sh` refreshes the snapshot from mWater before it gates, wherever the network and
credentials are available, and says so in its output. Where they are not, it falls back on the
committed snapshot and prints its age rather than skipping the check — and once that age passes
seven days the checker fails the build outright. Being offline is allowed; publishing a week-old
claim about a live form is not.
