# -*- coding: utf-8 -*-
"""Rerun the SDWS 1 allocation when the portfolio gains or loses a pump.

WHY THIS EXISTS
---------------
The people-served figure is a WorldPop allocation computed over the whole
portfolio at once: a 1 km service area per pump, the insurmountable-barrier
clip, the population of every shared cell split equally between the pumps
that reach it, then the pump's capacity cap. It was run on 16 September and
never again. When 742894057 joined on 23 September it had no allocation, so
Fort-Dauphin's people per pump fell from 323 to 320 and the people-served
total silently left it out.

Adding or removing a pump changes that pump's allocation AND the shares of
every pump whose 1 km area overlaps it; no other pump can move, because no
other pump shares a cell with it. So this step:

  1. compares the fleet (PUMPS) with the pumps the allocation covers (WPOP).
     Equal: nothing to do, and nothing outside the repository is needed.
  2. Otherwise reruns the existing pipeline, ~/sdws1/sdws1_population.py, on
     the run of record's own inputs with the joining pumps appended and the
     leaving ones dropped, with the parameters of the run of record: the
     R2025A raster pinned by checksum, 1 km, the barrier clip, equal split,
     the capacity cap. Into a new dated run folder; nothing is overwritten.
  3. Takes the new values for the joining and leaving pumps and every pump
     within 2 km of one (two 1 km areas can only overlap within 2 km), and
     FAILS if any other pump's allocation moved - that would mean the rerun
     is not reproducing the run of record, and nothing should be published.
  4. Writes WPOP, the run-derived WPOPMETA fields, the repository copy of the
     run summary (data/sdws1_summary_equal.json) and a line in
     data/wpop_rerun_log.json.

If a rerun is needed and the raster, its checksum, the barrier network, the
pipeline or its Python is unavailable, it exits non-zero with one plain
sentence as its last line, which the weekly build turns into its OUTCOME
line. It never publishes a blank allocation.

    python3 tools/rerun_wpop.py            # say what would happen
    python3 tools/rerun_wpop.py --write
    python3 tools/rerun_wpop.py --adopt r2025a_barriers_20260930 --reason "..."

--adopt takes a full run of the pipeline after a METHOD change (30 Sep 2026:
the barrier split fix), when every pump may move and the drift guard above
would rightly refuse. It adopts the run only if its input is the run of
record's own input (same pumps, same coordinates, same pump models), it was
made on the pinned raster by the pipeline as it is now (sha256 of
sdws1_population.py in the run summary) with no split failures, and it covers
exactly the fleet. Every pump is replaced; the log records the reason and every
change.
"""
import csv, datetime, hashlib, io, json, math, os, re, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
SUMMARY = os.path.join(REPO, "data", "sdws1_summary_equal.json")
RERUN_LOG = os.path.join(REPO, "data", "wpop_rerun_log.json")
sys.path.insert(0, os.path.join(REPO, "tools"))
import build_config as _cfg
_C = _cfg.load()["worldpop"]
SDWS1 = "/home/bushp/sdws1"
PIPELINE = os.path.join(SDWS1, "sdws1_population.py")
PY = os.path.join(SDWS1, "venv", "bin", "python")
RASTER = os.path.join(SDWS1, "rasters", _cfg.load()["worldpop"]["raster"])
# from data/build_config.json, which the page's footnotes render
RASTER_SHA256 = _C["raster_sha256"]
BARRIERS = os.path.join(SDWS1, "madagascar-barriers.osm.pbf")
# two service areas can only meet within twice the service radius
OVERLAP_M = _C["neighbourhood_radius_m"]
FROM_RUN = {"rows": "points", "points_with_a_barrier": "points_with_a_barrier",
            "points_cut_over_10pct": "points_cut_over_10pct",
            "points_at_the_cap": "points_at_the_cap",
            "raster_national_sum": "raster_national_sum", "raster": "raster",
            "pipeline_sha256": "pipeline_sha256"}


def stop(sentence):
    """The last line is one plain sentence; the build quotes it."""
    print(sentence)
    sys.exit(1)


def const(src, name):
    m = re.search(r"\bconst %s\s*=\s*" % name, src)
    i = m.end()
    close = "};" if src[i] == "{" else "];"
    j = src.index(close, i) + 1
    return i, j, json.loads(src[i:j])


