# SDWS 27 — the registered basis and the governing methodology version

Compiled 20 September 2026 from the registered VPA-DD and the two methodology
versions held in `Water Documents/Methodology of record/`. Everything between
quotation marks is verbatim from the source named above it. Nothing here is
paraphrase, and nothing is taken from a reviewer's or verifier's summary.

Sources read:

| Document | Path |
|---|---|
| Registered VPA-DD | `sites/Carbon2/Shared Documents/Gold Standard SaniTap Submission/VPA-1 GS12601 Clean Water (real-case)/3. GS Design Review/4. R3/GS12600_GS12601_VPA-1_Safe_Water_Madagascar_VPA-DD_V2_CLEAN.pdf` |
| ERSDWS v1.0 | `429_V1.0_ERSDWS_Emission-reductions-from-Safe-Drinking-Water-Supply.pdf` (sha256 `c709c093…`) |
| ERSDWS v2.0 | `429_V2.0_PAA-M400-12_Emission-reductions-from-Safe-Drinking-Water-Supply.pdf` (sha256 `4eb9050b…`) |

---

## (a) The VPA-DD — what is applied, and the condition on exceeding it

The SDWS 27 box sits in **section B.7.1, "Data and parameters monitored"** — not
in B.6.2, "Data and parameters fixed ex ante". Verbatim, in full:

> **Data/parameter ID** SDWS 27
> **Data / Parameter** 𝐷𝑂𝑝,𝑦
> **Unit** Days
> **Description** Days the project technology is operational for end-users in premises p in year y
> **Source of data** During project, this will be determined through either:
> 1. Measure directly using operation sensor, or
> 2. Demonstrate from log of operation and maintenance system.
>
> **Value(s) applied** Estimate: 347 days
> **Measurement methods and procedures** -
> **Monitoring frequency** Annually
> **QA/QC procedures** Values higher than 347 days may only be applied when option 1 is used. 347 days is 95% of days, in line with pump-maintenance in the literature.
> **Purpose of data** Calculation of the project scenario
> **Additional comment** Operational sensors may be applied on a (90/10) sample basis to assess operational days in the Project scenario

Equation 5 of the VPA-DD defines the term used:

> 𝐷𝑂𝑝,𝑦 = Days the project technology is operational for end users in premises p in year y

**A numbering error in the registered document.** Section B.7.3 item 5,
"Maintenance", tabulates the same parameter under the wrong ID:

> **ID** SDWS 20 **Parameter** 𝐷𝑂𝑝,𝑦 **Description** Days the project technology is operational for end-users in premises p in year y

SDWS 20 is the hygiene-campaign parameter, tabulated immediately above it in the
same section. This is an error in the registered VPA-DD, not in this note.

---

## (b) ERSDWS v1.0 — the registered methodology

Parameter box SDWS 27, page 36, verbatim in full:

> **Data/Parameter:** 𝐷𝑂𝑝,𝑦
> **Data unit:** Days
> **Description:** Days the project technology is operational for end-users in premises p in year y
> **Source of data:** In order of preference:
> 1. Measure directly using operation sensor, or
> 2. Demonstrate from log of operation and maintenance system.
>
> **Monitoring frequency:** Annually
> **QA/QC procedures:** Values higher than 347 days may only be applied when option 1 is used. 347 days is 95% of days, in line with pump-maintenance in the literature.
> For schools and other institutions, as applicable, the days must also be limited by the number of school days in the period, taking into account weekends and holidays.
> **Any comment:** Applies to CWT, CWS projects and IWT (schools)

**The v1.0 box has no "value applied" field and states no default.** 347 appears
once, as a ceiling in QA/QC.

§2.3.3 requires the log that option 2 relies on:

> All CWT and CWS projects must include ongoing maintenance and repair of the project technology. The PDD must describe the maintenance and repair plan, including the system for logging/documenting of technology operation and maintenance events including periods of downtime¹³. The log of operation and maintenance shall be required during the monitoring period to demonstrate project technology operation.

Footnote 13 defines downtime:

> Time during which the technology is out of action or unavailable for use.

§2.4.1:

> The date of entry into force of this methodology is 02 August 2021.

---

## (c) ERSDWS v2.0 — where operational days now sit

