# -*- coding: utf-8 -*-
"""What became of every breakdown call, and repair time against the target (7 Oct 2026).

act-repair-time follow-up (Adriaan Mol, 7 Oct 2026). Reads only the extracts the
build already pulls: the call-centre, preventive-maintenance and both repair
sources. For every managed pump, its calls reporting it not working (the rule of
tools/call_followup.py) in the twelve months to the latest call are grouped into
breakdowns:

  a breakdown opens with a not-working call and closes at the first repair
  record (either repair source) or the first record showing the pump working
  (a call answering "working", or a preventive visit finding it working, before
  or after its own repair)

Each call with no repair record after it falls in one class:

  (c) a duplicate or follow-up call: the pump's breakdown was already open
      when the call came in
  (a) the repair happened but was not logged: no repair record, but a later
      call or visit shows the pump working
  (b) still down, or no later record

The cleaned set is one call per breakdown (the first). Its time to repair runs
to the repair record, or for (a) to the first record showing the pump working
(an upper bound). The target (Adriaan Mol, 7 Oct 2026): at least 90% of
breakdowns repaired within 14 days - the 18 days of downtime a year that the
347-day ceiling allows. Breakdowns opened less than 14 days ago are not yet
scored.

    python3 tools/call_outcomes.py --write   # data/call_outcomes.json + page region
    python3 tools/call_outcomes.py --check
"""
import datetime, json, os, re, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_call_tables as B  # noqa: E402
import rebuild_activity as RA  # noqa: E402
import populations as POP  # noqa: E402
import build_config as _bc  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "call_outcomes.json")
PAGE = os.path.join(REPO, "index.html")
BEGIN = "<!-- BEGIN GENERATED call-outcomes :: tools/call_outcomes.py :: do not edit between these markers -->"
END = "<!-- END GENERATED call-outcomes -->"


def _codes(r):
    ents = r.get("entities") or []
    if isinstance(ents, str):
        try:
            ents = json.loads(ents)
        except ValueError:
            ents = []
    return [str(e.get("value")) for e in ents if isinstance(e, dict) and e.get("value")]


