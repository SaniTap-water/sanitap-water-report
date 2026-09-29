# The piped systems: what a system is, and where its water is sampled

Source: Adriaan Mol, 28 September 2026. This file is the reference for how the report treats the
Endur'O piped systems. Nothing in mWater was changed to write it.

## What a piped system is

Each Moramanga system is a **spring augmented by solar-pumped boreholes**, feeding:

1. **the sources**: the spring catchment, and one or more boreholes with solar pumps;
2. **header tank(s)**: storage above the distribution network;
3. **chlorination**: dosing before the water enters the network;
4. **piped distribution** to:
   - **public standposts** (*bornes fontaines*) and kiosks, where people collect their water;
   - **private connections** to households and institutions.

In mWater, the system is one `water_system` record. Each standpost, kiosk or connection is a
`water_point` (a Distribution Point, form `8a3af50c`) whose parent system is set on that
registration (question 1.3). The boreholes and the spring may also be `water_point` records.

## The four Moramanga systems

| System | mWater code | Status on the page |
|---|---|---|
| Amboasary gara | `1108783583` | **upgrade or new build under way** |
| Ambohibola | `1108783624` | **upgrade or new build under way** |
| Amboanjo | `1108783648` | **upgrade or new build under way** |
| Andilanatoby | `1108783662` | **upgrade or new build under way** |

Status source: Adriaan Mol, 28 Sep 2026. Some are **existing systems being upgraded**: their taps
exist and are in use. Others are **being built from scratch**. The status file still calls them
`in_process` (`data/piped_systems_status.json`, with `stage` and `stage_source` on each). The page
shows "upgrade or new build under way" wherever it used to say "in process".

**They stay out of every carbon and portfolio figure until they are complete.** A system joins the
managed portfolio only when its works are complete and its post-rehabilitation water-quality tests
are done (the join rule of 25 September 2026, `tools/rebuild_piped_wq.py`).

## Where the water is sampled

**For now, piped water quality is sampled only at public standposts and kiosks: what comes out of
the tap.** No source, tank or household samples.

- A sample is recorded on the piped sampling form `ef8cf735` against its **water point** (question
  1.1b), which must be a standpost or kiosk.
- A sample taken at system level (no water point) or at a household connection is **outside
  protocol**. It is flagged "outside protocol – sample at a public standpost" and never paired
  with a result.
- A result on the piped result form `0ac68d82` pairs with the most recent unpaired sample at the
  same water point taken within the **72 hours** before the result was submitted. Each sample pairs
  once. The rule is in `tools/rebuild_piped_wq.py` and the form notes in
  `docs/mwater_form_change_0ac68d82.md`.
- A sample on one of the four systems while its upgrade or new build is under way is a
  **pre-completion test**. It is shown and counted apart, and enters no carbon or portfolio figure.
- Results and samples submitted before the tap-level protocol went live (22 September 2026,
  `build_config.json` → `piped.pairing.protocol_live`) are **pre-project baseline**. They are not
  paired, flagged or counted, and are listed in the method notes as "baseline, not paired".

Private connections and the sources are **not in scope for now**, for sampling or for
registration (`act-moramanga-register-standposts`).

## Rehabilitated systems built by other NGOs

**Rehabilitated systems built by other NGOs: Endur'O registers its own records; earlier records are
kept as history and cross-referenced, never edited.** (Adriaan Mol, 29 Sep 2026.)

- The management contract for the Moramanga systems is with **Endur'O/NatuRano**. Endur'O
  registers its own new water points under its own system records: `1108783583`, `1108783624`,
  `1108783648`, `1108783662`.
- Some rehabilitated systems were built by other NGOs and already appear in mWater (WaterAid, MG
  MERL and others). Those records are historical. They are **never edited, relinked, deleted or
  asked to be transferred**. A duplicate system record owned by another organisation is resolved
  with a note: "superseded – other organisation's historical record; Endur'O record of record
  used".
- Where a standpost already exists from an earlier project, the new Endur'O Distribution Point
  quotes the old mWater ID in its description. `data/moramanga_wp_crosswalk.json` records old ID
  → new ID every build: *confirmed* from the quoted ID, or *suggested* from GPS within 30 m and a
  similar name. It is used so that no physical standpost is counted twice.
- The 19 earlier-project kiosks on Amboasary gara (WaterAid's `441839342`, one of them MG MERL's)
  are mapped to `1108783583` in the water-quality classification only. A stray sample taken at
  one still pairs and counts, flagged "sampled at an earlier-project record; use the Endur'O
  point".

## Getting the standposts into mWater

1. **One system record per scheme** (`act-moramanga-system-dedupe`). The four Endur'O records are
   the records of record. Other organisations' duplicates are resolved by note. Endur'O's own
   duplicates ("AEPP …", "Forage …", twin records) stay open until Endur'O retires them or notes
   them.
2. **Register every public standpost as a new Distribution Point** under the Endur'O record
   (`act-moramanga-register-standposts`), quoting the old mWater ID in the description where there
   is one. Existing systems are registered now; new systems at commissioning. Cathy samples a
   standpost as soon as it appears in the list (`docs/labels/piped_water_points.csv`).
