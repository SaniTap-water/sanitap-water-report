# -*- coding: utf-8 -*-
"""act-cal-working-day-ticks as a checklist Angelo fills in (7 Oct 2026).

The sheets listed in docs/transcription_round_notes.md, section "(a) Working-day
ticks", go into one Excel workbook in Water Documents/Work in Progress: one row
per sheet, a link to the full-size photograph on the published transcription
page, and a drop-down "Marks are" (Breakdown marks / Working-day ticks / Can't
tell). Angelo needs no access to this repository.

When the workbook comes back filled in, every build copies the answers into the
notes (generated region "calendar-check-answers") and into
data/calendar_check.json. The workbook is never overwritten once it exists.

    python tools/calendar_check.py --build   # photos + workbook (once)
    python tools/calendar_check.py --write   # answers -> notes and data (every build)
    python tools/calendar_check.py --check   # the notes match the data
Needs openpyxl (and cv2 for --build): run with ~/sdws1/venv/bin/python.
"""
import csv, datetime, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HUB = "/mnt/c/Users/bushp/OneDrive - SaniTap/Central Data Hub - Water Documents"
STORE = HUB + "/Evidence/mWater backup/images"
FOLDER = "Work in Progress"
NAME = "Calendar check - breakdown marks or working-day ticks.xlsx"
BOOK = os.path.join(HUB, FOLDER, NAME)
SP_URL = ("https://sanitap.sharepoint.com/sites/CentralDataHub/Water%20Documents/Work%20in%20Progress/"
          "Calendar%20check%20-%20breakdown%20marks%20or%20working-day%20ticks.xlsx")
SITE = "https://sanitap-water.github.io/sanitap-water-report/"
DATA = os.path.join(REPO, "data", "calendar_check.json")
NOTES = os.path.join(REPO, "docs", "transcription_round_notes.md")
BEGIN = "<!-- BEGIN GENERATED calendar-check-answers :: tools/calendar_check.py :: do not edit between these markers -->"
END = "<!-- END GENERATED calendar-check-answers -->"
CHOICES = ["Breakdown marks", "Working-day ticks", "Can't tell"]
HEAD = ["Calendar number", "Pump id and name", "District", "Printed year", "Photograph",
        "Marks are", "Comment"]
FIRST_ROW = 4                                  # rows 1-2 instructions, row 3 headers


def rows():
    """The sheets the notes list: calendar 43, then the run table."""
    notes = open(NOTES, encoding="utf8").read()
    sec = notes[notes.index("### (a) Working-day ticks"):notes.index("### (b)")]
    sel = {r["calendrier"]: r for r in csv.DictReader(open(os.path.join(REPO, "transcription", "validation_selection.csv"), encoding="utf8"))}
    years = {r["image_id"]: r["sheet_year"] for r in csv.DictReader(open(os.path.join(REPO, "data", "calendar_sheet_year.csv"), encoding="utf8"))}
    names = {}
    for r in csv.DictReader(open(os.path.expanduser("~/mwater-exports/wp_madavance.csv"), encoding="utf8")):
        names[r["code"]] = (r.get("name") or "").strip()
    out = []
    m = re.search(r"Calendar (\d+), water point (\d+) \(([^,]+), photographed (\d{4}-\d\d-\d\d)\)", sec)
    n, wp, site, date = m.groups()
    out.append({"calendar": int(n), "image": sel[n]["image_id"], "wp": wp, "site": site, "photo_date": date,
                "year": sel[n]["sheet_year"] or years.get(sel[n]["image_id"], ""),
                "url": f"{SITE}transcription/img/{int(n):02d}.jpg"})
    for r in re.finditer(r"^\| (\d+) \| (\S+) \| (\S+) \| (\d+) \| ([\w-]+) \| (\S+) \| ([0-9a-f]{32}) \|$", sec, re.M):
        run, a, z, wp, site, date, img = r.groups()
        out.append({"calendar": None, "image": img, "wp": wp, "site": site, "photo_date": date,
                    "year": years.get(img, ""), "run": f"{run} days marked in a row, {a} to {z}",
                    "url": f"{SITE}transcription/check/{img}.jpg"})
    for r in out:
        r["name"] = names.get(r["wp"], "")
    return out