def metres(a, b):
    r = math.pi / 180
    x = (math.sin((b[0] - a[0]) * r / 2) ** 2 + math.cos(a[0] * r)
         * math.cos(b[0] * r) * math.sin((b[1] - a[1]) * r / 2) ** 2)
    return 2 * 6371000 * math.asin(math.sqrt(x))


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def before_of(prev):
    """The run of record's figures before a method change, from its own summary."""
    return {"run": str(prev.get("_run", "")).split(",")[0].strip(),
            "reported_after_cap": prev.get("reported_after_cap"),
            "points_cut_over_10pct": prev.get("points_cut_over_10pct"),
            "points_at_the_cap": prev.get("points_at_the_cap")}


def pipeline_sha256():
    return sha256(PIPELINE)


PIN = _cfg.load()["worldpop"]["pipeline"]


def check_pipeline():
    """The method lives in SaniTap-water/sdws1-method; the report runs it only at the
    commit pinned in data/build_config.json, with the script unmodified (1 Oct 2026)."""
    try:
        head = subprocess.run(["git", "-C", SDWS1, "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", SDWS1, "status", "--porcelain", "--", PIN["script"]],
                               capture_output=True, text=True, check=True).stdout.strip()
    except Exception as e:
        stop(f"The SDWS 1 pipeline at {SDWS1} is not the {PIN['repo']} repository ({e}), so nothing was run.")
    if head != PIN["commit"]:
        stop(f"The SDWS 1 pipeline is at {head[:12]}, not the pinned commit {PIN['commit'][:12]} "
             f"of {PIN['repo']}, so nothing was run.")
    if dirty:
        stop(f"{PIN['script']} has local changes against the pinned commit, so nothing was run.")
    if pipeline_sha256() != PIN["script_sha256"]:
        stop("The pipeline script does not match the pinned sha256, so nothing was run.")


