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

The build now does that pairing itself (`tools/rebuild_piped_wq.py`). Each result is paired with its
record on the piped sampling form
[`ef8cf7353a974cf984d34860dcf2952d`](https://portal.mwater.co/#/forms/ef8cf7353a974cf984d34860dcf2952d)
by:

- the **same water point** (result 1.2b = sampling 1.1b) or, for a sample taken at the source or
  in the system, the **same water system** (result 1.2 = sampling 1.1); **and**
- the **same sampling day** (result 1.2.2 = the date of sampling 1.4, in Madagascar time).

A pair takes the GPS, the sample type and the photo from the sampling record, so the copy on the
result is not needed. The build already ignores 1.2.3. It reads 1.2.1 only as a cross-check when
it is filled, and never pairs on it.

What does not pair is listed on the page (collapsed, in the piped water-quality panel) with its
response codes, for Cathy to pair by hand. The list covers a result with no sample, a sample with
no result after 7 days, and a site and day with more than one sample or result. `publish.sh`
prints the same list as a gate readout and does not fail the build on it.

## What to watch after the change

- **More than one sample at the same site on the same day** cannot pair automatically. Each tap or
  kiosk sampled is its own water point (1.1b), so a round of taps pairs one by one. A round
  recorded against the **system** (1.1) with several samples on one day does not. All the
  existing sampling rounds (March to August 2026) were recorded that way, before 1.0b/1.1b
  existed on the sampling form, and all of them are flagged.
- **1.2.2 left at the wrong day** gives a result with no sample. The flag lists the samples on the
  same site from the week before the reading, so it can be put right in the portal.
- The 45 results on file at the change were all filed before 1.2.1, 1.2.2 and 1.2b existed
  (revisions 104 and 107). None carries a sampling date, so none pairs on its own; they are
  flagged with their candidate samples beside them.
