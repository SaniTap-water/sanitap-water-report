# -*- coding: utf-8 -*-
"""The gardien-calendar stratum figures, computed from the reader's outputs.

WHY THIS EXISTS
---------------
Days operational was restated as a stratum figure on 21 September (commit
6e5ec14) and its table - 415 point-years, a mean implied DO of 353.6, the
district and year rows - was typed into the page by hand. No script produced
it. Every value reproduces exactly from the calendar reader's own summary
file, so the rule is now written down here and the figures are a file the
repository produces rather than numbers only the page knows.

THE RULE (R), per point-year of data/calendar_extraction_summary.csv:
  n     = days in the sheet year (366 in a leap year)
  obs   = n - days_unobserved; the point-year is kept only if obs >= 30
  rate  = days_not_operational / obs
  DO    = n * (1 - max(rate - floor, 0)), floor = the false-positive rate the
          reader marks on cells that cannot exist (CALX.probe_marked_pct)
  "before the floor" is the same with floor = 0.
Means and medians are over point-years.

This does NOT re-run the reader. Its inputs are the reader's outputs:
data/calendar_extraction_summary.csv (tools/recompute_figures.py, run
2026-09-20), data/gardien_calendar_coverage.csv, data/calendar_year_coverage.csv
(tools/coverage.py), and from ~/sdws1/calendar_extract the photograph
inventory and the first reader's run log. Nothing on this path is random:
there is no seed.

    python3 tools/calendar_stratum.py --write   # data/calendar_stratum_figures.json
    python3 tools/calendar_stratum.py --check
"""
import calendar, csv, datetime, json, os, re, statistics, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAL = os.path.expanduser("~/sdws1/calendar_extract")
OUT = os.path.join(REPO, "data", "calendar_stratum_figures.json")


def d(*p):
    return os.path.join(REPO, "data", *p)


def mtime(p):
    return datetime.date.fromtimestamp(os.path.getmtime(p)).isoformat()


def band(n):
    n = int(n or 0)
    return "1-2" if n <= 2 else "3-5" if n <= 5 else "6+"


