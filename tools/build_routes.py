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
  * inside a commune, nearest neighbour by road time;
  * remote clusters as field trips (Adriaan Mol, 16 Oct 2026; until then every
    day returned to the base, and Fort-Dauphin's last four days carried 2 or 3
    pumps each at 177 to 231 km): a commune whose most central pump is more
    than PARAMS.route_overnight_oneway_h from the base, one way, is remote;
    remote communes within PARAMS.route_cluster_merge_km of each other are one
    cluster. Each is planned as day-returns and as a field trip - drive out
    working the pumps on the way and on arrival, overnight at the cluster's
    most central pump village, work from there, work the last pumps on the
    drive back - and the plan with fewer team-days, then road km, is kept
    (see Planner). Every other day starts and ends at the base;
  * a day is road time (OSRM driving) plus PARAMS.route_site_minutes on site
    per pump, within PARAMS.route_day_hours including the drive back and at
    most PARAMS.route_max_pumps pumps. A day always takes at least one pump,
    so a pump further than that makes a day of its own that runs over
    (marked "over");
  * OSRM driving time is multiplied by PARAMS.route_road_factor_<site>, so a
    site where MadAvance's real travel times differ can be corrected; the
    build prints OSRM's one-way time to every cluster more than FAR_LOG_KM
    from its base, straight line or by road, for that comparison;
  * the stretch between a pump and the road (OSRM's snap distance) is costed
    at PARAMS.route_offroad_kmh; between two pumps, a straight walk at that
    speed is taken instead of the road when it is quicker (neighbouring pumps
    far from any mapped road - some in Mahalevona snap 11 km away).

The values are read from PARAMS on the page, where each is declared with
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
              "route_offroad_kmh", "route_overnight_oneway_h", "route_cluster_merge_km")
ITIN_COLS = ["site", "day", "stop", "pump_id", "commune", "fokontany", "pump_type",
             "days_since_last_visit", "last_status", "people", "lat", "lon",
             "day_road_km", "day_hours", "day_start", "day_end", "trip", "trip_day",
             "trip_days", "trip_road_km"]


# ---- the page's own data ------------------------------------------------------
def const(src, name):
    m = re.search(r"^const %s=" % name, src, re.M)
    if not m:
        sys.exit(f"build_routes: no `const {name}=` line")
    val, end = json.JSONDecoder().raw_decode(src, m.end())
    return m.end(), end, val


def params(src):
    out = {}
    for k in PARAM_KEYS + tuple(factor_key(s_) for s_ in SITE_ORDER):
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

    def leg(self, a, b, kmh_off, factor=1.0):
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
            road = du / 3600.0 * factor + off_m / 1000.0 / kmh_off
            return (direct, 0.0, False) if direct < road else (road, di / 1000.0, False)
        km = hav_km(a, b) * FALLBACK_DETOUR
        return km / FALLBACK_KMH, km, True


# ---- the plan -----------------------------------------------------------------------
def factor_key(site):
    return "route_road_factor_" + re.sub(r"[^a-z]+", "_", site.lower()).strip("_")


def by_commune(pts):
    out = {}
    for p in pts:
        out.setdefault(p.get("commune") or "—", []).append(p)
    return out


def medoid(pts):
    """The most central pump: least total straight-line distance to the others."""
    return min(pts, key=lambda p: (sum(hav_km((p["lat"], p["lon"]), (q["lat"], q["lon"]))
                                       for q in pts), p["wp"]))


def place(kind, name, ll, **extra):
    return dict({"at": kind, "name": name, "lat": ll[0], "lon": ll[1]}, **extra)


