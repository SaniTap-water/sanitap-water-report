#!/usr/bin/env python3
"""Validate the calendar reader against transcription round 1.

Reads the calendars of round 1 that both human readers confirmed and the
machine reads (data/transcription_round1.json, three_way_calendars), on the
days inside each sheet's observed window (data/transcriptions/
round1_dieu-donne_nettoye.csv, inclus = oui; calendar 43's margin notes out).
Scores the reader against Adriaan Mol, against Dieu Donné Razafimahatratra and
against the days both humans read the same way (X or blank), and writes
data/reader_validation.json - the file the publication gate reads
(tools/check_consistency.py: no machine-reader downtime figure is published
unless sensitivity >= 0.90 and specificity >= 0.99 against both-human days,
on the held-out calendars and on all of them).

Two readers are scored:
  v2  the reader of record (extraction_days2.csv, the 30 Sep 2026 run);
  v3  tools/caltools.read_v3: registration on the printed month names and day
      numbers (OCR), ink against the local paper with the printed rules
      removed, and each cell compared with what the sheet prints there.

v3's one free parameter, the mark threshold, is chosen on the odd-numbered
calendars (the most sensitive threshold whose specificity there is at least
0.995) and reported on the even-numbered ones, which played no part in
choosing it, as well as on all. Everything else in v3 was designed by looking
at round-1 crops (data/reader_diagnosis/), so even the held-out figure is not
a clean out-of-sample test; the gate requires both.

    tools/reader_validation.py [--refresh]      # --refresh: re-register every sheet
"""
import argparse, csv, json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TDIR = os.path.join(REPO, "data", "transcriptions")
OUT_JSON = os.path.join(REPO, "data", "reader_validation.json")
OUT_CELLS = os.path.join(REPO, "data", "reader_diagnosis", "round1_reader_v3.csv")
CACHE = os.path.expanduser("~/sdws1/calendar_extract/v3_cache")
MACHINE_V2 = os.path.expanduser("~/sdws1/calendar_extract/extraction_days2.csv")
GATE = {"sensitivity": 0.90, "specificity": 0.99}
TUNE_SPEC = 0.995


def labels():
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
    cells = {k: (am.get(k, ""), v) for k, v in dd.items()}
    return sorted(three, key=int), cells


def register_all(cals, refresh=False):
    import cv2, caltools, run_extract2
    sel = {r["calendrier"]: r for r in csv.DictReader(
        open(os.path.join(REPO, "transcription", "validation_selection.csv"), encoding="utf-8-sig"))}
    years = {}
    for r in csv.DictReader(open(os.path.join(TDIR, "round1_dieu-donne_nettoye.csv"), encoding="utf8")):
        years.setdefault(r["calendrier"], r["annee_feuille"])
    os.makedirs(CACHE, exist_ok=True)
    out = {}
    for c in cals:
        img = sel[c]["image_id"]
        y = int(years[c]) if years.get(c, "").isdigit() else None
        f = os.path.join(CACHE, img + ".npz")
        if os.path.exists(f) and not refresh:
            z = np.load(f, allow_pickle=True)
            g = {k: z[k] for k in z.files}
            g["meta"] = json.loads(str(g["meta"]))
        else:
            im, small = caltools.load(os.path.join(run_extract2.STORE, img[:2], img + ".jpg"))
            b = caltools.read_v3(im, small, y)
            if "scores" not in b:
                g = {"meta": {"why": b["why"]}}
                np.savez_compressed(f, meta=json.dumps(g["meta"]))
            else:
                meta = {k: (int(b[k]) if isinstance(b[k], (np.integer,)) else b[k])
                        for k in ("k", "gen", "month_names", "numbers", "numbers_used", "columns_fitted", "xp", "yp")}
                meta = {k: (float(v) if isinstance(v, np.floating) else v) for k, v in meta.items()}
                g = {"rect": b["rect"], "left": b["left"], "right": b["right"], "top": b["top"],
                     "bottom": b["bottom"], "meta": meta}
                np.savez_compressed(f, meta=json.dumps(meta), **{k: g[k] for k in
                                                                  ("rect", "left", "right", "top", "bottom")})
        g["year"] = y
        g["image_id"] = img
        out[c] = g
        print(f"  {c:>3} {img[:8]} " + (g["meta"].get("why", "") or
              f"orientation {g['meta']['k']} names {g['meta']['month_names']} numbers {g['meta']['numbers_used']}"),
              flush=True)
    return out


