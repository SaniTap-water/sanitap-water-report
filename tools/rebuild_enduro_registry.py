# -*- coding: utf-8 -*-
"""Endur'O's registered water systems and water points, live from mWater (3 Oct 2026).

Reads the two Endur'O entity extracts (tools/pull_extract.py, group
c305b9b85f41417387b553d9a33c795b, named "Enduro" in mWater - confirmed 3 Oct
2026) and the piped water-quality sampling and result forms, and writes
data/enduro_registry.json (ENDUROREG on the page):

  - every registered water system and water point, per scheme, with type and
    whether GPS and a photograph are present;
  - the hand-entered figures of data/enduro_manual.json beside the registered
    counts, and the difference (the hand-entered figures stay the headline
    until the two are reconciled);
  - the SMARTAP check on the Amboasary gara smart taps (names, type, parent
    system, deviceID in the description);
  - Cathy's Moramanga sampling points, matched to the registered taps: a
    sample whose tap code (1.1b) or deviceID names a registered tap goes to
    it; otherwise samples are grouped into sampling points (within
    CLUSTER_M of one another) and each point goes to the nearest registered
    tap within MATCH_M. A tap appears once however many points match it.

Results on the piped result form name only their water system until the
tap-level protocol (question 1.2b, live 22 Sep 2026) is used, so results are
summarised per system and shown under each tap as the system's results, never
as the tap's own.

Read-only: reads files in ~/mwater-exports, writes data/enduro_registry.json.

    python3 tools/rebuild_enduro_registry.py --write
"""
import csv, datetime, io, json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exclude_retired import RETIRED_NAME_PREFIX  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS = os.path.expanduser("~/mwater-exports")
OUT = os.path.join(REPO, "data", "enduro_registry.json")
GROUP = "group:c305b9b85f41417387b553d9a33c795b"
GROUP_NAME = "Enduro"            # the group's name in mWater, read 3 Oct 2026
MATCH_M = 25                     # a sampling point matches a tap within this
CLUSTER_M = 15                   # samples this close are one sampling point
AMBOASARY = "1108783583"         # Amboasary gara, the system of record
SMARTAP = re.compile(r"^\s*SMAR\s*TAP\s*(\d+)\s*$", re.I)
DEVICE = re.compile(r"device\s*id\s*[:=#-]?\s*([A-Za-z0-9][A-Za-z0-9_-]{3,})", re.I)

# piped sampling form ef8cf735 and result form 0ac68d82 (tools/rebuild_piped_wq.py)
S_POINT, S_SYSTEM, S_GPS = "51eca87b", "a7f6f9e1", "b2875c48"
S_TYPE, S_PHOTO, SAMPLED = "bf966f97", "e14d9d8b", "630ccd46"
Q_SYSTEM, Q_TAP, Q_ECOLI = "a3390d2e", "7d0fce72", "892f1d81"
# the sampling form's point-type choices (as in tools/rebuild_piped_wq.py)
TYPE_LABEL = {"4hbaZYA": "public tapstand", "YZhKDk3": "water kiosk",
              "YLudYMc": "household connection", "zevJvCr": "institutional connection",
              "KMB99ey": "other"}


def rows(name):
    p = os.path.join(EXPORTS, name)
    with io.open(p, encoding="utf8", errors="replace") as fh:
        return [r for r in csv.DictReader(fh) if r.get("_managed_by") == GROUP]


def js(s, default=None):
    try:
        return json.loads(s) if s else default
    except ValueError:
        return default


def lonlat(r):
    g = js(r.get("location"), {}) or {}
    c = g.get("coordinates") or []
    return (float(c[0]), float(c[1])) if len(c) >= 2 else None


def photo(r):
    ph = js(r.get("photos"), []) or []
    if not ph:
        return None
    cover = [p for p in ph if p.get("cover")]
    return (cover or ph)[0].get("id")


def metres(a, b):
    """Great-circle distance between two (lon, lat) points."""
    la1, la2 = math.radians(a[1]), math.radians(b[1])
    dla, dlo = la2 - la1, math.radians(b[0] - a[0])
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(h))


def q(r, prefix):
    for k, v in (r.get("data") or {}).items():
        if k.startswith(prefix):
            return (v or {}).get("value")
    return None


def device_of(desc):
    m = DEVICE.search(desc or "")
    return m.group(1) if m else None