def compute():
    cfg = _bc.load()["repairs"]
    days_t, share_t = cfg["target_within_days"], cfg["target_share"]
    idx = open(PAGE, encoding="utf8").read()
    mp = re.search(r"\bconst PUMPS\s*=\s*", idx)
    pumps = {p["wp"]: p for p in json.loads(idx[mp.end():idx.index("];", mp.end()) + 1])}
    calls = B.load(RA.FORMS["call"], [B.Q_CALL, B.Q_PROBLEM])
    pm = B.load(RA.FORMS["pm"], [B.Q_PM, B.Q_PM_AFTER])
    repairs = {}
    for src, r in POP._repair_records():
        if (r.get("status") or "final") not in ("final", "pending"):
            continue
        ts = str(r.get("submittedOn") or "")
        if ts[:2] != "20":
            continue
        for c in _codes(r):
            repairs.setdefault(c, []).append(ts)

    def not_working(r):
        s = B.M_CALL.get(r[B.Q_CALL])
        if s == "down":
            return True
        if s != "partial":
            return False
        pr = r.get(B.Q_PROBLEM)
        pr = pr if isinstance(pr, list) else ([pr] if pr else [])
        return not (pr and all(x == B.C_SERVICE_REQUEST for x in pr))

    asof = max(c["date"] for v in calls.values() for c in v)
    lo = (datetime.date.fromisoformat(asof) - datetime.timedelta(days=365)).isoformat()
    d = lambda a, b: (datetime.date.fromisoformat(b[:10]) - datetime.date.fromisoformat(a[:10])).days
    rows, episodes = [], []
    for wp in sorted(set(calls) & set(pumps)):
        ev = []
        for c in calls[wp]:
            if (c.get("rstatus") or "final") not in RA.SUBMITTED:
                continue
            if not_working(c):
                ev.append((c["ts"], "call_down", c))
            elif B.M_CALL.get(c[B.Q_CALL]) == "ok":
                ev.append((c["ts"], "working", {"kind": "call", "rid": c["rid"]}))
        for v in pm.get(wp, []):
            if (v.get("rstatus") or "final") in RA.SUBMITTED and \
                    (B.M_PM.get(v[B.Q_PM]) == "ok" or B.M_PM_AFTER.get(v[B.Q_PM_AFTER]) == "ok"):
                ev.append((v["ts"], "working", {"kind": "visit", "rid": v["rid"]}))
        for ts in repairs.get(wp, []):
            ev.append((ts, "repair", {}))
        ev.sort(key=lambda e: e[0])
        rep_ts = sorted(repairs.get(wp, []))
        work_ts = sorted(t for t, k, _x in ev if k == "working")
        ep = None
        for ts, kind, x in ev:
            if kind == "call_down":
                in_window = lo < x["date"] <= asof
                if ep is None:
                    ep = {"wp": wp, "opened": x["date"], "rid": x["rid"], "calls": 1, "in_window": in_window}
                    if in_window:
                        rows.append({"wp": wp, "date": x["date"], "rid": x["rid"], "first": True, "ep": ep,
                                     "repair_after": any(t > ts for t in rep_ts), "working_after": any(t > ts for t in work_ts)})
                else:
                    ep["calls"] += 1
                    if in_window:
                        rows.append({"wp": wp, "date": x["date"], "rid": x["rid"], "first": False, "ep": ep,
                                     "repair_after": any(t > ts for t in rep_ts), "working_after": any(t > ts for t in work_ts)})
            elif ep is not None:
                ep["closed"] = ts[:10]
                ep["by"] = "repair" if kind == "repair" else "working"
                ep["days"] = d(ep["opened"], ts)
                episodes.append(ep)
                ep = None
        if ep is not None:
            ep["closed"] = None
            ep["by"] = None
            ep["days_open"] = d(ep["opened"], asof)
            episodes.append(ep)
    # the class of every call with no repair record after it
    # classes for the calls with no repair record after them (either repair source)
    cls = {"repaired": 0, "a": 0, "b": 0, "c": 0}
    for r in rows:
        if r["repair_after"]:
            cls["repaired"] += 1
            r["class"] = "repaired"
        elif not r["first"]:
            cls["c"] += 1
            r["class"] = "c"
        elif r["working_after"]:
            cls["a"] += 1
            r["class"] = "a"
        else:
            cls["b"] += 1
            r["class"] = "b"
    eps = [e for e in episodes if e["in_window"]]
    scored = [e for e in eps if e.get("closed") or e.get("days_open", 0) >= days_t]
    within = [e for e in scored if e.get("closed") and e["days"] <= days_t]
    closed = [e["days"] for e in scored if e.get("closed")]
    still_down = sorted(({"wp": e["wp"], "site": pumps[e["wp"]]["site"], "commune": pumps[e["wp"]].get("commune"),
                          "since": e["opened"], "days": e["days_open"], "calls": e["calls"], "rid": e["rid"]}
                         for e in eps if not e.get("closed")), key=lambda x: x["since"])
    unlogged = sorted(({"wp": e["wp"], "site": pumps[e["wp"]]["site"], "reported": e["opened"], "working_by": e["closed"]}
                       for e in eps if e.get("by") == "working"), key=lambda x: x["reported"])
    return {"note": "Written by tools/call_outcomes.py from the call-centre, preventive-maintenance and repair extracts.",
            "asof": asof, "window_from_excl": lo, "calls": len(rows),
            "classes": cls, "no_repair_calls": cls["a"] + cls["b"] + cls["c"],
            "breakdowns": len(eps), "scored": len(scored), "within_target": len(within),
            "share_within": round(100 * len(within) / len(scored), 1) if scored else None,
            "median_days": statistics.median(closed) if closed else None,
            "target": {"days": days_t, "share_pct": round(100 * share_t),
                       # the downtime a year the days-operational ceiling allows (365 - do_cap)
                       "downtime_days": 365 - int(float(re.search(r"\bdo_cap:\{v:([\d.]+)", idx).group(1)))},
            "meets_target": bool(scored) and len(within) / len(scored) >= share_t,
            "still_down": still_down, "unlogged": unlogged}


