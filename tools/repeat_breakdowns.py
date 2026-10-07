# -*- coding: utf-8 -*-
"""Repeat breakdowns and report-to-repair time, from the mWater records (7 Oct 2026).

act-repeat-breakdown and act-repair-time, done from the data (Adriaan Mol,
7 Oct 2026). Reads only the extracts the build already pulls:

  repeat breakdowns   repair records per managed pump, on both repair sources
                      (the retired combined form and the live repair form),
                      over the last twelve months and all time; the pumps with
                      the most, and the history of the two named pumps
  report to repair    every call in the last twelve months that reported a
                      managed pump not working (the rule of tools/call_followup.py),
                      and the days to the next submitted repair record

The repair time itself (breakdown notified -> repair completed, on the repair
record) is the TTR table beside this region, computed by tools/rebuild_ttr.py.

    python3 tools/repeat_breakdowns.py --write   # data/repeat_breakdowns.json + the page region
    python3 tools/repeat_breakdowns.py --check
"""
import datetime, json, os, re, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_call_tables as B  # noqa: E402
import rebuild_activity as RA  # noqa: E402
import call_followup as CF  # noqa: E402
import populations as POP  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "repeat_breakdowns.json")
PAGE = os.path.join(REPO, "index.html")
BEGIN = "<!-- BEGIN GENERATED repeat-breakdowns :: tools/repeat_breakdowns.py :: do not edit between these markers -->"
END = "<!-- END GENERATED repeat-breakdowns -->"
NAMED = {"742893805": "Ambinanibe", "742893953": "Andramaka"}
REPEAT_MIN = 4                   # repairs in twelve months that make a repeat breakdown


def _codes(r):
    ents = r.get("entities") or []
    if isinstance(ents, str):
        try:
            ents = json.loads(ents)
        except ValueError:
            ents = []
    return [str(e.get("value")) for e in ents if e.get("value") and e.get("entityType", "water_point") == "water_point"]


def _date(src, r):
    for q in (POP._Q_DONE[src], POP._Q_NOTIF[src]):
        v = str(POP._answer(r, q) or "")[:10]
        if v[:2] == "20":
            return v
    v = str(r.get("submittedOn") or "")[:10]
    return v if v[:2] == "20" else None


def pct(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]