def score_all(regs):
    import caltools
    sc = {}
    for c, g in regs.items():
        if "rect" not in g:
            continue
        gg = dict(left=g["left"], right=g["right"], top=g["top"], bottom=g["bottom"])
        dark = caltools.v3_dark(g["rect"], g["meta"]["yp"], g["meta"]["xp"])
        sc[c] = caltools.v3_cells(dark, gg, g["year"])
    return sc


def v2_calls(cals):
    sel = {r["calendrier"]: r["image_id"] for r in csv.DictReader(
        open(os.path.join(REPO, "transcription", "validation_selection.csv"), encoding="utf-8-sig"))}
    want = {sel[c]: c for c in cals}
    out = {}
    m = {"marked": "X", "illegible": "?", "clear": ""}
    with open(MACHINE_V2, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            c = want.get(r["image_id"])
            if c and r["call"] in m:
                out[(c, int(r["month"]), int(r["day"]))] = m[r["call"]]
    return out


def metrics(call, cells, keys, ref):
    """call: key -> 'X' | '' | '?'. ref: 'adriaan' | 'dieu_donne' | 'both'."""
    tp = fn = fp = tn = mq = 0
    for k in keys:
        a, d = cells[k]
        r = a if ref == "adriaan" else d if ref == "dieu_donne" else (a if a == d else None)
        if r not in ("X", ""):
            continue
        if k not in call:
            continue
        m = call[k]
        if m == "?":
            mq += 1
            continue
        if r == "X":
            tp += m == "X"
            fn += m == ""
        else:
            fp += m == "X"
            tn += m == ""
    n = tp + fn + fp + tn
    sens = tp / (tp + fn) if tp + fn else None
    spec = tn / (tn + fp) if tn + fp else None
    kappa = None
    if n:
        po = (tp + tn) / n
        pe = ((tp + fn) * (tp + fp) + (fp + tn) * (fn + tn)) / n / n
        kappa = (po - pe) / (1 - pe) if pe < 1 else None
    r4 = lambda x: None if x is None else round(x, 4)
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn, "machine_question_mark": mq,
            "sensitivity": r4(sens), "specificity": r4(spec), "kappa": r4(kappa)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    cals, cells = labels()
    tune = {c for c in cals if int(c) % 2 == 1}
    keys_all = sorted(cells)
    split = {"all": keys_all,
             "tuning (odd calendars)": [k for k in keys_all if k[0] in tune],
             "held out (even calendars)": [k for k in keys_all if k[0] not in tune]}

    v2 = v2_calls(cals)
    regs = register_all(cals, a.refresh)
    S = score_all(regs)

    def v3_call(t):
        out = {}
        for (c, m, d) in keys_all:
            if c in S:
                out[(c, m, d)] = "X" if S[c][m - 1, d - 1] >= t else ""
        return out

    # threshold on the tuning half only
    both = [k for k in split["tuning (odd calendars)"] if cells[k][0] == cells[k][1] and cells[k][0] in ("X", "")]
    cand = sorted({round(float(S[c][m - 1, d - 1]), 4) for (c, m, d) in both if c in S})
    best_t, best = None, None
    for t in cand:
        mt = metrics(v3_call(t), cells, both, "both")
        if mt["specificity"] is not None and mt["specificity"] >= TUNE_SPEC:
            if best is None or (mt["sensitivity"] or 0) > (best["sensitivity"] or 0):
                best_t, best = t, mt
    if best_t is None:
        best_t = max(cand) + 1e-6
    v3 = v3_call(best_t)

    res = {"note": "Written by tools/reader_validation.py: the calendar reader against transcription round 1 "
                   "(Adriaan Mol 28 Sep 2026; Dieu Donné Razafimahatratra 1 Oct 2026, cleaned), days inside each "
                   "sheet's observed window on the calendars both humans confirmed and the machine reads. X is "
                   "positive. 'both' takes only the days the two humans read the same way.",
           "gate": {"sensitivity_min": GATE["sensitivity"], "specificity_min": GATE["specificity"],
                    "against": "both", "on": ["all", "held out (even calendars)"]},
           "calendars": len(cals),
           "registered_v3": sum(1 for c in cals if c in S),
           "not_registered_v3": {c: regs[c]["meta"].get("why") for c in cals if c not in S},
           "v3_threshold": best_t, "v3_threshold_rule": f"most sensitive with specificity >= {TUNE_SPEC} "
                                                         "against both humans on the odd-numbered calendars",
           "readers": {}}
    for name, call in (("v2", v2), ("v3", v3)):
        res["readers"][name] = {sp: {ref: metrics(call, cells, ks, ref) for ref in ("adriaan", "dieu_donne", "both")}
                                for sp, ks in split.items()}

    def passes(name):
        r = res["readers"][name]
        return all(r[sp]["both"]["sensitivity"] is not None and r[sp]["both"]["sensitivity"] >= GATE["sensitivity"]
                   and r[sp]["both"]["specificity"] is not None and r[sp]["both"]["specificity"] >= GATE["specificity"]
                   for sp in res["gate"]["on"])
    res["gate_passed"] = {n: passes(n) for n in res["readers"]}
    # the diagnosis: the 40 both-X days, why the v2 reader missed each
    # (data/reader_diagnosis/cells.csv, reviewed by eye from the crops)
    dc = list(csv.DictReader(open(os.path.join(REPO, "data", "reader_diagnosis", "cells.csv"), encoding="utf8")))
    xs = [r for r in dc if r["humains"] == "X"]
    bl = [r for r in dc if r["humains"] == "blank" and r.get("ink_reader")]
    import collections as _co
    res["diagnosis"] = {
        "both_x_cells": len(xs), "blank_cells": len([r for r in dc if r["humains"] == "blank"]),
        "causes": dict(_co.Counter(r["cause"] for r in xs).most_common()),
        "v2_mark_threshold": 0.20, "v2_illegible_band": [0.12, 0.30],
        "v2_max_ink_on_x": round(max(float(r["ink_reader"]) for r in xs if r.get("ink_reader")), 3),
        "v2_max_ink_on_blank": round(max(float(r["ink_reader"]) for r in bl), 3),
        "x_cells_with_blue_or_purple_ink": sum(1 for r in xs if r.get("blue_ink") and float(r["blue_ink"]) >= 0.05),
        "sheets_turned_in_set": None,
        "reviewed": "by eye from the crops, 1 Oct 2026",
    }
    try:
        rot = {r["calendrier"]: r["rotation_cw"] for r in csv.DictReader(
            open(os.path.join(REPO, "data", "transcription_orientation.csv"), encoding="utf8"))}
        res["diagnosis"]["sheets_turned_in_set"] = sum(1 for c in cals if rot.get(c, "0") != "0")
    except OSError:
        pass
    res["reader_of_record"] = "v2"
    res["publishable"] = res["gate_passed"]["v2"]
    json.dump(res, open(OUT_JSON, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    open(OUT_JSON, "a").write("\n")

    os.makedirs(os.path.dirname(OUT_CELLS), exist_ok=True)
    with open(OUT_CELLS, "w", newline="", encoding="utf8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["calendrier", "mois", "jour", "adriaan", "dieu_donne", "v2", "v3_score", "v3"])
        for k in keys_all:
            c, m, d = k
            w.writerow([c, m, d, cells[k][0] or "vide", cells[k][1] or "vide", v2.get(k, "hors cadre") or "vide",
                        f"{S[c][m - 1, d - 1]:.4f}" if c in S else "", (v3.get(k, "") or "vide") if c in S else "non lu"])
    for name in res["readers"]:
        for sp in split:
            b = res["readers"][name][sp]["both"]
            print(f"  {name} {sp:28s} both: sens {b['sensitivity']} spec {b['specificity']} kappa {b['kappa']} "
                  f"(tp {b['tp']} fn {b['fn']} fp {b['fp']})")
    print(f"  v3 threshold {best_t}; gate passed: {res['gate_passed']}")
    print("  ->", os.path.relpath(OUT_JSON, REPO))


if __name__ == "__main__":
    main()
