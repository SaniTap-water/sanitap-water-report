#!/usr/bin/env python3
"""Gardien-calendar extraction prototype.

PROTOTYPE. Its output is a file. Nothing here feeds the weekly report, and no
published figure derives from it. DO_p,y stays exactly as it is until this has
been validated against independent human transcription.

Usage:  python3 tools/run_extract2.py [--dir DIR] [--limit N] [--out DIR]

--dir holds calendar_inventory.csv (default ~/sdws1/calendar_extract, where the
photographs' inventory and the reader's output files live); --out defaults to
--dir. The reader's code of record lives here (moved from ~/sdws1/calendar_extract
on 30 Sep 2026, with caltools.py; the copies there only point here).

Rows are registered by caltools.fit_day_rows (29 Sep 2026: the old fit
stretched the 31 rows over the sheet header, and days 1-5 were read off the
photographs and logos). legibility2.csv records which registration was used
per image in row_registration.
"""
import argparse, csv, os, sys, time
import numpy as np, cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import caltools

STORE = ("/mnt/c/Users/bushp/OneDrive - SaniTap/Central Data Hub - Water Documents"
         "/Evidence/mWater backup/images")
HERE = os.path.expanduser("~/sdws1/calendar_extract")

# An ink fraction above this reads as a pen mark. It is a placeholder: the
# threshold is exactly what the human transcription round is meant to set.
ADMISSIONS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "calendar_row_admissions.csv")
ADMITTED = ({r["image_id"] for r in csv.DictReader(open(ADMISSIONS))
             if r["admitted"] == "yes" and r["agreement"] and float(r["agreement"]) >= 0.97}
            if os.path.exists(ADMISSIONS) else set())

MARK_T = 0.20
AMBIG_LO, AMBIG_HI = 0.12, 0.30      # inside this band the cell is called illegible


