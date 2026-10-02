#!/usr/bin/env python3
"""Why the calendar reader misses marks: crops and measures on round-1 cells.

Takes the days both human readers marked X in transcription round 1 (Adriaan
Mol and Dieu Donné Razafimahatratra, cleaned, inside the observed window, on
calendars the machine reads) and an equal number of days both read blank
(seeded draw), re-runs the reader's own geometry on each photograph
(tools/run_extract2.classify, tools/caltools.py), and saves for each cell:

  * the cell window the reader samples (its marking window, inset), and
  * a context crop of the same day row across the whole cell and its
    neighbours, with the sampled window outlined,

side by side with the human mark, plus the ink measures the diagnosis needs:
the reader's own ink fraction, the same without the blue-tint mask, the
fraction of blue-ink pixels, and the best ink fraction anywhere within one
row pitch of the registered row (a registration offset shows up there).

Nothing here changes the reader. Output: data/reader_diagnosis/.

    tools/diagnose_reader.py [--n-blank 40] [--seed 20261001]
"""
import argparse, csv, json, os, random, sys
import numpy as np, cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import caltools, run_extract2  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "reader_diagnosis")
TDIR = os.path.join(REPO, "data", "transcriptions")


def round1_cells():
    """(cal, image, month, day) for both-X and both-blank days in round 1."""
    sel = {r["calendrier"]: r["image_id"] for r in
           csv.DictReader(open(os.path.join(REPO, "transcription", "validation_selection.csv"), encoding="utf-8-sig"))}
    r1 = json.load(open(os.path.join(REPO, "data", "transcription_round1.json"), encoding="utf8"))
    three = {str(c) for c in r1["three_way_calendars"]}
    dd = {}
    for r in csv.DictReader(open(os.path.join(TDIR, "round1_dieu-donne_nettoye.csv"), encoding="utf8")):
        if r["inclus"] == "oui" and r["calendrier"] in three:
            dd[(r["calendrier"], int(r["mois"]), int(r["jour"]))] = r["releve_net"]
    am = {}
    for r in csv.DictReader(open(os.path.join(TDIR, "releves_calendriers_mol-adriaan_serie1_2026-09-28.csv"),
                                 encoding="utf-8-sig")):
        if r["mois"] and r["jour"]:
            am[(r["calendrier"], int(r["mois"]), int(r["jour"]))] = (r["releve"] or "").strip()
    both_x, both_blank = [], []
    for k, v in dd.items():
        if k not in am:
            continue
        if v == "X" and am[k] == "X":
            both_x.append(k)
        elif v == "" and am[k] == "":
            both_blank.append(k)
    return sel, sorted(both_x, key=lambda k: (int(k[0]), k[1], k[2])), sorted(both_blank)


def geometry(image_id):
    """The reader's own geometry for one photograph, as run_extract2 computes it."""
    p = os.path.join(run_extract2.STORE, image_id[:2], image_id + ".jpg")
    im, small = caltools.load(p)
    stage, reason, b = run_extract2.classify({"image_id": image_id}, im, small)
    if stage != "extracted" or not b.get("day_calls"):
        return None, f"{stage}: {reason or 'no day calls'}"
    rect, bb, gen = b["rect"], b["bbox"], b["gen"]
    x0, y0, x1, y1 = bb
    rows = caltools.fit_day_rows(rect, bb, b["fit_x"], b["fit_pitch"])
    if rows is not None:
        method, y_top, y_p, offs = rows
        g = dict(kind="rows", method=method, xl=x0 + b["fit_x"], xp=b["fit_pitch"], yt=y_top, yp=y_p,
                 offs=list(offs))
    else:
        g = dict(kind="rule fit", method="rule fit", xl=x0 + b["fit_x"], xp=b["fit_pitch"],
                 yt=y0 + b["fit_y"], yp=b["fit_ypitch"], offs=[0.0] * 12)
    g.update(rect=rect, bb=bb, gen=gen, marks=b["marks"], generation=b.get("generation"))
    return g, ""


def ink_maps(rect, bb):
    hsv = cv2.cvtColor(rect, cv2.COLOR_BGR2HSV)
    v, s, h = (hsv[:, :, i].astype(np.float32) for i in (2, 1, 0))
    x0, y0, x1, y1 = bb
    thr = max(60.0, np.percentile(v[y0:y1, x0:x1], 25) * 0.75)
    tint = (h > 85) & (h < 140) & (s > 45)
    dark = v < thr
    return {"reader": (dark & ~tint), "no_tint_mask": dark, "tint": tint,
            "blue_ink": tint & (v < np.percentile(v[y0:y1, x0:x1], 50)) & (s > 80), "thr": thr}


def cell_box(g, m, d, full=False):
    f0, f1 = (0.0, 1.0) if full else caltools.cell_window(g["gen"])
    a = g["xl"] + (m + f0) * g["xp"]
    b = g["xl"] + (m + f1) * g["xp"]
    yt = g["yt"] + g["offs"][m]
    ins = 0 if full else max(1.0, g["yp"] * 0.18)
    c0 = yt + d * g["yp"] + ins
    c1 = yt + (d + 1) * g["yp"] - ins
    return int(round(a + (0 if full else 1))), int(round(c0)), int(round(b - (0 if full else 1))), int(round(c1))


