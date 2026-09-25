# -*- coding: utf-8 -*-
"""Recompute the summary fields that a population already defines.

Group A of the ungenerated backlog: fields that no generator wrote, but which
a population defined in populations.py reproduces exactly. They were stored
once and could not move; now they are computed every build and the gate
asserts them.

  S.by_site, S.by_pump          managed_fleet grouped by a register attribute
  S.down_list                   down_now - the list IS the population
  S.wq_untested                 managed_fleet less water_quality_tested, by site
  METRICS.points_over_6_months  the same rule as S.over6
  METRICS.points_no_works_record the same figure as S.never
  PUMPS[] / DOWN[] register columns   site, commune, fkt, pump, lat, lon

The register columns matter more than they look. They were copied into the
page once, so a point that moved commune, or gained a coordinate, kept the old
value for ever and every distance and grouping computed from it was quietly
stale.

    python3 tools/rebuild_summary.py            # show what would move
    python3 tools/rebuild_summary.py --write
"""
import json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
PAGE = os.path.join(REPO, "index.html")

REG_COLS = ["site", "commune", "fkt", "pump", "lat", "lon"]

# The page's "site" is SaniTap's operational grouping and is NOT a register
# column: the register calls Fort-Dauphin's district Taolagnaro. The mapping is
# 1:1 and is declared here rather than inferred, so an unknown district fails
# the build instead of silently renaming 127 points.
# from data/build_config.json, which the page's footnotes describe
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_config as _cfg
OVERDUE_DAYS = _cfg.load()["maintenance"]["overdue_after_days"]
DISTRICT_TO_SITE = dict(_cfg.load()["portfolio"]["districts"])


def register(fleet):
    """code -> the register attributes the page carries.

    Only fleet points need a site: the register also holds points we do not
    maintain, and their districts (Amboasary-Atsimo, and 118 records with no
    district at all) have no operational site and must not invent one.
    """
    import csv
    out = {}
    p = os.path.expanduser("~/mwater-exports/wp_madavance.csv")
    with open(p, encoding="utf8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            code = r.get("code")
            if not code:
                continue
            lat = lon = None
            try:
                c = json.loads(r["location"])["coordinates"]
                lat, lon = round(c[1], 6), round(c[0], 6)
            except Exception:
                pass
            d2 = r.get("admin_div2") or None
            if str(code) in fleet and d2 and d2 not in DISTRICT_TO_SITE:
                raise SystemExit(
                    f"rebuild_summary: register district {d2!r} on point "
                    f"{code} has no entry in DISTRICT_TO_SITE. Add it "
                    f"deliberately; do not let the site be guessed.")
            out[str(code)] = {
                "site": DISTRICT_TO_SITE.get(d2),
                "commune": r.get("admin_div3") or None,
                "fkt": r.get("admin_div4") or None,
                "pump": (r.get("name") or None),
                "lat": lat, "lon": lon,
            }
    return out


def load(src, name):
    m = re.search(rf"^const {name}\s*=\s*", src, re.M)
    if not m:
        return None, None, None
    close = "};" if src[m.end()] == "{" else "];"
    j = src.index(close, m.end())
    return json.loads(src[m.end():j + 1]), m.end(), j + 1


def main():
    import populations as P
    write = "--write" in sys.argv
    src = open(PAGE, encoding="utf8").read()
    S, _a, _b = load(src, "S")
    PUMPS, _c, _d = load(src, "PUMPS")
    METRICS, _e, _f = load(src, "METRICS")

    fleet = P.managed_fleet()
    reg = register(fleet)
    wq = P.water_quality_tested()
    down = P.down_now()
    by_wp = {p["wp"]: p for p in PUMPS}

    new_S = {}
    # by_site / by_pump: the fleet grouped by what the register says
    for key, col in (("by_site", "site"), ("by_pump", "pump")):
        g = {}
        for wp in fleet:
            v = (by_wp.get(wp) or {}).get(col)
            if v:
                g[v] = g.get(v, 0) + 1
        new_S[key] = dict(sorted(g.items(), key=lambda kv: -kv[1]))
    # wq_untested: fleet points with no water-quality result, by site
    g = {}
    for wp in sorted(fleet - wq):
        v = (by_wp.get(wp) or {}).get("site")
        if v:
            g[v] = g.get(v, 0) + 1
    new_S["wq_untested"] = dict(sorted(g.items()))
    # down_list: the down population, in the page's existing row shape
    new_S["down_list"] = [by_wp[wp] for wp in sorted(down) if wp in by_wp]

    new_M = {
        "points_over_6_months": sum(
            1 for p in PUMPS if p.get("days") is not None and p["days"] > OVERDUE_DAYS),
        "points_no_works_record": S.get("never"),
    }

    # register columns on PUMPS
    moved = []
    for p in PUMPS:
        r = reg.get(p.get("wp"))
        if not r:
            continue
        for c in REG_COLS:
            if r[c] is not None and p.get(c) != r[c]:
                moved.append((p["wp"], c, p.get(c), r[c]))

    print(f'{"FIELD":34} {"STORED":>22}  COMPUTED')
    for k, v in new_S.items():
        a = json.dumps(S.get(k))[:22]
        b = json.dumps(v)[:22]
        print(f"S.{k:32} {a:>22}  {b}{'' if a == b else '   <-- moves'}")
    for k, v in new_M.items():
        a, b = METRICS.get(k), v
        print(f"METRICS.{k:26} {str(a):>22}  {b}{'' if a == b else '   <-- moves'}")
    print(f"\nregister columns differing from the register: {len(moved)}")
    for wp, c, a, b in moved[:8]:
        print(f"    {wp}  {c}: {a!r} -> {b!r}")
    if len(moved) > 8:
        print(f"    ... and {len(moved) - 8} more")

    if not write:
        print("\n--dry run: nothing written")
        return 0

    for p in PUMPS:
        r = reg.get(p.get("wp"))
        if r:
            for c in REG_COLS:
                if r[c] is not None:
                    p[c] = r[c]
    S.update(new_S)
    METRICS.update(new_M)
    out = src
    for name, val in (("S", S), ("PUMPS", PUMPS), ("METRICS", METRICS)):
        m = re.search(rf"^const {name}\s*=\s*", out, re.M)
        close = "};" if out[m.end()] == "{" else "];"
        j = out.index(close, m.end())
        out = out[:m.end()] + json.dumps(val, separators=(", ", ": ")) + out[j + 1:]
    open(PAGE, "w", encoding="utf8").write(out)
    print(f"\nindex.html: S, PUMPS and METRICS summary fields recomputed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