def render(d):
    from table_notes import render as tablenote
    F = lambda e, v: f'<span data-fig="{e}">{v}</span>'
    c = d["classes"]
    rows = "".join(
        f'<tr><td class="mono">{p["wp"]}</td><td>{p["site"]}</td><td>{p.get("commune") or ""}</td>'
        f'<td class="num">{p["since"]}</td><td class="num">{F("CO.still_down[" + str(i) + "].days", p["days"])} days</td>'
        f'<td class="num">{F("CO.still_down[" + str(i) + "].calls", p["calls"])}</td></tr>' for i, p in enumerate(d["still_down"]))
    ul = "".join(f'<li><span class="mono">{u["wp"]}</span> ({u["site"]}): reported {u["reported"]}, working by {u["working_by"]}</li>'
                 for u in d["unlogged"])
    verdict = "meets" if d["meets_target"] else "is below"
    return (f'<p class="note" id="call-outcomes"><b>Repair time against the target</b> (Adriaan Mol, 7 Oct 2026: at least '
            f'{F("CO.target.share_pct", d["target"]["share_pct"])}% of breakdowns repaired within {F("CO.target.days", d["target"]["days"])} days, '
            f'in line with the {F("CO.target.downtime_days", d["target"].get("downtime_days", 18))} days of downtime a year the <span data-param="do_cap">347</span>-day ceiling allows). Of {F("CO.scored", d["scored"])} breakdowns in the twelve months to '
            f'{F("CO.asof", d["asof"])} old enough to score, {F("CO.within_target", d["within_target"])} '
            f'({F("CO.share_within", d["share_within"])}%) were repaired within the target, median {F("CO.median_days", d["median_days"])} days: '
            f'the record {verdict} the target. One call per breakdown; a repair not logged counts to the first record showing the pump working.</p>'
            f'<p class="note"><b>What became of the calls with no repair record</b> ({F("CO.no_repair_calls", d["no_repair_calls"])} of '
            f'{F("CO.calls", d["calls"])} not-working calls): (a) repaired but not logged &mdash; a later call or visit shows the pump working: '
            f'{F("CO.classes.a", c["a"])}; (b) still down or no later record: {F("CO.classes.b", c["b"])}; (c) a duplicate or follow-up call '
            f'about a breakdown already reported: {F("CO.classes.c", c["c"])}.</p>'
            '<details class="expl" id="calls-unlogged"><summary>Repairs not logged (a): the pumps</summary>'
            f'<ul class="note">{ul}</ul></details>'
            '<p class="note" id="pumps-still-down"><b>Pumps still down</b> (b), oldest first:</p>'
            '<div class="tablewrap"><table class="ind" data-table="stilldown"><thead><tr><th>Water point</th><th>Site</th><th>Commune</th>'
            '<th class="num">Down since</th><th class="num">Down for</th><th class="num">Calls</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>{tablenote("stilldown")}')


def main():
    from prerender_figures import same
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if mode == "--write":
        json.dump(compute(), open(OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    d = json.load(open(OUT, encoding="utf8"))
    idx = open(PAGE, encoding="utf8").read()
    if BEGIN not in idx:
        anchor = "<!-- END GENERATED repeat-breakdowns -->"
        idx = idx.replace(anchor, anchor + "\n" + BEGIN + "\n" + END, 1)
    a, z = idx.index(BEGIN) + len(BEGIN), idx.index(END)
    want = "\n" + render(d) + "\n"
    if mode == "--write":
        open(PAGE, "w", encoding="utf8").write(idx[:a] + want + idx[z:])
        c = d["classes"]
        print(f"call outcomes: {d['calls']} calls; repaired {c['repaired']}, a {c['a']}, b {c['b']}, c {c['c']}; "
              f"{d['within_target']}/{d['scored']} breakdowns within {d['target']['days']} d ({d['share_within']}%); "
              f"still down {len(d['still_down'])}")
        return 0
    ok = same(idx[a:z], want)
    print("call-outcomes region " + ("matches its generator" if ok else "DRIFTED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