def frac(mask, box):
    a, c0, b, c1 = box
    H, W = mask.shape
    a, b, c0, c1 = max(0, a), min(W, b), max(0, c0), min(H, c1)
    if b <= a or c1 <= c0:
        return 0.0
    return float(mask[c0:c1, a:b].mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-blank", type=int, default=None, help="default: as many as the X cells")
    ap.add_argument("--seed", type=int, default=20261001)
    a = ap.parse_args()
    sel, both_x, both_blank = round1_cells()
    rnd = random.Random(a.seed)
    blanks = sorted(rnd.sample(both_blank, a.n_blank or len(both_x)), key=lambda k: (int(k[0]), k[1], k[2]))
    os.makedirs(os.path.join(OUT, "crops"), exist_ok=True)

    geo = {}
    rows = []
    for human, cells in (("X", both_x), ("blank", blanks)):
        for cal, m, d in cells:
            img = sel[cal]
            if img not in geo:
                geo[img] = geometry(img)
            g, why = geo[img]
            row = {"calendrier": cal, "image_id": img, "mois": m, "jour": d, "humains": human}
            if g is None:
                row.update(note=why)
                rows.append(row)
                continue
            mk = ink_maps(g["rect"], g["bb"])
            box = cell_box(g, m - 1, d - 1)
            full = cell_box(g, m - 1, d - 1, full=True)
            # best reader ink within one row pitch above/below (registration offset)
            best, best_dy = 0.0, 0
            for dy in range(-int(g["yp"]), int(g["yp"]) + 1, max(1, int(g["yp"] / 6))):
                f = frac(mk["reader"], (box[0], box[1] + dy, box[2], box[3] + dy))
                if f > best:
                    best, best_dy = f, dy
            row.update(row_method=g["method"], generation=g["generation"], gen=g["gen"],
                       cell_w=round(g["xp"], 1), cell_h=round(g["yp"], 1),
                       ink_reader=round(float(g["marks"][m - 1, d - 1]), 4),
                       ink_recomputed=round(frac(mk["reader"], box), 4),
                       ink_no_tint_mask=round(frac(mk["no_tint_mask"], box), 4),
                       blue_ink=round(frac(mk["blue_ink"], box), 4),
                       ink_full_cell=round(frac(mk["reader"], full), 4),
                       ink_full_cell_no_mask=round(frac(mk["no_tint_mask"], full), 4),
                       best_ink_within_pitch=round(best, 4), best_dy_px=best_dy, note="")
            # crops: the sampled window, and the row in context with the window outlined
            R = g["rect"]
            H, W = R.shape[:2]
            pad_x, pad_y = int(g["xp"] * 0.6), int(g["yp"] * 1.5)
            cx0, cy0 = max(0, full[0] - pad_x), max(0, full[1] - pad_y)
            cx1, cy1 = min(W, full[2] + pad_x), min(H, full[3] + pad_y)
            ctx = R[cy0:cy1, cx0:cx1].copy()
            cv2.rectangle(ctx, (box[0] - cx0, box[1] - cy0), (box[2] - cx0, box[3] - cy0), (0, 0, 255), 1)
            cv2.rectangle(ctx, (full[0] - cx0, full[1] - cy0), (full[2] - cx0, full[3] - cy0), (0, 200, 0), 1)
            win = R[max(0, box[1]):max(0, box[3]), max(0, box[0]):max(0, box[2])]
            scale = 4
            ctx_big = cv2.resize(ctx, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
            if win.size:
                wb = cv2.resize(win, (win.shape[1] * scale * 2, win.shape[0] * scale * 2), interpolation=cv2.INTER_NEAREST)
            else:
                wb = np.full((40, 40, 3), 255, np.uint8)
            hh = max(ctx_big.shape[0], wb.shape[0]) + 60
            canvas = np.full((hh, ctx_big.shape[1] + wb.shape[1] + 30, 3), 255, np.uint8)
            canvas[60:60 + ctx_big.shape[0], :ctx_big.shape[1]] = ctx_big
            canvas[60:60 + wb.shape[0], ctx_big.shape[1] + 30:ctx_big.shape[1] + 30 + wb.shape[1]] = wb
            lab = f"cal {cal}  {d}/{m}  humans: {human}  reader ink {row['ink_reader']:.3f}  no-mask {row['ink_no_tint_mask']:.3f}"
            cv2.putText(canvas, lab, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
            cv2.putText(canvas, "red: reader window   green: whole cell", (6, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                        (80, 80, 80), 1, cv2.LINE_AA)
            name = f"{human}_cal{int(cal):02d}_{m:02d}-{d:02d}.jpg"
            cv2.imwrite(os.path.join(OUT, "crops", name), canvas, [cv2.IMWRITE_JPEG_QUALITY, 85])
            row["crop"] = "crops/" + name
            rows.append(row)
            print(f"  {name}  reader {row['ink_reader']:.3f}  no-mask {row['ink_no_tint_mask']:.3f}  "
                  f"blue {row['blue_ink']:.3f}  best±pitch {best:.3f} (dy {best_dy})", flush=True)

    cols = ["calendrier", "image_id", "mois", "jour", "humains", "row_method", "generation", "gen",
            "cell_w", "cell_h", "ink_reader", "ink_recomputed", "ink_no_tint_mask", "blue_ink",
            "ink_full_cell", "ink_full_cell_no_mask", "best_ink_within_pitch", "best_dy_px", "crop", "note"]
    with open(os.path.join(OUT, "cells.csv"), "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("  ->", os.path.relpath(os.path.join(OUT, "cells.csv"), REPO))


if __name__ == "__main__":
    main()
