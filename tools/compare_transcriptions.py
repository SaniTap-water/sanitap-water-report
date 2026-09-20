#!/usr/bin/env python3
"""Compare independent human transcriptions of the gardien calendars, and
compare each of them against the machine reading.

Usage:
    compare_transcriptions.py --out agreement.csv \
        releves_a.csv releves_b.csv [...] \
        [--machine /path/to/extraction_days2.csv]

Inputs
------
Each positional argument is a CSV exported by the transcription page. Its
columns are calendrier, point_eau, date_photo, mois, jour, releve, exclu,
exclu_motif, transcripteur, session_id, secondes_sur_calendrier, notes,
exporte_le. One file may hold several transcribers; they are separated on
(transcripteur, session_id), so a file is not assumed to be one person.

--machine points at the reader's per-cell output. Its calls are mapped
marked -> X, illegible -> ?, clear -> blank, which is the same three-way
vocabulary the page offers.

What is compared
----------------
Human-to-human and human-to-machine are reported SEPARATELY and never
pooled: they answer different questions, and mixing them would let the
machine's errors be absorbed into a figure labelled "inter-rater".

Cells outside the photograph's observable window are dropped from both sides:
the transcription page locks them, so a human never marks them, and comparing
a machine call there against a forced blank would measure nothing.

A sheet that ANY side marks "ce n'est pas un calendrier" is dropped from
every comparison involving that side. An excluded sheet is not a sheet of
blanks; scoring it as zeroes would manufacture perfect agreement out of two
people both declining to transcribe a signboard.

The calendar, not the cell, is the unit. Cells within one sheet share its
paper, its light, its handwriting and its template, so per-cell pooling
overstates precision. Agreement is computed per calendar, and the headline
figure is the mean over calendars with the spread beside it, not a pooled
cell count. Pooled cell agreement is printed too, clearly labelled, because
a verifier will ask for it.

Output
------
One CSV. Rows of kind "calendar" carry per-sheet agreement for one pair;
rows of kind "pair" carry that pair's summary over calendars. Nothing is
written to the report page.
"""
import argparse, collections, csv, itertools, json, math, os, statistics, sys

MACHINE_MAP = {"marked": "X", "illegible": "?", "clear": ""}

# An agreement figure is meaningless without the population it applies to. It
# is NOT "how well the extraction reads the calendars"; it is "how well it
# reads the ones it produces any output for at all". That denominator travels
# with the number - printed above the table, written into the output file, and
# asserted on the report page.
COVERAGE = []


def coverage_lines(figures_path):
    try:
        f = json.load(open(figures_path))
    except Exception:
        return []
    return [
        "COVERAGE THIS FIGURE APPLIES TO:",
        f"  the extraction produces day calls for {f['images_with_day_calls']:,} of "
        f"{f['images_readable']:,} readable calendar photographs and "
        f"{f['photographs_total']:,} held.",
        f"  Any agreement figure above describes ONLY those "
        f"{f['images_with_day_calls']:,}. It says nothing about the rest, which "
        "the extraction cannot read or cannot date.",
    ]


def read_human(path):
    """-> {(who, session): {sheet: {"cells": {(m,d): v}, "excluded": reason}}}"""
    out = collections.defaultdict(lambda: collections.defaultdict(
        # "comparable" is added to a sheet when the export flags it
        lambda: {"cells": {}, "excluded": None, "wp": "", "secs": 0,
                 "unobserved": 0}))
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            who = (r.get("transcripteur", "").strip(), r.get("session_id", "").strip())
            if not who[0]:
                sys.exit(f"{path}: a row has no transcripteur; refusing to guess who made it")
            sheet = r["calendrier"]
            rec = out[who][sheet]
            rec["wp"] = r.get("point_eau", "")
            try:
                rec["secs"] = max(rec["secs"], int(r.get("secondes_sur_calendrier") or 0))
            except ValueError:
                pass
            if r.get("comparable_machine"):
                rec["comparable"] = r["comparable_machine"].strip().lower() in ("oui", "yes", "1", "true")
            if (r.get("exclu", "") or "").strip().lower() in ("oui", "yes", "true", "1"):
                rec["excluded"] = (r.get("exclu_motif") or "autre").strip() or "autre"
                continue
            if r["releve"] == "EXCLU":          # older export, no exclu column
                rec["excluded"] = "autre"
                continue
            if not r["mois"] or not r["jour"]:
                continue
            # a cell the photograph could not show is not a blank cell: it is
            # not evidence either way, and it is kept out of the comparison
            # rather than scored as agreement between two empty boxes
            if (r.get("etat_cellule") or "observe").strip() != "observe":
                rec["unobserved"] = rec.get("unobserved", 0) + 1
                continue
            rec["cells"][(int(r["mois"]), int(r["jour"]))] = (r["releve"] or "").strip()
            if r.get("comparable_machine"):
                rec["comparable"] = r["comparable_machine"].strip().lower() in ("oui", "yes", "1", "true")
    return {k: dict(v) for k, v in out.items()}


