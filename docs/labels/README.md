# Water-quality labels for the piped water points

Made by `tools/make_wq_labels.py` from `piped_water_points.csv`. The CSV lists every water point
registered as a Distribution Point (form `8a3af50c`) on a managed or in-process piped system,
read live from mWater (read only) on 28 September 2026.

| File | What | Print on |
|---|---|---|
| `wq_bottle_labels.pdf` | 50 × 25 mm bottle labels, 24 per A4 sheet (3 × 8 on a 70 × 37 mm pitch), one full sheet per water point | A4 24-up sticker sheet, 70 × 37 mm (for example Herma 4453 or Avery 3475), at **100 % / actual size** |
| `wq_tap_plates.pdf` | one 100 × 70 mm plate per water point, to fix on the tap | polyester or vinyl label stock, or paper laminated both sides |
| `piped_water_points.csv` | the list: ID, name, parent system, region | — |

Each label shows the water point ID in large type, the point's name and its system's name. The QR
code encodes the ID and nothing else, so scanning it into the ID question fills that question.

**On 28 September 2026 the list holds one water point:** the Antananarivo SmarTap kiosk
`1125843383` (system `1125843376`). None of the four Moramanga systems (Amboasary gara
`1108783583`, Ambohibola `1108783624`, Amboanjo `1108783648`, Andilanatoby `1108783662`) has a
registered tap yet. When they are registered, add the rows to the CSV and run:

```
~/sdws1/venv/bin/python tools/make_wq_labels.py
```

The script fails if a final Distribution Point registration in the extract is missing from the
CSV.
