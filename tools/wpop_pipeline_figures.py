# -*- coding: utf-8 -*-
"""The people-served pipeline's own figures, read from its outputs.

WHY THIS EXISTS
---------------
The people-served section quotes figures the WorldPop allocation produced but
that data/sdws1_summary_equal.json does not carry: the people the barrier clip
excludes (27,459, of which 658 in Fort-Dauphin), the totals under the three
ways of splitting a shared service area, and the effect of treating streams as
barriers. They were typed into the page from the run folders, so nothing could
tell them from a typo - and one set of them had quietly come from the
quarantined 2020 raster rather than the raster of record.

This reads them from the run outputs in ~/sdws1 and writes one dated file,
with the raster checksum each run was pinned to. It does NOT re-run the
pipeline. The pipeline is deterministic (no random seed anywhere in
sdws1_population.py), so a figure here moves only if a run folder is replaced.

    python3 tools/wpop_pipeline_figures.py --write   # data/wpop_pipeline_figures.json
    python3 tools/wpop_pipeline_figures.py --check   # exit 1 if the file differs
"""
import csv, datetime, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SDWS1 = os.path.expanduser("~/sdws1")
OUT = os.path.join(REPO, "data", "wpop_pipeline_figures.json")
RUNS = {"barriers": "r2025a_barriers", "nobarriers": "r2025a_nobarriers",
        "streams_as_barriers": "sens_c"}
VARIANTS = {"equal": "equal", "idw": "idw-p2", "nearest": "nearest"}


def summary(run, variant):
    p = os.path.join(SDWS1, "runs", run, f"sdws1_summary_{variant}.json")
    return json.load(open(p, encoding="utf8")), p


def page_sites():
    src = open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    m = re.search(r"\bconst PUMPS\s*=\s*", src)
    arr = json.loads(src[m.end():src.index("];", m.end()) + 1])
    return {p["wp"]: p["site"] for p in arr}


def build():
    out = {"note": "Figures from the WorldPop people-served runs that the "
                   "page quotes and data/sdws1_summary_equal.json does not "
                   "carry. Read from the run outputs, never re-run.",
           "generator": "tools/wpop_pipeline_figures.py",
           "pipeline": "~/sdws1/sdws1_population.py",
           "seed": None,
           "runs": {}}
    for key, run in RUNS.items():
        out["runs"][key] = {"folder": f"~/sdws1/runs/{run}"}
        for name, variant in VARIANTS.items():
            try:
                s, p = summary(run, variant)
            except FileNotFoundError:
                continue
            out["runs"][key][name] = s["reported_after_cap"]
            out["runs"][key].setdefault("raster", s.get("raster"))
            out["runs"][key].setdefault("raster_sha256", s.get("raster_sha256"))
            out["runs"][key].setdefault(
                "run_on", datetime.date.fromtimestamp(os.path.getmtime(p)).isoformat())
    b, s = out["runs"]["barriers"]["equal"], out["runs"]["streams_as_barriers"]["equal"]
    out["streams_as_barriers_delta"] = s - b
    out["streams_as_barriers_delta_pct"] = round(100 * (s - b) / b, 2)

    # people the barrier clip cuts off from every pump that reached them
    p = os.path.join(SDWS1, "barrier_overexclusion.csv")
    sites = page_sites()
    by = {}
    tot = 0.0
    for r in csv.DictReader(open(p, encoding="utf8")):
        x = float(r["people_excluded"] or 0)
        if x <= 0:
            continue
        tot += x
        site = sites.get(r["code"], "not on the page")
        d = by.setdefault(site, {"people": 0.0, "points": 0})
        d["people"] += x
        d["points"] += 1
    out["barrier_exclusion"] = {
        "file": "~/sdws1/barrier_overexclusion.csv",
        "run_on": datetime.date.fromtimestamp(os.path.getmtime(p)).isoformat(),
        "people": round(tot),
        "by_site": {k: {"people": round(v["people"]), "points": v["points"]}
                    for k, v in sorted(by.items())}}
    return out


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    new = json.dumps(build(), indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    old = open(OUT, encoding="utf8").read() if os.path.isfile(OUT) else ""
    if mode == "--write":
        open(OUT, "w", encoding="utf8").write(new)
        print(f"wrote {OUT}")
        return 0
    if new == old:
        print("data/wpop_pipeline_figures.json matches the run outputs")
        return 0
    print("data/wpop_pipeline_figures.json DIFFERS from the run outputs")
    return 1


if __name__ == "__main__":
    sys.exit(main())
