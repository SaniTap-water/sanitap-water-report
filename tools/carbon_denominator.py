# -*- coding: utf-8 -*-
"""The carbon denominator, derived - because 727 never was.

WHAT WAS WRONG
--------------
727 appeared on the page as "active carbon points" and was used as the
denominator under carbon claims. It arrived already formed in commit 8b33228
(20 September 2026, the SDWS 27 basis work) with no computation beside it, and
nothing in this repository can reproduce it:

  * 732 corrected successful first rehabilitations minus 5 Marolinta = 727,
    but only as arithmetic. SUCC_CORRECTED counts corrected RECORDS, two of
    which are not in the maintained fleet, so subtracting Marolinta from it is
    not a set operation over the fleet.
  * 731 - 4, 736 - 9, 751 - 24, 738 - 11 all reach 727 and none of the
    subtrahends corresponds to any identified set.
  * The nearest principled reading - successfully rehabilitated, not
    Marolinta, less the points flagged "refer to James Walker before this
    point is counted in a monitoring report" - gives 728, not 727, because one
    of those three (742895010) is not in the fleet to begin with.

And it cannot be checked, because the data needed is not here:
premiere_rehabilitation.csv is header-only and wp_madavance.csv carries no
rehabilitation, eligibility or commissioning column. So no per-point
successful-rehabilitation set and no per-year activity set exists locally.

WHAT IS DERIVABLE
-----------------
The carbon denominator is the actively managed fleet less Marolinta, which is
Deichmann-funded and enters no carbon figure: 731 points, computed from the
register every build.

The 2026 calendar coverage then follows from the extraction, and it settles
which of the old figures was right: 434 points with no dated 2026 sheet
reproduces EXACTLY on the 731 basis. It was the denominator (727) and the
covered count (293) that were wrong; 293 was simply 727 - 434.

    python3 tools/carbon_denominator.py --write
"""
import csv, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "carbon_denominator.json")


def pumps():
    html = open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    m = re.search(r"\bconst PUMPS\s*=\s*\[", html)
    i = html.index("[", m.start())
    d, j = 0, i
    instr = esc = False
    while j < len(html):
        c = html[j]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        elif c == '"':
            instr = True
        elif c == "[":
            d += 1
        elif c == "]":
            d -= 1
            if d == 0:
                break
        j += 1
    return json.loads(html[i:j + 1])


def compute():
    P = pumps()
    carbon = {p["wp"] for p in P if p["site"] != "Marolinta"}
    rows = list(csv.DictReader(
        open(os.path.join(REPO, "data", "calendar_year_coverage.csv"),
             encoding="utf8")))
    y2026 = {r["water_point"] for r in rows if r["sheet_year"] == "2026"}
    with_ev = len(y2026 & carbon)
    return {
        "carbon_points": len(carbon),
        "carbon_points_with_2026_sheet": with_ev,
        "carbon_points_without_2026_sheet": len(carbon) - with_ev,
        "carbon_2026_coverage_pct": round(with_ev / len(carbon) * 100, 1),
        "sheets_2026_outside_the_fleet": len(y2026 - {p["wp"] for p in P}),
        "basis": ("actively managed register less Marolinta (Deichmann-funded, "
                  "no carbon figure); 2026 evidence is a dated 2026 sheet in "
                  "data/calendar_year_coverage.csv, sheet year read off the "
                  "sheet"),
        "supersedes": ("727 active carbon points and 293 covered, which were "
                       "carried from 2026-09-20 (commit 8b33228) with no "
                       "computation behind them and are not reproducible from "
                       "any data in this repository"),
    }


def main():
    doc = compute()
    if "--write" in sys.argv:
        json.dump(doc, open(OUT, "w", encoding="utf8"),
                  indent=1, ensure_ascii=False, sort_keys=True)
        print(f"written: {OUT}")
    for k, v in doc.items():
        print(f"  {k:36} {v}" if not isinstance(v, str)
              else f"  {k:36} {v[:70]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
