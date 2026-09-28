# -*- coding: utf-8 -*-
"""Printable water-quality bottle labels and tap plates for the piped water points.

The list is docs/labels/piped_water_points.csv: every water point registered as
a Distribution Point (form 8a3af50c) on a managed or in-process piped system,
read live from mWater (read only) on the date in the PDFs. This script renders
it; it never writes to mWater.

  docs/labels/wq_bottle_labels.pdf   A4, 24-up (3 x 8 on a 70 x 37 mm pitch, the
                                     common 24-label sticker sheet); each label
                                     is 50 x 25 mm, centred in its sticker, with
                                     a faint cut line. One full sheet per water
                                     point, so every round has spares.
  docs/labels/wq_tap_plates.pdf      one 100 x 70 mm page per water point, for a
                                     plate fixed on the tap (print on polyester
                                     or vinyl, or laminate).

Each label carries the water point ID in large type, the point's name, its
system's name and a QR code that encodes the ID and nothing else.

It fails if a final Distribution Point registration in the extract
(~/mwater-exports/piped_point_reg.json) is missing from the list.

    ~/sdws1/venv/bin/python tools/make_wq_labels.py
"""
import csv, datetime, html, io, json, os, sys

import segno
from playwright.sync_api import sync_playwright

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(REPO, "docs", "labels")
LIST = os.path.join(DIR, "piped_water_points.csv")
REG = os.path.expanduser("~/mwater-exports/piped_point_reg.json")
PT_REG_FORM, PR_POINT = "8a3af50ceec84cda85d454d96079991d", "8f174aec"
PER_SHEET, COLS, PITCH_W, PITCH_H = 24, 3, 70, 37      # mm
LABEL_W, LABEL_H = 50, 25                              # mm
PLATE_W, PLATE_H = 100, 70                             # mm


def points():
    with io.open(LIST, encoding="utf8") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("water_point_id")]
    listed = {r["water_point_id"] for r in rows}
    if os.path.isfile(REG):
        missing = set()
        for r in json.load(open(REG, encoding="utf8")):
            if r.get("form") != PT_REG_FORM or r.get("status") != "final":
                continue
            for k, v in (r.get("data") or {}).items():
                if k.startswith(PR_POINT):
                    code = ((v or {}).get("value") or {}).get("code")
                    if code and str(code) not in listed:
                        missing.add(str(code))
        if missing:
            sys.exit(f"make_wq_labels: registered point(s) missing from {LIST}: "
                     + ", ".join(sorted(missing)))
    return rows


def qr(code, mm):
    """The ID only, as an inline SVG sized in millimetres."""
    q = segno.make(code, error="m", micro=False)
    n = q.symbol_size(scale=1, border=2)[0]
    svg = q.svg_inline(scale=1, border=2, dark="#000")
    # segno writes width/height but no viewBox, so the symbol would not scale
    return svg.replace("<svg ", f'<svg viewBox="0 0 {n} {n}" preserveAspectRatio="xMidYMid meet" '
                       f'style="width:{mm}mm;height:{mm}mm;flex:none;display:block" ', 1)


BASE = """<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: {w}mm {h}mm; margin: 0 }}
* {{ box-sizing: border-box; margin: 0; padding: 0 }}
body {{ font-family: "DejaVu Sans", Arial, sans-serif; color: #000; -webkit-print-color-adjust: exact }}
.id {{ font-family: "DejaVu Sans Mono", monospace; font-weight: 700; letter-spacing: -0.02em; white-space: nowrap }}
.t {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis }}
{css}
</style></head><body>{body}</body></html>"""

