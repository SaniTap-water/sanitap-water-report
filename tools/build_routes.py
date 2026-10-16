# -*- coding: utf-8 -*-
"""Draw the catch-up route plans from this build's overdue list.

Until 16 October 2026 the route plans (ROUTES in index.html and routes.html,
PUMPS and XTRA in routes.html, itinerary.csv) were drawn once, on 10 September
2026, by a planner that was never in this repository, and every build carried
them forward unchanged. By 16 October the plan held 429 pumps while the page
counted 466 overdue, and pumps visited since 10 September were still routed.
This draws them again on every build, from the same overdue set the page
counts, with the method the old plan stated:

  * input: the pumps in PUMPS (the managed portfolio) whose maintenance clock
    is more than overdue_after_days old (data/build_config.json, the rule
    rebuild_activity.py and the page's agg() apply). A pump never visited is
    in it when its clock, which runs from its works record, is past six
    months; a pump with no works record at all has no clock and is not
    (it is in the maintenance schedule instead). A site is planned only if it
    has overdue pumps, so Marolinta appears only when it has some;
  * per site, from the MadAvance base (BASES below, as the 10 September plan
    had them), commune by commune: first the commune with the most
    never-visited overdue pumps (ties: the one nearest the base), then always
    the commune of the nearest remaining pump, straight line, from where the
    team is;
  * inside a commune, nearest neighbour by road time, every day a round trip
    from the base;
  * a day is road time (OSRM driving) plus PARAMS.route_site_minutes on site
    per pump, within PARAMS.route_day_hours including the drive back and at
    most PARAMS.route_max_pumps pumps. A day always takes at least one pump,
    so a pump further than a day's round trip makes a day of its own that runs
    over (marked "over": an overnight stop is needed);
  * the stretch between a pump and the road (OSRM's snap distance) is costed
    at PARAMS.route_offroad_kmh; between two pumps, a straight walk at that
    speed is taken instead of the road when it is quicker (neighbouring pumps
    far from any mapped road - some in Mahalevona snap 11 km away).

The four values are read from PARAMS on the page, where each is declared with
its source, so they have one home.

Road times come from router.project-osrm.org (table calls, at most one
request per second), cached in data/osrm_cache.json keyed by coordinates
rounded to five decimals. A leg the server cannot give - no network, an error,
no route - is costed as straight-line distance x 1.4 at 30 km/h, never cached,
and counted: the count is the last line this prints, which weekly_build.py
writes into logs/publisher.log.

    python3 tools/build_routes.py --write   # draw, and write every output
    python3 tools/build_routes.py --check   # exit 1 if an output differs from
                                            # what the cache and PUMPS give
                                            # (no network; keeps the date drawn)
"""
import csv, datetime, io, json, math, os, re, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_config as _bc

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(REPO, "index.html")
ROUTES_PAGE = os.path.join(REPO, "routes.html")
ITIN = os.path.join(REPO, "itinerary.csv")
CACHE = os.path.join(REPO, "data", "osrm_cache.json")
OUT = os.path.join(REPO, "data", "routes.json")

OSRM = "https://router.project-osrm.org"
UA = "sanitap-water-report tools/build_routes.py"
MIN_GAP_S = 1.05          # at most one request per second to the demo server
MAX_COORDS = 100          # the demo server's table size limit
FALLBACK_DETOUR, FALLBACK_KMH = 1.4, 30.0

# The MadAvance bases, as the 10 September plan had them in ROUTES.
BASES = {"Maroantsetra": [-15.4333, 49.7417],
         "Fort-Dauphin": [-25.0325, 46.9833],
         "Marolinta": [-25.12, 44.62]}
SITE_ORDER = ("Maroantsetra", "Fort-Dauphin", "Marolinta")
PARAM_KEYS = ("route_site_minutes", "route_day_hours", "route_max_pumps",
              "route_offroad_kmh")
ITIN_COLS = ["site", "day", "stop", "pump_id", "commune", "fokontany", "pump_type",
             "days_since_last_visit", "last_status", "people", "lat", "lon",
             "day_road_km", "day_hours"]


# ---- the page's own data ------------------------------------------------------
def const(src, name):
    m = re.search(r"^const %s=" % name, src, re.M)
    if not m:
        sys.exit(f"build_routes: no `const {name}=` line")
    val, end = json.JSONDecoder().raw_decode(src, m.end())
    return m.end(), end, val