def build():
    floor = json.load(open(d("calendar_extraction_figures.json")))["probe_marked_pct"] / 100
    cov = {r["code"]: r for r in csv.DictReader(open(d("gardien_calendar_coverage.csv")))}
    rows = []
    for r in csv.DictReader(open(d("calendar_extraction_summary.csv"))):
        y = int(r["period_year"])
        n = 366 if calendar.isleap(y) else 365
        obs = n - int(r["days_unobserved"])
        if obs < 30:
            continue
        rate = int(r["days_not_operational"]) / obs
        rows.append({"wp": r["water_point"], "site": r["site"], "year": y,
                     "do": n * (1 - max(rate - floor, 0)), "raw": n * (1 - rate)})

    def stratum(rs):
        return {"point_years": len(rs), "points": len({x["wp"] for x in rs}),
                "mean_do": round(statistics.mean(x["do"] for x in rs), 1),
                "median_do": round(statistics.median(x["do"] for x in rs), 1),
                "mean_do_before_floor": round(statistics.mean(x["raw"] for x in rs), 1)}

    out = {"note": "Gardien-calendar stratum figures, computed by rule R (see "
                   "the generator's docstring) from the calendar reader's "
                   "outputs. The reader is not re-run.",
           "generator": "tools/calendar_stratum.py",
           "input": "data/calendar_extraction_summary.csv",
           "input_written_by": "tools/recompute_figures.py",
           "input_run_on": "2026-09-20",
           "seed": None,
           "floor_pct": round(floor * 100, 2),
           "portfolio": stratum(rows),
           "by_site": {s: stratum([x for x in rows if x["site"] == s])
                       for s in sorted({x["site"] for x in rows})},
           "by_year": {str(y): stratum([x for x in rows if x["year"] == y])
                       for y in sorted({x["year"] for x in rows})}}
    # point-year means by how many calendar photographs the point has
    by_band = {}
    for x in rows:
        if x["wp"] in cov:
            by_band.setdefault(band(cov[x["wp"]]["photos_total"]), []).append(x["do"])
    out["mean_do_by_photos"] = {k: {"point_years": len(v),
                                    "mean_do": round(statistics.mean(v), 1)}
                                for k, v in sorted(by_band.items())}
    # which managed points the stratum evidences, by dimension
    ev = {x["wp"] for x in rows} & set(cov)
    dims = {}
    for dim, key in (("site", lambda r: r["site"]), ("pump", lambda r: r["pump"]),
                     ("photos", lambda r: band(r["photos_total"]))):
        t = {}
        for code, r in cov.items():
            c = t.setdefault(key(r), {"evidenced": 0, "not": 0})
            c["evidenced" if code in ev else "not"] += 1
        dims[dim] = dict(sorted(t.items()))
    # the year each point was first recorded in the register (its _created_on)
    reg = {}
    rp = os.path.expanduser("~/mwater-exports/wp_madavance.csv")
    if os.path.isfile(rp):
        reg = {r["code"]: (r.get("_created_on") or "")[:4]
               for r in csv.DictReader(open(rp, encoding="utf8"))}
    t = {}
    for code in cov:
        y = reg.get(code)
        if not y:
            continue
        c = t.setdefault(y, {"evidenced": 0, "not": 0})
        c["evidenced" if code in ev else "not"] += 1
    dims["first_recorded"] = dict(sorted(t.items()))
    out["evidenced_by"] = dims
    # calendar custody by site: the table under "Calendar custody", from the
    # coverage file (a photograph older than 182 days is "older than 6 months")
    cust = {}
    for r in cov.values():
        for k in (r["site"], "All sites"):
            c = cust.setdefault(k, {"points": 0, "with_calendar": 0,
                                    "none_ever": 0, "older_than_6_months": 0})
            c["points"] += 1
            has = r["has_calendar_photo"] == "True"
            c["with_calendar" if has else "none_ever"] += 1
            c["older_than_6_months"] += bool(has and r["days_since"]
                                             and int(r["days_since"]) > 182)
    for c in cust.values():
        c["coverage_pct"] = round(100 * c["with_calendar"] / c["points"], 1)
    out["custody"] = {"file": "data/gardien_calendar_coverage.csv",
                      "as_at": mtime(d("gardien_calendar_coverage.csv")),
                      "by_site": dict(sorted(cust.items()))}
    out["evidenced_points"] = len(ev)
    # the photograph inventory, from the reader's input list
    inv = os.path.join(CAL, "calendar_inventory.csv")
    q = {}
    total = managed = 0
    for r in csv.DictReader(open(inv, encoding="utf8")):
        total += 1
        managed += r["water_point"] in cov
        code = (r["question"] or "").split(" ")[0]
        q[code] = q.get(code, 0) + 1
    out["photographs"] = {"file": "~/sdws1/calendar_extract/calendar_inventory.csv",
                          "listed_on": mtime(inv), "total": total,
                          "on_a_managed_point": managed, "by_question": q}
    # how much of each year the sheets evidence (tools/coverage.py)
    yc = list(csv.DictReader(open(d("calendar_year_coverage.csv"))))
    fr = [float(r["fraction_covered"]) for r in yc]
    out["year_coverage"] = {"file": "data/calendar_year_coverage.csv",
                            "written_by": "tools/coverage.py",
                            "point_years": len(yc),
                            "median_fraction_pct": round(100 * statistics.median(fr)),
                            "below_90pct": sum(1 for f in fr if f < 0.9)}
    # the first reader, superseded, quoted for comparison only
    log = os.path.join(CAL, "run.log")
    m = re.search(r"^\s*(\d+)\s+extracted\s*$", open(log, encoding="utf8").read(), re.M)
    out["first_reader"] = {"file": "~/sdws1/calendar_extract/run.log",
                           "script": "~/sdws1/calendar_extract/run_extract.py",
                           "run_on": mtime(log),
                           "images_extracted": int(m.group(1)) if m else None}
    return out


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    new = json.dumps(build(), indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    old = open(OUT, encoding="utf8").read() if os.path.isfile(OUT) else ""
    if mode == "--write":
        open(OUT, "w", encoding="utf8").write(new)
        print(f"wrote {OUT}")
        return 0
    print("data/calendar_stratum_figures.json "
          + ("matches its inputs" if new == old else "DIFFERS from its inputs"))
    return 0 if new == old else 1


if __name__ == "__main__":
    sys.exit(main())