SHEET_CSS = f"""
.sheet {{ width: 210mm; height: 297mm; padding: {(297 - PITCH_H * 8) / 2}mm 0 0 0;
         display: grid; grid-template-columns: repeat({COLS}, {PITCH_W}mm);
         grid-auto-rows: {PITCH_H}mm; page-break-after: always }}
.sheet:last-child {{ page-break-after: auto }}
.cell {{ display: flex; align-items: center; justify-content: center }}
.lab {{ width: {LABEL_W}mm; height: {LABEL_H}mm; outline: 0.1mm dashed #bbb;
        padding: 1.2mm 1.5mm; display: flex; flex-direction: column }}
.lab .id {{ font-size: 18.5pt; line-height: 1; text-align: center }}
.lab .row {{ display: flex; gap: 1.6mm; margin-top: 1.1mm; align-items: center }}
.lab .txt {{ min-width: 0; font-size: 6.4pt; line-height: 1.25 }}
.lab .nm {{ font-weight: 700; font-size: 7.4pt }}
.lab .cap {{ color: #444; font-size: 5.2pt }}
"""

PLATE_CSS = """
.plate { width: 100mm; height: 70mm; padding: 4mm 5mm; display: flex; flex-direction: column;
         border: 0.6mm solid #000; page-break-after: always }
.plate:last-child { page-break-after: auto }
.plate .cap { font-size: 7.5pt; color: #333; letter-spacing: 0.02em }
.plate .id { font-size: 34pt; line-height: 1.05 }
.plate .row { display: flex; gap: 4mm; margin-top: 2mm; align-items: flex-start }
.plate .txt { min-width: 0; font-size: 9pt; line-height: 1.35 }
.plate .nm { font-weight: 700; font-size: 13pt; line-height: 1.2 }
"""


def label(p):
    e = html.escape
    return (f'<div class="lab"><div class="id">{e(p["water_point_id"])}</div>'
            f'<div class="row">{qr(p["water_point_id"], 13)}<div class="txt">'
            f'<div class="t nm">{e(p["name"])}</div>'
            f'<div class="t">{e(p["parent_system_name"])}</div>'
            f'<div class="t cap">Point d\'eau · échantillon QE</div></div></div></div>')


def plate(p):
    e = html.escape
    local = f' &mdash; {e(p["local_name"])}' if p.get("local_name") else ""
    return (f'<div class="plate"><div class="cap">POINT D\'EAU / WATER POINT ID</div>'
            f'<div class="id">{e(p["water_point_id"])}</div>'
            f'<div class="row">{qr(p["water_point_id"], 36)}<div class="txt">'
            f'<div class="nm">{e(p["name"])}{local}</div>'
            f'<div>Système / system: <b>{e(p["parent_system_name"])}</b> '
            f'({e(p["parent_system_id"])})</div>'
            f'<div class="cap" style="margin-top:2mm">{e(p["region"])}</div>'
            f'</div></div></div>')


def render(page, doc, out, w, h):
    page.set_content(doc, wait_until="load")
    page.pdf(path=out, width=f"{w}mm", height=f"{h}mm", print_background=True,
             margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})


def main():
    pts = points()
    if not pts:
        sys.exit("make_wq_labels: the list is empty")
    sheets = "".join(
        '<div class="sheet">' + "".join(f'<div class="cell">{label(p)}</div>'
                                        for _ in range(PER_SHEET)) + "</div>"
        for p in pts)
    plates = "".join(plate(p) for p in pts)
    out_l = os.path.join(DIR, "wq_bottle_labels.pdf")
    out_p = os.path.join(DIR, "wq_tap_plates.pdf")
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page()
        render(pg, BASE.format(w=210, h=297, css=SHEET_CSS, body=sheets), out_l, 210, 297)
        render(pg, BASE.format(w=PLATE_W, h=PLATE_H, css=PLATE_CSS, body=plates),
               out_p, PLATE_W, PLATE_H)
        b.close()
    print(f"{len(pts)} water point(s): {len(pts) * PER_SHEET} bottle labels on "
          f"{len(pts)} A4 sheet(s) -> {os.path.relpath(out_l, REPO)}; "
          f"{len(pts)} plate(s) -> {os.path.relpath(out_p, REPO)} "
          f"({datetime.date.today().isoformat()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
