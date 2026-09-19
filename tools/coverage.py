#!/usr/bin/env python3
"""How much of each year does the calendar evidence actually cover?

A gardien calendar photographed on date D evidences that year only up to D.
Everything after D is blank because it had not happened yet. So a point's
evidence for year Y runs from 1 January Y to the LATEST date on which one of
its year-Y sheets was photographed; earlier photographs of the same year
corroborate that stretch but cannot extend it.

Non-calendar images are excluded, and only sheets the reader could actually
read are counted. Sheets whose year could not be read off the sheet are
reported separately rather than assigned to a year.

    coverage.py --out coverage.csv
"""
import argparse, calendar, collections, csv, datetime as dt, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def parse(s):
    s = (s or "")[:10]
    try:
        return dt.date(*(int(x) for x in s.split("-")))
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=HERE)
    ap.add_argument("--exclude", default=os.path.join(HERE, "noncalendar_confirmed.csv"))
    ap.add_argument("--sheet-years", default=os.path.join(HERE, "sheet_year.csv"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    exc = {r["image_id"] for r in csv.DictReader(open(a.exclude))} if os.path.exists(a.exclude) else set()
    years = {}
    undated = set()
    for r in csv.DictReader(open(a.sheet_years)):
        if r["sheet_year"].isdigit():
            years[r["image_id"]] = int(r["sheet_year"])
        else:
            undated.add(r["image_id"])

    leg = list(csv.DictReader(open(os.path.join(a.dir, "legibility2.csv"))))
    readable = [r for r in leg if r["stage"] == "extracted" and r["image_id"] not in exc]

    # latest photograph per (point, sheet year), plus how many corroborate it
    latest = {}
    for r in readable:
        iid = r["image_id"]
        y = years.get(iid)
        d = parse(r["date"])
        if y is None or d is None:
            continue
        k = (r["water_point"], y)
        e = latest.setdefault(k, {"site": r["site"], "n": 0, "last": None, "first": None})
        e["n"] += 1
        if e["last"] is None or d > e["last"]:
            e["last"] = d
        if e["first"] is None or d < e["first"]:
            e["first"] = d

    rows = []
    for (wp, y), e in sorted(latest.items()):
        ylen = 366 if calendar.isleap(y) else 365
        d = e["last"]
        if d < dt.date(y, 1, 1):
            covered = 0                       # photographed before the year began
        elif d >= dt.date(y, 12, 31):
            covered = ylen
        else:
            covered = (d - dt.date(y, 1, 1)).days + 1
        rows.append({
            "water_point": wp, "site": e["site"], "sheet_year": y,
            "sheets": e["n"], "first_photo": e["first"].isoformat(),
            "last_photo": d.isoformat(), "days_covered": covered,
            "days_in_year": ylen,
            "fraction_covered": round(covered / ylen, 4),
        })

    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    print(f"  point-years with a readable, dated sheet: {len(rows)}")
    print(f"  images whose year could not be read:      {len([r for r in readable if r['image_id'] in undated or r['image_id'] not in years])}")
    by_year = collections.defaultdict(list)
    for r in rows:
        by_year[r["sheet_year"]].append(r["fraction_covered"])
    print()
    print(f"  {'year':6s} {'point-years':>11s} {'median':>8s} {'mean':>8s} "
          f"{'>=90%':>7s} {'>=50%':>7s} {'<25%':>7s}")
    for y in sorted(by_year):
        v = sorted(by_year[y])
        print(f"  {y:<6d} {len(v):>11d} {statistics.median(v):>8.1%} "
              f"{statistics.mean(v):>8.1%} "
              f"{sum(1 for x in v if x >= .9):>7d} {sum(1 for x in v if x >= .5):>7d} "
              f"{sum(1 for x in v if x < .25):>7d}")
    allv = sorted(r["fraction_covered"] for r in rows)
    print()
    print("  distribution of year coverage, all point-years:")
    edges = [0, .1, .25, .5, .75, .9, 1.01]
    lab = ["0-10%", "10-25%", "25-50%", "50-75%", "75-90%", "90-100%"]
    for i, l in enumerate(lab):
        n = sum(1 for x in allv if edges[i] <= x < edges[i + 1])
        bar = "#" * int(60 * n / max(1, len(allv)))
        print(f"    {l:>8s} {n:>5d}  {bar}")
    print(f"\n  median coverage across all point-years: {statistics.median(allv):.1%}")
    print(f"  -> {a.out}")


if __name__ == "__main__":
    main()
