#!/usr/bin/env python3
"""Read the year printed on each calendar sheet, with OCR.

Every generation of the template prints "20XX ID:" in the header. That string
is the only place the sheet says which year it is for, and the year is what
decides both the month lengths (2024 is a leap year) and the observable
window, so it has to be read off the sheet rather than taken from the date the
photograph happened to be taken.

Two stages, because OCR over a whole header band is slow:
  1. the '202' prefix - identical on every sheet ever printed - is located by
     multi-scale template match, in both orientations, since many of these
     photographs are upside down and the rectifier does not turn them;
  2. a small region around that match is passed to the OCR, and the first
     four-digit 20XX token is taken.
When the anchor finds nothing, the whole header band is OCR'd instead.

Nothing is guessed. A sheet whose year cannot be read is written out with an
empty year and a reason, and stays out of every year-dependent figure.
"""
import argparse, csv, os, re, sys, time
import numpy as np, cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import caltools

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = ("/mnt/c/Users/bushp/OneDrive - SaniTap/Central Data Hub - Water Documents"
         "/Evidence/mWater backup/images")
TMPL = os.path.join(HERE, "tmpl_202.png")
SCALES = np.linspace(0.55, 1.70, 20)
YEAR = re.compile(r"(?<!\d)20(2[0-9])(?!\d)")
ORIENTS_A = (0, 180)          # upright and upside down
ORIENTS_B = (90, 270)         # photographed on its side
PLAUSIBLE = {"2023", "2024", "2025", "2026", "2027", "2028"}


def upright(gray, k):
    """The rectified sheet turned the right way up for orientation k.

    The rectifier always warps the detected quad onto the same landscape
    rectangle, so a sheet photographed on its side comes out both turned AND
    stretched - a 1.44:1 frame holding what should be a 1:1.44 sheet. Turning
    it back and resizing to the canonical shape undoes the stretch, which
    matters because the template match is multi-scale but not anisotropic.
    """
    if k == 0:
        g = gray
    elif k == 180:
        g = cv2.rotate(gray, cv2.ROTATE_180)
    elif k == 90:
        g = cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE)
    else:
        g = cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE)
    if k in (90, 270):
        g = cv2.resize(g, (caltools.CANON_W, caltools.CANON_H),
                       interpolation=cv2.INTER_AREA)
    return g


