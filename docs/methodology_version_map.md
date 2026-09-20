# ERSDWS v1.0 → v2.0 divergence register

Compiled 20 September 2026 by reading both methodologies end to end:

- `429_V1.0_ERSDWS_Emission-reductions-from-Safe-Drinking-Water-Supply.pdf` (sha256 `c709c093…`)
- `429_V2.0_PAA-M400-12_Emission-reductions-from-Safe-Drinking-Water-Supply.pdf` (sha256 `4eb9050b…`)

**v1.0 governs the current crediting period.** v2.0 §3.3.1: *"The date of entry
into force is 90 days from the publication date of this methodology"* —
approximately 7 October 2026 — and §3.3 contains nothing else: no grandfathering
clause and no provision for activities already registered. The only
version-transition provision in either document is §17.1.1: *"At the renewal,
the activity developer shall apply the latest version of this methodology
available at the time of submission for renewal."* **v2.0 therefore applies at
renewal.** See `docs/sdws27_basis.md` for the clauses in full.

This register lists only what touches **what we collect, compute or evidence**.
Editorial changes ("project" → "activity" throughout, section reordering) are
not listed. `action_now = yes` means something must change in collection or
record-keeping **before** renewal, or a required series will have a hole in it
that cannot be filled retrospectively.

| # | Area | v1.0 | v2.0 | What changes for us | action_now |
|---|---|---|---|---|---|
| 1 | **Parameter renumbering** | 𝑀𝑞,𝑦 SDWS 18; 𝑓𝑁𝑅𝐵 SDWS 21; 𝑋𝑐𝑙𝑒𝑎𝑛𝑏𝑜𝑖𝑙 SDWS 22; 𝑄𝑚,𝑦 SDWS 23; 𝑄𝑃𝑊𝑝 SDWS 24; 𝐻𝑁𝑝,𝑦 SDWS 25; 𝐻𝐻𝑝,𝑦 SDWS 26; **𝐷𝑂𝑝,𝑦 SDWS 27**; 𝑁𝑝,𝑦 28; 𝑈𝑝,𝑦 29; 𝑡𝑝,𝑦 30; 𝐷𝑃𝑝,𝑦 31; 𝐷𝑁𝑝,𝑦 32; 𝑃𝑝,𝑓,𝑦 33; 𝐸𝐶𝑝,𝑦 34; 𝐿𝐸𝑦 35 | 𝑀𝑞,𝑦 SDWS 22; 𝑓𝑁𝑅𝐵 SDWS 25; 𝑋𝑐𝑙𝑒𝑎𝑛𝑏𝑜𝑖𝑙 SDWS 26; 𝑄𝑚,𝑦 SDWS 28; 𝑄𝑃𝑊𝑝 SDWS 29; 𝐻𝑁𝑝,𝑦 SDWS 30; 𝐻𝐻𝑝,𝑦 SDWS 31; **𝐷𝑂𝑝,𝑦 SDWS 32**; 𝑁𝑝,𝑦 33; 𝑈𝑝,𝑦 34; 𝑡𝑝,𝑦 35; 𝐷𝑃𝑝,𝑦 36; 𝐷𝑁𝑝,𝑦 37; 𝑃𝑝,𝑓,𝑦 38; 𝐸𝐶𝑝,𝑦 39; 𝐿𝐸 40/41 | Every SDWS number in our SOPs, monitoring plan, mWater forms and this report is written against v1.0. Nothing collected changes; every citation does. Mapping maintained here and reapplied at renewal. | no |
| 2 | **v2.0 §3.4.3 cross-reference is wrong** | §2.3.3 requires the O&M log, no parameter cross-reference | §3.4.3: *"This log is required during monitoring (SDWS 31)."* SDWS 31 is 𝐻𝐻𝑝,𝑦, the premises count; the log belongs to SDWS 32 | An error in the published methodology, not in our reading. Record it so a verifier reading §3.4.3 and our documents together is not confused. Worth reporting to Gold Standard. | no |
| 3 | **Days-operational cap wording** | SDWS 27 QA/QC: *"Values higher than 347 days may only be applied when option 1 is used."* | SDWS 32 Treatment of uncertainty: *"Values higher than 347 days (95% of days) may only be applied when Option 1 (sensor) is used. Uncertainty is managed by this conservative cap when relying on manual logs."* Option 2 is a log *"detailing uptime and downtime"* | Same effect, stated more plainly. Already applied: DO = min(347, log). | no |
| 4 | **Minimum sample size** | §4.2.2: *"for proportion parameter values, a minimum sample size of 30, or the whole group size if this is lower than 30, must always be applied"* | §14.5.3: *"A minimum sample size of 50 shall be selected for any given sample group or stratum. If the population size is less than 50, the entire population shall be surveyed (census)."* Also *"A minimum sample size of 50 units/households is required for any WCFT campaign"* | **30 becomes 50 per stratum.** The SDWS 27 sensor sample we scoped at 30 per district (60 units) becomes **50 per district (100 units)** if drawn after renewal. The calendar validation round at 34 sheets meets v1.0 and would not meet v2.0. | **yes** |
| 5 | **Mandatory conservativeness on sampling** | No equivalent. 90/10 required; no stated consequence of missing it | §14.5.4: *"If the 90/10 precision target is not met, the application of statistical conservatism (Lower/Upper Bounds of the 90% CI) is mandatory."* §7.4.2(b): the Lower Bound is used for 𝑀𝑞,𝑦 and 𝑈𝑝,𝑦 | We must retain **confidence intervals**, not just point estimates, for every sampled parameter from now on. A historic series of means alone cannot demonstrate which branch applies at renewal. | **yes** |
| 6 | **Double counting and end-user non-claiming** | No equivalent parameters | SDWS 18 *"Evidence of avoidance of double counting or double claiming with other parties directly involved"*; SDWS 19 review of other schemes; **SDWS 20** *"Evidence that end-users have been informed and notified that they cannot claim emission reductions from the activity"*, sourced from *"Transaction paperwork; Distribution records; Contracts with end-users"*, and *"The evidence shall be provided and verified before the first verification"* | **Nothing of this is collected today.** For a CWS the counterpart is the community: the Community Engagement Agreement must carry a clear written non-claiming assertion. Agreements signed without it cannot be fixed retrospectively. | **yes** |
| 7 | **Embodied-emissions leakage** | Leakage assessed under §3.8; embodied emissions not a source | **SDWS 21** 𝐸𝐹𝑒𝑚𝑏𝑜𝑑𝑖𝑒𝑑,𝑑𝑒𝑓𝑎𝑢𝑙𝑡, *"Default cradle-to-gate embodied-emissions deduction applied once per new activity-technology unit or system"*; Table 9 gives **rehabilitation 1,000** kg CO₂e per system, new borehole/mechanised 4,500. **SDWS 41** 𝑁𝑑𝑖𝑠𝑠𝑒𝑚𝑖𝑛𝑎𝑡𝑒𝑑,𝑦 counts new units per year | A one-off deduction per rehabilitation. On ~736 rehabilitated points that is of the order of **736 tCO₂e**. It is charged in the **year of commissioning**, so we need a defensible **per-year count by technology category** — which we do not currently maintain as a monitoring output. | **yes** |
| 8 | **Stove stacking** | No equivalent | **SDWS 27** *"Presence of Stove Stacking… Data on the presence and usage practices of baseline and other non-activity technology by activity technology end users"*, annual, via standardized survey | A new annual survey parameter feeding activity and leakage emissions. If the question is not in the annual survey now, there is **no time series** at renewal. | **yes** |
| 9 | **Stroke test as a recognised method** | SDWS 23 offers flow meter or operation sensor only. No alternative-methods option | **SDWS 28 Option 3** *"Alternative Methods (Handpumps only): If Options 1/2 are infeasible/inappropriate/prohibited, recognized methods/proxies (e.g., standardised stroke tests) are permitted. Requires robust justification and VVB validation. Measurement may be on a sampling basis"*, and *"For Option 3, the developer shall validate the proxy against a direct measurement (Option 1 or 2) quarterly"* | **This settles the numbering question in our own stroke-test SOP** — under v2.0 the stroke test is SDWS 28 Option 3, not SDWS 27 Option 3. **The quarterly validation does NOT bind our route.** The clause reads *"For Option 3, the developer shall validate the proxy against a direct measurement (Option 1 or 2) quarterly"* — expressly scoped to Option 3, and Option 2 is one of the direct measurements Option 3 is validated *against*, so it cannot be the thing validated. The frequency row confirms it: *"Continuously (Options 1 & 2) or Periodically (Option 3/Sampling)"*. **The StrokeMeter logger is an Option 2 sensor, so the quarterly requirement does not reach it**, and the plan's annual re-verification of the fleet conversion factor stands. Two further findings while reading this box: v2.0 **names our instrument** — *"Operation sensors (e.g., stroke counters)"*; and v2.0 **contradicts itself on Option 3**, requiring revalidation *quarterly* in the frequency row and *"annually"* in QA/QC. The stroke-test SOP still needs renumbering. | **yes** |
| 10 | **Market and behavioural leakage** | SDWS 35 𝐿𝐸𝑦, monitored every two years; our VPA-DD concluded 0% | **SDWS 40** 𝐿𝐸𝑀𝑎𝑟𝑘𝑒𝑡,𝑦: *"Option 1 (Default): Apply 2% deduction. Option 2 (Detailed Assessment): Conduct leakage investigation surveys"*, Option 2 every two years | A **2% haircut** on emission reductions at renewal unless Option 2 survey evidence is produced. Recompute at renewal; no collection change is forced today, but Option 2 needs survey design lead time. | no |
| 11 | **Non-eligible water uses** | No equivalent | SDWS 28: *"Mandatory Exclusion of Non-Eligible Uses: The flow meter shall capture only water dispensed for human consumption. Outlets for non-eligible uses (e.g., cattle troughs, irrigation) shall be located upstream of the meter or sub-metered."* | Irrelevant to hand pumps with no plumbed outlets; **relevant to the Moramanga piped system**, where metering design must separate non-eligible draw. Folded into the existing Endur'O action. | no |
| 12 | **Baseline construction** | Single baseline equation; 𝐵𝐸𝑦 = 𝐸𝐹𝑏 × (1 − 𝐶𝑏 − 𝑋𝑐𝑙𝑒𝑎𝑛𝑏𝑜𝑖𝑙) × 𝑄𝑦 × 𝑀𝑞,𝑦 | Five-step construction: Step 3 downward adjustment for uncertainty and ambition (§7.4), Step 4 conservative business-as-usual ceiling (§7.5), Step 5 selection of the crediting baseline (§7.6), plus transparent quantification of Δᵧ (§7.7) | A different and lower baseline at renewal. Nothing to collect differently; the recomputation is a renewal task. | no |
| 13 | **Rehabilitation eligibility** | §2.3.x, evidence of non-operational period | §3.2.6.1: *"verifiable evidence that it was non-operational for ≥ three months and that no maintenance or repair plan was in place (SDWS 2)"* | Same test, now explicitly cross-referenced to SDWS 2. Bears on the eight open 2.2.1(d) records already on the action list. | no |
| 14 | **Renewal reassessment** | Not specified | §17.3.1 lists what must be updated at renewal: regulatory framework (SDWS 4), water sources (SDWS 5), baseline technologies and fuels (SDWS 6, 11, 8), 𝐶𝑏 (SDWS 12), 𝑓𝑁𝑅𝐵 (SDWS 25), CWT/CWS performance (SDWS 3); §17.3.5 prohibits reversion testing | Defines the renewal workload. §17.3.5 rules out asking participants to revert to boiling for a baseline survey. | no |