def params(src):
    out = {}
    for k in PARAM_KEYS:
        m = re.search(r"\n " + k + r":\{v:([0-9.]+),", src)
        if not m:
            sys.exit(f"build_routes: PARAMS.{k} is missing from index.html; the route "
                     "method is declared there with its source.")
        out[k] = float(m.group(1))
    return out


def never_visited(p):
    return not (p.get("last_pm") or p.get("last_repair"))


def overdue(pumps):
    """site -> pumps over the maintenance threshold, the page's own rule."""
    lim = _bc.load()["maintenance"]["overdue_after_days"]
    out = {}
    for p in pumps:
        if p.get("days") is not None and p["days"] > lim:
            out.setdefault(p["site"], []).append(p)
    return out


# ---- road times -----------------------------------------------------------------
def key(ll):
    return f"{ll[0]:.5f},{ll[1]:.5f}"


def hav_km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 6371.0 * 2 * math.asin(math.sqrt(h))


class Roads:
    """Leg costs, from the cache, then OSRM, then the straight-line fallback."""

    def __init__(self, offline=False):
        self.offline = offline
        try:
            c = json.load(io.open(CACHE, encoding="utf8"))
        except (OSError, ValueError):
            c = {}
        self.pairs = c.get("pairs", {})     # "a>b" -> [seconds, metres]
        self.snap = c.get("snap", {})       # "a"   -> metres from the road
        self.failed = set()                 # pairs costed by the fallback this run
        self.requests = self.request_errors = 0
        self.added = 0
        self._last = 0.0

    def save(self):
        doc = {"note": "Road time and distance between coordinates, from OSRM "
                       "(router.project-osrm.org, driving profile, table service), "
                       "keyed by coordinates rounded to five decimals: pairs "
                       "'from>to' -> [seconds, metres]; snap 'point' -> metres from "
                       "the input coordinate to the road. Written only by "
                       "tools/build_routes.py. Fallback legs are never stored here. "
                       "Delete an entry, or the file, to have it fetched again.",
               "server": OSRM, "profile": "driving",
               "pairs": dict(sorted(self.pairs.items())),
               "snap": dict(sorted(self.snap.items()))}
        tmp = CACHE + ".tmp"
        with io.open(tmp, "w", encoding="utf8") as fh:
            json.dump(doc, fh, indent=0, separators=(",", ":"))
            fh.write("\n")
        os.replace(tmp, CACHE)

    def _fetch(self, srcs, dsts):
        """One table request; fills the cache, or marks the pairs failed."""
        coords = srcs + dsts
        url = (f"{OSRM}/table/v1/driving/"
               + ";".join(f"{c[1]:.5f},{c[0]:.5f}" for c in coords)
               + "?annotations=duration,distance"
               + "&sources=" + ";".join(str(i) for i in range(len(srcs)))
               + "&destinations=" + ";".join(str(len(srcs) + j) for j in range(len(dsts))))
        j = None
        for attempt in range(2):
            wait = self._last + MIN_GAP_S - time.time()
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            self.requests += 1
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=60) as r:
                    j = json.loads(r.read().decode("utf8"))
                if j.get("code") == "Ok":
                    break
            except Exception:                                  # noqa: BLE001
                j = None
            self.request_errors += 1
            time.sleep(5)
        if not j or j.get("code") != "Ok":
            for a in srcs:
                for b in dsts:
                    self.failed.add(key(a) + ">" + key(b))
            return
        for i, w in enumerate(j.get("sources") or []):
            self.snap[key(srcs[i])] = round(w.get("distance") or 0.0, 1)
        for i, w in enumerate(j.get("destinations") or []):
            self.snap[key(dsts[i])] = round(w.get("distance") or 0.0, 1)
        durs, dists = j.get("durations") or [], j.get("distances") or []
        for i, a in enumerate(srcs):
            for k2, b in enumerate(dsts):
                du = durs[i][k2] if i < len(durs) and durs[i] else None
                di = dists[i][k2] if i < len(dists) and dists[i] else None
                kk = key(a) + ">" + key(b)
                if du is None or di is None:
                    self.failed.add(kk)
                else:
                    self.pairs[kk] = [round(du, 1), round(di, 1)]
                    self.added += 1

    def ensure(self, srcs, dsts):
        """Make sure every pair srcs x dsts is cached or known to have failed."""
        srcs = list({key(s): s for s in srcs}.values())
        dsts = list({key(d): d for d in dsts}.values())

        def missing(a, b):
            kk = key(a) + ">" + key(b)
            return kk not in self.pairs and kk not in self.failed and key(a) != key(b)
        if self.offline or not any(missing(a, b) for a in srcs for b in dsts):
            return
        # blocks whose coordinates fit one request
        if len(srcs) + len(dsts) <= MAX_COORDS:
            blocks = [(srcs, dsts)]
        else:
            ns = max(1, min(len(srcs), MAX_COORDS // 2 if len(dsts) > MAX_COORDS // 2
                            else MAX_COORDS - len(dsts)))
            nd = MAX_COORDS - ns
            blocks = [(srcs[i:i + ns], dsts[k:k + nd])
                      for i in range(0, len(srcs), ns) for k in range(0, len(dsts), nd)]
        for bs, bd in blocks:
            if any(missing(a, b) for a in bs for b in bd):
                self._fetch(bs, bd)

    def leg(self, a, b, kmh_off):
        """(hours, road km, fell back?) from a to b.

        By road: OSRM's time between the two road points, plus the stretch
        from each end to its road point at the off-road speed. Two neighbouring
        pumps far from any mapped road are walked between directly, straight
        line at the off-road speed, when that is quicker - otherwise both
        would be charged the walk out to the road and back."""
        if key(a) == key(b):
            return 0.0, 0.0, False
        direct = hav_km(a, b) / kmh_off
        kk = key(a) + ">" + key(b)
        if kk in self.pairs:
            du, di = self.pairs[kk]
            off_m = self.snap.get(key(a), 0.0) + self.snap.get(key(b), 0.0)
            road = du / 3600.0 + off_m / 1000.0 / kmh_off
            return (direct, 0.0, False) if direct < road else (road, di / 1000.0, False)
        km = hav_km(a, b) * FALLBACK_DETOUR
        return km / FALLBACK_KMH, km, True


