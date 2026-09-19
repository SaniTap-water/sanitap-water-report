#!/usr/bin/env python3
"""Draw the human-to-machine validation sample, from the correct frame.

THE FRAME CHANGED, AND THIS RECORDS WHY.

The original fifty calendars were drawn from "readable calendar photographs".
That was the wrong population. A human transcript can only be compared with a
machine one where the machine produced something to compare, and under the
observed-cell basis that means the sheet must ALSO carry a year, because
without a year there is no observable window and no month lengths. The frame
is therefore:

    photographs the extraction produces day calls for,
    whose year could be read off the sheet,
    and which are calendars at all.

That is the correct population, not a convenient one: it is exactly the set
the extraction makes claims about, and an agreement figure computed on it
describes exactly that set and no more. Sheets outside it stay in the
transcription round and are scored human-to-human only - they answer the
different question of whether a person can read what the machine could not.

Sheets already drawn and inside the frame are KEPT; only the shortfall is
drawn. The draw is stratified by district and across the full quality range,
and the seed is recorded so it can be repeated.

    draw_validation_sample.py --target 34 --seed 20260919 --out selection.csv
"""
import argparse, collections, csv, datetime as dt, json, os, random, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FRAME_TEXT = ("photographs the extraction produces day calls for, whose year "
              "could be read off the sheet, and which are calendars")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=HERE)
    ap.add_argument("--sheet-years", default=os.path.join(HERE, "sheet_year_sweep.csv"))
    ap.add_argument("--exclude", default=os.path.join(HERE, "noncalendar_confirmed.csv"))
    ap.add_argument("--existing", default=os.path.join(HERE, "transcription_sheet_map.csv"))
    ap.add_argument("--target", type=int, default=34)
    ap.add_argument("--minimum", type=int, default=30)
    ap.add_argument("--frame-out", default=None,
                    help="write the whole frame, so the draw can be audited")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    D = a.dir
    exc = {r["image_id"] for r in csv.DictReader(open(a.exclude))}
    years = {r["image_id"]: r["sheet_year"]
             for r in csv.DictReader(open(a.sheet_years)) if r["sheet_year"]}
    leg = {r["image_id"]: r for r in csv.DictReader(open(os.path.join(D, "legibility2.csv")))}
    day_call = set()
    for r in csv.DictReader(open(os.path.join(D, "extraction_days2.csv"))):
        day_call.add(r["image_id"])

    def quality(iid):
        r = leg.get(iid, {})
        try:
            return float(r["geometry"]) * float(r["periodicity"])
        except Exception:
            return 0.0

    DISTRICTS = ("Fort-Dauphin", "Maroantsetra")
    frame = [i for i in sorted(day_call)
             if i not in exc and i in years and i in leg]
    # a district-stratified draw cannot use points with no district; there are
    # a handful, on water points the register has not placed
    unmapped = [i for i in frame if leg[i]["site"] not in DISTRICTS]
    frame = [i for i in frame if leg[i]["site"] in DISTRICTS]
    print(f"  frame: {len(frame)} images  ({FRAME_TEXT})")
    if unmapped:
        print(f"    excluded from the draw: {len(unmapped)} on water points with "
              f"no district recorded")

    existing = {}
    if os.path.exists(a.existing):
        for r in csv.DictReader(open(a.existing)):
            existing[r["image_id"]] = r["sheet"]
    kept = [i for i in frame if i in existing]
    out_of_frame = [(s, i) for i, s in existing.items() if i not in frame]
    print(f"  already drawn and inside the frame: {len(kept)}")
    print(f"  already drawn but outside it:       {len(out_of_frame)}"
          f"   (kept in the round, human-to-human only)")

    need = max(0, a.target - len(kept))
    print(f"  target {a.target} (methodology minimum {a.minimum}) -> draw {need}")

    pool = [i for i in frame if i not in existing]
    # stratify: district in proportion to the frame, and evenly across the
    # quality range inside each district, so the sample is not all easy sheets
    by_site = collections.defaultdict(list)
    for i in pool:
        by_site[leg[i]["site"]].append(i)
    frame_sites = collections.Counter(leg[i]["site"] for i in frame)
    rng = random.Random(a.seed)
    picked = []
    if need:
        tot = sum(frame_sites.values())
        quota = {s: max(1, round(need * frame_sites[s] / tot)) for s in frame_sites}
        while sum(quota.values()) > need:
            quota[max(quota, key=lambda s: quota[s])] -= 1
        while sum(quota.values()) < need:
            quota[max(frame_sites, key=lambda s: frame_sites[s])] += 1
        for site, k in quota.items():
            cand = sorted(by_site.get(site, []), key=quality)
            if not cand or k <= 0:
                continue
            # k quality bands, one draw from each, so the whole range is covered
            bands = [cand[j * len(cand) // k:(j + 1) * len(cand) // k] for j in range(k)]
            for b in bands:
                if b:
                    picked.append(rng.choice(b))
            print(f"    {site}: frame {frame_sites[site]}, pool {len(cand)}, drawn {k}")

    qs = [quality(i) for i in frame]
    cuts = [statistics.quantiles(qs, n=4)[j] for j in range(3)] if len(qs) > 4 else [0, 0, 0]
    def band(q):
        return 1 + sum(1 for c in cuts if q > c)

    stamp = dt.date.today().isoformat()
    rows = []
    for i in kept + picked:
        r = leg[i]
        rows.append({
            "calendrier": existing.get(i, ""), "image_id": i,
            "water_point": r["water_point"], "site": r["site"],
            "sheet_year": years[i], "photo_date": r["date"][:10],
            "quality": round(quality(i), 4), "quality_quartile": band(quality(i)),
            "in_frame": "yes",
            "origin": "kept from the original draw" if i in existing else "drawn to make up the shortfall",
            "drawn_on": stamp if i not in existing else "",
            "frame": FRAME_TEXT, "seed": a.seed,
        })
    for s, i in sorted(out_of_frame, key=lambda t: int(t[0])):
        r = leg.get(i, {})
        rows.append({
            "calendrier": s, "image_id": i,
            "water_point": r.get("water_point", ""), "site": r.get("site", ""),
            "sheet_year": years.get(i, ""), "photo_date": r.get("date", "")[:10],
            "quality": round(quality(i), 4), "quality_quartile": band(quality(i)),
            "in_frame": "no",
            "origin": "kept from the original draw, outside the frame",
            "drawn_on": "", "frame": FRAME_TEXT, "seed": a.seed,
        })
    with open(a.out, "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    infr = [r for r in rows if r["in_frame"] == "yes"]
    print(f"\n  comparison set: {len(infr)}  (minimum {a.minimum}: "
          f"{'met' if len(infr) >= a.minimum else 'NOT MET'})")
    print("  by district:", dict(collections.Counter(r["site"] for r in infr)))
    print("  by quality quartile:",
          dict(sorted(collections.Counter(r["quality_quartile"] for r in infr).items())))
    print("  by sheet year:",
          dict(sorted(collections.Counter(r["sheet_year"] for r in infr).items())))
    print(f"  human-to-human only: {len(rows) - len(infr)}")
    if a.frame_out:
        with open(a.frame_out, "w", newline="", encoding="utf8") as f:
            w = csv.writer(f)
            w.writerow(["image_id", "water_point", "site", "sheet_year",
                        "photo_date", "quality", "drawn"])
            drawn_ids = {r["image_id"] for r in rows if r["in_frame"] == "yes"}
            for i in frame:
                r = leg[i]
                w.writerow([i, r["water_point"], r["site"], years[i],
                            r["date"][:10], round(quality(i), 4),
                            "yes" if i in drawn_ids else "no"])
        print(f"  -> {a.frame_out}  ({len(frame)} rows)")
    print(f"  -> {a.out}")


if __name__ == "__main__":
    main()
