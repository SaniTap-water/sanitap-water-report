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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_config as _bc
# six months, from data/build_config.json - the one value the page, the tiles
# and every tool apply
OVERDUE_DAYS = _bc.load()["maintenance"]["overdue_after_days"]

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS = os.path.expanduser("~/mwater-exports")
SUBMITTED = ("final", "pending")        # mWater: approved, or submitted and awaiting approval
FORMS = {"pm": "pm.csv", "repair": "reparation_apres_panne.csv",
         "call": "appel_signalement_pannes.csv"}


def rows(name):
    p = os.path.join(EXPORTS, name)
    if not os.path.isfile(p):
        sys.exit(f"missing extract {p} - run tools/pull_extract.py --write")
    with io.open(p, encoding="utf8", errors="replace") as fh:
        return list(csv.DictReader(fh))


LATEST_ID = {}     # code -> (date, response id) of its latest submitted visit


def by_point(name):
    """code -> sorted list of submission dates, submitted records only (a draft
    or a rejected record is not a visit). The latest record's response id is
    kept in LATEST_ID, so the last-visit date links to the record it came from."""
    out = {}
    for r in rows(name):
        d = str(r.get("submittedOn") or "")[:10]
        if d[:2] != "20" or (r.get("status") or "final") not in SUBMITTED:
            continue
        ents = r.get("entities") or ""
        try:
            ents = json.loads(ents) if ents.startswith("[") else []
        except ValueError:
            ents = []
        for e in ents:
            if e.get("entityType") == "water_point" and e.get("value"):
                code = str(e["value"])
                out.setdefault(code, []).append(d)
                ts = str(r.get("submittedOn") or "")
                if r.get("_id") and ts >= LATEST_ID.get(code, ("", ""))[0]:
                    LATEST_ID[code] = (ts, r["_id"])
    return {k: sorted(v) for k, v in out.items()}


def counts(name, asof):
    # SUBMITTED records: final (approved) and pending (submitted, awaiting
    # approval in mWater). A draft is not yet submitted and a rejected record
    # was refused, so neither is counted. The tiles say "submitted"; the
    # time-to-repair table, which counts approved records only, says so too
    # (28 Sep 2026: the two used to sit side by side unlabelled).
    ds = [str(r.get("submittedOn") or "")[:10] for r in rows(name)
          if (r.get("status") or "final") in SUBMITTED]
    ds = [d for d in ds if d[:2] == "20"]
    def win(a, b):
        lo = (asof - datetime.timedelta(days=a)).isoformat()
        hi = (asof - datetime.timedelta(days=b)).isoformat()
        return sum(1 for d in ds if hi < d <= lo)
    wk, win_n = _bc.load()["activity"]["week_days"], _bc.load()["activity"]["window_days"]
    return [win(0, wk), win(wk, 2 * wk), win(0, win_n)]


def monthly(since="2025-09"):
    """[[YYYY-MM, submitted records], ...] for preventive visits and repairs."""
    import collections
    import populations as P
    pm = collections.Counter(str(r.get("submittedOn") or "")[:7] for r in rows(FORMS["pm"])
                             if (r.get("status") or "final") in SUBMITTED)
    rp = collections.Counter(str(r.get("submittedOn") or "")[:7] for _src, r in P._repair_records()
                             if (r.get("status") or "final") in SUBMITTED)
    months = sorted(m for m in set(pm) | set(rp) if m >= since and m[:2] == "20")
    return [[m, pm.get(m, 0)] for m in months], [[m, rp.get(m, 0)] for m in months]