# ---- the plan -----------------------------------------------------------------------
def plan_site(site, pts, P, roads):
    base = BASES[site]
    site_h, day_h = P["route_site_minutes"] / 60.0, P["route_day_hours"]
    max_n, kmh_off = int(P["route_max_pumps"]), P["route_offroad_kmh"]
    ll = {p["wp"]: (p["lat"], p["lon"]) for p in pts}
    by_c = {}
    for p in pts:
        by_c.setdefault(p.get("commune") or "—", []).append(p)
    # every leg the plan can use within a commune, and to and from the base
    allp = [ll[p["wp"]] for p in pts]
    roads.ensure([base], allp)
    roads.ensure(allp, [base])
    for c, v in by_c.items():
        roads.ensure([ll[p["wp"]] for p in v], [ll[p["wp"]] for p in v])

    def first_commune():
        def near(c):
            return min(hav_km(base, ll[p["wp"]]) for p in by_c[c])
        return sorted(by_c, key=lambda c: (-sum(never_visited(p) for p in by_c[c]),
                                           near(c), c))[0]

    left = {c: list(v) for c, v in by_c.items()}
    commune = first_commune()
    days, legs_fallback = [], 0
    while any(left.values()):
        pos, t, km, stops, comms, fb = base, 0.0, 0.0, [], [], 0
        while True:
            if not left.get(commune):
                rem = [p for v in left.values() for p in v]
                if not rem:
                    break
                nxt = min(rem, key=lambda p: (hav_km(pos, ll[p["wp"]]), p["wp"]))
                commune = nxt.get("commune") or "—"
                roads.ensure([pos], [ll[p["wp"]] for p in left[commune]])
            cand = sorted(left[commune],
                          key=lambda p: (roads.leg(pos, ll[p["wp"]], kmh_off)[0], p["wp"]))[0]
            h, k, f = roads.leg(pos, ll[cand["wp"]], kmh_off)
            back = roads.leg(ll[cand["wp"]], base, kmh_off)[0]
            if stops and (len(stops) >= max_n or t + h + site_h + back > day_h + 1e-9):
                break
            t, km, fb = t + h + site_h, km + k, fb + f
            pos = ll[cand["wp"]]
            left[commune].remove(cand)
            stops.append(cand)
            if commune not in comms:
                comms.append(commune)
            if len(stops) >= max_n:
                break
        h, k, f = roads.leg(pos, base, kmh_off)
        t, km, fb = t + h, km + k, fb + f
        legs_fallback += fb
        d = {"day": len(days) + 1, "communes": comms, "km": round(km), "hours": round(t, 1),
             "stops": [stop(p) for p in stops]}
        if t > day_h + 1e-9:
            d["over"] = True
        if fb:
            d["fallback_legs"] = fb
        days.append(d)
    return {"base": base, "n": len(pts), "never": sum(never_visited(p) for p in pts),
            "days": days}, legs_fallback