def repin(run, reason):
    """Adopt a rerun at a newly pinned commit whose per-point figures are identical."""
    check_pipeline()
    src = open(PAGE, encoding="utf8").read()
    wi, wj, wpop = const(src, "WPOP")
    out = os.path.join(SDWS1, "runs", run)
    summ = json.load(open(os.path.join(out, "sdws1_summary_equal.json"), encoding="utf8"))
    if summ.get("pipeline_sha256") != PIN["script_sha256"] or summ.get("raster_sha256") != RASTER_SHA256 \
            or summ.get("split_failures", 1) != 0:
        stop(f"The run {run} was not made by the pinned pipeline on the pinned raster without split failures, so it was not adopted.")
    new = {}
    for row in csv.DictReader(open(os.path.join(out, "sdws1_population_equal.csv"), encoding="utf8")):
        new[row["code"]] = [int(round(float(row["allocated"]))), int(float(row["revised"])), int(float(row["cap"]))]
    diff = [c for c in set(new) | set(wpop) if new.get(c) != wpop.get(c)]
    if diff:
        stop(f"The run {run} differs from the page on {len(diff)} pump(s) (first {sorted(diff)[0]}): a re-pin must "
             "reproduce every figure exactly, so it was not adopted.")
    prev = json.load(open(SUMMARY, encoding="utf8"))
    today = datetime.date.today().isoformat()
    mi, mj, meta = const(src, "WPOPMETA")
    for pf, rf in FROM_RUN.items():
        meta[pf] = summ[rf]
    meta["run"] = today
    src = src[:mi] + json.dumps(meta, ensure_ascii=False) + src[mj:]
    open(PAGE, "w", encoding="utf8").write(src)
    doc = dict(summ)
    doc["_before_method_change"] = prev.get("_before_method_change")
    doc["_copied"] = today
    doc["_run"] = f"{run}, allocation=equal"
    doc["_note"] = ("The WorldPop allocation run's own summary, copied verbatim from "
                    f"~/sdws1/runs/{run}/sdws1_summary_equal.json by tools/rerun_wpop.py --repin: {reason} "
                    "Every per-point figure is identical to the previous run of record. "
                    "tools/check_wpopmeta.py asserts the page against this file every build.")
    json.dump(doc, open(SUMMARY, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    log = json.load(open(RERUN_LOG, encoding="utf8")) if os.path.isfile(RERUN_LOG) else []
    log.append({"on": today, "run": f"~/sdws1/runs/{run}", "raster_sha256": RASTER_SHA256,
                "pipeline_sha256": summ["pipeline_sha256"], "pipeline_commit": PIN["commit"], "repin": reason,
                "joined": [], "left": [], "within_2km": [], "changed": {},
                "reported_after_cap": summ["reported_after_cap"]})
    json.dump(log, open(RERUN_LOG, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    print(f"re-pinned to {PIN['repo']}@{PIN['commit'][:12]}: run {run}, every figure identical "
          f"({summ['reported_after_cap']} reported after cap).")
    return 0


def adopt(run, reason):
    """Adopt a full rerun after a method change (see the module docstring)."""
    check_pipeline()
    src = open(PAGE, encoding="utf8").read()
    _pi, _pj, pumps = const(src, "PUMPS")
    wi, wj, wpop = const(src, "WPOP")
    fleet = {p["wp"]: p for p in pumps}
    out = os.path.join(SDWS1, "runs", run)
    summ = json.load(open(os.path.join(out, "sdws1_summary_equal.json"), encoding="utf8"))
    if summ.get("raster_sha256") != RASTER_SHA256:
        stop(f"The run {run} was not made on the pinned raster, so it was not adopted.")
    if summ.get("pipeline_sha256") != pipeline_sha256():
        stop(f"The run {run} was made by a different version of the pipeline than the one in "
             f"{PIPELINE}, so it was not adopted.")
    if summ.get("split_failures", 1) != 0:
        stop(f"The run {run} records {summ.get('split_failures')} barrier split failure(s), so it was not adopted.")
    _prev = json.load(open(SUMMARY, encoding="utf8"))
    _run_dir = os.path.join(SDWS1, "runs", str(_prev.get("_run") or "").split(",")[0].strip())
    rec_in = list(csv.DictReader(open(os.path.join(_run_dir, _prev.get("points_file") or "water_points.csv"), encoding="utf8")))
    new_in = list(csv.DictReader(open(os.path.join(out, "water_points.csv"), encoding="utf8")))
    if rec_in != new_in:
        stop(f"The input of {run} is not the run of record's own input, so it was not adopted.")
    new = {}
    for row in csv.DictReader(open(os.path.join(out, "sdws1_population_equal.csv"), encoding="utf8")):
        new[row["code"]] = [int(round(float(row["allocated"]))), int(float(row["revised"])), int(float(row["cap"]))]
    if set(new) != set(fleet):
        stop(f"The run {run} does not cover exactly the fleet, so it was not adopted.")
    changed = {c: {"was": wpop.get(c), "now": new[c]} for c in sorted(new) if new[c] != wpop.get(c)}
    src = src[:wi] + json.dumps(new, separators=(",", ":")) + src[wj:]
    today = datetime.date.today().isoformat()
    mi, mj, meta = const(src, "WPOPMETA")
    for pf, rf in FROM_RUN.items():
        meta[pf] = summ[rf]
    meta["before_method_change"] = before_of(_prev)
    meta["run"] = today
    meta["pipeline_sha256"] = summ["pipeline_sha256"]
    src = src[:mi] + json.dumps(meta, ensure_ascii=False) + src[mj:]
    open(PAGE, "w", encoding="utf8").write(src)
    doc = dict(summ)
    doc["_before_method_change"] = before_of(_prev)
    doc["_copied"] = today
    doc["_run"] = f"{run}, allocation=equal"
    doc["_note"] = ("The WorldPop allocation run's own summary, copied verbatim from "
                    f"~/sdws1/runs/{run}/sdws1_summary_equal.json by tools/rerun_wpop.py --adopt, "
                    f"which adopted a full rerun after a method change: {reason} "
                    "tools/check_wpopmeta.py asserts the page against this file every build.")
    json.dump(doc, open(SUMMARY, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    log = json.load(open(RERUN_LOG, encoding="utf8")) if os.path.isfile(RERUN_LOG) else []
    log.append({"on": today, "run": f"~/sdws1/runs/{run}", "raster_sha256": RASTER_SHA256,
                "pipeline_sha256": summ["pipeline_sha256"], "method_change": reason,
                "joined": [], "left": [], "within_2km": [], "changed": changed,
                "reported_after_cap": summ["reported_after_cap"]})
    json.dump(log, open(RERUN_LOG, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    print(f"adopted ~/sdws1/runs/{run}: {len(changed)} pump(s) changed; reported after cap "
          f"{_prev.get('reported_after_cap')} -> {summ['reported_after_cap']}.")
    return 0


def main():
    if "--repin" in sys.argv:
        reason = sys.argv[sys.argv.index("--reason") + 1] if "--reason" in sys.argv else "re-pin"
        return repin(sys.argv[sys.argv.index("--repin") + 1], reason)
    if "--adopt" in sys.argv:
        i = sys.argv.index("--adopt")
        reason = sys.argv[sys.argv.index("--reason") + 1] if "--reason" in sys.argv else "method change"
        return adopt(sys.argv[i + 1], reason)
    write = "--write" in sys.argv
    src = open(PAGE, encoding="utf8").read()
    _pi, _pj, pumps = const(src, "PUMPS")
    wi, wj, wpop = const(src, "WPOP")
    fleet = {p["wp"]: p for p in pumps}
    joined = sorted(set(fleet) - set(wpop))
    left = sorted(set(wpop) - set(fleet))
    if not joined and not left:
        print(f"WorldPop allocation covers the fleet ({len(fleet)} pumps); no rerun needed.")
        return 0
    print(f"the fleet changed since the allocation run: {len(joined)} joined "
          f"({', '.join(joined) or 'none'}), {len(left)} left ({', '.join(left) or 'none'})")
    if not write:
        return 0

    what = f"{len(joined)} joining and {len(left)} leaving pump(s)"
    check_pipeline()
    for path, label in ((PIPELINE, "the SDWS1 pipeline"), (PY, "the SDWS1 Python"),
                        (RASTER, "the R2025A raster"), (BARRIERS, "the barrier network")):
        if not os.path.exists(path):
            stop(f"The WorldPop allocation must be rerun for {what}, but {label} "
                 f"({path}) is unavailable, so nothing was published with a blank allocation.")
    if sha256(RASTER) != RASTER_SHA256:
        stop(f"The WorldPop allocation must be rerun for {what}, but the raster at "
             f"{RASTER} does not match the pinned R2025A checksum, so nothing was "
             "published with a blank allocation.")
    missing = [w for w in joined if fleet[w].get("lat") is None or not fleet[w].get("pump")]
    if missing:
        stop(f"The WorldPop allocation must be rerun, but {', '.join(missing)} has no "
             "coordinate or pump model, so nothing was published with a blank allocation.")

    today = datetime.date.today().isoformat()
    run = f"r2025a_barriers_{today.replace('-', '')}"
    out = os.path.join(SDWS1, "runs", run)
    os.makedirs(out, exist_ok=True)
    # The inputs of the run of record are reused as they were, in their
    # order: the page's coordinates are re-rounded from the register (about
    # 0.1 m), and on 23 September that alone moved 90 capped allocations far
    # from any change. Pumps already in the run keep their run inputs; a
    # joining pump is appended from the register; a leaving one is dropped.
    _summ = json.load(open(SUMMARY, encoding="utf8"))
    prev = _summ.get("points_file") or ""
    if not os.path.isabs(prev):
        # a relative input is the run's OWN copy, in its run folder. Resolving
        # it against the pipeline root (until 29 Sep 2026) read an older input
        # that lacked the pump that joined on 23 September, so the rerun moved
        # its neighbours and the drift guard rightly refused to publish.
        _run_dir = os.path.join(SDWS1, "runs", str(_summ.get("_run") or "").split(",")[0].strip())
        prev = next((c for c in (os.path.join(_run_dir, prev), os.path.join(SDWS1, prev))
                     if os.path.isfile(c)), os.path.join(SDWS1, prev))
    if not os.path.isfile(prev):
        stop(f"The WorldPop allocation must be rerun for {what}, but the input of the "
             f"run of record ({prev}) is unavailable, so nothing was published with a "
             "blank allocation.")
    all_rows = list(csv.DictReader(open(prev, encoding="utf8")))
    prev_loc = {r["code"]: (float(r["lat"]), float(r["lon"])) for r in all_rows}
    rows = [r for r in all_rows if r["code"] not in left]
    pts = os.path.join(out, "water_points.csv")
    with open(pts, "w", newline="", encoding="utf8") as fh:
        w = csv.writer(fh)
        w.writerow(["code", "lat", "lon", "pump"])
        for r in rows:
            w.writerow([r["code"], r["lat"], r["lon"], r["pump"]])
        for code in joined:
            p = fleet[code]
            w.writerow([code, p["lat"], p["lon"], p["pump"]])
    r = subprocess.run([PY, PIPELINE, "--points", pts, "--raster", RASTER,
                        "--osm", BARRIERS, "--out", out, "--allocation", "equal"],
                       cwd=SDWS1, capture_output=True, text=True)
    io.open(os.path.join(out, "run.log"), "w", encoding="utf8").write(r.stdout + r.stderr)
    if r.returncode != 0:
        tail = (r.stderr or r.stdout).strip().splitlines()[-1:] or ["no output"]
        stop(f"The WorldPop allocation rerun for {what} failed ({tail[0][:120]}), "
             "so nothing was published with a blank allocation.")

    new = {}
    for row in csv.DictReader(open(os.path.join(out, "sdws1_population_equal.csv"),
                                   encoding="utf8")):
        new[row["code"]] = [int(round(float(row["allocated"]))), int(float(row["revised"])),
                            int(float(row["cap"]))]
    moved_pumps = joined + left
    loc = {c: (p["lat"], p["lon"]) for c, p in fleet.items()}
    for c in left:                                   # a leaving pump's place
        old = next((p for p in pumps if p["wp"] == c), None)
        if old:
            loc[c] = (old["lat"], old["lon"])
        elif c in prev_loc:                          # already gone from PUMPS:
            loc[c] = prev_loc[c]                     # its place in the run input
    near = {c for c in fleet for m in moved_pumps
            if c != m and m in loc and metres(loc[c], loc[m]) < OVERLAP_M}
    allowed = set(joined) | near
    drift = [c for c in fleet if c not in allowed and new.get(c) != wpop.get(c)]
    if drift:
        stop(f"The WorldPop rerun moved {len(drift)} pump(s) that do not overlap the "
             f"change (first: {drift[0]} {wpop.get(drift[0])} -> {new.get(drift[0])}), "
             "so it is not reproducing the run of record and nothing was published.")

    changed = {c: {"was": wpop.get(c), "now": new[c]} for c in sorted(allowed)
               if c in new and new[c] != wpop.get(c)}
    for c in allowed:
        if c in new:
            wpop[c] = new[c]
    for c in left:
        wpop.pop(c, None)
    src = src[:wi] + json.dumps(wpop, separators=(",", ":")) + src[wj:]

    summ = json.load(open(os.path.join(out, "sdws1_summary_equal.json"), encoding="utf8"))
    mi, mj, meta = const(src, "WPOPMETA")
    for pf, rf in FROM_RUN.items():
        meta[pf] = summ[rf]
    meta["run"] = today
    src = src[:mi] + json.dumps(meta, ensure_ascii=False) + src[mj:]
    open(PAGE, "w", encoding="utf8").write(src)

    doc = dict(summ)
    doc["_copied"] = today
    doc["_run"] = f"{run}, allocation=equal"
    doc["_note"] = ("The WorldPop allocation run's own summary, copied verbatim from "
                    f"~/sdws1/runs/{run}/sdws1_summary_equal.json by tools/rerun_wpop.py, "
                    "which reran the allocation because the portfolio changed. "
                    "tools/check_wpopmeta.py asserts the page against this file every build.")
    json.dump(doc, open(SUMMARY, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    log = json.load(open(RERUN_LOG, encoding="utf8")) if os.path.isfile(RERUN_LOG) else []
    log.append({"on": today, "run": f"~/sdws1/runs/{run}", "raster_sha256": RASTER_SHA256,
                "joined": joined, "left": left,
                "within_2km": sorted(near), "changed": changed,
                "reported_after_cap": summ["reported_after_cap"]})
    json.dump(log, open(RERUN_LOG, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    print(f"reran the allocation into ~/sdws1/runs/{run}: {len(changed)} pump(s) changed "
          f"({len(near)} within 2 km of a change); every other pump reproduced exactly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