def down_reports(managed, asof):
    """Distinct managed pumps that a call-centre contact reported NOT fully
    working - "Is the pump currently working?" answered No or Partially - in
    each window: [this week, previous week, last window_days].

    This is a count of new reports in a window, not the pumps down now: a pump
    reported down on Monday and repaired on Tuesday is in it, and a pump down
    since June and not called about is not. The current total is S.status.down
    (the last answered record on each pump). A "Partially" whose only reported
    problem is a routine service request says the pump works, and is left out,
    exactly as the status rule in build_call_tables.py leaves it out."""
    import build_call_tables as B
    calls = B.load(FORMS["call"], [B.Q_CALL, B.Q_PROBLEM])
    wk, win_n = _bc.load()["activity"]["week_days"], _bc.load()["activity"]["window_days"]

    def not_working(r):
        s = B.M_CALL.get(r[B.Q_CALL])
        if s == "down":
            return True
        if s != "partial":
            return False
        pr = r.get(B.Q_PROBLEM)
        pr = pr if isinstance(pr, list) else ([pr] if pr else [])
        return not (pr and all(x == B.C_SERVICE_REQUEST for x in pr))

    def pumps(a, b, want=None):
        lo = (asof - datetime.timedelta(days=a)).isoformat()
        hi = (asof - datetime.timedelta(days=b)).isoformat()
        return {wp for wp, rs in calls.items() if wp in managed
                for r in rs if hi < r["date"] <= lo and not_working(r)
                and (r.get("rstatus") or "final") in SUBMITTED
                and (want is None or B.M_CALL.get(r[B.Q_CALL]) == want)}
    this_wk = pumps(0, wk)
    down = pumps(0, wk, "down")
    return ([len(this_wk), len(pumps(wk, 2 * wk)), len(pumps(0, win_n))],
            # this week, split: reported down / reported partially working only
            [len(down), len(this_wk - down)])


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
    # in the browser from PUMPS.days > OVERDUE_DAYS. They had already drifted apart -
    # the stored copy said 438 against 432 computed - so they are rebuilt here
    # from the same rule the page uses, and can no longer disagree.
    over6_old, never_old = S.get("over6"), S.get("never")
    over6 = sum(1 for p in pumps if p.get("days") is not None and p["days"] > OVERDUE_DAYS)
    never = sum(1 for p in pumps if p.get("days") is None)
    by_site = {}
    for p in pumps:
        if p.get("days") is not None and p["days"] > OVERDUE_DAYS:
            by_site[p["site"]] = by_site.get(p["site"], 0) + 1

    week_old = dict(S.get("week") or {})
    week_new = {"pm": counts(FORMS["pm"], asof),
                "repairs": counts(FORMS["repair"], asof),
                "calls": counts(FORMS["call"], asof),
                }
    week_new["down_reports"], week_new["down_reports_split"] = \
        down_reports({p["wp"] for p in pumps}, asof)
    # Until 28 Sep 2026 a fourth counter, breakdown_reports, was set to the
    # call counts above and shown as "Pumps reported down or reduced": the same
    # numbers as "Call-centre contacts" under a meaning they do not have. It is
    # gone; down_reports counts what that label promised, and
    # check_consistency.py fails if any stored figure is a copy of another.

    print(f"as-of date from the extract: {asof}")
    print(f"pumps whose activity dates move: {len(moved)} of {len(pumps)}")
    for c, o, n in moved[:12]:
        print(f"   {c}  last_visit {o[2]} -> {n[2]}   days {o[3]} -> {n[3]}")
    if len(moved) > 12:
        print(f"   ... and {len(moved) - 12} more")
    print(f"\npumps more than 6 months without a visit: {over6_old} -> {over6}")
    print(f"pumps with no visit or repair on record:  {never_old} -> {never}")
    print("\nweek counters (7 days / previous 7 / 28 days):")
    for k in ("pm", "repairs", "calls", "down_reports"):
        print(f"   {k:9s} {week_old.get(k)} -> {week_new[k]}")
    if unseen:
        print(f"\n{len(unseen)} point(s) have activity but are not in the "
              f"maintained register: {', '.join(unseen[:8])}")
    if mode != "--write":
        print("\n--dry-run: nothing written")
        return 0

    S["week"] = week_new
    # over6 and never are rebuilt by the rule the page itself applies in agg():
    # a pump with no preventive visit and no repair on record has no clock
    # (days is null). never used to be left alone here, on the grounds that it
    # also counted rehabilitation and construction records; in fact it was a
    # frozen 57 while the page's own count of the same pumps was 6, and an
    # action closed on the frozen one (28 Sep 2026).
    S["over6"] = over6
    S["never"] = never
    # the monthly series, from SUBMITTED records (final + pending): they were
    # stored and written by nothing, and the repair series matched neither
    # repair source (28 Sep 2026). Repairs are the two sources the
    # time-to-repair figures use.
    S["pm_month"], S["rep_month"] = monthly()
    S["over6_site"] = {k: by_site.get(k, 0) for k in (S.get("over6_site") or by_site)}
    out = (idx[:mp.end()] + json.dumps(pumps, separators=(", ", ": "))
           + idx[idx.index("];", mp.end()) + 1:])
    # RESP.v: the response behind each pump's last-visit date. It was a stored
    # map no step refreshed, so 41 pumps with a visit on record had no link to
    # it (28 Sep 2026).
    mr = re.search(r"\bconst RESP\s*=\s*", out)
    if mr:
        je = out.index("};", mr.end())
        RESP = json.loads(out[mr.end():je + 1])
        # a last repair on the retired combined form is linked only where that
        # record's own date IS the pump's last-repair date: a link must open
        # the record the date came from, never a neighbour of it
        import populations as P
        retired = {}
        for src, r in P._repair_records():
            if src == "retired" and (r.get("status") or "final") in SUBMITTED:
                retired.setdefault(P._point_of(r), {})[str(r.get("submittedOn") or "")[:10]] = r["_id"]
        for p in pumps:
            e = RESP.setdefault(p["wp"], {})
            e.pop("v", None)                     # a link is the matching record or nothing
            if not (p.get("last_visit") and (p.get("last_pm") or p.get("last_repair"))):
                continue
            hit = LATEST_ID.get(p["wp"])
            if hit and hit[0][:10] == p["last_visit"]:
                e["v"] = hit[1]
            elif (retired.get(p["wp"]) or {}).get(p.get("last_repair") or ""):
                e["v"] = retired[p["wp"]][p["last_repair"]]
        out = out[:mr.end()] + json.dumps(RESP, separators=(",", ":")) + out[je + 1:]
    ms2 = re.search(r"\bconst S\s*=\s*", out)
    out = (out[:ms2.end()] + json.dumps(S, separators=(", ", ": "))
           + out[out.index("};", ms2.end()) + 1:])
    open(os.path.join(REPO, "index.html"), "w", encoding="utf8").write(out)
    print(f"\nindex.html: {len(moved)} pumps and the week counters rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