def stop(p):
    s = {"wp": p["wp"], "commune": p.get("commune") or "—", "fkt": p.get("fkt") or "",
         "lat": p["lat"], "lon": p["lon"], "days": p["days"],
         "status": p.get("status") or "unknown", "people": p.get("wpop"),
         "pump": p.get("pump") or "", "last": p.get("last_visit")}
    if never_visited(p):
        s["never"] = True
    return s


def draw(drawn, offline=False):
    src = io.open(INDEX, encoding="utf8").read()
    pumps = const(src, "PUMPS")[2]
    wpop = const(src, "WPOP")[2]
    for p in pumps:                       # people served, as the page attaches it
        v = wpop.get(p["wp"])
        p["wpop"] = v[1] if v else None
    P = params(src)
    over = overdue(pumps)
    roads = Roads(offline=offline)
    routes, fb = {}, {}
    for site in SITE_ORDER:
        pts = over.get(site) or []
        if not pts:
            continue
        if site not in BASES:
            sys.exit(f"build_routes: {site} has overdue pumps and no base in BASES")
        r, fb[site] = plan_site(site, pts, P, roads)
        r["drawn"] = drawn
        # the values applied, so routes.html and the exports state them without
        # a second copy (their home is PARAMS on index.html)
        r["params"] = {"site_minutes": P["route_site_minutes"], "day_hours": P["route_day_hours"],
                       "max_pumps": P["route_max_pumps"], "offroad_kmh": P["route_offroad_kmh"]}
        r["params"] = {k: int(v) if float(v).is_integer() else v for k, v in r["params"].items()}
        routes[site] = r
    unknown = sorted(set(over) - set(SITE_ORDER))
    if unknown:
        sys.exit(f"build_routes: overdue pumps at a site with no base: {unknown}")
    return src, pumps, P, routes, fb, roads