def build():
    import cv2
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    rs = rows()
    os.makedirs(os.path.join(REPO, "transcription", "check"), exist_ok=True)
    for r in rs:
        if r["calendar"] is not None:
            continue
        dst = os.path.join(REPO, "transcription", "check", r["image"] + ".jpg")
        if os.path.isfile(dst):
            continue
        im = cv2.imread(os.path.join(STORE, r["image"][:2], r["image"] + ".jpg"))
        if im is None:
            sys.exit(f"cannot read the photograph {r['image']}")
        h, w = im.shape[:2]
        s = 1600 / float(max(h, w))
        if s < 1:
            im = cv2.resize(im, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
        cv2.imwrite(dst, im, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if os.path.isfile(BOOK):
        print(f"workbook exists, not overwritten: {BOOK}")
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Calendar check"
        ws["A1"] = ("FR : Ouvrez chaque photo (lien), regardez les marques du gardien et choisissez une réponse par ligne "
                    "dans « Marks are » : marques de panne, coches de jours de fonctionnement, ou impossible à dire.")
        ws["A2"] = ("EN: Open each photo (link), look at the guardian's marks and choose one answer per row in "
                    "\"Marks are\": breakdown marks, working-day ticks, or can't tell.")
        for c in ("A1", "A2"):
            ws[c].font = Font(bold=True)
            ws[c].alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells("A1:G1")
        ws.merge_cells("A2:G2")
        ws.row_dimensions[1].height = 36
        ws.row_dimensions[2].height = 36
        for i, h in enumerate(HEAD, 1):
            c = ws.cell(row=3, column=i, value=h)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="0E7490")
        dv = DataValidation(type="list", formula1='"' + ",".join(CHOICES) + '"', allow_blank=True,
                            showDropDown=False, showErrorMessage=True,
                            errorTitle="Marks are", error="Choose Breakdown marks, Working-day ticks or Can't tell.")
        ws.add_data_validation(dv)
        for k, r in enumerate(rs):
            row = FIRST_ROW + k
            ws.cell(row=row, column=1, value=r["calendar"] if r["calendar"] is not None else "—")
            ws.cell(row=row, column=2, value=f"{r['wp']} {r['name']}".strip())
            ws.cell(row=row, column=3, value=r["site"])
            ws.cell(row=row, column=4, value=int(r["year"]) if str(r["year"]).isdigit()
                    else f"not read; run dated {r['run'].split(', ')[1][:4]}" if r.get("run") else "not read")
            link = ws.cell(row=row, column=5, value=f"Open photo ({r['photo_date']})")
            link.hyperlink = r["url"]
            link.font = Font(color="0563C1", underline="single")
            dv.add(ws.cell(row=row, column=6))
            ws.cell(row=row, column=7, value=None)
        for col, w in zip("ABCDEFG", (16, 40, 16, 22, 26, 22, 50)):
            ws.column_dimensions[col].width = w
        ws.freeze_panes = "A4"
        wb.save(BOOK)
        print(f"workbook written: {BOOK} ({len(rs)} rows)")
    doc = {"note": "act-cal-working-day-ticks: the checklist Angelo fills in, and the answers copied from it at "
                   "each build (tools/calendar_check.py). Generated; do not edit.",
           "workbook": SP_URL, "rows": rs, "answers": {}, "read_on": None}
    if os.path.isfile(DATA):
        old = json.load(open(DATA, encoding="utf8"))
        doc["answers"], doc["read_on"] = old.get("answers", {}), old.get("read_on")
    json.dump(doc, open(DATA, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return 0


def read_answers(doc):
    """The workbook's choices, by image id. None when it cannot be read here."""
    if not os.path.isfile(BOOK):
        return None
    from openpyxl import load_workbook
    ws = load_workbook(BOOK, data_only=True).active
    out = {}
    for k, r in enumerate(doc["rows"]):
        choice = ws.cell(row=FIRST_ROW + k, column=6).value
        comment = ws.cell(row=FIRST_ROW + k, column=7).value
        if choice or comment:
            out[r["image"]] = {"marks_are": (choice or "").strip() or None, "comment": (comment or "").strip() or None}
    return out


def region(doc):
    n = len(doc["rows"])
    done = sum(1 for r in doc["rows"] if (doc["answers"].get(r["image"]) or {}).get("marks_are") in CHOICES)
    lines = [f"**Checklist for Angelo** ({doc['workbook']}): {done} of {n} sheets answered"
             + (f", read {doc['read_on']}." if doc.get("read_on") else "."), "",
             "| calendar | water point | site | photograph | marks are | comment |",
             "|---|---|---|---|---|---|"]
    for r in doc["rows"]:
        a = doc["answers"].get(r["image"]) or {}
        lines.append(f"| {r['calendar'] or '—'} | {r['wp']} | {r['site']} | [{r['image'][:8]}]({r['url']}) | "
                     f"{a.get('marks_are') or '—'} | {(a.get('comment') or '').replace('|', '/')} |")
    return "\n".join(lines)


def put_region(text, body):
    if BEGIN not in text:
        anchor = "### (b) Handwritten sheet year"
        text = text.replace(anchor, BEGIN + "\n" + END + "\n\n" + anchor, 1)
    a = text.index(BEGIN) + len(BEGIN)
    z = text.index(END)
    return text[:a] + "\n" + body + "\n" + text[z:]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if mode == "--build":
        return build()
    doc = json.load(open(DATA, encoding="utf8"))
    if mode == "--write":
        got = read_answers(doc)
        if got is None:
            print("calendar check: workbook not readable here; the committed answers stay")
        elif got != doc["answers"]:
            doc["answers"], doc["read_on"] = got, datetime.date.today().isoformat()
            json.dump(doc, open(DATA, "w", encoding="utf8"), indent=1, ensure_ascii=False)
        notes = open(NOTES, encoding="utf8").read()
        new = put_region(notes, region(doc))
        if new != notes:
            open(NOTES, "w", encoding="utf8").write(new)
        done = sum(1 for a in doc["answers"].values() if a.get("marks_are") in CHOICES)
        print(f"calendar check: {done} of {len(doc['rows'])} sheets answered")
        return 0
    if mode == "--check":
        notes = open(NOTES, encoding="utf8").read()
        ok = BEGIN in notes and put_region(notes, region(doc)) == notes
        print("calendar check: notes " + ("match the data" if ok else "DIFFER from data/calendar_check.json (run --write)"))
        return 0 if ok else 1
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main())