**The parameter numbering in the brief needs correcting.** In v2.0, **SDWS 31 is
𝐻𝐻𝑝,𝑦, the number of premises served**, and **DO𝑝,𝑦 is SDWS 32**. From Equation 5,
page 30:

> 𝐻𝐻𝑝,𝑦 = Number of premises type p served by the activity (SDWS 31)
> 𝐻𝑁𝑝,𝑦 = Number of individuals per premises type p (SDWS 30)
> 𝑄𝑃𝑊𝑝 = Volume of drinking water per person per day (SDWS 29)
> 𝐷𝑂𝑝,𝑦 = Days the activity technology is operational (SDWS 32)

§3.4.3, which is where the O&M log requirement lives:

> **CWT/CWS Maintenance and Operation:** All CWT and CWS activities shall include an ongoing maintenance and repair plan. The PDD/VPA-DD shall describe this plan, including the system for logging operation, maintenance events, and periods of downtime. This log is required during monitoring (SDWS 31).

That cross-reference to SDWS 31 is **wrong in v2.0 itself** — SDWS 31 is the
premises count; the log belongs to SDWS 32. A second numbering error, in the
other document.

Parameter box SDWS 32, page 68, verbatim in full:

> **Parameter ID** SDWS 32
> **Data/parameter:** 𝐷𝑂𝑝,𝑦
> **Description:** Days the activity technology is operational for end-users in premises p in year y (CWT/CWS/IWT).
> **Data unit:** Days
> **Purpose of data:** Baseline emissions
> Operation sensor or Log of operation and maintenance.
> **Measurement and updating frequency** Annually.
> **Measurement methods and procedures:** In order of preference:
> 1. Measure directly using operation sensor.
> 2. Demonstrate from log of operation and maintenance system (Section 3.2.6 |), detailing uptime and downtime.
>
> **Entity/person responsible for the measurement:** Activity developer or trained enumerators or designated system operator/institutional representative.
> **Measuring instrument(s): Type of instrument** Operation sensors; Standardized operation and maintenance logs.
> **QA/QC procedures:** Regular verification of sensor data or auditing of logbooks. For institutions, days shall be limited by the number of operating days (e.g., school days), accounting for weekends/holidays.
> **Treatment of uncertainty** Values higher than 347 days (95% of days) may only be applied when Option 1 (sensor) is used. Uncertainty is managed by this conservative cap when relying on manual logs.
> **Comments:** Applies to CWT, CWS activities and IWT.

Two things v2.0 says that v1.0 does not. It requires the log to be
"**detailing uptime and downtime**", and it calls 347 "**this conservative
cap**" applied "**when relying on manual logs**".

---

## (d) The word used, and whether it is defined

The word is **"operation sensor"** (v1.0 and the VPA-DD) and
**"operation sensor" / "operation sensors"** (v2.0). The phrase
**"monitoring device" does not appear in either version** — zero occurrences.

**Neither version defines it.** Neither definitions section (v1.0 §1, v2.0 §2)
contains an entry for sensor, operation sensor, or any equivalent, and no
sentence of the form "sensor means / is defined as / refers to" exists in
either document.

The only functional characterisation anywhere is incidental, in the
water-volume parameter — v1.0 SDWS 23, carried into v2.0 SDWS 28:

> Option 2: Operation sensor measures directly operation time or pump stroke count, and volume is calculated as capacity (defined in Project technology description) multiplied by operation time or pump strokes, depending on the sensor type.

**A device that counts pump strokes is squarely within that description.** The
StrokeMeter is a stroke counter. On the only text either methodology offers,
it is an operation sensor. That is a reading of an undefined term, not a
settled fact, and it should be put to Gold Standard rather than assumed.

---

## (e) Is DO a fixed ex ante estimate, or the period less documented downtime?

**Neither version defines DO as a fixed ex ante estimate.** In both it is a
parameter **monitored annually**, determined "in order of preference" by an
operation sensor or by the operation-and-maintenance log. In the registered
VPA-DD it likewise sits among the **monitored** parameters, with monitoring
frequency "Annually"; the 347 there is entered as the project's own
"**Estimate**", which is what a VPA-DD ex ante value is.

