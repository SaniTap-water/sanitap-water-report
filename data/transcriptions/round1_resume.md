# Transcription check, round 1

Written by `tools/transcription_round1.py`; do not edit by hand. Inputs (SHA-256):

- Dieu Donné Razafimahatratra (MadAvance MERV): `releves_calendriers_dieu-donne_serie1_2026-10-01.csv`, exported 2026-10-01T07:50:01.947Z, `8fb8317d5ffe0797…`; raw file kept as exported
- Adriaan Mol, round 1 (28 Sep 2026): `releves_calendriers_mol-adriaan_serie1_2026-09-28.csv`, `c03063a17eead980…`
- machine reader: `extraction_days2.csv` (30 Sep 2026 row-fix run), `712f0a5e6af4b53c…`

Read-only on mWater; no transcription result was changed. Every cleaning step is a row of `round1_ajustements.csv`.

## Cleaning (Dieu Donné's data only)

Raw: 29,943 rows, 83 calendars, 105 X, 126 ?.

- **a. Void after the photo date:** 31 marks (4 X, 27 ?) on calendars 2, 12, 66, 68, 69, 72, 86, 90, 92, 97.
- **b. Calendar 43, margin notes:** 33 X and 3 ? tagged `margin_note`, out of grid accuracy (below).
- **c. Doubtful sign counted as ?:** 18 (7/1), 30 (28/10), 38 (25/5), 64 (28/10), 87 (17/1). Also doubtful by note but already void under (a): 66 (25/3), 68 (16/7).
- **d. Held out (2027 sheets, 0 observed days):** 7, 23, 31, 32, 55, 61, 71, 76, 81.
- **e. Excluded:** 3.

**Cleaned totals** (calendars Dieu Donné confirmed, inside the observed window, margin notes apart): 73 calendars, 15,738 days, **63 X**, 101 ?, 23 calendars with at least one X.

### Year questions from (a)

Void marks that would fall on or before the photo date if the sheet were one year earlier. These are questions about the sheet year, not transcription errors.

| calendar | sheet year | photo date | cell | mark | date with year − 1 |
|---|---|---|---|---|---|
| 2 | 2026 | 2026-01-12 | 1/4 | ? | 2025-04-01 |
| 2 | 2026 | 2026-01-12 | 31/5 | ? | 2025-05-31 |
| 2 | 2026 | 2026-01-12 | 1/7 | ? | 2025-07-01 |
| 2 | 2026 | 2026-01-12 | 31/8 | ? | 2025-08-31 |
| 2 | 2026 | 2026-01-12 | 1/10 | ? | 2025-10-01 |
| 2 | 2026 | 2026-01-12 | 31/10 | ? | 2025-10-31 |
| 12 | 2026 | 2026-03-10 | 23/3 | ? | 2025-03-23 |
| 12 | 2026 | 2026-03-10 | 24/3 | ? | 2025-03-24 |
| 66 | 2026 | 2026-01-23 | 25/3 | X | 2025-03-25 |
| 68 | 2026 | 2026-07-03 | 16/7 | X | 2025-07-16 |
| 69 | 2025 | 2025-10-06 | 25/10 | ? | 2024-10-25 |
| 69 | 2025 | 2025-10-06 | 26/10 | ? | 2024-10-26 |
| 72 | 2026 | 2026-05-30 | 19/8 | ? | 2025-08-19 |
| 72 | 2026 | 2026-05-30 | 20/8 | ? | 2025-08-20 |
| 86 | 2026 | 2026-02-11 | 7/7 | ? | 2025-07-07 |
| 86 | 2026 | 2026-02-11 | 11/9 | ? | 2025-09-11 |
| 90 | 2026 | 2026-03-20 | 8/7 | ? | 2025-07-08 |
| 90 | 2026 | 2026-03-20 | 9/7 | ? | 2025-07-09 |
| 90 | 2026 | 2026-03-20 | 28/8 | ? | 2025-08-28 |
| 90 | 2026 | 2026-03-20 | 29/8 | ? | 2025-08-29 |
| 90 | 2026 | 2026-03-20 | 8/10 | ? | 2025-10-08 |
| 92 | 2026 | 2026-03-11 | 20/4 | ? | 2025-04-20 |
| 92 | 2026 | 2026-03-11 | 8/5 | ? | 2025-05-08 |
| 92 | 2026 | 2026-03-11 | 25/6 | ? | 2025-06-25 |
| 92 | 2026 | 2026-03-11 | 27/6 | ? | 2025-06-27 |
| 92 | 2026 | 2026-03-11 | 15/10 | ? | 2025-10-15 |
| 92 | 2026 | 2026-03-11 | 11/11 | ? | 2025-11-11 |
| 92 | 2026 | 2026-03-11 | 15/12 | ? | 2025-12-15 |
| 92 | 2026 | 2026-03-11 | 17/12 | ? | 2025-12-17 |
| 97 | 2025 | 2025-09-19 | 25/11 | X | 2024-11-25 |
| 97 | 2025 | 2025-09-19 | 26/11 | X | 2024-11-26 |