class Planner:
    """One site's plan: clusters, then day-returns and field trips.

    Clusters are communes. A commune whose most central pump is more than
    PARAMS.route_overnight_oneway_h from the base (one way, by the same leg
    cost as every other leg) is far; far communes whose nearest overdue pumps
    lie within PARAMS.route_cluster_merge_km of each other are one cluster.
    Near communes keep the day-return method: every day starts and ends at the
    base. A far cluster is planned both ways - as day-returns, and as a field
    trip (drive out and work the stops on the way and on arrival, overnight at
    the cluster's most central pump village, work from there, work the last
    stops and drive back) - and the plan with fewer team-days, then fewer road
    km, is kept; a tie stays a day-return."""

    def __init__(self, site, pts, P, roads):
        self.site, self.pts, self.roads = site, pts, roads
        self.base = BASES[site]
        self.site_h, self.day_h = P["route_site_minutes"] / 60.0, P["route_day_hours"]
        self.max_n, self.kmh_off = int(P["route_max_pumps"]), P["route_offroad_kmh"]
        self.factor = P[factor_key(site)]
        self.far_h, self.merge_km = P["route_overnight_oneway_h"], P["route_cluster_merge_km"]
        self.ll = {p["wp"]: (p["lat"], p["lon"]) for p in pts}
        self.base_place = place("base", f"MadAvance base, {site}", self.base)

    def leg(self, a, b):
        return self.roads.leg(a, b, self.kmh_off, self.factor)

    # -- choosing a day's stops -------------------------------------------------------
    def first_commune(self, left):
        def near(c):
            return min(hav_km(self.base, self.ll[p["wp"]]) for p in left[c])
        live = [c for c in left if left[c]]
        return sorted(live, key=lambda c: (-sum(never_visited(p) for p in left[c]),
                                           near(c), c))[0]

    def select(self, start, end, left, commune):
        """Stops for one day from start to end, commune by commune, nearest
        neighbour by leg time; removes them from left. A day always takes at
        least one pump. Returns (stops, commune the team is in)."""
        pos, t, stops = start, 0.0, []
        while True:
            if not left.get(commune):
                rem = [p for v in left.values() for p in v]
                if not rem:
                    break
                nxt = min(rem, key=lambda p: (hav_km(pos, self.ll[p["wp"]]), p["wp"]))
                commune = nxt.get("commune") or "—"
                self.roads.ensure([pos], [self.ll[p["wp"]] for p in left[commune]])
            cand = min(left[commune], key=lambda p: (self.leg(pos, self.ll[p["wp"]])[0], p["wp"]))
            h = self.leg(pos, self.ll[cand["wp"]])[0]
            back = self.leg(self.ll[cand["wp"]], end)[0]
            if stops and (len(stops) >= self.max_n or t + h + self.site_h + back > self.day_h + 1e-9):
                break
            t += h + self.site_h
            pos = self.ll[cand["wp"]]
            left[commune].remove(cand)
            stops.append(cand)
            if len(stops) >= self.max_n:
                break
        return stops, commune

    def cost(self, start, end, stops):
        """(hours, road km, fallback legs, km of the legs from and to the base)."""
        pts = [(start["lat"], start["lon"])] + [self.ll[p["wp"]] for p in stops] \
            + [(end["lat"], end["lon"])]
        t, km, fb, base_km = self.site_h * len(stops), 0.0, 0, 0.0
        for i in range(len(pts) - 1):
            h, k, f = self.leg(pts[i], pts[i + 1])
            t, km, fb = t + h, km + k, fb + f
            if (i == 0 and start["at"] == "base") or (i == len(pts) - 2 and end["at"] == "base"):
                base_km += k
        return t, km, fb, base_km

    def day(self, start, end, stops, clusters):
        t, km, fb, base_km = self.cost(start, end, stops)
        comms = []
        for p in stops:
            c = p.get("commune") or "—"
            if c not in comms:
                comms.append(c)
        d = {"communes": comms, "km": round(km), "hours": round(t, 1),
             "start": start, "end": end, "clusters": clusters,
             "base_km": round(base_km), "stops": stops, "_fb": fb}
        if t > self.day_h + 1e-9:
            d["over"] = True
        return d

    @staticmethod
    def copy(left):
        return {c: list(v) for c, v in left.items()}

    # -- the two ways to plan a set of pumps -----------------------------------------
    def day_returns(self, pts, cid_of):
        left = by_commune(pts)
        commune, days = self.first_commune(left), []
        while any(left.values()):
            stops, commune = self.select(self.base, self.base, left, commune)
            days.append(self.day(self.base_place, self.base_place, stops,
                                 sorted({cid_of[p["wp"]] for p in stops})))
        return days

    def fits_home(self, at, left, commune):
        """Would one day from `at` back to the base take every pump left?"""
        trial = self.copy(left)
        self.select(at, self.base, trial, commune)
        return not any(trial.values())

    def field_trip(self, pts, stay, cid):
        """The trip's days, or None when one day-return takes the whole cluster."""
        left = by_commune(pts)
        commune = self.first_commune(left)
        if self.fits_home(self.base, left, commune):
            return None
        S = (stay["lat"], stay["lon"])
        days, start = [], self.base_place
        while True:
            at = (start["lat"], start["lon"])
            if start["at"] == "stay" and self.fits_home(at, left, commune):
                stops, commune = self.select(at, self.base, left, commune)
                days.append(self.day(start, self.base_place, stops, [cid]))
                return days
            stops, commune = self.select(at, S, left, commune)
            # never end a working day at the stay point with nothing left: the
            # last pumps go back to the day that drives home
            while not any(left.values()) and len(stops) > 1:
                p = stops.pop()
                left.setdefault(p.get("commune") or "—", []).append(p)
                if self.fits_home(S, left, commune):
                    break
            if not any(left.values()):
                # one pump, and even it cannot be followed by the drive home:
                # the drive back is its own (short) day
                days.append(self.day(start, stay, stops, [cid]))
                days.append(self.day(stay, self.base_place, [], [cid]))
                return days
            days.append(self.day(start, stay, stops, [cid]))
            start = stay

    # -- the site -------------------------------------------------------------------
    def clusters(self):
        comm = by_commune(self.pts)
        allp = [self.ll[p["wp"]] for p in self.pts]
        self.roads.ensure([self.base], allp)
        self.roads.ensure(allp, [self.base])
        for v in comm.values():
            self.roads.ensure([self.ll[p["wp"]] for p in v], [self.ll[p["wp"]] for p in v])

        def oneway(v):
            m = medoid(v)
            return m, self.leg(self.base, self.ll[m["wp"]])
        far = sorted(c for c, v in comm.items() if oneway(v)[1][0] > self.far_h)
        # far communes within merge distance of each other: one cluster (single linkage)
        groups = [[c] for c in far]
        merged = True
        while merged:
            merged = False
            for i in range(len(groups)):
                for k in range(i + 1, len(groups)):
                    gap = min(hav_km(self.ll[p["wp"]], self.ll[q["wp"]])
                              for a in groups[i] for p in comm[a]
                              for b in groups[k] for q in comm[b])
                    if gap <= self.merge_km:
                        groups[i] = sorted(groups[i] + groups[k])
                        del groups[k]
                        merged = True
                        break
                if merged:
                    break
        groups += [[c] for c in sorted(comm) if c not in far]
        out = []
        for g in groups:
            v = [p for c in g for p in comm[c]]
            if len(g) > 1:
                cl = [self.ll[p["wp"]] for p in v]
                self.roads.ensure(cl, cl)
            m, (h, k, _f) = oneway(v)
            kk = key(self.base) + ">" + key(self.ll[m["wp"]])
            raw = self.roads.pairs.get(kk)
            out.append({
                "id": " + ".join(g), "communes": g, "far": g[0] in far,
                "n": len(v), "never": sum(never_visited(p) for p in v),
                "pumps": sorted(p["wp"] for p in v),
                "stay": place("stay", f"{m.get('fkt') or m['wp']}, {m.get('commune') or '—'}",
                              self.ll[m["wp"]], village=m.get("fkt") or "",
                              commune=m.get("commune") or "—", wp=m["wp"]),
                "oneway_h": round(h, 2), "oneway_road_km": round(k, 1),
                "osrm_drive_h": round(raw[0] / 3600.0, 2) if raw else None,
                "osrm_road_km": round(raw[1] / 1000.0, 1) if raw else None,
                "line_km": round(hav_km(self.base, self.ll[m["wp"]]), 1),
                "_pts": v})
        return out

    def plan(self):
        cls = self.clusters()
        cid_of = {p["wp"]: c["id"] for c in cls for p in c["_pts"]}
        near = [p for c in cls if not c["far"] for p in c["_pts"]]
        blocks = []
        if near:
            blocks.append((None, self.day_returns(near, cid_of)))
        for c in cls:
            if c["far"]:
                c["plan"] = "day-return"
        for c in sorted((c for c in cls if c["far"]), key=lambda c: (-c["never"], c["oneway_h"], c["id"])):
            dr = self.day_returns(c["_pts"], cid_of)
            ft = self.field_trip(c["_pts"], c["stay"], c["id"])
            tally = lambda ds: [len(ds), sum(d["km"] for d in ds)]          # noqa: E731
            c["compared"] = {"day_return": tally(dr), "field_trip": tally(ft) if ft else None}
            if ft and tally(ft) < tally(dr):
                c["plan"] = "field trip"
                blocks.append((c, ft))
            else:
                blocks.append((None, dr))
        for c in cls:
            if not c["far"]:
                c["plan"] = "day-return"
        days, trips, fb = [], [], 0
        for c, ds in blocks:
            if c is not None:
                n = len(trips) + 1
                tkm = sum(d["km"] for d in ds)
                trips.append({"trip": n, "cluster": c["id"], "stay": c["stay"],
                              "days": len(ds), "nights": len(ds) - 1, "km": tkm,
                              "first_day": len(days) + 1})
                for i, d in enumerate(ds, 1):
                    d.update({"trip": n, "trip_day": i, "trip_days": len(ds), "trip_km": tkm})
            for d in ds:
                d["day"] = len(days) + 1
                f = d.pop("_fb")
                fb += f
                if f:
                    d["fallback_legs"] = f
                d["stops"] = [stop(p) for p in d["stops"]]
                days.append({k: d[k] for k in ("day", *[x for x in d if x != "day"])})
        for c in cls:
            del c["_pts"]
        return {"base": self.base, "n": len(self.pts),
                "never": sum(never_visited(p) for p in self.pts),
                "days": days, "trips": trips, "clusters": cls}, fb