What the log-based option measures is stated in v2.0 in terms: a log
"**detailing uptime and downtime**", downtime being "time during which the
technology is out of action or unavailable for use" (v1.0 fn 13). That is the
period-less-documented-downtime construction, and it is the one the registered
text supports.

**347 is a ceiling on that construction, not a floor and not an entitlement.**
v2.0 says so explicitly: it is "this conservative cap" for "relying on manual
logs". So the registered basis is:

> **DO𝑝,𝑦 = min( 347 , days demonstrated operational by the O&M log )**,
> unless an operation sensor is used, in which case the cap does not apply.

---

## (f) Which version applies to an already-registered activity

**v2.0 §3.3 consists of one clause in its entirety.** Quoted in full:

> **3.3 | Entry into force**
> **3.3.1 |** The date of entry into force is 90 days from the publication date of this methodology.

There is nothing else in §3.3 — no grandfathering clause, no transition
provision, and no statement about activities already registered under v1.0.

**§17.1.1 in full:**

> **17.1.1 |** The crediting period is a maximum of five years, renewable twice (total of 15 years). At the renewal, the activity developer shall apply the latest version of this methodology available at the time of submission for renewal.

The remainder of §17 concerns what must be reassessed **at renewal** —
§17.2 the baseline scenario, §17.3 the ex-ante baseline parameters (regulatory
framework, water sources, baseline technologies and fuels, 𝐶𝑏, 𝑓𝑁𝑅𝐵 which is
SDWS 25 in v2.0, and CWT/CWS performance), §17.4 additionality. Every
obligation in §17 is triggered by renewal. **None is triggered by publication of
a new version.**

**Nothing in either document makes a version change apply mid monitoring
period.** v1.0 states only its own entry into force (§2.4.1, 02 August 2021).
v2.0 states only its own (§3.3.1). The single provision in either document that
connects an activity to a *later* version is §17.1.1, and it operates **at
renewal**, not on publication and not during a monitoring period.

---

## The two findings, stated plainly

**1. Which version governs the 2026 monitoring period.**

The VPA is registered under v1.0 — the Design Review assurance form
(`GS12601_DESR_RF RD3_GS.docx`) names the applied methodology throughout as
*"METHODOLOGY - Emission reductions from Safe Drinking Water Supply v.1.0"*.
v2.0 enters into force 90 days from publication, approximately **7 October
2026** on the cover date of 09/07/2026. Neither document contains any provision
applying a new version to an already-registered activity before renewal, and
the only version-transition provision in either, §17.1.1, operates at renewal.

**On the documents, v1.0 governs the 2026 monitoring period.** The point is not
academic in one respect and is academic in another: v1.0 and v2.0 say
materially the *same* thing about DO — same two options, same order of
preference, same 347 ceiling conditioned on the sensor. v2.0 is more explicit,
not more permissive. **Whichever version governs, the answer on DO is the
same.** Confirming the version with Gold Standard remains worth doing, because
parameter numbering and several other requirements do differ; it is not worth
doing in the hope of a different answer on DO.

**2. Which construction of DO the registered text supports — and this one goes
against us.**

The registered text supports **DO = min(347, days demonstrated by the O&M
log)**. It does not support a flat 347 irrespective of evidence, and it does not
support anything above 347 on calendar evidence.

**Our observed-window reading of 356.2 days is above the cap and is therefore
not claimable.** The gardien calendars are a manual log. Under both versions a
manual log cannot carry a value above 347 days, however well it is read and
however complete its coverage becomes. The reading of 356.2 days has **no
carbon value on its own**.

What the calendars *can* do is defend the 347 already registered, and expose the
case where they cannot. Because the cap binds from above and the log binds from
below, better calendar evidence can only ever confirm 347 or **reduce** it. A
complete, well-read calendar record that showed more than 18 days of downtime in
a year would oblige us to apply **less** than 347 for those points. On the
current reading — an implied 8.8 days not operational — the calendars support
347 comfortably. That is the upside, and it is the only upside: the calendar
work protects the registered figure; it cannot raise it.

**The only route above 347 is an operation sensor**, deployable on a (90/10)
sample basis under the VPA-DD's own "Additional comment", with §4.2.2 of v1.0
setting a minimum sample of 30 for a proportion parameter.
