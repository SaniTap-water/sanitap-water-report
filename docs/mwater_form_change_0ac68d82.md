# Piped result form `0ac68d82`: stop asking for the sampling code and the GPS

28 September 2026. Decision: Adriaan Mol. **To be made by hand in the mWater portal designer.
Nothing in this repository changes mWater, and nothing here has been applied.**

Form: *Piped Water || Water Quality Testing_ SDWS 3__ Result* —
<https://portal.mwater.co/#/forms/0ac68d8274d24f54af0c28b29119b77d>
(design read through the read-only MCP, 28 September 2026).

## The change

In the portal designer, section **General information**:

| Code | Question | Column | Now | Set to |
|---|---|---|---|---|
| **1.2.1** | Sampling record code | `data:680e7b715b5e4fc49bef6205be59301a` | required | **not required**, then **disabled** |
| **1.2.3** | GPS of the sampling point | `data:d8d6ba9b457349db868b3bc07bfaabb9` | optional | **disabled** (stays not required) |

Order: untick *Required* on 1.2.1 first, then tick *Disabled* on both, then save and deploy a new
revision. Disabled questions keep the answers already given and collect nothing new, so no data is
lost.

Leave everything else as it is. In particular, keep these **required**, because the build now pairs on them:

- **1.1b** *Where was this sample taken?* (`6a0f3dc2`), which routes to the system or the tap question;
- **1.2** *Water System ID* (`a3390d2e`), for a sample at the source or in the system;
- **1.2b** *Water point ID* (`7d0fce72`), for a sample at a tap or kiosk;
- **1.2.2** *Sampling date & time (from the sampling record)* (`b25338d8`): this is now the pairing
  key. Its hint still tells the laboratory to copy the date from the sampling record, which is
  right.

### A second change, on the sampling form `ef8cf735`

The piped sampling form
(<https://portal.mwater.co/#/forms/ef8cf7353a974cf984d34860dcf2952d>) uses question code **1.7**
twice: *Who will benefit from the water point?* (`1ca2e9bb`) and the disabled *Type of
infrastructure installed* (`8509404f`). Codes are export column headers, so the two collide in
every export. Give the disabled question a code that no other question uses, for example
**1.8**, which is free. The build reads the form by question id, so the pairing does not depend on
this. But `tools/check_consistency.py` fails any form in the snapshot that reuses a code, so the
sampling form is pulled as an extract and **is not yet in the form snapshot**
(`tools/refresh_form_snapshot.py`). Add it there once the code is fixed.

## Why

Until now the laboratory copied two things by hand from the sampling record onto each result: the
sampling record's response code (1.2.1) and its GPS (1.2.3). Both were there only to let a result
be traced back to its sample, and copying a code or a coordinate by hand is where the errors come
in.

**Scope: public standposts and kiosks only.** Piped water quality is sampled, for now, only where
people collect their water: at a public standpost or kiosk, what comes out of the tap. No source,
tank or household samples (Adriaan Mol, 28 Sep 2026; `docs/piped_system_model.md`).

The build now does that pairing itself (`tools/rebuild_piped_wq.py`), by the **72-hour rule**
(Adriaan Mol, 28 Sep 2026, replacing the same-day rule written earlier that day):

- a result pairs with the **most recent unpaired** record on the piped sampling form
  [`ef8cf7353a974cf984d34860dcf2952d`](https://portal.mwater.co/#/forms/ef8cf7353a974cf984d34860dcf2952d)
  at the **same water point** (result 1.2b = sampling 1.1b), taken within the **72 hours before
  the result was submitted**;
- results are taken in submission order, and **each sample pairs at most once**.

A pair takes the GPS, the sample type and the photo from the sampling record, so the copy on the
result is not needed. **1.2.2 is a cross-check only**: if it is more than one day from the paired
sample's day, the pair is kept and carries a "date mismatch" note. **1.2.1 and 1.2.3 are not read
at all.**

- A sample with no water point (taken at system level) or at a household connection is **outside
  protocol**. It is flagged "outside protocol – sample at a public standpost" and never paired.
- A sample on one of the four Moramanga systems while its upgrade or new build is under way is a
  **pre-completion test**. It is shown and counted apart, and enters no carbon or portfolio figure.
- Results and samples **submitted before the tap-level protocol went live** are pre-project
  baseline: not paired, flagged or counted, and listed in the method notes as "baseline, not
  paired". The protocol went live on **22 September 2026**, when the sampling form was saved at
  revision 75, the first revision carrying 1.1b (15:58 UTC; `build_config.json` →
  `piped.pairing.protocol_live`).

What does not pair is listed on the page (collapsed, in the piped water-quality panel) with its
response codes, for Cathy to pair by hand: a result with no sample, a sample with no result after
7 days, and every outside-protocol sample. `publish.sh` prints the same list as a gate readout and
does not fail the build on it.

## What to watch after the change

- **Record the sample against its standpost.** A sample recorded against the system (1.1), or at
  a household, cannot pair and is flagged as outside protocol.
- **Submit the result within 72 hours of sampling.** A result submitted later than that finds no
  sample and is flagged. The flag lists the samples at the same water point from the week before,
  so the pair can be made by hand.
- **1.2.2 on the wrong day** no longer breaks a pair. It adds a date-mismatch note to check.
- **The 45 results on file were all submitted before the protocol went live** (the last on
  24 August 2026). So were every earlier sample except one: the sample of 28 September 2026 on
  Andilanatoby, which was taken at system level and is flagged as outside protocol. All 45
  results are baseline, not paired.
