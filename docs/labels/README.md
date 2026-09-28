# Water-quality labels for the piped water points

Made by `tools/make_wq_labels.py` from `piped_water_points.csv`. The CSV lists every water point
registered as a Distribution Point (form `8a3af50c`) on a managed or in-process piped system,
read live from mWater (read only) on 28 September 2026.

## How the ID gets onto a sample

**Cathy writes the water point ID on each bottle by hand.** Pre-printed stickers are hard to get
in Antananarivo, so the bottle-label sheet is optional. Use it if stickers are to hand; the round
does not depend on it.

**She copies the ID from the tap itself:** from the tap plate below, or from the ID painted or
stencilled on the tap. That is the reference, not a list carried in the field.

**Only public standposts and kiosks are sampled**, for now: what comes out of the tap. No
source, tank or household samples. A sample recorded against the system, or at a household, is
flagged as outside protocol and never paired.

**A wrong ID is caught when the result is paired.** The build pairs each result with the most
recent unpaired sampling record at the **same water point**, taken within the **72 hours** before
the result was submitted; each sample pairs once (`tools/rebuild_piped_wq.py`). A result whose ID
matches no such sample is left unpaired and flagged, with its response code, in the collapsed
pairing block of the piped water-quality panel and in the `publish.sh` readout. A sample with no
result after 7 days is flagged the same way. The sampling date on the result is only a
cross-check. Nothing is paired on a guess.

## The files

| File | What | Print on |
|---|---|---|
| `wq_bottle_labels.pdf` | *optional* — 50 × 25 mm bottle labels, 24 per A4 sheet (3 × 8 on a 70 × 37 mm pitch), one full sheet per water point | A4 24-up sticker sheet, 70 × 37 mm (for example Herma 4453 or Avery 3475), at **100 % / actual size** |
| `wq_tap_plates.pdf` | one 100 × 70 mm plate per water point, to fix on the tap: the reference the ID is copied from | polyester or vinyl label stock, or paper laminated both sides |
| `piped_water_points.csv` | the list: ID, name, parent system, region | — |

Each label shows the water point ID in large type, the point's name and its system's name. The QR
code encodes the ID and nothing else, so scanning it into the ID question fills that question.

**On 28 September 2026 the list holds one water point:** the Antananarivo SmarTap kiosk
`1125843383` (system `1125843376`). None of the four Moramanga systems (Amboasary gara
`1108783583`, Ambohibola `1108783624`, Amboanjo `1108783648`, Andilanatoby `1108783662`) has a
registered standpost yet. They are registered once the duplicate system records around Amboasary
are reconciled (actions `act-moramanga-system-dedupe` and `act-moramanga-register-standposts`).
Then add the rows to the CSV and run:

```
~/sdws1/venv/bin/python tools/make_wq_labels.py
```

The script fails if a final Distribution Point registration in the extract is missing from the
CSV.