def plan_site(site, pts, P, roads):
    return Planner(site, pts, P, roads).plan()


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
                       "max_pumps": P["route_max_pumps"], "offroad_kmh": P["route_offroad_kmh"],
                       "overnight_oneway_h": P["route_overnight_oneway_h"],
                       "cluster_merge_km": P["route_cluster_merge_km"],
                       "road_factor": P[factor_key(site)]}
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
                             s["lat"], s["lon"], d["km"], d["hours"],
                             d["start"]["name"], d["end"]["name"], d.get("trip", ""),
                             d.get("trip_day", ""), d.get("trip_days", ""), d.get("trip_km", "")])
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
        "far_clusters": far_lines(routes),
        "fallback": {"rule": f"straight line x {FALLBACK_DETOUR} at {FALLBACK_KMH:g} km/h",
                     "legs_by_site": fb},
        "sites": {s: {"routed": R["n"], "never_visited": R["never"],
                      "team_days": len(R["days"]),
                      "road_km": sum(d["km"] for d in R["days"]),
                      "hours": round(sum(d["hours"] for d in R["days"]), 1),
                      "days_over_length": sum(1 for d in R["days"] if d.get("over")),
                      "field_trips": len(R["trips"]),
                      "overnights": sum(t["nights"] for t in R["trips"]),
                      "trip_team_days": sum(t["days"] for t in R["trips"]),
                      "pumps": sorted(s_["wp"] for d in R["days"] for s_ in d["stops"])}
                  for s, R in routes.items()},
    }
    return {INDEX: new_idx, ROUTES_PAGE: new_rt, ITIN: itinerary_text(routes),
            OUT: json.dumps(summary, ensure_ascii=False, indent=1) + "\n"}, routes, fb, roads


