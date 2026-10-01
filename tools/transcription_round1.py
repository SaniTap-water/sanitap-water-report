#!/usr/bin/env python3
"""Transcription check, round 1: ingest Dieu Donné Razafimahatratra's export,
clean it by the rules agreed on 1 Oct 2026, and compare three readers of the
same calendars and days: Adriaan Mol (round 1, 28 Sep), Dieu Donné (cleaned)
and the machine reader (extraction_days2.csv, the 30 Sep row-fix run).

The raw export is never edited. Every change the cleaning makes is a row of
the adjustments CSV, with its rule and reason.

Cleaning rules (Dieu Donné's data only)
  a  a mark (X or ?) on a cell after the photo date (etat_cellule non_observe)
     is void. Each is checked against the year before the sheet year: if the
     mark would fall on or before the photo date, it is listed as a year
     question, not a transcription error.
  b  calendar 43: the X (and the ? of 10-12 Feb) come from the gardien's notes
     in the margin, not from grid marks. Tagged margin_note, kept out of grid
     accuracy, reported separately.
  c  an X on a date the calendar's note calls a doubtful sign ("point suspect",
     "barre suspecte", "chiffre ... suspect") counts as ?. Matched on the note
     text: the sign phrase and the date(s) written before it, +/- 1 day.
     "croix suspecte" is a cross, so it is not converted.
  d  calendars 7, 23, 31, 32, 55, 61, 71, 76, 81 (sheet year 2027, 0 observed
     days) are held out until MadAvance confirms which side was marked.
  e  calendar 3 stays excluded.

Comparison
  One observed window for every reader: the sheet year of record (the year in
  Dieu Donné's export, which carries the years set on 28 Sep with their
  source) and the photo date. Adriaan's export predates those years on ten
  sheets, so his own etat_cellule is not used. Cells are keyed on calendar,
  month and day (the grid position each reader read).

  X versus blank is scored; ? is its own row and column, never right or wrong.
  The machine is joined on the image (transcription/validation_selection.csv).

Usage: tools/transcription_round1.py [--write | --check]
Writes into data/transcriptions/ and data/transcription_round1.json.
"""
import argparse, collections, csv, datetime as dt, hashlib, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TDIR = os.path.join(REPO, "data", "transcriptions")
RAW_DD = os.path.join(TDIR, "releves_calendriers_dieu-donne_serie1_2026-10-01.csv")
RAW_AM = os.path.join(TDIR, "releves_calendriers_mol-adriaan_serie1_2026-09-28.csv")
SELECTION = os.path.join(REPO, "transcription", "validation_selection.csv")
MACHINE = os.path.expanduser("~/sdws1/calendar_extract/extraction_days2.csv")
OUT_JSON = os.path.join(REPO, "data", "transcription_round1.json")
OUT = {k: os.path.join(TDIR, v) for k, v in {
    "cleaned": "round1_dieu-donne_nettoye.csv",
    "adjustments": "round1_ajustements.csv",
    "disagreements": "round1_desaccords_humains.csv",
    "calendars": "round1_calendriers.csv",
    "confusion": "round1_matrices.csv",
    "summary": "round1_resume.md",
}.items()}

DD_NAME = "Dieu Donné Razafimahatratra (MadAvance MERV)"
AM_NAME = "Adriaan Mol"
EXPECT = {"rows": 29943, "calendars": 83, "exported": "2026-10-01T07:50:01",
          "header": "calendrier,point_eau,date_photo,annee_feuille",
          "transcriber": "R.DIEU DONNE"}
VOID_CALS = {2, 12, 66, 68, 69, 72, 86, 90, 92, 97}
VOID_COUNT = 31
MARGIN_CAL, MARGIN_X = 43, 33
DOUBT_CALS = {18, 30, 38, 64, 66, 68}          # 87 too if its note says so
HOLDOUT = {7, 23, 31, 32, 55, 61, 71, 76, 81}
EXCLUDED = {3}
TRANSCRIBED = {"marque", "vide_verifie"}     # vu_sans_confirmation is not a reading
MACHINE_MAP = {"marked": "X", "illegible": "?", "clear": ""}

MOIS = {"janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4, "mai": 5,
        "juin": 6, "juillet": 7, "aout": 8, "août": 8, "septembre": 9, "octobre": 10,
        "novembre": 11, "decembre": 12, "décembre": 12}
SIGN = re.compile(r"\b(points?|barres?|chiffres?)\b[^.;]{0,15}?suspect", re.I)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(path):
    cals = collections.OrderedDict()
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            cals.setdefault(int(r["calendrier"]), []).append(r)
    return cals