# ---- the outputs -------------------------------------------------------------------
def j(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def itinerary_rows(routes):
    rows = []
    for site, R in routes.items():
        for d in R["days"]:
            for i, s in enumerate(d["stops"], 1):
                rows.append([site, d["day"], i, s["wp"], s["commune"], s["fkt"], s["pump"],
                             "never" if s.get("never") else s["days"], s["status"],
                             "" if s["people"] is None else s["people"],
                             s["lat"], s["lon"], d["km"], d["hours"]])
    return rows


def itinerary_text(routes):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(ITIN_COLS)
    w.writerows(itinerary_rows(routes))
    return buf.getvalue()


def routes_page_data(pumps, routes, page_src):
    """PUMPS and XTRA for routes.html. XTRA's photograph id is carried forward
    for a pump still in the portfolio: photographs are chosen by a ranked
    selection that is not part of the build (as in tools/render_portfolio.py),
    so a pump that joined is drawn without one rather than with a guess.
    Everything else in it is rewritten from the report's own data."""
    old_x = const(page_src, "XTRA")[2]
    idx = io.open(INDEX, encoding="utf8").read()
    resp = const(idx, "RESP")[2]
    routed = {s["wp"] for R in routes.values() for d in R["days"] for s in d["stops"]}
    P, X = [], {}
    for p in pumps:
        if p.get("lat") is None or p.get("lon") is None:
            continue
        P.append({"wp": p["wp"], "lat": p["lat"], "lon": p["lon"], "site": p["site"],
                  "fkt": p.get("fkt") or "", "commune": p.get("commune") or "",
                  "days": p.get("days"), "status": p.get("status") or "unknown",
                  "last": p.get("last_visit"), "nv": never_visited(p),
                  "o": p["wp"] in routed})
        x = {}
        if p.get("wpop") is not None:          # people served, WorldPop capped
            x["wpop"] = p["wpop"]
        if p.get("pump"):
            x["pump"] = p["pump"]
        if (old_x.get(p["wp"]) or {}).get("ph"):
            x["ph"] = old_x[p["wp"]]["ph"]
        r = resp.get(p["wp"]) or {}
        if r.get("v"):
            x["v"] = r["v"]
        if r.get("q"):
            x["q"] = r["q"]
        if p.get("wq"):
            x["wq"] = p["wq"]
        if p.get("wq_date"):
            x["wq_date"] = p["wq_date"]
        X[p["wp"]] = x
    return P, X


def splice(src, name, value):
    a, b, _ = const(src, name)
    return src[:a] + value + src[b:]


def outputs(drawn, offline):
    src, pumps, P, routes, fb, roads = draw(drawn, offline)
    rsrc = io.open(ROUTES_PAGE, encoding="utf8").read()
    rp, rx = routes_page_data(pumps, routes, rsrc)
    new_idx = splice(src, "ROUTES", j(routes))
    new_rt = splice(splice(splice(rsrc, "ROUTES", j(routes)), "PUMPS", j(rp)), "XTRA", j(rx))
    summary = {
        "note": "Written by tools/build_routes.py at each build: the catch-up route plans "
                "drawn from the build's overdue list. The page's ROUTES, routes.html and "
                "itinerary.csv are its output; tools/check_routes.py gates them.",
        "drawn": drawn,
        "params": P,
        "osrm": {"server": OSRM, "requests": roads.requests,
                 "request_errors": roads.request_errors,
                 "pairs_added_to_cache": roads.added,
                 "pairs_fallback": len(roads.failed)},
        "fallback": {"rule": f"straight line x {FALLBACK_DETOUR} at {FALLBACK_KMH:g} km/h",
                     "legs_by_site": fb},
        "sites": {s: {"routed": R["n"], "never_visited": R["never"],
                      "team_days": len(R["days"]),
                      "road_km": sum(d["km"] for d in R["days"]),
                      "hours": round(sum(d["hours"] for d in R["days"]), 1),
                      "days_over_length": sum(1 for d in R["days"] if d.get("over")),
                      "pumps": sorted(s_["wp"] for d in R["days"] for s_ in d["stops"])}
                  for s, R in routes.items()},
    }
    return {INDEX: new_idx, ROUTES_PAGE: new_rt, ITIN: itinerary_text(routes),
            OUT: json.dumps(summary, ensure_ascii=False, indent=1) + "\n"}, routes, fb, roads


def stored_drawn():
    try:
        return json.load(io.open(OUT, encoding="utf8"))["drawn"]
    except (OSError, ValueError, KeyError):
        return None


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if mode == "--write":
        drawn = datetime.date.today().isoformat()
        files, routes, fb, roads = outputs(drawn, offline=False)
        for path, text in files.items():
            io.open(path, "w", encoding="utf8", newline="").write(text)
        roads.save()
        for s, R in routes.items():
            print(f"  {s}: {R['n']} pumps routed over {len(R['days'])} team-days, "
                  f"{sum(d['km'] for d in R['days'])} road km, "
                  f"{sum(1 for d in R['days'] if d.get('over'))} day(s) over length")
        print(f"build_routes: drawn {drawn}; "
              f"{sum(R['n'] for R in routes.values())} pumps routed "
              f"({', '.join(s + ' ' + str(R['n']) for s, R in routes.items())}); "
              f"OSRM {roads.requests} request(s), {roads.request_errors} error(s), "
              f"{roads.added} pair(s) added to the cache; "
              f"OSRM fallbacks: {sum(fb.values())} leg(s) in the plan "
              f"({', '.join(f'{s} {n}' for s, n in fb.items())}), "
              f"{len(roads.failed)} pair(s) costed by the fallback")
        return 0
    if mode == "--check":
        drawn = stored_drawn()
        if not drawn:
            print("build_routes --check: data/routes.json is missing; run --write")
            return 1
        # the date drawn is the stored one; the json's request counters are
        # the drawing run's, so only its plan is compared
        files, *_ = outputs(drawn, offline=True)
        bad = []
        for path, text in files.items():
            have = io.open(path, encoding="utf8", newline="").read() if os.path.isfile(path) else ""
            if path == OUT:
                a, b = json.loads(text), json.loads(have or "{}")
                for x in (a, b):
                    x.pop("osrm", None)
                if a != b:
                    bad.append(os.path.relpath(path, REPO))
            elif have != text:
                bad.append(os.path.relpath(path, REPO))
        if bad:
            print("build_routes --check: these differ from what PUMPS, PARAMS and the "
                  "OSRM cache give: " + ", ".join(bad) + ". Run tools/build_routes.py --write.")
            return 1
        print("build_routes --check: every route output matches PUMPS, PARAMS and the cache")
        return 0
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main())
