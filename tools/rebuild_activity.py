# -*- coding: utf-8 -*-
"""Rebuild the activity fields of the page from the freshly pulled extract.

Scope, deliberately narrow: the fields that go stale when the pull stops are
the ones derived from the three activity forms - when each pump was last
visited, last repaired, how many days that is, and the week counters. Those
are rebuilt here from the canonical CSVs and written back into the inlined
data in index.html.

Everything else on the page - the register, population, water quality, the
carbon file - comes from sources that are refreshed on their own cadence and
is left untouched. This tool reports what it changed and what it did not, so
nothing is quietly restated.

    python3 tools/rebuild_activity.py --dry-run   # what would move
    python3 tools/rebuild_activity.py --write
"""
import csv, datetime, io, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS = os.path.expanduser("~/mwater-exports")
FORMS = {"pm": "pm.csv", "repair": "reparation_apres_panne.csv",
         "call": "appel_signalement_pannes.csv"}


def rows(name):
    p = os.path.join(EXPORTS, name)
    if not os.path.isfile(p):
        sys.exit(f"missing extract {p} - run tools/pull_extract.py --write")
    with io.open(p, encoding="utf8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def by_point(name):
    """code -> sorted list of submission dates."""
    out = {}
    for r in rows(name):
        d = str(r.get("submittedOn") or "")[:10]
        if d[:2] != "20":
            continue
        ents = r.get("entities") or ""
        try:
            ents = json.loads(ents) if ents.startswith("[") else []
        except ValueError:
            ents = []
        for e in ents:
            if e.get("entityType") == "water_point" and e.get("value"):
                out.setdefault(str(e["value"]), []).append(d)
    return {k: sorted(v) for k, v in out.items()}


def counts(name, asof):
    ds = [str(r.get("submittedOn") or "")[:10] for r in rows(name)]
    ds = [d for d in ds if d[:2] == "20"]
    def win(a, b):
        lo = (asof - datetime.timedelta(days=a)).isoformat()
        hi = (asof - datetime.timedelta(days=b)).isoformat()
        return sum(1 for d in ds if hi < d <= lo)
    return [win(0, 7), win(7, 14), win(0, 28)]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--dry-run"
    idx = open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    mp = re.search(r"\bconst PUMPS\s*=\s*", idx)
    pumps = json.loads(idx[mp.end():idx.index("];", mp.end()) + 1])
    ms = re.search(r"\bconst S\s*=\s*", idx)
    S = json.loads(idx[ms.end():idx.index("};", ms.end()) + 1])

    pm, rep = by_point(FORMS["pm"]), by_point(FORMS["repair"])
    all_d = [d for v in list(pm.values()) + list(rep.values()) for d in v]
    all_d += [str(r.get("submittedOn") or "")[:10] for r in rows(FORMS["call"])]
    asof = datetime.date.fromisoformat(max(d for d in all_d if d[:2] == "20"))

    moved, unseen = [], []
    for p in pumps:
        c = p["wp"]
        new_pm = max(pm.get(c, []) or [""]) or None
        new_rp = max(rep.get(c, []) or [""]) or None
        new_lv = max([x for x in (new_pm, new_rp) if x] or [""]) or None
        if not new_lv:
            continue
        old = (p.get("last_pm"), p.get("last_repair"), p.get("last_visit"),
               p.get("days"))
        days = (asof - datetime.date.fromisoformat(new_lv)).days
        new = (new_pm, new_rp, new_lv, days)
        if old[:3] != new[:3] or old[3] != days:
            moved.append((c, old, new))
        if mode == "--write":
            p["last_pm"], p["last_repair"] = new_pm, new_rp
            p["last_visit"], p["days"] = new_lv, days
            if p.get("last_visit_real"):
                p["last_visit_real"] = new_lv
    seen = set(pm) | set(rep)
    unseen = sorted(seen - {p["wp"] for p in pumps})

    # S.over6 / S.never are stored copies of figures the page also recomputes
    # in the browser from PUMPS.days > 182. They had already drifted apart -
    # the stored copy said 438 against 432 computed - so they are rebuilt here
    # from the same rule the page uses, and can no longer disagree.
    over6_old, never_old = S.get("over6"), S.get("never")
    over6 = sum(1 for p in pumps if p.get("days") is not None and p["days"] > 182)
    never = sum(1 for p in pumps if p.get("days") is None)
    by_site = {}
    for p in pumps:
        if p.get("days") is not None and p["days"] > 182:
            by_site[p["site"]] = by_site.get(p["site"], 0) + 1

    week_old = dict(S.get("week") or {})
    week_new = {"pm": counts(FORMS["pm"], asof),
                "repairs": counts(FORMS["repair"], asof),
                "calls": counts(FORMS["call"], asof)}
    week_new["breakdown_reports"] = week_new["calls"]

    print(f"as-of date from the extract: {asof}")
    print(f"pumps whose activity dates move: {len(moved)} of {len(pumps)}")
    for c, o, n in moved[:12]:
        print(f"   {c}  last_visit {o[2]} -> {n[2]}   days {o[3]} -> {n[3]}")
    if len(moved) > 12:
        print(f"   ... and {len(moved) - 12} more")
    print(f"\npumps more than 6 months without a visit: {over6_old} -> {over6}")
    print(f"pumps with no visit or repair on record:  {never} "
          f"(S.never stays {never_old}: it counts works records too, which this "
          f"tool does not pull)")
    print("\nweek counters (7 days / previous 7 / 28 days):")
    for k in ("pm", "repairs", "calls"):
        print(f"   {k:9s} {week_old.get(k)} -> {week_new[k]}")
    if unseen:
        print(f"\n{len(unseen)} point(s) have activity but are not in the "
              f"maintained register: {', '.join(unseen[:8])}")
    if mode != "--write":
        print("\n--dry-run: nothing written")
        return 0

    S["week"] = week_new
    # over6 is purely visit-derived, so it is rebuilt. never is NOT: it counts
    # points with no works record of any kind - rehabilitation and construction
    # included - and this tool pulls neither, so overwriting it with the
    # visit-only count would narrow the figure silently.
    S["over6"] = over6
    S["over6_site"] = {k: by_site.get(k, 0) for k in (S.get("over6_site") or by_site)}
    out = (idx[:mp.end()] + json.dumps(pumps, separators=(", ", ": "))
           + idx[idx.index("];", mp.end()) + 1:])
    ms2 = re.search(r"\bconst S\s*=\s*", out)
    out = (out[:ms2.end()] + json.dumps(S, separators=(", ", ": "))
           + out[out.index("};", ms2.end()) + 1:])
    open(os.path.join(REPO, "index.html"), "w", encoding="utf8").write(out)
    print(f"\nindex.html: {len(moved)} pumps and the week counters rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