**14 divergences recorded. 6 require action now: rows 4, 5, 6, 7, 8 and 9.**

**On divergence 9 the finding is negative and that is worth stating plainly:** the v2.0 quarterly validation attaches to Option 3 alone and does not bind the Option 2 sensor route the StrokeMeter programme is built on. **No reconciliation action is required**, because there is nothing to reconcile — the plan's annual re-verification is consistent with the QA/QC clause's *"Proxies shall be revalidated annually"*. Divergence 9 keeps `action_now = yes` for the SOP renumbering, which still stands.

Each of those six has a matching Action List item in the report, and
`tools/check_consistency.py` asserts that mapping so a row cannot be added here
with `action_now = yes` and no action against it.

<!-- action_now index, parsed by check_consistency.py -->
| row | action_now | action_id |
|---|---|---|
| 1 | no | |
| 2 | no | |
| 3 | no | |
| 4 | yes | act-v2-sample-size |
| 5 | yes | act-v2-confidence-intervals |
| 6 | yes | act-v2-nonclaiming |
| 7 | yes | act-v2-embodied |
| 8 | yes | act-v2-stove-stacking |
| 9 | yes | act-v2-stroke-test |
| 10 | no | |
| 11 | no | |
| 12 | no | |
| 13 | no | |
| 14 | no | |
