#!/usr/bin/env python3
"""Recompute the published calendar-extraction figures.

Inputs (in --dir unless stated):
  calendar_inventory.csv    every calendar photograph mWater holds
  legibility2.csv           one row per image the reader read
  extraction_days2.csv      one row per printed day cell
  --exclude FILE            image_ids that are not calendars at all
  --sheet-years FILE        image_id,sheet_year read off the sheet itself

Three corrections this carries, each switchable so the previous basis stays
reproducible:

  * images later found not to be calendars are excluded from every count
    rather than inflating the readable total (--exclude);

  * the impossible-cell count comes from the real month lengths of the
    SHEET's year. Every sheet prints a 12 x 31 grid, so a common year has
    seven cells that cannot exist (29, 30, 31 February and four 31sts) and a
    leap year has six. Taking the year from the photograph's date got this
    wrong on any sheet photographed in a later year;

  * --observed-window classifies each real cell as observed or unobserved.
    A calendar photographed on date D can only carry marks for days up to D.
    Cells after D were blank by construction, and counting them in the
    denominator of a marked rate is not measuring anything. With the switch
    off the script reproduces the pre-observed-window basis exactly.

Writes calendar_extraction_figures.json and calendar_extraction_summary.csv
to --out.
"""
import argparse, calendar, collections, csv, datetime as dt, json, os, statistics, sys

MONTHS, DAYS = 12, 31


def month_len(year, m):
    return calendar.monthrange(year, m)[1]


def cell_state(year, m, d, photo):
    """observed | unobserved | impossible, for one printed cell.

    `photo` is the photograph's date, or None when it is unknown, in which
    case nothing can be called unobserved and the cell is treated as observed
    - the conservative direction, since it keeps blank cells in the
    denominator rather than quietly discarding them.
    """
    if d > month_len(year, m):
        return "impossible"
    if photo is None:
        return "observed"
    return "observed" if dt.date(year, m, d) <= photo else "unobserved"