31 of 31 void marks pass the test. The test is weak here: on 10 of these 10 calendars the photo was taken during the sheet year, so any mark after the photo date falls before it a year earlier. It marks the year as worth a look; it is not evidence that the year is wrong.

Calendar 84 has no sheet year (the transcriber reads 2015 or 2025; photographed 2025-09-10). Its 2 X (25/12, 26/12) are scored as observed; if the sheet is 2025 they fall after the photo date and would be void under (a).

### Calendar 43: margin notes (reported apart)

X from the gardien's margin notes: 1/1, 2/1, 3/1, 4/1, 5/1, 6/1, 7/1, 8/1, 9/1, 10/1, 11/1, 12/1, 13/1, 14/1, 15/1, 16/1, 17/1, 18/1, 19/1, 20/1, 1/2, 2/2, 3/2, 4/2, 5/2, 6/2, 7/2, 8/2, 9/2, 16/2, 17/2, 18/2, 5/9. Uncertain (?): 10/2, 11/2, 12/2. Adriaan confirmed 43 with no grid mark; the grid comparison drops these cells for every reader.

## Agreement

One observed window for every reader: the sheet year of record (Dieu Donné's export) and the photo date. Adriaan's export predates the sheet years set on 28 Sep on ten sheets, so his own `etat_cellule` is not used. Calendars both humans confirmed: **73**; of these the machine reads **68** (three-way set).

### Day level: X versus blank (? shown, never scored)

**Adriaan Mol × Dieu Donné Razafimahatratra (MadAvance MERV)** (three-way set: 68 calendars, 14,865 days in the window). Agreement on X/blank **99.8%** over 14,785 scored days; Cohen's κ 0.7539.

| Adriaan Mol ↓ / Dieu Donné Razafimahatratra (MadAvance MERV) → | X | blank | ? |
|---|---|---|---|
| X | 40 | 5 | 1 |
| blank | 21 | 14719 | 76 |
| ? | 0 | 0 | 0 |

**Adriaan Mol × machine reader** (three-way set: 68 calendars, 14,865 days in the window). Agreement on X/blank **99.3%** over 14,730 scored days; Cohen's κ -0.0035.

| Adriaan Mol ↓ / machine reader → | X | blank | ? |
|---|---|---|---|
| X | 0 | 46 | 0 |
| blank | 60 | 14624 | 132 |
| ? | 0 | 0 | 0 |

**Dieu Donné Razafimahatratra (MadAvance MERV) × machine reader** (three-way set: 68 calendars, 14,865 days in the window). Agreement on X/blank **99.2%** over 14,656 scored days; Cohen's κ -0.0041.

| Dieu Donné Razafimahatratra (MadAvance MERV) ↓ / machine reader → | X | blank | ? |
|---|---|---|---|
| X | 0 | 61 | 0 |
| blank | 60 | 14535 | 132 |
| ? | 0 | 77 | 0 |

**Adriaan Mol × Dieu Donné Razafimahatratra (MadAvance MERV)** (all calendars both humans confirmed: 73 calendars, 15,738 days in the window). Agreement on X/blank **99.8%** over 15,633 scored days; Cohen's κ 0.7628.

| Adriaan Mol ↓ / Dieu Donné Razafimahatratra (MadAvance MERV) → | X | blank | ? |
|---|---|---|---|
| X | 42 | 5 | 1 |
| blank | 21 | 15565 | 100 |
| ? | 0 | 0 | 0 |

### Calendar level: marked (≥ 1 X) versus not, and X per calendar

| pair | scope | calendars | both marked | only A | only B | neither | X total A | X total B | same X count |
|---|---|---|---|---|---|---|---|---|---|
| Adriaan Mol × Dieu Donné Razafimahatratra (MadAvance MERV) | three way | 68 | 17 | 1 | 5 | 45 | 46 | 61 | 60 |
| Adriaan Mol × machine reader | three way | 68 | 2 | 16 | 5 | 45 | 46 | 60 | 45 |
| Dieu Donné Razafimahatratra (MadAvance MERV) × machine reader | three way | 68 | 3 | 19 | 4 | 42 | 61 | 60 | 43 |
| Adriaan Mol × Dieu Donné Razafimahatratra (MadAvance MERV) | all human | 73 | 18 | 1 | 5 | 49 | 48 | 63 | 65 |

Per calendar: `round1_calendriers.csv`.

### Machine reader: sensitivity and specificity

Reference X = positive. Days the machine calls ? are left out and counted.

| reference | TP | FN | FP | TN | machine ? | sensitivity | specificity |
|---|---|---|---|---|---|---|---|
| Adriaan Mol | 0 | 46 | 60 | 14627 | 132 | 0.0% | 99.6% |
| Dieu Donné Razafimahatratra (MadAvance MERV) | 0 | 61 | 60 | 14535 | 132 | 0.0% | 99.6% |
| both humans agree | 0 | 40 | 60 | 14530 | 132 | 0.0% | 99.6% |

## Human disagreements: settle by eye before scoring the machine

**127** days on 26 calendars (? contre X: 1, ? contre vide: 100, X contre vide: 26). Full list: `round1_desaccords_humains.csv`.

| calendar | date | Adriaan | Dieu Donné (cleaned) | Dieu Donné (raw) | machine |
|---|---|---|---|---|---|
| 4 | 2026-01-31 | vide | X | X | vide |
| 14 | 2024-05-09 | vide | ? | ? | vide |
| 14 | 2024-05-10 | vide | ? | ? | vide |
| 14 | 2024-05-11 | vide | ? | ? | vide |
| 14 | 2024-05-12 | vide | ? | ? | vide |
| 14 | 2024-05-13 | vide | ? | ? | vide |
| 14 | 2024-05-14 | vide | ? | ? | vide |
| 14 | 2024-05-15 | vide | ? | ? | vide |
| 14 | 2024-05-16 | vide | ? | ? | vide |
| 14 | 2024-05-18 | vide | ? | ? | vide |
| 14 | 2024-06-24 | vide | X | X | vide |
| 14 | 2024-10-09 | vide | X | X | vide |
| 18 | 2026-01-07 | X | ? | X | vide |
| 19 | 2026-04-30 | vide | ? | ? | vide |
| 30 | 2024-10-28 | vide | ? | X | hors cadre |
| 38 | 2025-05-25 | vide | ? | X | vide |
| 50 | 2024-09-27 | vide | X | X | vide |
| 50 | 2024-12-03 | vide | X | X | vide |
| 59 | 2025-06-30 | vide | X | X | vide |
| 59 | 2025-10-07 | vide | ? | ? | vide |
| 59 | 2025-10-08 | vide | ? | ? | vide |
| 62 | 2024-03-25 | vide | X | X | vide |
| 62 | 2024-03-26 | vide | X | X | vide |
| 62 | 2024-05-05 | vide | X | X | vide |
| 62 | 2024-05-06 | vide | X | X | vide |
| 62 | 2024-05-09 | vide | X | X | vide |
| 62 | 2024-06-03 | vide | ? | ? | vide |
| 62 | 2024-08-09 | vide | X | X | vide |
| 62 | 2024-08-11 | vide | X | X | vide |
| 64 | 2024-10-28 | vide | ? | X | vide |
| 69 | 2025-05-25 | vide | ? | ? | vide |
| 69 | 2025-05-26 | vide | ? | ? | vide |
| 70 | 2025-06-08 | vide | ? | ? | vide |
| 70 | 2025-07-18 | vide | ? | ? | vide |
| 72 | 2026-04-03 | vide | ? | ? | vide |
| 73 | 2025-09-06 | vide | ? | ? | vide |
| 79 | 2024-03-03 | vide | ? | ? | vide |
| 79 | 2024-03-12 | vide | ? | ? | vide |
| 79 | 2024-03-15 | vide | ? | ? | vide |
| 79 | 2024-04-12 | vide | ? | ? | vide |
| 79 | 2024-04-13 | vide | ? | ? | vide |
| 79 | 2024-04-14 | vide | ? | ? | vide |
| 79 | 2024-04-15 | vide | ? | ? | vide |
| 79 | 2024-04-16 | vide | ? | ? | vide |
| 79 | 2024-04-17 | vide | ? | ? | vide |
| 79 | 2024-04-19 | vide | ? | ? | vide |
| 79 | 2024-05-04 | vide | ? | ? | vide |
| 79 | 2024-05-10 | vide | ? | ? | vide |
| 79 | 2024-05-11 | vide | ? | ? | vide |
| 79 | 2024-05-14 | vide | ? | ? | vide |
| 79 | 2024-05-15 | vide | ? | ? | vide |
| 79 | 2024-05-18 | vide | ? | ? | vide |
| 79 | 2024-05-29 | vide | ? | ? | vide |
| 80 | 2024-07-03 | vide | ? | ? | vide |
| 80 | 2024-07-05 | vide | ? | ? | vide |
| 80 | 2024-07-08 | vide | ? | ? | vide |
| 80 | 2024-07-10 | vide | ? | ? | vide |
| 80 | 2024-07-14 | vide | ? | ? | vide |
| 80 | 2024-07-17 | vide | ? | ? | vide |
| 80 | 2024-08-09 | vide | ? | ? | vide |
| 82 | 2025-03-04 | vide | ? | ? | vide |
| 82 | 2025-03-05 | vide | ? | ? | vide |
| 83 | 2026-01-03 | vide | ? | ? | vide |
| 83 | 2026-02-10 | vide | ? | ? | vide |
| 83 | 2026-04-26 | vide | ? | ? | vide |
| 83 | 2026-06-21 | vide | ? | ? | vide |
| 83 | 2026-08-10 | vide | ? | ? | vide |
| 83 | 2026-08-17 | vide | ? | ? | vide |
| 83 | 2026-08-27 | vide | ? | ? | vide |
| 84 | 25/12 | vide | X | X | vide |
| 84 | 26/12 | vide | X | X | vide |
| 87 | 2026-01-17 | vide | ? | X | vide |
| 88 | 2026-01-30 | vide | X | X | vide |
| 90 | 2026-01-21 | vide | ? | ? | vide |
| 92 | 2026-01-01 | vide | ? | ? | hors cadre |
| 92 | 2026-01-14 | vide | ? | ? | hors cadre |
| 92 | 2026-01-15 | vide | ? | ? | hors cadre |
| 92 | 2026-01-18 | vide | ? | ? | hors cadre |
| 92 | 2026-02-02 | vide | ? | ? | hors cadre |
| 92 | 2026-02-06 | vide | ? | ? | hors cadre |
| 92 | 2026-02-08 | vide | ? | ? | hors cadre |
| 92 | 2026-02-12 | vide | ? | ? | hors cadre |
| 92 | 2026-03-08 | vide | ? | ? | hors cadre |
| 92 | 2026-03-11 | vide | ? | ? | hors cadre |
| 93 | 2025-01-15 | vide | ? | ? | hors cadre |
| 93 | 2025-03-29 | vide | ? | ? | hors cadre |
| 93 | 2025-04-08 | vide | ? | ? | hors cadre |
| 93 | 2025-04-24 | vide | ? | ? | hors cadre |
| 93 | 2025-05-10 | vide | ? | ? | hors cadre |
| 93 | 2025-06-03 | vide | ? | ? | hors cadre |
| 93 | 2025-07-02 | vide | ? | ? | hors cadre |
| 93 | 2025-07-07 | vide | ? | ? | hors cadre |
| 93 | 2025-08-06 | vide | ? | ? | hors cadre |
| 93 | 2025-11-16 | vide | ? | ? | hors cadre |
| 93 | 2025-11-29 | vide | ? | ? | hors cadre |
| 93 | 2025-12-04 | vide | ? | ? | hors cadre |
| 93 | 2025-12-06 | vide | ? | ? | hors cadre |
| 95 | 2024-01-02 | vide | ? | ? | vide |
| 95 | 2024-02-07 | vide | ? | ? | vide |
| 95 | 2024-02-28 | vide | ? | ? | vide |
| 95 | 2024-03-28 | vide | ? | ? | vide |
| 95 | 2024-06-10 | vide | ? | ? | vide |
| 95 | 2024-06-30 | vide | ? | ? | vide |
| 95 | 2024-09-23 | vide | ? | ? | vide |
| 95 | 2024-09-27 | vide | ? | ? | vide |
| 95 | 2024-10-22 | vide | ? | ? | vide |
| 95 | 2024-10-23 | vide | ? | ? | vide |
| 95 | 2024-10-24 | vide | ? | ? | vide |
| 95 | 2024-11-17 | vide | ? | ? | vide |
| 95 | 2024-11-23 | vide | ? | ? | vide |
| 95 | 2024-12-26 | vide | ? | ? | vide |
| 96 | 2025-01-14 | vide | X | X | vide |
| 96 | 2025-01-15 | vide | X | X | vide |
| 96 | 2025-02-14 | X | vide | vide | vide |
| 96 | 2025-02-15 | X | vide | vide | vide |
| 96 | 2025-04-03 | vide | ? | ? | vide |
| 96 | 2025-08-10 | vide | ? | ? | vide |
| 96 | 2025-08-11 | vide | ? | ? | vide |
| 96 | 2025-08-15 | vide | ? | ? | vide |
| 96 | 2025-08-17 | vide | ? | ? | vide |
| 96 | 2025-08-18 | vide | ? | ? | vide |
| 96 | 2025-10-12 | X | vide | vide | vide |
| 96 | 2025-10-13 | X | vide | vide | vide |
| 96 | 2025-10-14 | X | vide | vide | vide |
| 96 | 2025-11-12 | vide | X | X | vide |
| 96 | 2025-11-13 | vide | X | X | vide |
| 96 | 2025-11-14 | vide | X | X | vide |