def compute():
    idx = open(PAGE, encoding="utf8").read()
    mp = re.search(r"\bconst PUMPS\s*=\s*", idx)
    pumps = json.loads(idx[mp.end():idx.index("];", mp.end()) + 1])
    site = {p["wp"]: p["site"] for p in pumps}
    commune = {p["wp"]: p.get("commune") for p in pumps}
    reps = {}
    for src, r in POP._repair_records():
        if (r.get("status") or "final") not in ("final", "pending"):
            continue
        d = _date(src, r)
        for c in _codes(r):
            if c in site and d:
                reps.setdefault(c, set()).add((d, r["_id"]))
    asof = max(d for v in reps.values() for d, _ in v)
    lo = (datetime.date.fromisoformat(asof) - datetime.timedelta(days=365)).isoformat()
    per = []
    for c, v in reps.items():
        ds = sorted(d for d, _ in v)
        last12 = [d for d in ds if d > lo]
        gaps = [(datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days for a, b in zip(ds, ds[1:])]
        per.append({"wp": c, "site": site[c], "commune": commune.get(c), "repairs": len(ds), "repairs_12m": len(last12),
                    "first": ds[0], "last": ds[-1], "median_gap_days": statistics.median(gaps) if gaps else None})
    per.sort(key=lambda x: (-x["repairs_12m"], -x["repairs"], x["wp"]))
    repeat = [p for p in per if p["repairs_12m"] >= REPEAT_MIN]
    named = {c: next((p for p in per if p["wp"] == c), {"wp": c, "repairs": 0, "repairs_12m": 0}) for c in NAMED}
    # report -> next repair, every qualifying call in the last twelve months
    rep_v = CF.visits(RA.FORMS["repair"])
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
    waits, none_yet, n_calls = [], 0, 0
    for wp, rs in calls.items():
        if wp not in site:
            continue
        for c in rs:
            if not (lo < c["date"] <= asof and not_working(c) and (c.get("rstatus") or "final") in RA.SUBMITTED):
                continue
            n_calls += 1
            nr = next(((t, rid) for t, rid in rep_v.get(wp, []) if t > c["ts"]), None)
            if nr:
                waits.append((datetime.date.fromisoformat(nr[0][:10]) - datetime.date.fromisoformat(c["date"])).days)
            else:
                none_yet += 1
    call = {"calls": n_calls, "with_repair": len(waits), "no_repair_yet": none_yet,
            "median_days": statistics.median(waits) if waits else None, "p90_days": pct(waits, 90),
            "within_7": sum(1 for w in waits if w <= 7), "within_30": sum(1 for w in waits if w <= 30)}
    ttr = json.load(open(os.path.join(REPO, "data", "ttr_table.json"), encoding="utf8"))["all"]
    return {"note": "Written by tools/repeat_breakdowns.py from the mWater repair and call-centre extracts (7 Oct 2026). "
                    "act-repeat-breakdown and act-repair-time.",
            "asof": asof, "window_from_excl": lo, "repeat_min": REPEAT_MIN,
            "pumps_with_repairs": len(per), "repeat": repeat, "top": per[:12], "named": named,
            "call_to_repair": call, "repair_time": ttr}


def render(d):
    from table_notes import render as tablenote
    F = lambda e, v: f'<span data-fig="{e}">{v}</span>'
    rows = "".join(
        f'<tr><td class="mono">{p["wp"]}</td><td>{p["site"]}</td><td>{p.get("commune") or ""}</td>'
        f'<td class="num">{F("RB.top[" + str(i) + "].repairs_12m", p["repairs_12m"])}</td>'
        f'<td class="num">{F("RB.top[" + str(i) + "].repairs", p["repairs"])}</td>'
        f'<td class="num">{p["last"]}</td></tr>' for i, p in enumerate(d["top"]))
    c = d["call_to_repair"]
    return (f'<p class="note" id="repeat-breakdowns"><b>Repeat breakdowns</b> (act-repeat-breakdown): '
            f'{F("RB.repeat.length", len(d["repeat"]))} managed pumps had {F("RB.repeat_min", d["repeat_min"])} or more repairs '
            f'in the twelve months to {F("RB.asof", d["asof"])}. Ambinanibe (742893805): '
            f'{F("RB.named[&apos;742893805&apos;].repairs", d["named"]["742893805"].get("repairs"))} repairs on file, '
            f'{F("RB.named[&apos;742893805&apos;].repairs_12m", d["named"]["742893805"].get("repairs_12m"))} in twelve months; '
            f'Andramaka (742893953): {F("RB.named[&apos;742893953&apos;].repairs", d["named"]["742893953"].get("repairs"))} on file, '
            f'{F("RB.named[&apos;742893953&apos;].repairs_12m", d["named"]["742893953"].get("repairs_12m"))} in twelve months. '
            f'<b>Report to repair</b> (act-repair-time): of {F("RB.call_to_repair.calls", c["calls"])} calls in twelve months that '
            f'reported a managed pump not working, {F("RB.call_to_repair.with_repair", c["with_repair"])} were followed by a repair '
            f'record, a median {F("RB.call_to_repair.median_days", c["median_days"])} days later '
            f'(p90 {F("RB.call_to_repair.p90_days", c["p90_days"])}); {F("RB.call_to_repair.no_repair_yet", c["no_repair_yet"])} '
            f'have none yet. Dispatch is not recorded on any form, so report-to-dispatch cannot be measured.</p>'
            '<div class="tablewrap"><table class="ind" data-table="repeatbd"><thead><tr><th>Water point</th><th>Site</th>'
            '<th>Commune</th><th class="num">Repairs, past year</th><th class="num">Repairs, all</th><th class="num">Last</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div>{tablenote("repeatbd")}')


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    from prerender_figures import same
    if mode == "--write":
        d = compute()
        json.dump(d, open(OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    d = json.load(open(OUT, encoding="utf8"))
    idx = open(PAGE, encoding="utf8").read()
    if BEGIN not in idx:
        anchor = "<!-- END GENERATED tablenote-ttr -->"
        idx = idx.replace(anchor, anchor + "\n" + BEGIN + "\n" + END, 1)
    a, z = idx.index(BEGIN) + len(BEGIN), idx.index(END)
    want = "\n" + render(d) + "\n"
    if mode == "--write":
        open(PAGE, "w", encoding="utf8").write(idx[:a] + want + idx[z:])
        print(f"repeat breakdowns: {len(d['repeat'])} pumps with {d['repeat_min']}+ repairs in 12 months; "
              f"calls {d['call_to_repair']['calls']}, median {d['call_to_repair']['median_days']} d to repair")
        return 0
    ok = same(idx[a:z], want)
    print("repeat-breakdowns region " + ("matches its generator" if ok else "DRIFTED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