def doubtful_dates(note):
    """(month, day) pairs written before a doubtful-sign phrase in the note."""
    m = SIGN.search(note or "")
    if not m:
        return None, set()
    head = note[:m.start()]
    head = head[head.rfind(".") + 1:]      # the clause the sign phrase sits in
    out = set()
    for d, mo in re.findall(r"\b(\d{1,2})/(\d{1,2})/\d{4}", head):
        out.add((int(mo), int(d)))
    for d1, d2, mo in re.findall(r"\b(\d{1,2})\s+au\s+(\d{1,2})\s+([a-zéû]+)", head, re.I):
        if mo.lower() in MOIS:
            out |= {(MOIS[mo.lower()], d) for d in range(int(d1), int(d2) + 1)}
    for d, mo in re.findall(r"\b(\d{1,2})\s+([A-Za-zéû]+)", head):
        if mo.lower() in MOIS:
            out.add((MOIS[mo.lower()], int(d)))
    return m.group(0), out


def cell_date(year, m, d):
    try:
        return dt.date(int(year), m, d)
    except ValueError:
        return None


def observed(year, photo, m, d):
    """The one window used for all readers: on or before the photo date."""
    if not year:
        return None                       # no sheet year: window unknown
    c = cell_date(year, m, d)
    return c is not None and c <= dt.date.fromisoformat(photo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="the default: write the outputs")
    ap.add_argument("--check", action="store_true",
                    help="recompute and fail if any written output differs")
    a = ap.parse_args()

    # ---- 1. the export is what it should be ---------------------------------
    with open(RAW_DD, encoding="utf-8-sig") as f:
        header = f.readline()
    dd_raw = load(RAW_DD)
    rows = [r for rs in dd_raw.values() for r in rs]
    stamps = {r["exporte_le"] for r in rows}
    who = {r["transcripteur"] for r in rows}
    fails = []
    if not header.startswith(EXPECT["header"]):
        fails.append("header")
    if len(rows) != EXPECT["rows"]:
        fails.append(f"rows {len(rows)}")
    if len(dd_raw) != EXPECT["calendars"]:
        fails.append(f"calendars {len(dd_raw)}")
    if len(stamps) != 1 or not next(iter(stamps)).startswith(EXPECT["exported"]):
        fails.append(f"exported {stamps}")
    if len(who) != 1 or not next(iter(who)).startswith(EXPECT["transcriber"]):
        fails.append(f"transcriber {who}")
    if fails:
        sys.exit("export is not the one expected: " + "; ".join(fails))
    raw_name = next(iter(who))

    am_raw = load(RAW_AM)
    sel = {int(r["calendrier"]): r for r in csv.DictReader(open(SELECTION, encoding="utf-8-sig"))}

    adj = []          # the adjustments CSV

    def note_adj(rule, c, r, before, after, reason, **extra):
        adj.append({"regle": rule, "calendrier": c, "point_eau": r.get("point_eau", "") if r else "",
                    "date_photo": r.get("date_photo", "") if r else "",
                    "annee_feuille": r.get("annee_feuille", "") if r else "",
                    "mois": r.get("mois", "") if r else "", "jour": r.get("jour", "") if r else "",
                    "releve_brut": before, "releve_net": after, "motif": reason,
                    "annee_moins_un_avant_photo": extra.get("prev", "")})

    adj.append({"regle": "nom", "calendrier": "", "point_eau": "", "date_photo": "",
                "annee_feuille": "", "mois": "", "jour": "", "releve_brut": raw_name,
                "releve_net": DD_NAME, "annee_moins_un_avant_photo": "",
                "motif": f"transcripteur shortened on all {len(rows)} rows; the raw export keeps "
                         "the original text (the instruction Dieu Donné was given)"})

    # ---- 2. clean Dieu Donné ------------------------------------------------
    clean = {}            # cal -> {(m,d): value}  (grid cells, window applied later)
    margin = {}           # cal 43 cells from margin notes
    voids, year_q, conversions, doubt_seen = [], [], [], {}
    cal_meta = {}
    for c, rs in dd_raw.items():
        r0 = rs[0]
        cal_meta[c] = {"wp": r0["point_eau"], "photo": r0["date_photo"],
                       "year": r0["annee_feuille"], "year_src": r0["annee_source"],
                       "statut": r0["statut"], "note": r0["notes"],
                       "comparable": r0["comparable_machine"] == "oui"}
        phrase, ddates = doubtful_dates(r0["notes"])
        if phrase:
            doubt_seen[c] = (phrase, sorted(ddates))
        if c in EXCLUDED:
            note_adj("e", c, r0, r0["releve"] or "", "", "calendar 3 stays excluded (also excluded by the transcriber: "
                     + (r0["exclu_motif"] or "") + ")")
            continue
        if c in HOLDOUT:
            note_adj("d", c, r0, "", "", f"held out: sheet year {r0['annee_feuille']}, "
                     f"{sum(1 for r in rs if r['etat_cellule'] == 'observe')} observed days; until MadAvance "
                     "confirms which side was marked")
            continue
        cells = {}
        for r in rs:
            if not r["mois"] or not r["jour"]:
                continue
            k = (int(r["mois"]), int(r["jour"]))
            v = (r["releve"] or "").strip()
            if v and r["etat_cellule"] == "non_observe":
                prev = cell_date(int(r["annee_feuille"]) - 1, *k) if r["annee_feuille"] else None
                fits = bool(prev and prev <= dt.date.fromisoformat(r["date_photo"]))
                voids.append((c, k, v, fits))
                reason = "mark on a cell after the photo date: void"
                if fits:
                    reason += (f"; with sheet year {int(r['annee_feuille']) - 1} it would fall on "
                               f"{prev.isoformat()}, on or before the photo date: a year question")
                    year_q.append((c, k, v, prev))
                if phrase and v == "X" and any(abs((cell_date(2001, *k) - cell_date(2001, *dd)).days) <= 1
                                              for dd in ddates if cell_date(2001, *dd)):
                    reason += f"; the note also calls this sign doubtful (\"{phrase}\"), superseded by the void"
                    conversions.append((c, k, "void"))
                note_adj("a", c, r, v, "", reason, prev="oui" if fits else "non")
                v = ""
            elif c == MARGIN_CAL and v:
                margin[k] = v
                note_adj("b", c, r, v, "margin_note",
                         "taken from the gardien's notes in the margin, not a grid mark; "
                         "kept out of grid accuracy, reported separately")
                v = ""
            elif v == "X" and phrase:
                near = [dd for dd in ddates if cell_date(2001, *dd)
                        and abs((cell_date(2001, *k) - cell_date(2001, *dd)).days) <= 1]
                if near:
                    off = "" if k in ddates else (f" (the note writes {near[0][1]}/{near[0][0]}, "
                                                  f"the X is on {k[1]}/{k[0]})")
                    note_adj("c", c, r, "X", "?", f"the calendar note calls this sign doubtful: "
                             f"\"{phrase}\"{off}; counts as ?")
                    conversions.append((c, k, "?"))
                    v = "?"
            cells[k] = v
        clean[c] = cells

    # the rules' own counts, as given: fail loudly if the data says otherwise
    problems = []
    if len(voids) != VOID_COUNT or {c for c, *_ in voids} != VOID_CALS:
        problems.append(f"void marks {len(voids)} on {sorted({c for c, *_ in voids})}")
    if sum(1 for v in margin.values() if v == "X") != MARGIN_X:
        problems.append(f"calendar 43 margin X {sum(1 for v in margin.values() if v == 'X')}")
    conv_cals = {c for c, _, _ in conversions}
    if not DOUBT_CALS <= conv_cals or conv_cals - DOUBT_CALS - {87}:
        problems.append(f"doubtful-sign calendars {sorted(conv_cals)}")
    for c in HOLDOUT:
        m = cal_meta[c]
        if m["year"] != "2027" or any(r["etat_cellule"] == "observe" for r in dd_raw[c]):
            problems.append(f"hold-out {c} is not a 2027 sheet with 0 observed days")
    if problems:
        sys.exit("the data does not match the rules as given: " + "; ".join(problems))

    # ---- 3. three readers on one window --------------------------------------
    def window(c):
        """Observed cells: sheet year of record and photo date. With no sheet year
        (calendar 84) the export's own etat_cellule is the only window there is."""
        m = cal_meta[c]
        if m["year"]:
            return {k for k in clean.get(c, {}) if observed(m["year"], m["photo"], *k)}
        return {(int(r["mois"]), int(r["jour"])) for r in dd_raw[c]
                if r["mois"] and r["etat_cellule"] == "observe"}

    am = {}
    am_statut = {}
    for c, rs in am_raw.items():
        am_statut[c] = rs[0]["statut"]
        if rs[0]["statut"] not in TRANSCRIBED or (rs[0]["exclu"] or "") == "oui":
            continue
        am[c] = {(int(r["mois"]), int(r["jour"])): (r["releve"] or "").strip()
                 for r in rs if r["mois"] and r["jour"]}

    dd = {c: v for c, v in clean.items() if cal_meta[c]["statut"] in TRANSCRIBED}
    not_transcribed = {"adriaan": sorted(c for c in am_raw if c not in am and c not in EXCLUDED | HOLDOUT),
                       "dieu_donne": sorted(c for c in clean if c not in dd)}

    img = {c: sel[c]["image_id"] for c in sel}
    want = {img[c] for c in dd if c in img}
    mach = collections.defaultdict(dict)
    with open(MACHINE, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["image_id"] in want and r["call"] in MACHINE_MAP:
                mach[r["image_id"]][(int(r["month"]), int(r["day"]))] = MACHINE_MAP[r["call"]]
    machine = {c: mach[img[c]] for c in dd if c in img and img[c] in mach}

    win = {c: window(c) - (set(margin) if c == MARGIN_CAL else set()) for c in dd}
    readers = {"adriaan": am, "dieu_donne": dd, "machine": machine}
    labels = {"adriaan": AM_NAME, "dieu_donne": DD_NAME, "machine": "machine reader"}
    both_h = sorted(set(am) & set(dd), key=int)
    all3 = [c for c in both_h if c in machine]

    def val(rd, c, k):
        return readers[rd][c].get(k, "")

    def matrix(ra, rb, cals):
        mx = collections.Counter()
        for c in cals:
            for k in win[c]:
                if k in readers[ra][c] and k in readers[rb][c]:
                    mx[(val(ra, c, k) or "-", val(rb, c, k) or "-")] += 1
        return mx

    def scored(mx):
        xx, xb, bx, bb = mx[("X", "X")], mx[("X", "-")], mx[("-", "X")], mx[("-", "-")]
        n = xx + xb + bx + bb
        q = sum(v for (p, s), v in mx.items() if "?" in (p, s))
        cohen = None
        if n:
            po = (xx + bb) / n
            pe = ((xx + xb) * (xx + bx) + (bx + bb) * (xb + bb)) / n / n
            cohen = round((po - pe) / (1 - pe), 4) if pe < 1 else None
        return {"cells_scored": n, "agree": xx + bb, "agreement": round((xx + bb) / n, 4) if n else None,
                "both_x": xx, "a_x_b_blank": xb, "a_blank_b_x": bx, "both_blank": bb,
                "cells_with_question_mark": q, "kappa": cohen,
                "matrix": {f"{p}|{s}": v for (p, s), v in sorted(mx.items())}}

    pairs = []
    for ra, rb, cals, scope in [
            ("adriaan", "dieu_donne", all3, "three_way"),
            ("adriaan", "machine", all3, "three_way"),
            ("dieu_donne", "machine", all3, "three_way"),
            ("adriaan", "dieu_donne", both_h, "all_human")]:
        s = scored(matrix(ra, rb, cals))
        s.update({"a": ra, "b": rb, "scope": scope, "calendars": len(cals),
                  "cells_in_window": sum(len(win[c]) for c in cals)})
        pairs.append(s)

    def sens_spec(ref_fn, cals):
        tp = fn = fp = tn = mq = 0
        for c in cals:
            for k in win[c]:
                ref = ref_fn(c, k)
                if ref not in ("X", "") or k not in machine[c]:
                    continue
                m = machine[c][k]
                if m == "?":
                    mq += 1
                elif ref == "X":
                    tp, fn = tp + (m == "X"), fn + (m == "")
                else:
                    fp, tn = fp + (m == "X"), tn + (m == "")
        return {"tp": tp, "fn": fn, "fp": fp, "tn": tn, "machine_question_mark": mq,
                "sensitivity": round(tp / (tp + fn), 4) if tp + fn else None,
                "specificity": round(tn / (tn + fp), 4) if tn + fp else None}

    def agreed(c, k):
        x, y = val("adriaan", c, k), val("dieu_donne", c, k)
        return x if x == y and "?" not in (x, y) else None

    machine_vs = {"adriaan": sens_spec(lambda c, k: val("adriaan", c, k), all3),
                  "dieu_donne": sens_spec(lambda c, k: val("dieu_donne", c, k), all3),
                  "both_humans_agree": sens_spec(agreed, all3)}

    # ---- calendar level -------------------------------------------------------
    cal_rows = []
    for c in both_h:
        row = {"calendrier": c, "point_eau": cal_meta[c]["wp"], "date_photo": cal_meta[c]["photo"],
               "annee_feuille": cal_meta[c]["year"], "jours_observes": len(win[c]),
               "machine": "oui" if c in machine else "non"}
        for rd in readers:
            if c not in readers[rd]:
                row[f"{rd}_x"] = row[f"{rd}_q"] = row[f"{rd}_marque"] = ""
                continue
            vs = [val(rd, c, k) for k in win[c] if k in readers[rd][c]]
            row[f"{rd}_x"], row[f"{rd}_q"] = vs.count("X"), vs.count("?")
            row[f"{rd}_marque"] = "oui" if vs.count("X") else "non"
        cal_rows.append(row)

    def cal_matrix(ra, rb, cals):
        mx = collections.Counter()
        for r in cal_rows:
            if r["calendrier"] in cals:
                mx[(r[f"{ra}_marque"], r[f"{rb}_marque"])] += 1
        return {"both_marked": mx[("oui", "oui")], "a_only": mx[("oui", "non")],
                "b_only": mx[("non", "oui")], "neither": mx[("non", "non")],
                "x_total_a": sum(r[f"{ra}_x"] for r in cal_rows if r["calendrier"] in cals),
                "x_total_b": sum(r[f"{rb}_x"] for r in cal_rows if r["calendrier"] in cals),
                "same_x_count": sum(1 for r in cal_rows if r["calendrier"] in cals and r[f"{ra}_x"] == r[f"{rb}_x"])}

    cal_pairs = [dict(a=ra, b=rb, scope=sc, calendars=len(cs), **cal_matrix(ra, rb, set(cs)))
                 for ra, rb, cs, sc in [("adriaan", "dieu_donne", all3, "three_way"),
                                        ("adriaan", "machine", all3, "three_way"),
                                        ("dieu_donne", "machine", all3, "three_way"),
                                        ("adriaan", "dieu_donne", both_h, "all_human")]]

    # ---- human disagreements: the cells to settle by eye ----------------------
    dis = []
    for c in both_h:
        for k in sorted(win[c]):
            x, y = val("adriaan", c, k), val("dieu_donne", c, k)
            if x != y:
                d = cell_date(cal_meta[c]["year"], *k) if cal_meta[c]["year"] else None
                kind = "X / vide" if {x, y} == {"X", ""} else "? / " + ((x or y) if (x or y) != "?" else "?")
                raw = next((r["releve"] for r in dd_raw[c] if r["mois"] and (int(r["mois"]), int(r["jour"])) == k), "")
                dis.append({"calendrier": c, "point_eau": cal_meta[c]["wp"],
                            "date": d.isoformat() if d else f"{k[1]:02d}/{k[0]:02d}",
                            "mois": k[0], "jour": k[1], "adriaan": x or "vide", "dieu_donne": y or "vide",
                            "dieu_donne_brut": raw or "vide",
                            "type": "X contre vide" if {x, y} == {"X", ""} else "? contre " + ("X" if "X" in (x, y) else "vide"),
                            "machine": (machine[c].get(k, "") or "vide") if c in machine else "hors cadre"})
    dis.sort(key=lambda r: (r["calendrier"], r["mois"], r["jour"]))

    # ---- totals -------------------------------------------------------------
    def totals(cells_by_cal, cals):
        vs = [cells_by_cal[c].get(k, "") for c in cals for k in win[c] if k in cells_by_cal[c]]
        return {"calendars": len(cals), "days": len(vs), "x": vs.count("X"), "question": vs.count("?"),
                "calendars_marked": sum(1 for c in cals if any(cells_by_cal[c].get(k) == "X" for k in win[c]))}
    raw_x = sum(1 for r in rows if r["releve"] == "X")
    raw_q = sum(1 for r in rows if r["releve"] == "?")

    out = {
        "note": "Written by tools/transcription_round1.py. Transcription check, round 1: Adriaan Mol "
                "(28 Sep 2026), Dieu Donné Razafimahatratra (MadAvance MERV, 1 Oct 2026, cleaned) and the "
                "machine reader (extraction_days2.csv, 30 Sep 2026) on one observed window per sheet "
                "(sheet year of record and photo date). X versus blank is scored; ? is never scored.",
        "inputs": {"dieu_donne": os.path.relpath(RAW_DD, REPO), "dieu_donne_sha256": sha256(RAW_DD),
                   "adriaan": os.path.relpath(RAW_AM, REPO), "adriaan_sha256": sha256(RAW_AM),
                   "machine": "extraction_days2.csv", "machine_sha256": sha256(MACHINE),
                   "exported": next(iter(stamps))},
        "raw": {"rows": len(rows), "calendars": len(dd_raw), "x": raw_x, "question": raw_q,
                "statut": dict(collections.Counter(rs[0]["statut"] for rs in dd_raw.values()))},
        "cleaning": {"void_after_photo": len(voids), "void_calendars": sorted({c for c, *_ in voids}),
                     "void_x": sum(1 for v in voids if v[2] == "X"), "void_q": sum(1 for v in voids if v[2] == "?"),
                     "year_questions": [{"calendrier": c, "mois": k[0], "jour": k[1], "releve": v,
                                         "date_if_year_minus_one": p.isoformat(),
                                         "date_photo": cal_meta[c]["photo"], "annee_feuille": cal_meta[c]["year"]}
                                        for c, k, v, p in year_q],
                     "year_question_calendars": sorted({c for c, *_ in year_q}),
                     "margin_note_x": sum(1 for v in margin.values() if v == "X"),
                     "margin_note_q": sum(1 for v in margin.values() if v == "?"),
                     "x_to_question": [{"calendrier": c, "mois": k[0], "jour": k[1]} for c, k, t in conversions if t == "?"],
                     "doubtful_superseded_by_void": [{"calendrier": c, "mois": k[0], "jour": k[1]}
                                                     for c, k, t in conversions if t == "void"],
                     "held_out": sorted(HOLDOUT), "excluded": sorted(EXCLUDED),
                     "adjustment_rows": len(adj)},
        "clean_totals": totals(dd, sorted(dd)),
        "clean_totals_note": "Dieu Donné after cleaning, over the calendars he transcribed (statut marque or "
                             "vide_verifie), excluding 3 and the hold-outs, inside the observed window; "
                             "calendar 43's margin-note cells are outside the grid figures",
        "not_transcribed": not_transcribed,
        "calendars_both_humans": len(both_h), "calendars_three_way": len(all3),
        "three_way_calendars": all3,
        "pairs": pairs, "calendar_pairs": cal_pairs, "machine_vs": machine_vs,
        "human_disagreements": len(dis),
        "human_disagreements_by_type": dict(collections.Counter(r["type"] for r in dis)),
        "human_disagreement_calendars": len({r["calendrier"] for r in dis}),
        "evidence": "data/transcriptions/round1_resume.md",
    }

    # ---- write ----------------------------------------------------------------
    files = {}

    def csv_text(fields, rs):
        import io
        b = io.StringIO()
        w = csv.DictWriter(b, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rs)
        return b.getvalue()

    clean_rows = []
    for c, rs in dd_raw.items():
        for r in rs:
            k = (int(r["mois"]), int(r["jour"])) if r["mois"] and r["jour"] else None
            if c in EXCLUDED:
                inc, why = "non", "e: exclu"
            elif c in HOLDOUT:
                inc, why = "non", "d: retenu (2027)"
            elif cal_meta[c]["statut"] not in TRANSCRIBED:
                inc, why = "non", "statut " + cal_meta[c]["statut"]
            elif c == MARGIN_CAL and k in margin:
                inc, why = "non", "b: margin_note"
            elif k not in win.get(c, set()):
                inc, why = "non", "hors fenêtre observée"
            else:
                inc, why = "oui", ""
            net = clean.get(c, {}).get(k, "") if k else ""
            if c == MARGIN_CAL and k in margin:
                net = "margin_note:" + margin[k]
            clean_rows.append({"calendrier": c, "point_eau": r["point_eau"], "date_photo": r["date_photo"],
                               "annee_feuille": r["annee_feuille"], "mois": r["mois"], "jour": r["jour"],
                               "releve_brut": r["releve"], "releve_net": net, "etat_cellule": r["etat_cellule"],
                               "inclus": inc, "motif_exclusion": why, "transcripteur": DD_NAME,
                               "session_id": r["session_id"], "statut": r["statut"]})
    files["cleaned"] = csv_text(list(clean_rows[0]), clean_rows)
    files["adjustments"] = csv_text(["regle", "calendrier", "point_eau", "date_photo", "annee_feuille", "mois",
                                     "jour", "releve_brut", "releve_net", "annee_moins_un_avant_photo", "motif"], adj)
    files["disagreements"] = csv_text(["calendrier", "point_eau", "date", "mois", "jour", "adriaan", "dieu_donne",
                                       "dieu_donne_brut", "type", "machine"], dis)
    files["calendars"] = csv_text(list(cal_rows[0]), cal_rows)
    mrows = []
    for p in pairs:
        for key, v in p["matrix"].items():
            ra_v, rb_v = key.split("|")
            mrows.append({"portee": p["scope"], "a": labels[p["a"]], "b": labels[p["b"]],
                          "a_lit": ra_v, "b_lit": rb_v, "jours": v})
    files["confusion"] = csv_text(["portee", "a", "b", "a_lit", "b_lit", "jours"], mrows)
    files["summary"] = summary_md(dict(out, _dd84=clean.get(84, {})), pairs, cal_pairs, machine_vs, dis,
                                  labels, cal_meta, margin, adj)
    js = json.dumps(out, indent=1, ensure_ascii=False) + "\n"

    stale = []
    for k, text in files.items():
        if a.check:
            if not os.path.isfile(OUT[k]) or open(OUT[k], encoding="utf8").read() != text:
                stale.append(OUT[k])
        else:
            open(OUT[k], "w", encoding="utf8", newline="").write(text)
    if a.check:
        if not os.path.isfile(OUT_JSON) or open(OUT_JSON, encoding="utf8").read() != js:
            stale.append(OUT_JSON)
        if stale:
            sys.exit("transcription_round1: out of date: " + ", ".join(os.path.relpath(p, REPO) for p in stale))
        print("transcription_round1: outputs match the inputs")
        return
    open(OUT_JSON, "w", encoding="utf8").write(js)
    for k in files:
        print("  ->", os.path.relpath(OUT[k], REPO))
    print("  ->", os.path.relpath(OUT_JSON, REPO))


def pct(x):
    return "n/a" if x is None else f"{x * 100:.1f}%"


def summary_md(o, pairs, cal_pairs, mv, dis, labels, meta, margin, adj):
    L = []
    w = L.append
    cl = o["cleaning"]
    t = o["clean_totals"]
    w("# Transcription check, round 1\n")
    w("Written by `tools/transcription_round1.py`; do not edit by hand. Inputs (SHA-256):\n")
    w(f"- Dieu Donné Razafimahatratra (MadAvance MERV): `{os.path.basename(o['inputs']['dieu_donne'])}`, "
      f"exported {o['inputs']['exported']}, `{o['inputs']['dieu_donne_sha256'][:16]}…`; raw file kept as exported")
    w(f"- Adriaan Mol, round 1 (28 Sep 2026): `{os.path.basename(o['inputs']['adriaan'])}`, "
      f"`{o['inputs']['adriaan_sha256'][:16]}…`")
    w(f"- machine reader: `extraction_days2.csv` (30 Sep 2026 row-fix run), `{o['inputs']['machine_sha256'][:16]}…`\n")
    w("Read-only on mWater; no transcription result was changed. Every cleaning step is a row of "
      "`round1_ajustements.csv`.\n")
    w("## Cleaning (Dieu Donné's data only)\n")
    w(f"Raw: {o['raw']['rows']:,} rows, {o['raw']['calendars']} calendars, {o['raw']['x']} X, {o['raw']['question']} ?.\n")
    w(f"- **a. Void after the photo date:** {cl['void_after_photo']} marks ({cl['void_x']} X, {cl['void_q']} ?) "
      f"on calendars {', '.join(map(str, cl['void_calendars']))}.")
    w(f"- **b. Calendar 43, margin notes:** {cl['margin_note_x']} X and {cl['margin_note_q']} ? tagged "
      "`margin_note`, out of grid accuracy (below).")
    w("- **c. Doubtful sign counted as ?:** " + ", ".join(f"{x['calendrier']} ({x['jour']}/{x['mois']})"
                                                       for x in cl["x_to_question"])
      + ". Also doubtful by note but already void under (a): "
      + ", ".join(f"{x['calendrier']} ({x['jour']}/{x['mois']})" for x in cl["doubtful_superseded_by_void"]) + ".")
    w(f"- **d. Held out (2027 sheets, 0 observed days):** {', '.join(map(str, cl['held_out']))}.")
    w(f"- **e. Excluded:** {', '.join(map(str, cl['excluded']))}.\n")
    w("**Cleaned totals** (calendars Dieu Donné confirmed, inside the observed window, margin notes "
      f"apart): {t['calendars']} calendars, {t['days']:,} days, **{t['x']} X**, {t['question']} ?, "
      f"{t['calendars_marked']} calendars with at least one X.\n")
    if o["not_transcribed"]["dieu_donne"]:
        w(f"Not a reading (statut `vu_sans_confirmation`): Dieu Donné {o['not_transcribed']['dieu_donne'] or '—'}.\n")
    w("### Year questions from (a)\n")
    w("Void marks that would fall on or before the photo date if the sheet were one year earlier. "
      "These are questions about the sheet year, not transcription errors.\n")
    w("| calendar | sheet year | photo date | cell | mark | date with year − 1 |")
    w("|---|---|---|---|---|---|")
    for y in cl["year_questions"]:
        w(f"| {y['calendrier']} | {y['annee_feuille']} | {y['date_photo']} | {y['jour']}/{y['mois']} | "
          f"{y['releve']} | {y['date_if_year_minus_one']} |")
    others = sorted(set(cl["void_calendars"]) - set(cl["year_question_calendars"]))
    in_year = sum(1 for c in cl["void_calendars"] if meta[c]["photo"][:4] == meta[c]["year"])
    w(f"\n{len(cl['year_questions'])} of {cl['void_after_photo']} void marks pass the test"
      + (f"; calendars {', '.join(map(str, others))} do not." if others else ".")
      + f" The test is weak here: on {in_year} of these {len(cl['void_calendars'])} calendars the photo was "
      "taken during the sheet year, so any mark after the photo date falls before it a year earlier. "
      "It marks the year as worth a look; it is not evidence that the year is wrong.\n")
    if not meta[84]["year"]:
        x84 = [k for k, v in o["_dd84"].items() if v == "X"]
        w(f"Calendar 84 has no sheet year (the transcriber reads 2015 or 2025; photographed {meta[84]['photo']}). "
          f"Its {len(x84)} X ({', '.join(f'{d}/{m}' for m, d in sorted(x84))}) are scored as observed; "
          "if the sheet is 2025 they fall after the photo date and would be void under (a).\n")
    w("### Calendar 43: margin notes (reported apart)\n")
    w("X from the gardien's margin notes: " + ", ".join(f"{d}/{m}" for (m, d), v in sorted(margin.items()) if v == "X")
      + ". Uncertain (?): " + ", ".join(f"{d}/{m}" for (m, d), v in sorted(margin.items()) if v == "?")
      + ". Adriaan confirmed 43 with no grid mark; the grid comparison drops these cells for every reader.\n")
    w("## Agreement\n")
    w(f"One observed window for every reader: the sheet year of record (Dieu Donné's export) and the "
      f"photo date. Adriaan's export predates the sheet years set on 28 Sep on ten sheets, so his own "
      f"`etat_cellule` is not used. Calendars both humans confirmed: **{o['calendars_both_humans']}**; "
      f"of these the machine reads **{o['calendars_three_way']}** (three-way set).\n")
    w("### Day level: X versus blank (? shown, never scored)\n")
    for p in pairs:
        A, B = labels[p["a"]], labels[p["b"]]
        scope = "three-way set" if p["scope"] == "three_way" else "all calendars both humans confirmed"
        w(f"**{A} × {B}** ({scope}: {p['calendars']} calendars, {p['cells_in_window']:,} days in the window). "
          f"Agreement on X/blank **{pct(p['agreement'])}** over {p['cells_scored']:,} scored days; "
          f"Cohen's κ {p['kappa'] if p['kappa'] is not None else 'n/a'}.\n")
        vals = ["X", "-", "?"]
        w(f"| {A} ↓ / {B} → | X | blank | ? |")
        w("|---|---|---|---|")
        for va in vals:
            w(f"| {'blank' if va == '-' else va} | " + " | ".join(str(p["matrix"].get(f"{va}|{vb}", 0)) for vb in vals) + " |")
        w("")
    w("### Calendar level: marked (≥ 1 X) versus not, and X per calendar\n")
    w("| pair | scope | calendars | both marked | only A | only B | neither | X total A | X total B | same X count |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for p in cal_pairs:
        w(f"| {labels[p['a']]} × {labels[p['b']]} | {p['scope'].replace('_', ' ')} | {p['calendars']} | {p['both_marked']} | "
          f"{p['a_only']} | {p['b_only']} | {p['neither']} | {p['x_total_a']} | {p['x_total_b']} | {p['same_x_count']} |")
    w("\nPer calendar: `round1_calendriers.csv`.\n")
    w("### Machine reader: sensitivity and specificity\n")
    w("Reference X = positive. Days the machine calls ? are left out and counted.\n")
    w("| reference | TP | FN | FP | TN | machine ? | sensitivity | specificity |")
    w("|---|---|---|---|---|---|---|---|")
    for k, nm in [("adriaan", AM_NAME), ("dieu_donne", DD_NAME), ("both_humans_agree", "both humans agree")]:
        s = mv[k]
        w(f"| {nm} | {s['tp']} | {s['fn']} | {s['fp']} | {s['tn']} | {s['machine_question_mark']} | "
          f"{pct(s['sensitivity'])} | {pct(s['specificity'])} |")
    w("")
    w("## Human disagreements: settle by eye before scoring the machine\n")
    w(f"**{len(dis)}** days on {o['human_disagreement_calendars']} calendars "
      f"({', '.join(f'{k}: {v}' for k, v in sorted(o['human_disagreements_by_type'].items()))}). "
      "Full list: `round1_desaccords_humains.csv`.\n")
    w("| calendar | date | Adriaan | Dieu Donné (cleaned) | Dieu Donné (raw) | machine |")
    w("|---|---|---|---|---|---|")
    for r in dis:
        w(f"| {r['calendrier']} | {r['date']} | {r['adriaan']} | {r['dieu_donne']} | {r['dieu_donne_brut']} | {r['machine']} |")
    w("")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
