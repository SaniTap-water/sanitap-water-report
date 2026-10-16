# -*- coding: utf-8 -*-
"""Gate: the catch-up route plans are this build's, and they cover the overdue list.

Until 16 October 2026 the route plans were drawn once, on 10 September, and
carried forward by every build: on 16 October the plan held 429 pumps while
the page counted 466 overdue, and pumps visited since were still routed. Every
check passed, because nothing compared the plan with the overdue list.
tools/build_routes.py now draws them at every build (it runs in
tools/weekly_build.py); this gate, run by tools/publish.sh, refuses an edition
whose plans are not that build's or do not cover exactly the overdue pumps.

  routes_fresh          the date every plan was drawn is the edition's issue
                        date (the masthead), in index.html, routes.html and
                        data/routes.json alike
  routes_cover_overdue  per site, the set of routed pumps is the set of overdue
                        pumps (PUMPS, the managed portfolio, by the page's own
                        rule in data/build_config.json); each pump once; no
                        site planned without overdue pumps
  routes_outputs        index.html ROUTES, routes.html (ROUTES, PUMPS, XTRA),
                        itinerary.csv and data/routes.json are exactly what
                        build_routes.py gives from PUMPS, PARAMS and the OSRM
                        cache (build_routes.py --check, no network)
  routes_params         the method values in data/routes.json are PARAMS
  routes_wording        no sentence left from the plan of 10 September (a
                        fixed drawing date, "not yet on a route"), no team size
                        set by the plan, and the field-lead sentence present

    python3 tools/check_routes.py     # exit 1 on any failure
"""
import csv, io, json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_routes as BR
from weekly_build import masthead_of

REPO = BR.REPO
RESULTS = []
TEAM_NOTE = ("A day is one field team&rsquo;s working day; how many technicians go is decided "
             "by the field lead (Adriaan Mol, 16 Oct 2026).")
TEAM_NOTE_JS = ("A day is one field team's working day; how many technicians go is decided by "
                "the field lead (Adriaan Mol, 16 Oct 2026).")
STALE = ("drawn on 10 September 2026", "not yet on a route", "pumps overdue when the route was drawn",
         "no build step redraws it", "route_crew", "technician-day", "technicians per team")


def check(name, ok, detail):
    RESULTS.append((name, bool(ok), detail))


def main():
    idx = io.open(BR.INDEX, encoding="utf8").read()
    rt = io.open(BR.ROUTES_PAGE, encoding="utf8").read()
    R = BR.const(idx, "ROUTES")[2]
    R2 = BR.const(rt, "ROUTES")[2]
    pumps = BR.const(idx, "PUMPS")[2]
    try:
        summary = json.load(io.open(BR.OUT, encoding="utf8"))
    except (OSError, ValueError):
        summary = {}

    # routes_fresh
    issued, _ = masthead_of(BR.INDEX)
    drawn = sorted({r.get("drawn") for r in R.values()} | {r.get("drawn") for r in R2.values()}
                   | {summary.get("drawn")})
    check("routes_fresh",
          issued is not None and drawn == [issued.isoformat()],
          f"issued {issued}, drawn {', '.join(str(d) for d in drawn)}")

    # routes_cover_overdue
    over = BR.overdue(pumps)
    bad = []
    for site in sorted(set(over) | set(R)):
        want = {p["wp"] for p in over.get(site, [])}
        stops = [s["wp"] for d in (R.get(site) or {}).get("days", []) for s in d["stops"]]
        got = set(stops)
        if len(stops) != len(got):
            bad.append(f"{site}: a pump is on more than one stop")
        if got != want:
            bad.append(f"{site}: {len(got)} routed, {len(want)} overdue"
                       f" ({len(want - got)} overdue not routed, {len(got - want)} routed not overdue)")
        if site in R and R[site].get("n") != len(stops):
            bad.append(f"{site}: ROUTES n {R[site].get('n')} against {len(stops)} stops")
    per_site = ", ".join(f"{s} {len(over.get(s, []))}" for s in sorted(over))
    check("routes_cover_overdue", not bad, "; ".join(bad) if bad else f"routed = overdue: {per_site}")

    # routes_outputs
    r = subprocess.run([sys.executable, os.path.join(REPO, "tools", "build_routes.py"), "--check"],
                       capture_output=True, text=True, cwd=REPO)
    out = (r.stdout + r.stderr).strip().splitlines()
    rows = list(csv.reader(io.open(BR.ITIN, encoding="utf8")))
    n_stops = sum(len(d["stops"]) for x in R.values() for d in x["days"])
    check("routes_outputs",
          r.returncode == 0 and R2 == R and rows[:1] == [BR.ITIN_COLS] and len(rows) - 1 == n_stops,
          (out[-1] if out else "no output")
          + f"; routes.html ROUTES {'equals' if R2 == R else 'DIFFERS FROM'} index.html's; "
          f"itinerary.csv {len(rows) - 1} rows for {n_stops} stops")

    # routes_params
    P = BR.params(idx)
    check("routes_params", summary.get("params") == P,
          f"applied {summary.get('params')}, PARAMS {P}")

    # routes_wording
    det = io.open(os.path.join(REPO, "data", "action_details.json"), encoding="utf8").read()
    hits = [f"{name}: '{w}'" for name, txt in (("index.html", idx), ("routes.html", rt),
                                               ("action_details.json", det))
            for w in STALE if w in txt]
    if TEAM_NOTE not in idx:
        hits.append("index.html: the field-lead sentence is missing")
    if TEAM_NOTE_JS not in rt:
        hits.append("routes.html: the field-lead sentence is missing")
    check("routes_wording", not hits, "; ".join(hits) if hits else "no stale route wording; field-lead sentence on both pages")

    w = max(len(n) for n, *_ in RESULTS)
    for name, ok, detail in RESULTS:
        print(f"  {name.ljust(w)} {'PASS  ' if ok else 'FAIL !'} {detail}")
    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n  route gates: {len(RESULTS) - len(failed)} of {len(RESULTS)} passed"
          + (f"; FAILED: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