def anchor(gray, tmpl, orients=(0, 180)):
    best = None
    for orient in orients:
        g = upright(gray, orient)
        H = g.shape[0]
        band = g[:int(0.42 * H)]
        for s in SCALES:
            t = cv2.resize(tmpl, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            if t.shape[0] >= band.shape[0] or t.shape[1] >= band.shape[1]:
                continue
            res = cv2.matchTemplate(band, t, cv2.TM_CCOEFF_NORMED)
            _, mx, _, loc = cv2.minMaxLoc(res)
            if best is None or mx > best[0]:
                best = (mx, orient, loc[0], loc[1], t.shape[1], t.shape[0])
    return best


def read_text(ocr, img):
    try:
        res, _ = ocr(img)
    except Exception:
        return []
    return [(t[1], float(t[2])) for t in (res or [])]


def pick(items):
    best = None
    for txt, conf in items:
        t = txt.replace(" ", "")
        for m in YEAR.finditer(t):
            y = "20" + m.group(1)
            if y in PLAUSIBLE and (best is None or conf > best[1]):
                best = (y, conf, txt)
    return best


# ---------------------------------------------------------------------------
# Weekday-layout fallback (28 Sep 2026). Some sheets carry no printed year:
# an older template has only "ID:" in its header and the year, if any, is
# written by hand, which the anchor above never sees. Every template does
# print the weekday beside each day ("01 LUN", "02 MAR" ...), one column per
# month, and that layout fixes the year: only one year in PLAUSIBLE puts each
# weekday where the sheet has it. The result is a DEDUCTION, written to its
# own file and shown on the transcription page as "a confirmer"; it never
# fills sheet_year, which stays the year read off the sheet.
# ---------------------------------------------------------------------------
WD = {"LUN": 0, "MAR": 1, "MER": 2, "JEU": 3, "VEN": 4, "SAM": 5, "DIM": 6,
      "LUIN": 0, "VEND": 4}
WD_RE = re.compile(r"(\d{1,2})?\s*(LUIN|VEND|LUN|MAR|MER|JEU|VEN|SAM|DIM)\b")
NUM_RE = re.compile(r"^\s*(\d{1,2})\s*$")


def weekday_pairs(items):
    """items: [(box, text)] -> [(x, day, weekday)] from the printed grid"""
    toks, nums = [], []
    for box, txt in items:
        cx = sum(p[0] for p in box) / 4.0
        cy = sum(p[1] for p in box) / 4.0
        h = max(p[1] for p in box) - min(p[1] for p in box)
        t = txt.upper().replace("O", "0") if NUM_RE.match(txt.upper().replace("O", "0")) else txt.upper()
        m = NUM_RE.match(t)
        if m:
            nums.append((cx, cy, h, int(m.group(1))))
            continue
        for m in WD_RE.finditer(txt.upper()):
            toks.append((cx, cy, h, int(m.group(1)) if m.group(1) else None, WD[m.group(2)]))
    pairs = []
    for cx, cy, h, d, w in toks:
        if d is None:
            near = [n for n in nums if abs(n[1] - cy) < 0.6 * max(h, n[2], 1)
                    and 0 < cx - n[0] < 6 * max(h, 1)]
            if not near:
                continue
            d = min(near, key=lambda n: cx - n[0])[3]
        if 1 <= d <= 31:
            pairs.append((cx, d, w))
    return pairs


def weekday_year(pairs):
    """-> (year, agreement, margin, n) or None. Months come from column
    position: x is clustered into columns, the column pitch is the median
    spacing of adjacent clusters, and every offset that keeps twelve columns
    on the sheet is tried, so a missing first column cannot shift a month."""
    import datetime, statistics
    if len(pairs) < 8:
        return None
    xs = sorted(p[0] for p in pairs)
    span = xs[-1] - xs[0]
    if span <= 0:
        return None
    cl = [[xs[0]]]
    for x in xs[1:]:
        (cl[-1].append(x) if x - cl[-1][-1] < span / 30.0 else cl.append([x]))
    cent = [sum(c) / len(c) for c in cl]
    gaps = [b - a for a, b in zip(cent, cent[1:])]
    if not gaps:
        return None
    pitch = statistics.median(gaps)
    idx = [round((p[0] - cent[0]) / pitch) for p in pairs]
    top = max(idx)
    if top > 11:
        return None
    scores = {}
    for y in sorted(int(v) for v in PLAUSIBLE):
        best = 0.0
        for shift in range(0, 12 - top):
            ok = n = 0
            for (x, d, w), k in zip(pairs, idx):
                m = k + shift + 1
                try:
                    wd = datetime.date(y, m, d).weekday()
                except ValueError:
                    continue
                n += 1
                ok += (wd == w)
            if n:
                best = max(best, ok / n)
        scores[y] = best
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    (y1, s1), (_, s2) = ranked[0], ranked[1]
    return y1, s1, s1 - s2, len(pairs)


def weekday_fallback(ocr, a):
    """--weekday-fallback LIST.csv (image_id,path) -> --out CSV"""
    rows = list(csv.DictReader(open(a.weekday_fallback)))
    out = open(a.out, "w", newline="")
    w = csv.writer(out)
    w.writerow(["image_id", "deduced_year", "agreement", "margin", "pairs",
                "orientation", "accepted", "note"])
    for r in rows:
        im = cv2.imread(r["path"])
        best = None
        for k in (0, 180):
            g = im if k == 0 else cv2.rotate(im, cv2.ROTATE_180)
            try:
                res, _ = ocr(g)
            except Exception:
                res = []
            got = weekday_year(weekday_pairs([(t[0], t[1]) for t in (res or [])]))
            if got and (best is None or (got[1], got[3]) > (best[1][1], best[1][3])):
                best = (k, got)
        if best is None:
            w.writerow([r["image_id"], "", "", "", "", "", "no", "too few weekday labels read"])
            print(f"  {r['image_id'][:8]}  no deduction")
            continue
        k, (y, s1, mg, n) = best
        ok = n >= 8 and s1 >= 0.85 and mg >= 0.25
        w.writerow([r["image_id"], y if ok else "", f"{s1:.3f}", f"{mg:.3f}", n, k,
                    "yes" if ok else "no",
                    "deduced from the printed weekday layout - to be confirmed" if ok
                    else f"best {y} not clear enough"])
        print(f"  {r['image_id'][:8]}  {y}  agreement {s1:.2f}  margin {mg:.2f}  pairs {n}  "
              f"{'ACCEPTED' if ok else 'rejected'}")
        out.flush()
    out.close()
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="extracted")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--only", default=None,
                    help="file of image_ids, one per line: re-read just these")
    ap.add_argument("--out", default=os.path.join(HERE, "sheet_year_ocr.csv"))
    ap.add_argument("--weekday-fallback", default=None,
                    help="CSV of image_id,path for sheets with no printed year: deduce "
                         "the year from the printed weekday layout, to --out")
    a = ap.parse_args()

    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()
    if a.weekday_fallback:
        return weekday_fallback(ocr, a)
    tmpl = cv2.imread(TMPL, cv2.IMREAD_GRAYSCALE)

    rows = list(csv.DictReader(open(os.path.join(HERE, "legibility2.csv"))))
    if a.stage:
        rows = [r for r in rows if r["stage"] == a.stage]
    if a.only:
        want = {ln.strip() for ln in open(a.only) if ln.strip()}
        rows = [r for r in rows if r["image_id"] in want]
    if a.skip:
        rows = rows[a.skip:]
    if a.limit:
        rows = rows[:a.limit]

    out = open(a.out, "w", newline="")
    w = csv.writer(out)
    w.writerow(["image_id", "water_point", "site", "photo_date", "sheet_year",
                "confidence", "route", "anchor_score", "text"])
    t0, got = time.time(), 0
    for i, r in enumerate(rows, 1):
        p = os.path.join(STORE, r["image_id"][:2], r["image_id"] + ".jpg")
        year, conf, route, ascore, text = "", 0.0, "none", 0.0, ""
        try:
            im, small = caltools.load(p)
            if im is not None:
                q, _ = caltools.sheet_quad(small)
                if q is not None:
                    rect = caltools.rectify(im, q, im.shape[1] / float(small.shape[1]))
                    gray = cv2.cvtColor(rect, cv2.COLOR_BGR2GRAY)
                    hit = anchor(gray, tmpl, ORIENTS_A)
                    hits = []
                    if hit:
                        ascore = hit[0]
                        _, orient, x, y0, tw, th = hit
                        g = upright(gray, orient)
                        dw = tw / 3.0
                        X0 = max(0, int(x - dw * 2.0))
                        X1 = min(g.shape[1], int(x + tw + dw * 7.0))
                        Y0 = max(0, int(y0 - th * 0.8))
                        Y1 = min(g.shape[0], int(y0 + th * 1.8))
                        crop = g[Y0:Y1, X0:X1]
                        if crop.size and crop.shape[0] > 12 and crop.shape[1] > 30:
                            hits = read_text(ocr, cv2.resize(
                                crop, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC))
                            route = "anchor"
                    best = pick(hits)
                    if best is None:
                        # fall back to the whole header band, each way up
                        for k in ORIENTS_A:
                            g = upright(rect, k)
                            b = g[:int(g.shape[0] * 0.30)]
                            b = cv2.resize(b, None, fx=0.6, fy=0.6,
                                           interpolation=cv2.INTER_AREA)
                            best = pick(read_text(ocr, b))
                            if best:
                                route = "band"
                                break

                    if best is None:
                        # Sideways. Five of eleven undated sheets inspected by
                        # hand were photographed at 90 degrees, which puts the
                        # header up the side of the rectified frame where
                        # nothing above looks. This costs a second sweep, so it
                        # is only paid on sheets that have already failed.
                        hit2 = anchor(gray, tmpl, ORIENTS_B)
                        if hit2:
                            _, orient, x, y0, tw, th = hit2
                            g = upright(gray, orient)
                            dw = tw / 3.0
                            crop = g[max(0, int(y0 - th * 0.8)):
                                     min(g.shape[0], int(y0 + th * 1.8)),
                                     max(0, int(x - dw * 2.0)):
                                     min(g.shape[1], int(x + tw + dw * 7.0))]
                            if crop.size and crop.shape[0] > 12 and crop.shape[1] > 30:
                                best = pick(read_text(ocr, cv2.resize(
                                    crop, None, fx=2.0, fy=2.0,
                                    interpolation=cv2.INTER_CUBIC)))
                                if best:
                                    route = "sideways-anchor"
                                    ascore = max(ascore, hit2[0])
                        if best is None:
                            for k in ORIENTS_B:
                                g = upright(rect, k)
                                b = g[:int(g.shape[0] * 0.30)]
                                b = cv2.resize(b, None, fx=0.6, fy=0.6,
                                               interpolation=cv2.INTER_AREA)
                                best = pick(read_text(ocr, b))
                                if best:
                                    route = "sideways-band"
                                    break
                    if best:
                        year, conf, text = best[0], best[1], best[2][:60]
                        got += 1
        except Exception:
            pass
        w.writerow([r["image_id"], r["water_point"], r["site"], r["date"],
                    year, f"{conf:.3f}", route, f"{ascore:.3f}", text])
        if i % 100 == 0:
            out.flush()
            print(f"  {i}/{len(rows)}  dated {got}  {time.time()-t0:.0f}s", flush=True)
    out.close()
    print(f"  {len(rows)} images, {got} dated, {time.time()-t0:.0f}s -> {a.out}")


if __name__ == "__main__":
    main()
