#!/usr/bin/env python3
"""Calls that reported a pump not working, and what followed (1 Oct 2026).

The activity tile "Pumps a call reported not working" counts distinct managed
pumps that a call-centre contact reported down or partially working (a
"partially" whose only problem is a routine service request excluded), in the
latest week_days and window_days before the as-of date - tools/rebuild_activity.py,
down_reports(). This takes the same pumps, the same rule and the same windows
and asks what came next in mWater after the call: a repair record, a
preventive-maintenance visit, or nothing yet, with dates and days elapsed. It
also lists the preventive visits submitted in each window and counts the pump
codes the two lists share.

One row per pump, from its first qualifying call in the window (later calls
are counted beside it). A repair within followup_days (7) of the call is a
follow-up; a call younger than that is "not yet due".

Writes data/call_followup.json (CALLF on the page).

    python3 tools/call_followup.py [--write]
"""
import datetime, io, csv, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_config as _bc  # noqa: E402
import build_call_tables as B  # noqa: E402
import rebuild_activity as RA  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "call_followup.json")
FOLLOWUP_DAYS = 7


def visits(name):
    """code -> [(timestamp, response id)] of submitted records, oldest first."""
    out = {}
    for r in RA.rows(name):
        ts = str(r.get("submittedOn") or "")
        if ts[:2] != "20" or (r.get("status") or "final") not in RA.SUBMITTED:
            continue
        try:
            ents = json.loads(r.get("entities") or "[]")
        except ValueError:
            ents = []
        for e in ents:
            if e.get("entityType") == "water_point" and e.get("value"):
                out.setdefault(str(e["value"]), []).append((ts, r.get("_id")))
    return {k: sorted(v) for k, v in out.items()}


def main():
    write = "--write" in sys.argv
    idx = open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    mp = re.search(r"\bconst PUMPS\s*=\s*", idx)
    pumps = json.loads(idx[mp.end():idx.index("];", mp.end()) + 1])
    site = {p["wp"]: p["site"] for p in pumps}
    managed = set(site)

    pm, rep = visits(RA.FORMS["pm"]), visits(RA.FORMS["repair"])
    all_d = [t[:10] for v in list(pm.values()) + list(rep.values()) for t, _ in v]
    all_d += [str(r.get("submittedOn") or "")[:10] for r in RA.rows(RA.FORMS["call"])]
    asof = datetime.date.fromisoformat(max(d for d in all_d if d[:2] == "20"))
    wk, win_n = _bc.load()["activity"]["week_days"], _bc.load()["activity"]["window_days"]

    calls = B.load(RA.FORMS["call"], [B.Q_CALL, B.Q_PROBLEM])

    def not_working(r):
        s = B.M_CALL.get(r[B.Q_CALL])
        if s == "down":
            return True
        if s != "partial":
            return False
        pr = r.get(B.Q_PROBLEM)
        pr = pr if isinstance(pr, list) else ([pr] if pr else [])
        return not (pr and all(x == B.C_SERVICE_REQUEST for x in pr))

    def bounds(n):
        return (asof - datetime.timedelta(days=n)).isoformat(), asof.isoformat()

    def nxt(lst, ts):
        return next(((t, rid) for t, rid in lst if t > ts), None)

    def days(a, b):
        return (datetime.date.fromisoformat(b[:10]) - datetime.date.fromisoformat(a[:10])).days

    res = {"note": "Written by tools/call_followup.py. Pumps a call reported not "
                   "working (down, or partially working for a reason other than a routine service request), "
                   "first qualifying call per pump in each window, and the next submitted repair or "
                   "preventive-maintenance record after it in mWater.",
           "asof": asof.isoformat(), "followup_days": FOLLOWUP_DAYS, "windows": {}}
    for name, n in (("week", wk), ("window", win_n)):
        lo, hi = bounds(n)
        rows = []
        for wp, rs in calls.items():
            if wp not in managed:
                continue
            q = [r for r in rs if lo < r["date"] <= hi and not_working(r)
                 and (r.get("rstatus") or "final") in RA.SUBMITTED]
            if not q:
                continue
            c = q[0]
            nr, npm = nxt(rep.get(wp, []), c["ts"]), nxt(pm.get(wp, []), c["ts"])
            first = min([x for x in (nr and ("repair",) + nr, npm and ("preventive visit",) + npm) if x],
                        key=lambda x: x[1], default=None)
            age = days(c["date"], hi)
            if nr and days(c["date"], nr[0]) <= FOLLOWUP_DAYS:
                flag = "repaired within 7 days"
            elif age < FOLLOWUP_DAYS:
                flag = "not yet due"
            else:
                flag = "no repair after 7 days"
            rows.append({"wp": wp, "site": site[wp], "call_date": c["date"], "call_rid": c["rid"],
                         "status": B.M_CALL.get(c[B.Q_CALL]), "calls_in_window": len(q),
                         "next": ({"kind": first[0], "date": first[1][:10], "rid": first[2],
                                   "days": days(c["date"], first[1])} if first else None),
                         "next_repair": ({"date": nr[0][:10], "rid": nr[1], "days": days(c["date"], nr[0])} if nr else None),
                         "next_pm": ({"date": npm[0][:10], "rid": npm[1], "days": days(c["date"], npm[0])} if npm else None),
                         "flag": flag})
        rows.sort(key=lambda r: (r["call_date"], r["wp"]))
        vis = sorted(({"wp": wp, "site": site.get(wp, "not in the maintained register"), "date": t[:10], "rid": rid}
                      for wp, lst in pm.items() for t, rid in lst if lo < t[:10] <= hi),
                     key=lambda r: (r["date"], r["wp"]))
        called = {r["wp"] for r in rows}
        visited = {v["wp"] for v in vis}
        res["windows"][name] = {
            "days": n, "from_excl": lo, "to": hi, "calls": rows, "pm_visits": vis,
            "pumps_called": len(called), "pm_records": len(vis), "pumps_visited": len(visited),
            "overlap": sorted(called & visited), "overlap_n": len(called & visited),
            "no_repair_7d": sum(1 for r in rows if r["flag"] == "no repair after 7 days"),
            "repaired_7d": sum(1 for r in rows if r["flag"] == "repaired within 7 days"),
            "not_yet_due": sum(1 for r in rows if r["flag"] == "not yet due"),
            "nothing_after": sum(1 for r in rows if r["next"] is None)}
    txt = json.dumps(res, indent=1, ensure_ascii=False) + "\n"
    if write:
        open(OUT, "w", encoding="utf8").write(txt)
        print("  ->", os.path.relpath(OUT, REPO))
    elif not os.path.isfile(OUT) or open(OUT, encoding="utf8").read() != txt:
        print("call_followup: data/call_followup.json is out of date (run --write)")
        return 1
    for k, w in res["windows"].items():
        print(f"  {k} ({w['days']} d to {w['to']}): pumps called {w['pumps_called']}, PM records {w['pm_records']} "
              f"on {w['pumps_visited']} pumps, overlap {w['overlap_n']}; no repair after 7 d {w['no_repair_7d']}, "
              f"repaired within 7 d {w['repaired_7d']}, not yet due {w['not_yet_due']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