def parse_date(s):
    s = (s or "")[:10]
    try:
        return dt.date(*(int(x) for x in s.split("-")))
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--exclude", default=None)
    ap.add_argument("--sheet-years", default=None,
                    help="image_id,sheet_year; without it the period year is "
                         "taken from the photograph's date, as it used to be")
    ap.add_argument("--observed-window", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    D = a.dir
    rd = lambda n: list(csv.DictReader(open(os.path.join(D, n))))

    excluded = set()
    if a.exclude:
        excluded = {r["image_id"] for r in csv.DictReader(open(a.exclude))}

    sheet_year, undated = {}, set()
    if a.sheet_years:
        for r in csv.DictReader(open(a.sheet_years)):
            y = (r.get("sheet_year") or "").strip()
            if y.isdigit():
                sheet_year[r["image_id"]] = int(y)
            else:
                undated.add(r["image_id"])

    inv = rd("calendar_inventory.csv")
    leg = rd("legibility2.csv")
    quality = {}
    for r in leg:
        try:
            quality[r["image_id"]] = float(r["geometry"]) * float(r["periodicity"])
        except Exception:
            quality[r["image_id"]] = 0.0

    readable = {r["image_id"] for r in leg
                if r["stage"] == "extracted" and r["image_id"] not in excluded}

    # a visit is one mWater response, not one point-day: a point can be
    # visited twice in a day and each visit carries its own photograph
    visits_all = {r["response_id"] for r in inv}
    visits_ok = {r["response_id"] for r in inv if r["image_id"] in readable}
    points_all = {r["water_point"] for r in inv}
    points_ok = {r["water_point"] for r in inv if r["image_id"] in readable}

    # ---- the day cells -------------------------------------------------
    tot = collections.Counter()          # state -> cells
    marked = collections.Counter()       # state -> marked calls
    illeg = collections.Counter()
    probe_cells = probe_marked = 0       # impossible cells in a started month
    per_image = {}                       # image -> aggregate, for the summary
    day_call_images = set()
    year_of, photo_of, site_of, wp_of = {}, {}, {}, {}

    for r in csv.DictReader(open(os.path.join(D, "extraction_days2.csv"))):
        iid = r["image_id"]
        if iid in excluded:
            continue
        if iid not in year_of:
            if a.sheet_years:
                if iid in sheet_year:
                    year_of[iid] = sheet_year[iid]
                else:
                    year_of[iid] = None          # undated: no basis to classify
            else:
                year_of[iid] = int(r["period_year"])
            photo_of[iid] = parse_date(r["photo_date"])
            site_of[iid] = r["site"]
            wp_of[iid] = r["water_point"]
        y = year_of[iid]
        if y is None:
            continue                              # undated sheets carry no cells
        day_call_images.add(iid)
        m, d = int(r["month"]), int(r["day"])
        photo = photo_of[iid] if a.observed_window else None
        st = cell_state(y, m, d, photo)
        call = r["call"]
        tot[st] += 1
        if call == "marked":
            marked[st] += 1
        elif call == "illegible":
            illeg[st] += 1
        if st == "impossible" and a.observed_window:
            p = photo_of[iid]
            if p is None or p >= dt.date(y, m, 1):
                probe_cells += 1
                probe_marked += call == "marked"
        agg = per_image.setdefault(iid, collections.Counter())
        agg[st + ":" + call] += 1
        agg["any:" + call] += 1

    if not a.observed_window:
        probe_cells, probe_marked = tot["impossible"], marked["impossible"]

    obs = tot["observed"]
    obs_marked_pct = round(100 * marked["observed"] / obs, 2) if obs else 0.0
    obs_illeg_pct = round(100 * illeg["observed"] / obs, 2) if obs else 0.0
    probe_pct = round(100 * probe_marked / probe_cells, 2) if probe_cells else 0.0
    true_pct = round(obs_marked_pct - probe_pct, 2)

    # ---- per pump-period summary: best image per (point, sheet year) ----
    best = {}
    for iid, agg in per_image.items():
        y = year_of[iid]
        cand = {
            "water_point": wp_of[iid], "site": site_of[iid], "period_year": y,
            "photo_date": photo_of[iid].isoformat() if photo_of[iid] else "",
            "image_id": iid,
            # with the window off, every printed cell counts, which is what
            # the previous basis did; with it on, only observed cells do
            "days_not_operational": (agg["observed:marked"] if a.observed_window
                                     else agg["any:marked"]),
            "days_illegible": (agg["observed:illegible"] if a.observed_window
                               else agg["any:illegible"]),
            "days_unobserved": agg["unobserved:clear"] + agg["unobserved:marked"]
                               + agg["unobserved:illegible"],
            "_q": quality.get(iid, 0.0),
        }
        k = (cand["water_point"], y)
        if k not in best or cand["_q"] > best[k]["_q"]:
            best[k] = cand
    summ = []
    for k in sorted(best, key=lambda t: (t[0], str(t[1]))):
        v = dict(best[k])
        q = v.pop("_q")
        denom = (366 if calendar.isleap(v["period_year"]) else 365) \
                if a.observed_window else float(MONTHS * DAYS)
        v["confidence"] = round(max(0.0, min(1.0, q))
                                * (1.0 - min(1.0, v["days_illegible"] / float(denom))), 3)
        v["validated"] = "NO"
        summ.append(v)

    by_year = collections.Counter(year_of[i] for i in day_call_images)

    fig = {
        "photographs_total": len(inv),
        "photographs_held": len(leg),
        "photographs_excluded_not_calendar": len(excluded),
        "images_readable": len(readable),
        "images_with_day_calls": len(day_call_images),
        "sheets_dated_from_the_sheet": len([i for i in readable if i in sheet_year]),
        "sheets_not_dated": len([i for i in readable if i not in sheet_year]) if a.sheet_years else 0,
        "visits_total": len(visits_all),
        "visits_with_readable": len(visits_ok),
        "visits_without_readable": len(visits_all) - len(visits_ok),
        "points_total": len(points_all),
        "points_without_readable": len(points_all) - len(points_ok),
        "pump_periods": len(summ),
        "water_points": len({v["water_point"] for v in summ}),
        "days_not_operational": sum(v["days_not_operational"] for v in summ),
        "days_illegible": sum(v["days_illegible"] for v in summ),
        "days_unobserved": sum(v["days_unobserved"] for v in summ),
        "median_confidence": round(statistics.median(v["confidence"] for v in summ), 2) if summ else 0,
        "observed_cells": tot["observed"],
        "unobserved_cells": tot["unobserved"],
        "impossible_cells": tot["impossible"],
        # "could not be read" and "had not happened yet" are different states
        # and are never added together
        "observed_marked": marked["observed"],
        "observed_illegible": illeg["observed"],
        "unobserved_called_illegible": illeg["unobserved"],
        "unobserved_called_marked": marked["unobserved"],
        "observed_marked_pct": obs_marked_pct,
        "observed_illegible_pct": obs_illeg_pct,
        "probe_cells": probe_cells,
        "probe_marked_pct": probe_pct,
        "implied_true_marked_pct": true_pct,
        "implied_days_not_operational": round(365 * true_pct / 100, 1),
        "implied_uptime_days": round(365 - 365 * true_pct / 100, 1),
        "basis": ("observed cells only, sheet year read off the sheet"
                  if a.observed_window else
                  "every printed cell, period year from the photograph date"),
    }
    if a.sheet_years:
        fig["sheets_by_year"] = {str(k): v for k, v in sorted(by_year.items(),
                                                              key=lambda t: str(t[0]))}
    if not a.observed_window:
        # names the old basis used, kept so the previous edition reproduces
        fig["real_cells"] = tot["observed"]
        fig["real_marked_pct"] = obs_marked_pct
        fig["impossible_marked_pct"] = probe_pct

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "calendar_extraction_figures.json"), "w") as f:
        json.dump(fig, f, indent=1)
        f.write("\n")
    cols = ["water_point", "site", "period_year", "photo_date", "image_id",
            "days_not_operational", "days_illegible", "days_unobserved",
            "confidence", "validated"]
    with open(os.path.join(a.out, "calendar_extraction_summary.csv"), "w",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for v in summ:
            w.writerow({c: v[c] for c in cols})

    for k, v in fig.items():
        print(f"  {k:38s} {v}")


if __name__ == "__main__":
    main()
