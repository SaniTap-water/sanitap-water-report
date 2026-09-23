# -*- coding: utf-8 -*-
"""Draw the SDWS 26 annual usage survey sample, reproducibly.

The VPA-DD commits us to a specific design (section B.7.2): 90% confidence and
a 10% margin of error using the CDM sample size calculator, a minimum of 100
households PER PROJECT SCENARIO, with Anosy and Maroantsetra as separate
scenarios; the project database drives a randomiser that picks the water points
to visit; and a minimum of 8 villages or communes randomly selected per
scenario as clusters.

This draws that sample from the live register extract and records everything
needed to redraw it identically: the seed, the extract's pull date, and the
register row count it was drawn from. A sample nobody can redraw is a sample
nobody can check.

It does NOT decide anything the operation has not decided. A managed point that
falls in neither named scenario is REPORTED for a decision, never assigned to
one: the five Androy points are the Marolinta boreholes, which sit outside the
carbon fleet, and whether they carry a usage survey of their own is a question
for a person.

The density stratification hook is here because the SDWS 23 volume sample will
need it and the same machinery should serve both: every drawn point carries the
number of other fleet points within STRATA_KM, so a later draw can stratify on
it without rebuilding the selection.

    python3 tools/draw_usage_sample.py                    # show the draw
    python3 tools/draw_usage_sample.py --write            # write it
    python3 tools/draw_usage_sample.py --seed 20260923
"""
import argparse, csv, datetime, hashlib, json, math, os, random, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
REGISTER = os.path.expanduser("~/mwater-exports/wp_madavance.csv")
MANIFEST = os.path.join(REPO, "data", "extract_manifest.json")

# VPA-DD B.7.2. Both are floors, not targets.
MIN_HOUSEHOLDS = 100
MIN_CLUSTERS = 8
# The two named project scenarios, by the register's own region field.
SCENARIOS = {"Anosy": "Anosy", "Maroantsetra": "Ambatosoa"}
STRATA_KM = 2.0            # radius for the local pump-density stratum


def haversine(a, b):
    R = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    x = (math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2)
         * math.sin(math.radians(b[1] - a[1]) / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(x))


def fleet_points():
    """Managed points with their region, commune and coordinate."""
    import populations as P
    fleet = P.managed_fleet()
    out = []
    with open(REGISTER, encoding="utf8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            code = str(r.get("code") or "")
            if code not in fleet:
                continue
            try:
                c = json.loads(r["location"])["coordinates"]
                lat, lon = c[1], c[0]
            except Exception:
                lat = lon = None
            out.append({"wp": code,
                        "region": r.get("admin_div1") or None,
                        "district": r.get("admin_div2") or None,
                        "commune": r.get("admin_div3") or None,
                        "fkt": r.get("admin_div4") or None,
                        "lat": lat, "lon": lon})
    return out


def density(points):
    """Fleet points within STRATA_KM of each point - the stratification hook."""
    loc = [(p, (p["lat"], p["lon"])) for p in points if p["lat"] is not None]
    for p, a in loc:
        p["neighbours_2km"] = sum(
            1 for q, b in loc if q is not p and haversine(a, b) <= STRATA_KM * 1000)
    for p in points:
        p.setdefault("neighbours_2km", None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260923)
    ap.add_argument("--clusters", type=int, default=MIN_CLUSTERS)
    ap.add_argument("--households", type=int, default=MIN_HOUSEHOLDS)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    if a.clusters < MIN_CLUSTERS:
        sys.exit(f"--clusters may not go below the VPA-DD floor of {MIN_CLUSTERS}")
    if a.households < MIN_HOUSEHOLDS:
        sys.exit(f"--households may not go below the VPA-DD floor of {MIN_HOUSEHOLDS}")

    pts = fleet_points()
    density(pts)

    man = json.load(open(MANIFEST, encoding="utf8"))["files"].get("wp_madavance.csv", {})
    extract_date = (man.get("written") or "")[:10]
    register_rows = man.get("rows")
    with open(REGISTER, "rb") as fh:
        register_sha = hashlib.sha256(fh.read()).hexdigest()

    by_scen, unassigned = {}, []
    for p in pts:
        scen = next((s for s, reg in SCENARIOS.items() if p["region"] == reg), None)
        if scen is None:
            unassigned.append(p)
        else:
            by_scen.setdefault(scen, []).append(p)

    out = {"note": "SDWS 26 annual usage survey sample. Redraw identically with "
                   "the same --seed against the same register extract.",
           "commitment": "VPA-DD section B.7.2: 90% confidence, 10% margin of "
                         "error, CDM sample size calculator; minimum 100 "
                         "households per project scenario; minimum 8 villages "
                         "or communes randomly selected per scenario as "
                         "clusters; Anosy and Maroantsetra are separate scenarios.",
           "drawn_on": datetime.date.today().isoformat(),
           "seed": a.seed,
           "register_extract_pulled": extract_date,
           "register_rows": register_rows,
           "register_sha256": register_sha,
           "clusters_per_scenario": a.clusters,
           "households_per_scenario": a.households,
           "density_stratum_km": STRATA_KM,
           "scenarios": {}, "not_in_any_scenario": []}

    print(f"seed {a.seed} | register pulled {extract_date} "
          f"({register_rows} rows, sha256 {register_sha[:12]}…)\n")

    for scen, pool in sorted(by_scen.items()):
        communes = sorted({p["commune"] for p in pool if p["commune"]})
        rng = random.Random(f"{a.seed}:{scen}")
        n_cl = min(a.clusters, len(communes))
        chosen = sorted(rng.sample(communes, n_cl))
        inside = [p for p in pool if p["commune"] in chosen]
        rng2 = random.Random(f"{a.seed}:{scen}:points")
        rng2.shuffle(inside)
        per = max(1, math.ceil(a.households / max(1, len(inside))))
        out["scenarios"][scen] = {
            "region": SCENARIOS[scen],
            "fleet_points": len(pool),
            "communes_available": len(communes),
            "clusters_drawn": chosen,
            "clusters_short": max(0, a.clusters - len(communes)),
            "points_in_clusters": len(inside),
            "households_target": a.households,
            "households_per_point": per,
            "points": [{"wp": p["wp"], "commune": p["commune"], "fkt": p["fkt"],
                        "neighbours_2km": p["neighbours_2km"]} for p in inside],
        }
        short = ("" if len(communes) >= a.clusters else
                 f"   ** only {len(communes)} communes exist, "
                 f"{a.clusters} required **")
        print(f"{scen}: {len(pool)} fleet points across {len(communes)} communes"
              f"{short}")
        print(f"   clusters drawn ({n_cl}): {', '.join(chosen)}")
        print(f"   points in those clusters: {len(inside)}; "
              f"{a.households} households target, {per} per point")

    for p in unassigned:
        out["not_in_any_scenario"].append(
            {"wp": p["wp"], "region": p["region"], "district": p["district"],
             "commune": p["commune"]})
    if unassigned:
        regs = sorted({p["region"] for p in unassigned})
        print(f"\nNOT IN ANY NAMED SCENARIO: {len(unassigned)} managed point(s) "
              f"in {', '.join(regs)}")
        print("   Reported for a decision, NOT assigned to a scenario. These are "
              "the Marolinta boreholes,\n   which sit outside the carbon fleet; "
              "whether they carry a usage survey of their own is\n   a question "
              "for a person, not for this script.")

    if not a.write:
        print("\n--dry run: nothing written")
        return 0
    p = os.path.join(REPO, "data",
                     f"usage_sample_{out['drawn_on']}.json")
    json.dump(out, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    print(f"\nwritten: {os.path.relpath(p, REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