FAR_LOG_KM = 30


def site_tally(s, R):
    return (f"{s} {len(R['days'])} team-days, {sum(d['km'] for d in R['days'])} km, "
            f"{len(R['trips'])} trip(s), {sum(t['nights'] for t in R['trips'])} night(s)")


def far_lines(routes):
    out = []
    for s, R in routes.items():
        for c in R["clusters"]:
            if c["line_km"] <= FAR_LOG_KM and (c["osrm_road_km"] or 0) <= FAR_LOG_KM:
                continue
            drive = (f"OSRM {c['osrm_drive_h']:.2f} h driving, {c['osrm_road_km']:.0f} road km"
                     if c["osrm_drive_h"] is not None else "no OSRM time (fallback)")
            out.append(f"build_routes: one way {s} base -> {c['id']} (stay {c['stay']['name']}, "
                       f"{c['line_km']:.0f} km straight line): {drive}; costed "
                       f"{c['oneway_h']:.2f} h in the plan (OSRM time x road factor "
                       f"{R['params']['road_factor']:g}, plus the off-road stretch, or the straight walk where quicker); planned as {c['plan']}")
    return out


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
                  f"{sum(d['km'] for d in R['days'])} road km, {len(R['trips'])} field trip(s) "
                  f"with {sum(t['nights'] for t in R['trips'])} overnight(s), "
                  f"{sum(1 for d in R['days'] if d.get('over'))} day(s) over length")
        # the OSRM one-way time to every cluster further than FAR_LOG_KM, for
        # comparison with MadAvance's real travel times (PARAMS.route_road_factor_*)
        for line in far_lines(routes):
            print(line)
        print(f"build_routes: drawn {drawn}; "
              f"{sum(R['n'] for R in routes.values())} pumps routed "
              f"({', '.join(s + ' ' + str(R['n']) for s, R in routes.items())}) over "
              f"{', '.join(site_tally(s, R) for s, R in routes.items())}; "
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
