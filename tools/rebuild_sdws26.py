# -*- coding: utf-8 -*-
"""The SDWS 26 round, computed from the survey rather than stored.

Everything the section renders comes from here: the per-scenario denominators,
the served counts per season, the clusters actually reached against the VPA-DD
B.7.3 minimum, the household-size means, the approval state and the round's
date range.

Nothing is asserted. The served set is matched BY CHOICE ID - the declared
scale is not monotonic, "More than 1 time per day" sits second - and was
confirmed by James Walker on 23 September 2026. The seasonal rule is his
ruling of the same day: the served share is the AVERAGE of the dry-season
(WS1.18) and rainy-season (WS1.39) shares, which the page computes from
served_dry and served_rain. The both-seasons and either-season counts are
still computed, for the derivation panel only.

    python3 tools/rebuild_sdws26.py            # show
    python3 tools/rebuild_sdws26.py --write
"""
import collections, csv, json, os, re, statistics, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
PAGE = os.path.join(REPO, "index.html")
MIN_CLUSTERS = 8          # VPA-DD B.7.3


def register():
    out = {}
    p = os.path.expanduser("~/mwater-exports/wp_madavance.csv")
    with open(p, encoding="utf8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if r.get("code"):
                out[str(r["code"])] = r
    return out


def compute():
    import populations as P
    rows = P._cbn()
    both = P._cbn_answered_both()
    reg = register()

    def wps(r):
        return [str(e["value"]) for e in (r.get("entities") or [])
                if isinstance(e, dict) and e.get("entityType") == "water_point"
                and e.get("value")]

    def hh(r):
        v = P._answer(r, P.Q_HH_SIZE)
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    out = {"form": P.F_CBN,
           "q_dry": P.Q_USE_DRY, "q_rain": P.Q_USE_RAIN,
           "served_choices": sorted(P.SERVED_CHOICES),
           "min_clusters": MIN_CLUSTERS,
           "responses_total": len(rows),
           "excluded_part_entries": len(rows) - len(both),
           "scenarios": {}}

    ds = sorted(str(r.get("submittedOn") or "")[:10] for r in rows
                if str(r.get("submittedOn") or "")[:2] == "20")
    out["round_from"], out["round_to"] = (ds[0], ds[-1]) if ds else (None, None)
    out["approved"] = sum(1 for r in rows if (r.get("approvals") or []))
    out["statuses"] = dict(collections.Counter(r.get("status") or "none" for r in rows))

    for scen in ("Fort-Dauphin", "Maroantsetra"):
        srows = [r for r in rows if P._cbn_scenario(r) == scen]
        sboth = [r for r in both if P._cbn_scenario(r) == scen]
        sd = [r for r in sboth if P._answer(r, P.Q_USE_DRY) in P.SERVED_CHOICES]
        sr = [r for r in sboth if P._answer(r, P.Q_USE_RAIN) in P.SERVED_CHOICES]
        sb = [r for r in sboth
              if P._answer(r, P.Q_USE_DRY) in P.SERVED_CHOICES
              and P._answer(r, P.Q_USE_RAIN) in P.SERVED_CHOICES]
        se = [r for r in sboth
              if P._answer(r, P.Q_USE_DRY) in P.SERVED_CHOICES
              or P._answer(r, P.Q_USE_RAIN) in P.SERVED_CHOICES]
        pts = {w for r in srows for w in wps(r)}
        com = {(reg.get(w) or {}).get("admin_div3") for w in pts}
        com.discard(None)
        sizes = [hh(r) for r in srows]
        sizes = [x for x in sizes if x is not None]
        out["scenarios"][scen] = {
            "responses": len(srows),
            "answered_both": len(sboth),
            "served_dry": len(sd),
            "served_rain": len(sr),
            "served_both_seasons": len(sb),
            "served_either_season": len(se),
            "water_points": len(pts),
            "clusters": len(com),
            "clusters_short_by": max(0, MIN_CLUSTERS - len(com)),
            "communes": sorted(com),
            "hh_size_n": len(sizes),
            "hh_size_mean": round(statistics.mean(sizes), 2) if sizes else None,
        }
    tot_both = sum(v["answered_both"] for v in out["scenarios"].values())
    out["answered_both"] = tot_both
    out["served_dry"] = sum(v["served_dry"] for v in out["scenarios"].values())
    out["served_rain"] = sum(v["served_rain"] for v in out["scenarios"].values())
    out["served_both_seasons"] = sum(v["served_both_seasons"] for v in out["scenarios"].values())
    out["served_either_season"] = sum(v["served_either_season"] for v in out["scenarios"].values())
    out["rule_difference"] = out["served_either_season"] - out["served_both_seasons"]
    return out


def main():
    write = "--write" in sys.argv
    new = compute()
    src = open(PAGE, encoding="utf8").read()
    m = re.search(r"^const SDWS26\s*=\s*", src, re.M)
    cur = None
    if m:
        j = src.index("};", m.end())
        cur = json.loads(src[m.end():j + 1])

    print(json.dumps(new, indent=1, ensure_ascii=False))
    if cur == new:
        print("\nSDWS26 on the page already matches")
    if not write:
        print("\n--dry run: nothing written")
        return 0
    blob = "const SDWS26=" + json.dumps(new, separators=(", ", ": ")) + ";"
    if m:
        src = src[:m.start()] + blob + src[j + 2:]
    else:
        anchor = "const PARAMS={"
        src = src.replace(anchor, blob + "\n" + anchor, 1)
    open(PAGE, "w", encoding="utf8").write(src)
    print("\nindex.html: SDWS26 written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