def read_machine(path, wanted_sheets_by_wp):
    # NOTE the machine file is per-cell for the whole printed grid. Only the
    # cells the humans kept are compared, so restricting the humans to the
    # observed window restricts the machine to it too, automatically.
    """The reader keys on image, the page keys on sheet number, so the join is
    on water point. Only sheets the humans actually transcribed are loaded."""
    want = set(wanted_sheets_by_wp)
    cells = collections.defaultdict(dict)
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            wp = r["water_point"]
            if wp not in want:
                continue
            call = MACHINE_MAP.get(r["call"])
            if call is None:
                continue
            cells[wp][(int(r["month"]), int(r["day"]))] = call
    return cells


def agree(a, b):
    """Agreement over the cells both sides actually have a value for."""
    keys = set(a) & set(b)
    if not keys:
        return None
    same = sum(1 for k in keys if a[k] == b[k])
    conf = collections.Counter((a[k] or "-", b[k] or "-") for k in keys if a[k] != b[k])
    return len(keys), same, conf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--machine", default=None,
                    help="per-cell reader output (extraction_days2.csv)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--figures", default=None,
                    help="data/calendar_extraction_figures.json, so the coverage "
                         "the agreement applies to is printed alongside it")
    ap.add_argument("--comparable", default=None,
                    help="CSV of the sheets the extraction produces day calls for "
                         "(the human-to-machine frame). Sheets outside it are still "
                         "compared human-to-human, under their own heading, and are "
                         "never folded into the machine figure.")
    a = ap.parse_args()

    global COVERAGE
    if a.figures:
        COVERAGE = coverage_lines(a.figures)

    # The validation frame is "sheets the extraction produces day calls for".
    # Sheets outside it answer a DIFFERENT question - whether a human can read
    # what the machine could not - which is the evidence for choosing between
    # the extraction and manual transcription.
    # the export now carries the flag itself, so no separate frame file and no
    # hand editing is needed; --comparable stays as an override
    frame = None
    if a.comparable:
        frame = {r["calendrier"].strip()
                 for r in csv.DictReader(open(a.comparable))
                 if r.get("in_frame", "yes").strip().lower() in
                 ("yes", "oui", "1", "true")}

    people = {}
    for p in a.files:
        for who, sheets in read_human(p).items():
            if who in people:
                sys.exit(f"{who[0]} / session {who[1]} appears in more than one file")
            people[who] = sheets
    if not people:
        sys.exit("no transcriptions found")

    wp_of = {}
    for sheets in people.values():
        for s, rec in sheets.items():
            if rec["wp"]:
                wp_of[s] = rec["wp"]

    machine = {}
    if a.machine:
        by_wp = read_machine(a.machine, set(wp_of.values()))
        for s, wp in wp_of.items():
            if wp in by_wp:
                machine[s] = by_wp[wp]

    rows = []

    def compare_pair(kind, name_a, name_b, sheets_a, sheets_b, excl_a, excl_b):
        per_cal, dropped = [], []
        for s in sorted(set(sheets_a) & set(sheets_b), key=lambda x: int(x)):
            why = []
            if s in excl_a:
                why.append(f"{name_a}: {excl_a[s]}")
            if s in excl_b:
                why.append(f"{name_b}: {excl_b[s]}")
            if why:
                dropped.append((s, "; ".join(why)))
                rows.append({"kind": "calendar", "comparison": kind, "a": name_a,
                             "b": name_b, "calendrier": s, "point_eau": wp_of.get(s, ""),
                             "cells_compared": 0, "cells_agreeing": 0, "agreement": "",
                             "status": "excluded", "detail": "; ".join(why)})
                continue
            res = agree(sheets_a[s], sheets_b[s])
            if res is None:
                rows.append({"kind": "calendar", "comparison": kind, "a": name_a,
                             "b": name_b, "calendrier": s, "point_eau": wp_of.get(s, ""),
                             "cells_compared": 0, "cells_agreeing": 0, "agreement": "",
                             "status": "no overlapping cells", "detail": ""})
                continue
            n, same, conf = res
            per_cal.append(same / n)
            top = "; ".join(f"{x or 'vide'}->{y or 'vide'} x{c}"
                            for (x, y), c in conf.most_common(3))
            rows.append({"kind": "calendar", "comparison": kind, "a": name_a,
                         "b": name_b, "calendrier": s, "point_eau": wp_of.get(s, ""),
                         "cells_compared": n, "cells_agreeing": same,
                         "agreement": round(same / n, 4), "status": "compared",
                         "detail": top})
        pooled_n = sum(r["cells_compared"] for r in rows
                       if r["comparison"] == kind and r["a"] == name_a
                       and r["b"] == name_b and r["status"] == "compared")
        pooled_s = sum(r["cells_agreeing"] for r in rows
                       if r["comparison"] == kind and r["a"] == name_a
                       and r["b"] == name_b and r["status"] == "compared")
        rows.append({
            "kind": "pair", "comparison": kind, "a": name_a, "b": name_b,
            "calendrier": "", "point_eau": "",
            "cells_compared": pooled_n, "cells_agreeing": pooled_s,
            "agreement": round(statistics.mean(per_cal), 4) if per_cal else "",
            "status": f"{len(per_cal)} calendars compared, {len(dropped)} excluded",
            "detail": ("mean over calendars; sd "
                       + (f"{statistics.stdev(per_cal):.4f}" if len(per_cal) > 1 else "n/a")
                       + f"; min {min(per_cal):.4f}; pooled-cell "
                       + f"{pooled_s / pooled_n:.4f}" if per_cal else "nothing compared"),
        })

    if frame is None:
        # the export flags each sheet itself, so the frame needs no second file
        flagged = {s_ for sheets in people.values() for s_, r in sheets.items()
                   if r.get("comparable")}
        any_flag = any("comparable" in r for sheets in people.values()
                       for r in sheets.values())
        if any_flag:
            frame = flagged

    names = {who: f"{who[0]} [{who[1][:6]}]" for who in people}

    def sel(w, inside):
        """That transcriber's sheets, inside or outside the machine frame."""
        return {s: r["cells"] for s, r in people[w].items()
                if frame is None or ((s in frame) == inside)}

    for wa, wb in itertools.combinations(sorted(people, key=lambda w: names[w]), 2):
        ea = {s: r["excluded"] for s, r in people[wa].items() if r["excluded"]}
        eb = {s: r["excluded"] for s, r in people[wb].items() if r["excluded"]}
        compare_pair("human-human", names[wa], names[wb],
                     sel(wa, True), sel(wb, True), ea, eb)
        if frame is not None:
            compare_pair("human-human-not-machine-readable", names[wa], names[wb],
                         sel(wa, False), sel(wb, False), ea, eb)

    # human to machine
    if machine:
        for w in sorted(people, key=lambda w: names[w]):
            ca = sel(w, True)
            ea = {s: r["excluded"] for s, r in people[w].items() if r["excluded"]}
            cm = {s: machine[s] for s in ca if s in machine}
            compare_pair("human-machine", names[w], "machine", ca, cm, ea, {})
    elif a.machine:
        print("  ! no machine cells matched these sheets", file=sys.stderr)

    cols = ["kind", "comparison", "a", "b", "calendrier", "point_eau",
            "cells_compared", "cells_agreeing", "agreement", "status", "detail"]
    with open(a.out, "w", newline="", encoding="utf8") as f:
        for line in COVERAGE:
            f.write("# " + line + "\n")
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    for r in rows:
        if r["kind"] == "pair":
            print(f"  {r['comparison']:32s} {r['a']} vs {r['b']}: "
                  f"{r['agreement']}  ({r['status']})")
    if COVERAGE:
        print()
        for line in COVERAGE:
            print(f"  {line}")
    print(f"  -> {a.out}")


if __name__ == "__main__":
    main()
