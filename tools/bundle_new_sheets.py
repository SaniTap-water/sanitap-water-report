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


def carry_deduced(a, tr, cals):
    """Set 'yd' where the reader read no year and the weekday layout gave an
    accepted deduction; clear it everywhere else. The join is the selection
    file's calendrier -> image_id."""
    img = {r["calendrier"].strip(): r["image_id"].strip()
           for r in csv.DictReader(open(a.selection, encoding="utf-8-sig")) if r.get("calendrier")}
    ded = {r["image_id"]: int(r["deduced_year"])
           for r in csv.DictReader(open(a.deduced)) if r.get("accepted") == "yes" and r.get("deduced_year")}
    n = 0
    for c in cals:
        yd = None if c.get("y") else ded.get(img.get(str(c["n"]), ""))
        if yd:
            c["yd"] = yd; n += 1
        else:
            c.pop("yd", None)
    json.dump(cals, open(os.path.join(tr, "calendars.json"), "w"), separators=(",", ":"))
    print(f"  deduced year carried on {n} sheet(s), shown as 'a confirmer'")
    return 0


def sha(p):
    import hashlib
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def apply_orientation(a, tr, cals):
    """Serve every photograph upright (28 Sep 2026).

    The images carry no EXIF orientation, so a sheet photographed sideways or
    upside down was shown that way and the transcriber had to turn it. The
    reviewed rotation for each calendar is in --orientation (degrees clockwise
    to upright, one row per calendar, with who reviewed it). For a rotated
    calendar the original is kept in img_original/ and the upright copy is
    written to img/ FROM THAT ORIGINAL, so running this twice never rotates
    twice. The manifest records the applied rotation as "rot" and the upright
    size; data/transcription_orientation.csv records, per calendar, the
    rotation and the SHA-256 of the original and of the served file, which
    tools/check_consistency.py holds the served images to.
    """
    from PIL import Image
    TURN = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
            270: Image.Transpose.ROTATE_90}          # PIL turns counter-clockwise
    rev = {int(r["calendrier"]): r for r in csv.DictReader(open(a.orientation))}
    miss = sorted(c["n"] for c in cals if c["n"] not in rev)
    if miss:
        sys.exit(f"no orientation review for calendar(s) {miss}: review them before bundling")
    os.makedirs(os.path.join(tr, "img_original"), exist_ok=True)
    rec, turned = [], 0
    for c in cals:
        r = rev[c["n"]]
        deg = int(r["rotation_cw"]) % 360
        if deg not in (0, 90, 180, 270):
            sys.exit(f"calendar {c['n']}: rotation {deg} is not a quarter turn")
        served = os.path.join(tr, c["f"])
        orig = os.path.join(tr, "img_original", os.path.basename(c["f"]))
        if deg:
            if not os.path.isfile(orig):                     # first time: keep it
                import shutil
                shutil.copy2(served, orig)
            im = Image.open(orig)
            im.load()
            up = im.transpose(TURN[deg])
            up.save(served, "JPEG", quality=95, optimize=True)
            turned += 1
        elif os.path.isfile(orig):
            sys.exit(f"calendar {c['n']}: an original is kept but the review says 0 degrees")
        src = orig if deg else served
        ow, oh = Image.open(src).size
        w, h = Image.open(served).size
        c["w"], c["h"] = w, h
        if deg:
            c["rot"] = deg
        else:
            c.pop("rot", None)
        rec.append([c["n"], c["f"], deg,
                    os.path.relpath(src, a.repo), sha(src), f"{ow}x{oh}",
                    sha(served), f"{w}x{h}", r["reviewed_by"], r["reviewed_on"]])
    out = os.path.join(a.repo, "data", "transcription_orientation.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["calendrier", "served", "rotation_cw", "original", "original_sha256",
                    "original_size", "served_sha256", "served_size", "reviewed_by", "reviewed_on"])
        w.writerows(sorted(rec))
    json.dump(sorted(cals, key=lambda c: c["n"]), open(os.path.join(tr, "calendars.json"), "w"),
              separators=(",", ":"))
    print(f"  {turned} calendar(s) served upright from a kept original; "
          f"{len(cals) - turned} already upright; record in {os.path.relpath(out, a.repo)}")
    return 0


# year sources, as the page shows and exports them
YEAR_SRC = {"imprime": "claude_imprime", "manuscrit": "claude_manuscrit",
            "calendrier": "claude_calendrier"}


def apply_years(a, tr, cals):
    """Sheet years read by a person where the reader read none (28 Sep 2026).

    --years lists calendrier, year and how it was read: printed on the sheet,
    handwritten on it, or deduced from the printed weekday layout. The year
    becomes the sheet's "y" with its source in "ysrc", so the page shows who
    read it and exports it as annee_source; the transcriber can still change
    it. A deduced-but-unconfirmed "yd" is cleared where a year is now set."""
    by_n = {c["n"]: c for c in cals}
    n = 0
    for r in csv.DictReader(open(a.years)):
        c = by_n.get(int(r["calendrier"]))
        if c is None:
            sys.exit(f"calendar {r['calendrier']} is not in calendars.json")
        if c.get("y") and not c.get("ysrc") and int(c["y"]) != int(r["year"]):
            sys.exit(f"calendar {c['n']}: the reader read {c['y']}, the list says {r['year']}")
        c["y"], c["ysrc"] = int(r["year"]), YEAR_SRC[r["source"]]
        c.pop("yd", None)
        n += 1
    json.dump(sorted(cals, key=lambda c: c["n"]), open(os.path.join(tr, "calendars.json"), "w"),
              separators=(",", ":"))
    print(f"  {n} sheet year(s) set with their source; "
          f"{sum(1 for c in cals if not c.get('y'))} calendar(s) still without a year")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selection", required=True)
    ap.add_argument("--repo", default="/home/bushp/sanitap-water-report")
    ap.add_argument("--map", default=os.path.join(HERE, "transcription_sheet_map.csv"))
    ap.add_argument("--deduced", default=None,
                    help="data/calendar_sheet_year_deduced.csv: carry an ACCEPTED year "
                         "deduced from the printed weekday layout as 'yd' on a sheet with "
                         "no year read. It is shown on the page as 'a confirmer', never as y.")
    ap.add_argument("--deduced-only", action="store_true",
                    help="only set or clear 'yd' from --deduced; bundle nothing")
    ap.add_argument("--orientation", default=None,
                    help="data/transcription_orientation_review.csv: serve every "
                         "calendar upright; bundle nothing")
    ap.add_argument("--years", default=None,
                    help="data/transcription_sheet_years.csv: set sheet years read by a "
                         "person, with their source; bundle nothing")
    a = ap.parse_args()

    tr = os.path.join(a.repo, "transcription")
    cals = json.load(open(os.path.join(tr, "calendars.json")))
    if a.deduced_only:
        return carry_deduced(a, tr, cals)
    if a.orientation or a.years:
        if a.orientation:
            apply_orientation(a, tr, cals)
        if a.years:
            apply_years(a, tr, cals)
        return 0
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
    sys.exit(main())