def classify(rec, im, small):
    """Return (stage, reason, payload).

    The gate is whether the day grid can actually be located and is the right
    shape - not whether the photograph is well lit or sharply focused. The
    first pass gated on exposure, focus and an autocorrelation pitch calibrated
    on the 2024/25 sheet, and threw away legible photographs that were merely
    dim, slightly soft, or printed to a later template. Those conditions are
    still measured; they are now used to explain a failure rather than to cause
    one.
    """
    if im is None:
        return "load", "file unreadable", None
    h, w = im.shape[:2]
    if min(h, w) < 400:
        return "resolution", "image too small (min side < 400 px)", None

    q, frac = caltools.sheet_quad(small)
    if q is None:
        return "sheet", "no sheet found (paper not separable from background)", None

    b = caltools.analyse(im, q, im.shape[1] / small.shape[1])
    g = cv2.cvtColor(b["rect"], cv2.COLOR_BGR2GRAY)
    ex = caltools.exposure(g)
    b.update(exposure=ex, sharp=caltools.sharpness(g),
             shade=caltools.shade_unevenness(g), area_frac=frac,
             aspect=caltools.quad_aspect(q))

    bb = caltools.grid_bbox(b["rect"])
    if bb is None:
        # say which measured condition most likely destroyed the tint signal
        if ex["clip_hi"] > 0.35:
            return "exposure", "grid not locatable: sheet blown out", b
        if ex["mean"] < 0.18:
            return "exposure", "grid not locatable: underexposed", b
        if b["shade"] > 0.20:
            return "shade", "grid not locatable: hard shadow across the sheet", b
        if b["sharp"] < 25:
            return "focus", "grid not locatable: out of focus", b
        if frac < 0.06:
            return "framing", "grid not locatable: sheet too small in frame", b
        return "grid", "grid not locatable: no printed tint found", b

    fit_sc, fit_x, fit_p = caltools.fit_month_grid(b["rect"], bb)
    row_sc, fit_y, fit_yp = caltools.fit_day_grid(b["rect"], bb)
    b["month_rules"], b["fit_x"], b["fit_pitch"] = fit_sc, fit_x, fit_p
    b["day_rules"], b["fit_y"], b["fit_ypitch"] = row_sc, fit_y, fit_yp
    rules = fit_sc
    ok, why = caltools.bbox_plausible(bb)
    if not ok:
        if frac < 0.06:
            return "framing", f"sheet too small in frame ({why})", b
        return "grid", f"grid found but wrong shape ({why})", b

    # A twelve-column grid must actually fit the vertical rules present. Set at
    # 0.75 on hand-read photographs: every legible sheet scored 0.77 or better.
    # It favours recall - the human transcription round is the backstop, and the
    # extraction's measured bias is towards over-counting, the safe direction.
    if fit_sc < 0.75:
        return "grid", (f"no twelve-column grid fits the rules here "
                        f"(fit {fit_sc:.2f})"), b
    # Two gates, two questions. The column fit answers "can this sheet be read
    # at all" and governs coverage. Row registration answers "can individual
    # days be called on it" and governs only whether day-level output is
    # emitted. Conflating them threw away readable sheets to buy signal.
    #
    # 30 Sep 2026: the row gate is the fixed row finder (fit_day_rows). A sheet
    # the old rule fit rejected (day_rules < 0.55) gets day calls only if the
    # fixed finder anchors it on the weekend shading or the month-name band AND
    # it is on data/calendar_row_admissions.csv with admitted=yes, i.e. its
    # agreement with Adriaan Mol's transcription was measured at 0.97 or better.
    # A sheet nobody has transcribed cannot be measured, so it is not admitted.
    b["day_calls"] = row_sc >= 0.55
    b["admitted_by_row_finder"] = False
    if not b["day_calls"] and rec["image_id"] in ADMITTED:
        rows = caltools.fit_day_rows(b["rect"], bb, fit_x, fit_p)
        if rows is not None:
            b["day_calls"] = b["admitted_by_row_finder"] = True
    gen, per = caltools.generation(b["rect"], bb, rules)
    b["generation"] = gen
    cw, rh = caltools.grid_from_bbox(bb)
    b["bbox"], b["gen"], b["boxes_per_cell"] = bb, gen, per
    b["cell_px"] = cw * rh
    if b["cell_px"] < 120:
        return "resolution", f"day cell too small to read ({b['cell_px']:.0f} px)", b
    if b["day_calls"]:
        rows = caltools.fit_day_rows(b["rect"], bb, fit_x, fit_p)
        if rows is not None:
            method, y_top, y_p, offs = rows
            b["row_registration"] = method + (" (admitted: transcribed, agreement >= 0.97)"
                                              if b.get("admitted_by_row_finder") else "")
            b["marks"] = caltools.cell_marks_rows(b["rect"], bb, gen, fit_x, fit_p,
                                                  y_top, y_p, offs)
        else:
            b["row_registration"] = "rule fit (no shading or header band found)"
            b["marks"] = caltools.cell_marks_registered(b["rect"], bb, gen, fit_x, fit_p,
                                                        fit_y, fit_yp)
    return "extracted", "", b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dir", default=HERE)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    a.out = a.out or a.dir

    rows = [r for r in csv.DictReader(open(os.path.join(a.dir, "calendar_inventory.csv")))
            if r["local"] == "True"]
    if a.limit:
        rows = rows[:a.limit]

    leg_f = open(os.path.join(a.out, "legibility2.csv"), "w", newline="")
    leg = csv.writer(leg_f)
    leg.writerow(["image_id", "water_point", "site", "form", "question", "date", "status",
                  "stage", "reason", "area_frac", "aspect", "sharpness", "clip_hi",
                  "mean_lum", "shade", "geometry", "periodicity", "cell_px", "green_y",
                  "generation", "boxes_per_cell", "month_rules", "day_rules", "day_calls",
                  "row_registration"])
    ext_f = open(os.path.join(a.out, "extraction_days2.csv"), "w", newline="")
    ext = csv.writer(ext_f)
    ext.writerow(["image_id", "water_point", "site", "period_year", "photo_date",
                  "month", "day", "ink_fraction", "call"])

    t0 = time.time()
    counts, per_pump = {}, {}
    for i, r in enumerate(rows, 1):
        p = os.path.join(STORE, r["image_id"][:2], r["image_id"] + ".jpg")
        try:
            im, small = caltools.load(p)
        except Exception:
            im = small = None
        stage, reason, b = classify(r, im, small)
        counts[reason or "extracted"] = counts.get(reason or "extracted", 0) + 1
        g = (lambda k, d="": (b or {}).get(k, d))
        leg.writerow([r["image_id"], r["water_point"], r["site"], r["form"], r["question"],
                      r["date"], r["status"], stage, reason,
                      f"{g('area_frac',0):.3f}", f"{g('aspect',0):.2f}", f"{g('sharp',0):.0f}",
                      f"{(g('exposure',{}) or {}).get('clip_hi',0):.3f}",
                      f"{(g('exposure',{}) or {}).get('mean',0):.3f}",
                      f"{g('shade',0):.3f}", f"{g('geometry',0):.2f}", f"{g('periodicity',0):.2f}",
                      f"{g('cell_px',0):.0f}", g("green_y") if g("green_y") is not None else "",
                      g("generation", ""), f"{g('boxes_per_cell',0):.2f}", f"{g('month_rules',0):.2f}", f"{g('day_rules',0):.2f}", "yes" if g("day_calls") else "no",
                      g("row_registration", "")])

        if stage == "extracted" and b.get("day_calls"):
            marks = b["marks"]
            year = (r["date"] or "")[:4]
            nmark = nill = 0
            for m in range(caltools.MONTHS):
                for d in range(caltools.DAYS):
                    v = float(marks[m, d])
                    call = "marked" if v >= MARK_T else "clear"
                    if AMBIG_LO <= v <= AMBIG_HI:
                        call = "illegible"
                    if call == "marked": nmark += 1
                    elif call == "illegible": nill += 1
                    ext.writerow([r["image_id"], r["water_point"], r["site"], year, r["date"],
                                  m + 1, d + 1, f"{v:.4f}", call])
            key = (r["water_point"], year)
            cur = per_pump.get(key)
            cand = dict(days_not_operational=nmark, days_illegible=nill,
                        image_id=r["image_id"], photo_date=r["date"], site=r["site"],
                        quality=float(b["geometry"]) * float(b["periodicity"]))
            if cur is None or cand["quality"] > cur["quality"]:
                per_pump[key] = cand
        if i % 200 == 0:
            print(f"  {i}/{len(rows)}  {time.time()-t0:.0f}s", flush=True)

    leg_f.close(); ext_f.close()

    with open(os.path.join(a.out, "extraction_summary2.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["water_point", "site", "period_year", "photo_date", "image_id",
                    "days_not_operational", "days_illegible", "confidence", "validated"])
        for (wp, yr), v in sorted(per_pump.items()):
            # confidence: grid quality, discounted by how much of the sheet was ambiguous
            conf = max(0.0, min(1.0, v["quality"])) * (1.0 - min(1.0, v["days_illegible"] / 372.0))
            w.writerow([wp, v["site"], yr, v["photo_date"], v["image_id"],
                        v["days_not_operational"], v["days_illegible"], f"{conf:.3f}", "NO"])

    print(f"\n  {len(rows)} images, {time.time()-t0:.0f}s")
    print("  outcome profile:")
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"    {v:5d}  {k}")
    print(f"\n  pump-periods with an extraction attempt: {len(per_pump)}")


if __name__ == "__main__":
    main()
