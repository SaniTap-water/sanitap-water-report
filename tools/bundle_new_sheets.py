#!/usr/bin/env python3
"""Bundle newly drawn validation sheets into the transcription page.

Reads the selection file, copies any image not already bundled into
transcription/img/ at the same size and quality as the original fifty, and
extends calendars.json. Sheets that are in the round but outside the
human-to-machine frame keep their place; the page shows them identically and
the comparison tool keeps them apart.

    bundle_new_sheets.py --selection selection.csv --repo /path/to/repo
"""
import argparse, csv, json, os, sys
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = ("/mnt/c/Users/bushp/OneDrive - SaniTap/Central Data Hub - Water Documents"
         "/Evidence/mWater backup/images")
LONG_EDGE, QUALITY = 1600, 82


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selection", required=True)
    ap.add_argument("--repo", default="/home/bushp/sanitap-water-report")
    ap.add_argument("--map", default=os.path.join(HERE, "transcription_sheet_map.csv"))
    a = ap.parse_args()

    tr = os.path.join(a.repo, "transcription")
    cals = json.load(open(os.path.join(tr, "calendars.json")))
    have = {r["image_id"]: r["sheet"] for r in csv.DictReader(open(a.map))}
    by_n = {c["n"]: c for c in cals}
    nxt = max(by_n) + 1

    sel = list(csv.DictReader(open(a.selection)))
    added, updated = 0, 0
    for r in sel:
        iid = r["image_id"]
        if iid in have:                      # already bundled: just carry the year
            c = by_n.get(int(have[iid]))
            if c is not None and r["sheet_year"]:
                if c.get("y") != int(r["sheet_year"]):
                    c["y"] = int(r["sheet_year"]); updated += 1
            continue
        src = os.path.join(STORE, iid[:2], iid + ".jpg")
        im = cv2.imread(src)
        if im is None:
            print(f"  ! cannot read {iid}", file=sys.stderr); continue
        h, w = im.shape[:2]
        s = LONG_EDGE / float(max(h, w))
        if s < 1:
            im = cv2.resize(im, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
        h, w = im.shape[:2]
        name = f"{nxt:02d}.jpg"
        cv2.imwrite(os.path.join(tr, "img", name), im, [cv2.IMWRITE_JPEG_QUALITY, QUALITY])
        rec = {"n": nxt, "f": f"img/{name}", "wp": r["water_point"],
               "site": r["site"], "date": r["photo_date"], "w": w, "h": h}
        if r["sheet_year"]:
            rec["y"] = int(r["sheet_year"])
        cals.append(rec)
        have[iid] = str(nxt)
        with open(a.map, "a", newline="") as f:
            csv.writer(f).writerow([nxt, iid, "drawn for the frame correction"])
        nxt += 1; added += 1

    # write the assigned sheet numbers back into the selection file, or the
    # selection and the page cannot be joined at all for the new sheets
    if sel:
        for r in sel:
            if not r.get("calendrier") and r["image_id"] in have:
                r["calendrier"] = have[r["image_id"]]
        with open(a.selection, "w", newline="", encoding="utf8") as f:
            w = csv.DictWriter(f, fieldnames=list(sel[0].keys()))
            w.writeheader(); w.writerows(sel)

    cals.sort(key=lambda c: c["n"])
    json.dump(cals, open(os.path.join(tr, "calendars.json"), "w"),
              separators=(",", ":"))
    n_img = len([f for f in os.listdir(os.path.join(tr, "img")) if f.endswith(".jpg")])
    print(f"  {added} sheets bundled, {updated} years updated")
    print(f"  calendars.json now {len(cals)} records, img/ holds {n_img} files")
    print(f"  with a year: {sum(1 for c in cals if c.get('y'))}")


if __name__ == "__main__":
    main()