def build():
    sysrows, ptrows = rows("piped_systems.csv"), rows("enduro_points.csv")
    systems = {}
    for r in sysrows:
        systems[r["_id"]] = dict(code=r["code"], name=(r.get("name") or "").strip() or None,
                                 type=(r.get("type") or "").strip() or None,
                                 gps=lonlat(r) is not None, photo=photo(r) is not None,
                                 status=(r.get("status") or "").strip() or None)
    by_code = {s["code"]: s for s in systems.values()}
    points, retired = [], []
    for r in ptrows:
        # a retired record is marked only by its name prefix (tools/exclude_retired.py)
        if (r.get("name") or "").strip().upper().startswith(RETIRED_NAME_PREFIX):
            retired.append(r["code"])
            continue
        ll = lonlat(r)
        parent = systems.get((r.get("water_system") or "").strip())
        points.append(dict(code=r["code"], name=(r.get("name") or "").strip() or None,
                           type=(r.get("type") or "").strip() or None,
                           system=parent["code"] if parent else None,
                           gps=ll is not None, lon=round(ll[0], 6) if ll else None,
                           lat=round(ll[1], 6) if ll else None,
                           photo=photo(r), device=device_of(r.get("desc")),
                           desc=(r.get("desc") or "").strip() or None,
                           created=(r.get("_created_on") or "")[:10] or None))
    points.sort(key=lambda p: (p["system"] or "~", p["name"] or "~", p["code"]))
    if len({p["code"] for p in points}) != len(points):
        sys.exit("rebuild_enduro_registry: a water point code repeats in the extract")

    # per scheme: each registered water system, then the points with none set
    schemes = []
    for s in sorted(systems.values(), key=lambda s: (s["name"] or "~", s["code"])):
        mine = [p for p in points if p["system"] == s["code"]]
        schemes.append(dict(code=s["code"], name=s["name"], type=s["type"], gps=s["gps"],
                            photo=s["photo"], status=s["status"], points=len(mine),
                            points_gps=sum(p["gps"] for p in mine),
                            points_photo=sum(bool(p["photo"]) for p in mine),
                            point_types=dict(sorted(_count(p["type"] or "not set" for p in mine).items()))))
    loose = [p for p in points if not p["system"]]
    no_system = dict(points=len(loose), points_gps=sum(p["gps"] for p in loose),
                     points_photo=sum(bool(p["photo"]) for p in loose),
                     point_types=dict(sorted(_count(p["type"] or "not set" for p in loose).items())))

    # the SMARTAP check
    taps = {}
    for p in points:
        m = SMARTAP.match(p["name"] or "")
        if m:
            taps.setdefault(int(m.group(1)), []).append(p)
    smart_rows = []
    for n in sorted(taps):
        for p in taps[n]:
            smart_rows.append(dict(n=n, code=p["code"], name=p["name"], type=p["type"],
                                   kiosk=(p["type"] or "").lower() == "kiosk",
                                   system=p["system"], linked=p["system"] == AMBOASARY,
                                   device=p["device"], gps=p["gps"], photo=bool(p["photo"])))
    nums = sorted(taps)
    expected = list(range(1, (max(nums) if nums else 0) + 1))
    smartap = dict(found=len(smart_rows), numbers=nums,
                   missing=[n for n in expected if n not in taps],
                   repeated=[n for n in nums if len(taps[n]) > 1],
                   kiosk=sum(r["kiosk"] for r in smart_rows),
                   linked=sum(r["linked"] for r in smart_rows),
                   with_device=sum(bool(r["device"]) for r in smart_rows),
                   with_gps=sum(r["gps"] for r in smart_rows),
                   with_photo=sum(r["photo"] for r in smart_rows),
                   code_min=min((r["code"] for r in smart_rows), default=None),
                   code_max=max((r["code"] for r in smart_rows), default=None),
                   system_name=(by_code.get(AMBOASARY) or {}).get("name"),
                   rows=smart_rows)

    # Cathy's sampling points, matched to registered taps
    samples = []
    for s in json.load(open(os.path.join(EXPORTS, "wq_sampling_piped.json"), encoding="utf8")):
        if s.get("status") != "final":
            continue
        g = q(s, S_GPS) or {}
        ll = (g.get("longitude"), g.get("latitude")) if g.get("latitude") is not None else None
        tp = q(s, S_TYPE)
        tlabel = TYPE_LABEL.get(tp) if isinstance(tp, str) else None
        pt = q(s, S_POINT)
        ph = q(s, S_PHOTO) or []
        samples.append(dict(id=s["_id"], ll=ll, system=(q(s, S_SYSTEM) or {}).get("code"),
                            photo_id=(ph[0] or {}).get("id") if isinstance(ph, list) and ph else None,
                            day=(q(s, SAMPLED) or s.get("submittedOn") or "")[:10],
                            tap_code=(pt or {}).get("code") if isinstance(pt, dict) else None,
                            type=tlabel, photo=bool(q(s, S_PHOTO))))
    reg = [p for p in points if p["gps"]]
    by_point = {p["code"]: p for p in points}
    by_device = {p["device"]: p for p in points if p["device"]}
    # 1. a recorded tap code or deviceID names the tap
    direct, rest = {}, []
    for s in samples:
        tap = by_point.get(s["tap_code"] or "") or by_device.get(s["tap_code"] or "")
        if tap:
            direct.setdefault(tap["code"], []).append(s)
        else:
            rest.append(s)
    # 2. the remaining samples with GPS, grouped into sampling points
    clusters = []
    for s in sorted((s for s in rest if s["ll"]), key=lambda s: (s["day"], s["id"])):
        home = next((c for c in clusters if any(metres(s["ll"], o["ll"]) <= CLUSTER_M for o in c)), None)
        if home is None:
            clusters.append([s])
        else:
            home.append(s)
    spoints = []
    for i, c in enumerate(sorted(clusters, key=lambda c: (-len(c), c[0]["day"])), 1):
        cen = (sum(s["ll"][0] for s in c) / len(c), sum(s["ll"][1] for s in c) / len(c))
        near = min(((metres(cen, (p["lon"], p["lat"])), p) for p in reg), default=(None, None),
                   key=lambda x: x[0])
        d, p = near
        days = sorted(s["day"] for s in c if s["day"])
        types = sorted({s["type"] for s in c if s["type"]})
        spoints.append(dict(id=f"S{i:02d}", samples=len(c), first=days[0] if days else None,
                            last=days[-1] if days else None, types=types,
                            systems=sorted({s["system"] for s in c if s["system"]}),
                            photo=any(s["photo"] for s in c),
                            photo_id=next((s["photo_id"] for s in sorted(c, key=lambda s: s["day"], reverse=True)
                                           if s["photo_id"]), None),
                            lon=round(cen[0], 6), lat=round(cen[1], 6),
                            nearest_tap=p["code"] if p else None,
                            nearest_name=p["name"] if p else None,
                            nearest_m=round(d, 1) if d is not None else None,
                            tap=p["code"] if p is not None and d <= MATCH_M else None,
                            method="position" if p is not None and d <= MATCH_M else None))
    no_gps = [s for s in rest if not s["ll"]]

    # what each registered tap carries: its samples, by code or by position
    tapinfo = {}
    for code, ss in direct.items():
        t = tapinfo.setdefault(code, dict(samples=0, days=[], points=[], methods=set()))
        t["samples"] += len(ss)
        t["days"] += [s["day"] for s in ss if s["day"]]
        t["methods"].add("tap code or deviceID")
    for sp in spoints:
        if sp["tap"]:
            t = tapinfo.setdefault(sp["tap"], dict(samples=0, days=[], points=[], methods=set()))
            t["samples"] += sp["samples"]
            t["days"] += [d for d in (sp["first"], sp["last"]) if d]
            t["points"].append(sp["id"])
            t["methods"].add("position")

    # results per system: the tap-level code (1.2b) is not used yet
    res = {}
    for r in json.load(open(os.path.join(EXPORTS, "wq_results_piped.json"), encoding="utf8")):
        if r.get("status") != "final":
            continue
        code = (q(r, Q_SYSTEM) or {}).get("code")
        if code not in by_code:
            continue
        e = (q(r, Q_ECOLI) or {}).get("quantity")
        x = res.setdefault(code, dict(name=by_code[code]["name"], tests=0, ecoli_present=0,
                                      ecoli_ge10=0, first=None, last=None, tap_coded=0))
        x["tests"] += 1
        x["ecoli_present"] += int(e is not None and e > 0)
        x["ecoli_ge10"] += int(e is not None and e >= 10)
        x["tap_coded"] += int(bool((q(r, Q_TAP) or {}).get("code") if isinstance(q(r, Q_TAP), dict) else q(r, Q_TAP)))
        d = (q(r, SAMPLED) or r.get("submittedOn") or "")[:10]
        x["first"] = min(filter(None, [x["first"], d])) if d else x["first"]
        x["last"] = max(filter(None, [x["last"], d])) if d else x["last"]

    tap_rows = []
    for code, t in sorted(tapinfo.items()):
        p = by_point[code]
        days = sorted(t["days"])
        tap_rows.append(dict(code=code, name=p["name"], system=p["system"], samples=t["samples"],
                             first=days[0] if days else None, last=days[-1] if days else None,
                             points=t["points"], method=" and ".join(sorted(t["methods"])),
                             system_results=(res.get(p["system"]) or {}).get("tests", 0)))
    matched_taps = [t["code"] for t in tap_rows]
    # no tap may appear twice: several sampling points can land on one tap
    merged = {c: [sp["id"] for sp in spoints if sp["tap"] == c] for c in matched_taps}
    merged = {c: v for c, v in merged.items() if len(v) > 1}

    man = json.load(open(os.path.join(REPO, "data", "enduro_manual.json"), encoding="utf8"))
    m_sys = man["figures"]["systems"]["v"]
    m_pts = man["register"]["points"]
    m_regsys = man["register"]["systems"]
    n_sys, n_pts = len(systems), len(points)
    no_photo = [p["code"] for p in points if not p["photo"]]
    manifest = json.load(open(os.path.join(REPO, "data", "extract_manifest.json"), encoding="utf8"))
    written = ((manifest.get("files") or {}).get("enduro_points.csv") or {}).get("written")
    return dict(
        note="Written by tools/rebuild_enduro_registry.py from Endur'O's own mWater group. "
             "Live registered counts; NOT reconciled to the hand-entered figures in "
             "data/enduro_manual.json, which stay the headline until they are.",
        group=dict(id=GROUP.split(":")[1], name=GROUP_NAME), pulled=(written or "")[:10] or None,
        counts=dict(systems=n_sys, systems_gps=sum(s["gps"] for s in systems.values()),
                    systems_photo=sum(s["photo"] for s in systems.values()),
                    points=n_pts, points_gps=sum(p["gps"] for p in points),
                    points_photo=n_pts - len(no_photo), points_no_photo=len(no_photo),
                    points_with_system=n_pts - len(loose), points_no_system=len(loose),
                    retired_excluded=len(retired),
                    point_types=dict(sorted(_count(p["type"] or "not set" for p in points).items()))),
        compare=dict(systems_manual=m_sys, systems_registered=n_sys, systems_diff=n_sys - m_sys,
                     points_manual=m_pts, points_registered=n_pts, points_diff=n_pts - m_pts,
                     regsys_manual=m_regsys, regsys_diff=n_sys - m_regsys,
                     manual_as_at=man["register"]["as_at"], headline_as_at=man["figures"]["systems"]["as_at"]),
        schemes=schemes, no_system=no_system, smartap=smartap,
        taps=[dict(code=p["code"], name=p["name"], type=p["type"], system=p["system"],
                   lon=p["lon"], lat=p["lat"], photo=p["photo"], device=p["device"], desc=p["desc"])
              for p in points if p["gps"]],
        sampling=dict(samples=len(samples), with_gps=sum(bool(s["ll"]) for s in samples),
                      no_gps=len(no_gps), by_code=sum(len(v) for v in direct.values()),
                      points=spoints, matched=sum(bool(sp["tap"]) for sp in spoints),
                      unmatched=[sp["id"] for sp in spoints if not sp["tap"]],
                      match_m=MATCH_M, cluster_m=CLUSTER_M),
        tap_samples=tap_rows, merged=merged,
        results_by_system=res,
        dq=dict(smartap_missing=smartap["missing"], kiosk_pending=smartap["kiosk"],
                no_photo=no_photo, smartap_no_photo=[r["code"] for r in smart_rows if not r["photo"]]))


def _count(it):
    out = {}
    for x in it:
        out[x] = out.get(x, 0) + 1
    return out


def main():
    if "--write" not in sys.argv:
        sys.exit("usage: rebuild_enduro_registry.py --write")
    doc = build()
    json.dump(doc, open(OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    open(OUT, "a").write("\n")
    c, sm, sa = doc["counts"], doc["smartap"], doc["sampling"]
    print(f"enduro registry: {c['systems']} water systems, {c['points']} water points "
          f"({c['points_gps']} with GPS, {c['points_photo']} with a photo, {c['points_no_system']} with no system set)")
    print(f"  SMARTAP: {sm['found']} found {sm['numbers']}; missing {sm['missing']}; kiosk {sm['kiosk']}, "
          f"linked to {AMBOASARY} {sm['linked']}, deviceID {sm['with_device']}, photo {sm['with_photo']}")
    print(f"  sampling: {sa['samples']} final samples, {len(sa['points'])} sampling points, "
          f"{sa['matched']} matched to a tap within {MATCH_M} m, unmatched {sa['unmatched']}, by code {sa['by_code']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
