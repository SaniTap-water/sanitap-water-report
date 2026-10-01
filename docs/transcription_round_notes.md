# Calendar transcription round — working notes

Internal notes on the human transcription of the gardien calendars
(`transcription/`). **No figure here is on the report page**, and none may be
copied there until the validation round is complete: the page reports the round
only through the action list and the method block of the calendar section.

## First pass — Adriaan Mol, series 1, exported 28 Sep 2026

File: `releves_calendriers_mol-adriaan_serie1_2026-09-28.csv` (Downloads, 14:12),
session `smue156dh7pl9`, **22 calendars** of the 83 loaded.

### Why only 22 of about 83

A calendar viewed and left empty — a pump with no breakdown, the commonest case —
was neither counted as started nor exported: the export kept a calendar only if it
had a mark, an exclusion or a note. The 22 are the 20 with marks plus two with
notes (6 and 43). Fixed on 28 Sep 2026 in `transcription/index.html`:

- per-calendar status: *Vérifié — aucune croix* (button under the grid), and a
  prompt on *Suivant* when a calendar has no marks ("Aucune croix sur ce calendrier :
  confirmer comme vérifié ?" — Oui / Revenir);
- the export carries every answered calendar with a `statut` column:
  `marque`, `exclu`, `vide_verifie`, and `vu_sans_confirmation` for a calendar that
  was on screen (time recorded) but never confirmed — **never** exported as checked-empty;
  `non_vu` is not exported;
- the header reads "vérifiés N / 83";
- storage key and format unchanged (`sanitap-transcription-v2`); fields only added;
- `tools/test_transcription_page.py` drives the page (view 3, mark 1, confirm 2,
  reload, export → 3 calendars) and runs in `tools/publish.sh`.

### Recovery of the first pass

The browser store records the seconds spent on each calendar, so the calendars
Adriaan looked at and left empty are recoverable from it — but **only he can
confirm them**. On his next visit the page offers *Revoir les calendriers vus sans
confirmation (N)*, which walks exactly those, and exports them meanwhile as
`vu_sans_confirmation`. A *Sauvegarde (JSON)* button downloads the whole store.
**Not yet verified**: the number seen but never confirmed can only be counted from
that backup; until it arrives it is unknown here.

## Comparison of the first pass with the machine — not the validation round

`tools/compare_transcriptions.py`, human against `extraction_days2.csv`.
**It covers 11 calendars** — the machine-comparable ones among the 22 exported;
the other 11 have no day calls for their selected image or sit outside the frame.
It is a check of the tooling and an early look, **not the validation round**
(50 machine-comparable calendars, see `act-transcription-round`).

**Join corrected before this was run.** The tool joined the machine to a sheet on
water point; 15 of the 22 sheets sit on a water point with 2–5 photographs in the
machine file, so a sheet could be scored against a different photograph. It now joins
on the image through `transcription/validation_selection.csv`, and refuses to compare
with the machine without it. The old-join column shows what the bug did.

Human-to-machine, mean agreement over calendars **0.910** (11 calendars compared, 0 excluded; mean over calendars; sd 0.0345; min 0.8333; pooled-cell 0.9228).

| calendar | water point | cells | agreement | (old water-point join) | machine X, human blank | human X, machine blank | machine ?, human blank |
|---|---|---|---|---|---|---|---|
| 18 | 742894985 | 12 | 0.833 | 0.833 | 0 | 0 | 1 |
| 27 | 742893843 | 136 | 0.897 | 0.904 | 7 | 1 | 6 |
| 40 | 742895577 | 140 | 0.929 | 0.929 | 9 | 1 | 0 |
| 42 | 742893946 | 75 | 0.867 | 0.867 | 7 | 2 | 1 |
| 43 | 742895168 | 253 | 0.945 | 0.945 | 6 | 0 | 8 |
| 48 | 794587460 | 202 | 0.901 | 0.931 | 14 | 2 | 4 |
| 51 | 698771275 | 350 | 0.931 | 0.926 | 14 | 3 | 7 |
| 54 | 742895498 | 232 | 0.944 | 0.858 | 7 | 1 | 5 |
| 59 | 699596743 | 365 | 0.910 | 0.937 | 25 | 2 | 6 |
| 69 | 742897249 | 279 | 0.921 | 0.921 | 9 | 4 | 9 |
| 75 | 800634100 | 365 | 0.934 | 0.959 | 19 | 2 | 3 |
| **total** | | | | | **117** | **18** | **50** |

**Machine calls X, Adriaan did not** (day/month):

- 27: 3/3, 4/3, 5/3, 2/4, 3/4, 4/4, 5/4
- 40: 1/2, 2/2, 3/2, 1/3, 2/3, 3/3, 1/4, 2/4, 3/4
- 42: 2/1, 3/1, 1/2, 2/2, 1/3, 2/3, 3/3
- 43: 1/3, 1/4, 1/5, 3/5, 1/6, 1/7
- 48: 2/1, 3/1, 4/1, 5/1, 3/2, 4/2, 5/2, 1/3, 2/3, 3/3, 4/3, 5/3, 3/5, 3/7
- 51: 1/1, 2/1, 3/1, 1/2, 2/2, 3/2, 1/3, 2/3, 3/3, 1/4, 1/5, 3/5, 1/6, 1/7
- 54: 3/1, 1/2, 2/2, 3/2, 1/3, 2/3, 3/3
- 59: 2/1, 3/1, 4/1, 1/2, 2/2, 3/2, 4/2, 5/2, 1/3, 2/3, 3/3, 4/3, 5/3, 2/4, 2/5, 4/5, 2/7, 1/8, 2/8, 3/8, 4/8, 1/9, 2/9, 3/9, 4/9
- 69: 2/1, 1/2, 2/2, 3/2, 1/3, 2/3, 3/3, 1/6, 1/7
- 75: 2/2, 3/2, 4/2, 2/3, 3/3, 4/3, 1/4, 2/4, 3/4, 4/4, 31/8, 1/9, 2/9, 3/9, 4/9, 1/10, 2/10, 3/10, 4/10

**Adriaan calls X, the machine did not** (day/month):

- 27: 22/4
- 40: 20/5
- 42: 10/1, 24/2
- 48: 11/2, 21/7
- 51: 21/8, 22/8, 15/12
- 54: 20/8
- 59: 7/11, 8/11
- 69: 14/4, 15/4, 16/9, 17/9
- 75: 30/10, 31/10

**Pattern.** 116 of the 117 cells where the machine calls X and Adriaan saw nothing fall
on **days 1–5 of a month** (93 on days 1–3); the one exception is 31 August. That is
a systematic over-call at the top of each month column, not random reading error, and
it runs in the direction of more downtime. It should be looked at in the reader before
the validation round is scored. Adriaan's own X marks the machine missed (18) are
scattered.

## Open items

### (a) Working-day ticks — `act-cal-working-day-ticks`

Calendar 43, water point 742895168 (Fort-Dauphin, photographed 2026-09-10): the gardien
ticked every day for about six weeks at the start of the year and then stopped —
positive ticks for working days, not breakdown marks (transcriber's note). Read as
marks they would count working days as downtime. **On this sheet the machine read the
ticks as clear** (January–February: 56 clear, 6 "?", no X), so it did not happen here.

Search for the same convention elsewhere: consecutive marked days in the machine output.
A tick run the machine reads as clear is invisible to this search, so it is a starting
list, not a census.

Searched: 836 images with day calls and a sheet year in `sdws1/calendar_extract/extraction_days2.csv`, observable days only (up to the photo date).

- runs of **20 or more** consecutive marked days: **3 images, 2 water points**
- runs of **10 or more**: **11 images, 10 water points**

| run (days) | from | to | water point | site | photo date | image |
|---|---|---|---|---|---|---|
| 23 | 2026-01-08 | 2026-01-30 | 820198370 | Maroantsetra | 2026-06-16 | 767469f0ce7646a28d8cb69749fb0665 |
| 20 | 2026-01-12 | 2026-01-31 | 814009107 | Maroantsetra | 2026-06-24 | 1f02774e423246b3b469c7a521eb5033 |
| 20 | 2026-01-12 | 2026-01-31 | 814009107 | Maroantsetra | 2026-06-24 | 3f4d6acc82de4813851f96898836df87 |
| 16 | 2025-01-18 | 2025-02-02 | 742895869 | Maroantsetra | 2025-11-05 | 10d9cce997e745db8f3a80c318f7b755 |
| 16 | 2025-01-01 | 2025-01-16 | 742894851 | Fort-Dauphin | 2025-12-05 | 200136b2366f4bd989c5d1a2761e798a |
| 14 | 2026-01-01 | 2026-01-14 | 742893850 | Fort-Dauphin | 2026-01-28 | 1ce48bc7587c4b698fb04b12a60affaf |
| 14 | 2025-09-22 | 2025-10-05 | 699595979 | Maroantsetra | 2025-12-11 | fcd5e3f6964e427f94f74cedd8ff7229 |
| 13 | 2025-03-01 | 2025-03-13 | 742895515 | Maroantsetra | 2025-11-14 | 65932d79698847ea8430a8c4a383bdd8 |
| 11 | 2026-01-01 | 2026-01-11 | 698772001 | Maroantsetra | 2026-01-15 | e9c26d924f8d46ea928ffd78fc437ebd |
| 10 | 2025-10-20 | 2025-10-29 | 742897029 | Maroantsetra | 2025-10-29 | 28fe578e85d84188b79b1175980331e7 |
| 10 | 2025-01-23 | 2025-02-01 | 742895821 | Fort-Dauphin | 2025-12-12 | b612c08cd63c4812b27db81d4ad3de04 |

Without the observable-window restriction, three further runs of 20+ days appear in
December 2026 on photographs taken in March 2026 — days that had not happened yet, so
machine artefacts outside the window, not marks.

### (b) Handwritten sheet year — `act-cal-handwritten-year`

Calendar 6, water point 742895508 (Maroantsetra, photographed 2025-11-07), image
`11c8b50200784ddc918ce8e5c02d6f92`: `annee_feuille` blank; the transcriber notes a
2024 sheet. `data/calendar_sheet_year.csv` has an empty year, confidence 0.000, route
`anchor`, anchor score 0.578, no OCR text. The sheet is an **older template with no
printed "20XX" in the header**; the year is written by hand in blue ink beside the
SaniTap logo. The reader anchors on the printed "202" and OCRs the region around it,
so it found no year. The page therefore opened every cell on a 2026 grid (no 29 February).

The printed layout settles it: 1 January is a Monday and February has a 29th — 2024,
and no other year in 2023–2028.

**Built 28 Sep 2026.** `tools/read_year_ocr.py --weekday-fallback` OCRs the printed grid
("01 LUN", "02 MAR" …), assigns each label to its month by column position and scores every
year in 2023–2028 (accepted only with 8+ pairs, 85%+ agreement and a 0.25 margin over the next
year). Result in `data/calendar_sheet_year_deduced.csv`; it **never** fills `sheet_year`.
`tools/bundle_new_sheets.py --deduced-only` carries an accepted year to the page as `yd`, which
the page offers as "année déduite du calendrier — à confirmer" and uses only once the
transcriber confirms it (exported as `annee_source` = `transcripteur`). On the 12 transcription
sheets with no year read:

| sheet | image | deduced | agreement | margin | label pairs |
|---|---|---|---|---|---|
| 6 | 11c8b502 | **2024** | 0.94 | 0.93 | 241 |
| 30 | 0ef11769 | **2024** | 0.98 | 0.97 | 289 |
| 34 | 68f48ea9 | **2024** | 0.92 | 0.89 | 74 |
| 46 | fd6a0f27 | **2024** (photo upside down) | 0.95 | 0.93 | 276 |
| 50 | 491177a6 | **2024** | 0.92 | 0.30 (narrow) | 60 |
| 97 | 41ccd1d2 | **2025** | 0.92 | 0.90 | 146 |
| 38, 89 | c268070e, bd2ad55a | not clear enough | | | |
| 84, 91, 92, 99 | | too few weekday labels read | | | |

Sheet 6 agrees with the handwritten 2024; sheet 30 was checked by eye (same template, "2024"
handwritten). Sheet 6 is **not** set to 2024 in anyone's data: Adriaan confirms it on the page.

## Full first pass — Adriaan Mol, series 1, exported 28 Sep 2026 17:13

File `releves_calendriers_mol-adriaan_serie1_2026-09-28 (1).csv`: **all 83 calendars**, 63
confirmed empty (`vide_verifie`) and 20 marked; no photo was rotated on the page.

**Against the machine** (`tools/compare_transcriptions.py`, image join): **42 calendars** compared —
the machine-comparable ones with overlapping cells; 8 more in the frame have no overlapping cells.
Mean agreement over calendars **0.921** (sd 0.082, min 0.531; pooled-cell 0.938). Lowest: 58
(0.53) and 56 (0.71), both photographed sideways, where the machine returns "?" on cells the human
reads blank. Still not the validation round: one transcriber, who had seen the aggregate statistics.

**The days 1–5 over-count holds.** The machine calls X where Adriaan saw nothing on **394** cells, and
**366 of them (93%) fall on days 1–5** of a month (283 on days 1–3), on **36 of the 42** calendars.
By day: 1: 103, 2: 98, 3: 82, 4: 51, 5: 32, then 3 or fewer per day. The other way round, Adriaan's
X that the machine missed: 18 cells. The over-count runs in the direction of more downtime and is
the first thing to fix in the reader before the validation round is scored.

## Orientation and sheet years — before Angelo's team starts (28 Sep 2026)

- **26 photographs are now served upright**; the other 57 already were. Rotation per image, the
  original's and the served file's SHA-256, and who reviewed it: `data/transcription_orientation.csv`
  (from `data/transcription_orientation_review.csv`, via `tools/bundle_new_sheets.py --orientation`).
  Originals are kept in `transcription/img_original/`. The images carry no EXIF orientation.
- **Marks map to the same cells.** Adriaan's full pass, replayed through the new page and exported
  again: all 51 marks on the same calendar, month and day, including the 7 on turned photographs; no
  statut changed. A rotation a transcriber saved on the page before this is converted once, so it
  cannot turn an upright photo.
- **Sheet years set with their source** (`data/transcription_sheet_years.csv`, read by Claude): printed
  89, 91, 92, 99 = 2026; handwritten 6, 30 = 2024; weekday layout 34, 46, 50 = 2024 and 38, 97 = 2025.
  Shown on the page as "lue par Claude — …", editable, exported as `annee_source` `claude_imprime` /
  `claude_manuscrit` / `claude_calendrier`. **84** is unreadable and left for the transcriber.
- **Calendar 89 conflicts with its printed year.** The sheet prints "2026", its weekday layout is
  2026, but it was photographed on 18 Dec 2025 and carries marks on 22 Oct, 12 Nov and 17 Dec:
  the gardien was marking a 2026 sheet through late 2025. With 2026 every day is outside the
  observable window, so those three marks are kept but exported as `non_observe`. This is the
  question open as `act-printed-year-meaning`; the year stays editable.

## Transcription check, round 1 — Dieu Donné Razafimahatratra (MadAvance MERV), exported 1 Oct 2026

File `data/transcriptions/releves_calendriers_dieu-donne_serie1_2026-10-01.csv` (Downloads, 1 Oct 2026
20:33; the browser had already renamed the download from its `.tmp` name), 29,943 rows,
83 calendars, exported 2026-10-01T07:50:01.947Z, kept byte for byte as exported
(SHA-256 `8fb8317d5ffe0797263f4c53eab01182796958483e5b7d57af983fb2e4f09867`). The transcriber field carried the instruction he was
given; it reads "Dieu Donné Razafimahatratra (MadAvance MERV)" in the cleaned data and everything after it.

`tools/transcription_round1.py` cleans it (rules a–e, set by Adriaan Mol on 1 Oct 2026; every step a row of
`round1_ajustements.csv`), compares Adriaan, Dieu Donné and the machine on one observed window (sheet year of
record and photo date), and writes `round1_resume.md`, `round1_desaccords_humains.csv`,
`round1_calendriers.csv`, `round1_matrices.csv` and `data/transcription_round1.json`. The script fails if the
data no longer matches the rules as given (31 void marks on the ten calendars, 33 margin X on 43, the doubtful-sign
calendars, the nine 2027 sheets with no observed day). The block "Transcription check, round 1" on the page renders
from that JSON (`tools/render_transcription_round1.py`). No action's status changed.

- Rule (c) is matched on the note: a doubtful-sign phrase (point, barre or chiffre … suspect) and the dates written
  before it, ±1 day. "Croix suspecte" is a cross and is not converted, which is why calendar 14 (X on 24 Jun and
  9 Oct, its suspect points on 9–18 May) is not converted. Calendar 18's note says 6 Jan; the X is on 7 Jan, where
  Adriaan also has it.
- Calendar 43: the 3 ? of 10–12 Feb come from the same margin notes as the 33 X and are tagged with them.
- Adriaan's export predates the sheet years set on 28 Sep on ten sheets (30, 34, 38, 46, 50, 89, 91, 92, 97, 99),
  so his own `etat_cellule` is not used; on 89 his three X fall outside the window.
- Calendar 84 has no sheet year; its 2 X (25–26 Dec) are scored as observed, but would be void if it is 2025.

Cleaned: 63 X, 101 ? on 73 calendars (23 with an X).
On the 68 calendars all three read: humans agree on X/blank 99.8% (κ 0.7539);
Adriaan × machine 99.3% (κ -0.0035); Dieu Donné × machine 99.2% (κ -0.0041).
**The machine finds none of the humans' X** (sensitivity 0% against either, and against the
40 X both agree on); its 60 X fall on cells both read blank. This agrees with the
30 Sep figures (missed X 20 of Adriaan's 20 in frame), which the page's "rarely misses a marked day" does not.
Human disagreements to settle by eye: 127 days on 26 calendars.
