# -*- coding: utf-8 -*-
"""Water points that failed their SDWS 3 commissioning test are not creditable (21 Oct 2026).

DECISION: James Walker, Head of Carbon, 20 Oct 2026 (comment on the SDWS 3
SOP): a water point that did not pass SDWS 3 is not creditable, is not part of
the carbon portfolio, and is excluded from survey frames.

THE RULE lives in data/sdws3_rule.json, byte-identical in the sanitap-sampler
repository (data/sdws3_rule.json there, embedded in app.js as
Core.SDWS3_RULE). This tool interprets it; it states no threshold of its own.

  1. Per water point, only its LATEST final result on the SDWS 3 results form
     counts, by result date (WS7.10), then by submission time. A later passing
     retest restores the point.
  2. The result fails if E. coli > 0 CFU/100 mL, arsenic > 10 ug/L,
     fluoride >= 1.5 mg/L (the kit maximum: 1.5 means over-range) or
     turbidity > 5 NTU. A blank parameter does not fail.
  3. EXCEPTIONS (the named list in the rule file, nowhere else): a listed
     response has the listed parameters ignored, with the reason recorded.
     Today: 742894851, response Cathy_MadAvance-D5V5UQ, 26 Apr 2025,
     turbidity 11 NTU, a data-entry slip.
  4. A point with no final result is not touched.

OUTPUT: data/sdws3_creditable.json (inlined in the page as NOCREDIT) and the
collapsed list "Not creditable: failed SDWS 3" (region sdws3-not-creditable).
The carbon fleet (tools/populations.py), the carbon denominator
(tools/carbon_denominator.py) and every carbon-portfolio expression on the
page (CPUMPS) leave these points out; the managed fleet keeps them.
tools/check_creditable.py fails the build if one is counted in the carbon
portfolio.

    python3 tools/sdws3_creditable.py --write   # data/sdws3_creditable.json + the page region
    python3 tools/sdws3_creditable.py --check
"""
import collections, hashlib, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULE = os.path.join(REPO, "data", "sdws3_rule.json")
OUT = os.path.join(REPO, "data", "sdws3_creditable.json")
PAGE = os.path.join(REPO, "index.html")
STATE = os.path.join(REPO, "data", "action_state.json")
MANIFEST = os.path.join(REPO, "data", "extract_manifest.json")
BEGIN = ("<!-- BEGIN GENERATED sdws3-not-creditable :: tools/sdws3_creditable.py :: "
         "do not edit between these markers -->")
END = "<!-- END GENERATED sdws3-not-creditable -->"
ANCHOR = "<!-- BEGIN GENERATED iron-manganese"
MWR = "https://portal.mwater.co/#/responses/"
SITE_DISTRICT = {"Maroantsetra": "Maroantsetra", "Fort-Dauphin": "Taolagnaro", "Marolinta": "Beloha"}

# The action that tracks a retest, per water point. A point not listed here
# says so on the page: nothing on the action list follows it.
RETEST_ACTIONS = {"833033198": "act-wq-retest"}

OPS = {">": lambda v, t: v > t, ">=": lambda v, t: v >= t}


def load_rule():
    raw = open(RULE, "rb").read()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _answer(r, q):
    v = (r.get("data") or {}).get(q)
    return v.get("value") if isinstance(v, dict) else v


def _num(x):
    if x is None or x == "" or isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def judge(r, rule):
    """Failing parameters of one response under the rule, after its exception."""
    exc = {e["response"]: e for e in rule["exceptions"]}.get(r.get("code"))
    ignore = set(exc["ignore"]) if exc else set()
    failing, ignored = [], []
    for t in rule["fail_if"]:
        v = _num(_answer(r, t["q"]))
        if v is None or not OPS[t["op"]](v, t["limit"]):
            continue
        item = {"key": t["key"], "label": t["label"], "value": v, "op": t["op"],
                "limit": t["limit"], "unit": t["unit"]}
        (ignored if t["key"] in ignore else failing).append(item)
    return failing, ignored, exc


def point_of(r, rule):
    s = _answer(r, rule["form"]["site_q"])
    return str(s["code"]) if isinstance(s, dict) and s.get("code") else None


def latest_by_point(rows, rule):
    by = collections.defaultdict(list)
    for r in rows:
        if r.get("form") not in (None, rule["form"]["id"]) or r.get("status") != rule["form"]["status"]:
            continue
        wp = point_of(r, rule)
        if wp:
            by[wp].append(r)
    key = lambda r: (str(_answer(r, rule["form"]["date_q"]) or ""), str(r.get("submittedOn") or ""))
    return {wp: sorted(rs, key=key) for wp, rs in by.items()}


def evaluate(rows, rule):
    """{wp: verdict} for every point with a final result. Pure: the tests call it."""
    out = {}
    for wp, rs in latest_by_point(rows, rule).items():
        last = rs[-1]
        failing, ignored, exc = judge(last, rule)
        earlier_fail = any(judge(r, rule)[0] for r in rs[:-1])
        out[wp] = {"creditable": not failing, "failing": failing, "ignored": ignored,
                   "exception": exc, "response": last.get("code"), "response_id": last.get("_id"),
                   "result_date": str(_answer(last, rule["form"]["date_q"]) or last.get("submittedOn") or "")[:10],
                   "results": len(rs), "restored": bool(earlier_fail and not failing)}
    return out


def js_array(src, name):
    i = src.index(f"\nconst {name}=")
    return json.JSONDecoder().raw_decode(src[i + len(f"\nconst {name}="):])[0]


def compute():
    import populations as P
    rule, sha = load_rule()
    verdicts = evaluate(P._wq_results(), rule)
    pumps = {p["wp"]: p for p in js_array(open(PAGE, encoding="utf8").read(), "PUMPS")}
    state = (json.load(open(STATE, encoding="utf8")).get("state") or {}) if os.path.isfile(STATE) else {}
    rows = []
    for wp in sorted(w for w, v in verdicts.items() if not v["creditable"]):
        v, p = verdicts[wp], pumps.get(wp) or {}
        act = RETEST_ACTIONS.get(wp)
        st = state.get(act) or {}
        rows.append({
            "wp": wp, "in_fleet": wp in pumps, "site": p.get("site"),
            "district": SITE_DISTRICT.get(p.get("site"), p.get("site") or ""), "commune": p.get("commune") or "",
            "failing": v["failing"], "result_date": v["result_date"], "response": v["response"],
            "response_id": v["response_id"], "results": v["results"],
            "retest": {"action": act, "open": (st.get("satisfied") is False) if act else None,
                       "says": st.get("evidence") if act else None}})
    fleet_rows = [r for r in rows if r["in_fleet"]]
    man = json.load(open(MANIFEST, encoding="utf8"))["files"].get("wq_results.json", {}) \
        if os.path.isfile(MANIFEST) else {}
    applied = [{"wp": wp, "response": v["response"], "result_date": v["result_date"],
                "ignored": v["ignored"], "reason": v["exception"]["reason"]}
               for wp, v in sorted(verdicts.items()) if v["exception"]]
    return {
        "note": "Water points whose latest final SDWS 3 result fails the rule in data/sdws3_rule.json: "
                "not creditable, outside the carbon portfolio, still in the managed fleet. "
                "Written by tools/sdws3_creditable.py.",
        "rule": {"file": "data/sdws3_rule.json", "sha256": sha, "version": rule["version"],
                 "decided_by": rule["decision"]["by"], "decided_on": rule["decision"]["on"],
                 "fail_if": rule["fail_if"]},
        "form": rule["form"]["id"], "extract": "wq_results.json", "extracted": (man.get("written") or "")[:10],
        "points_with_result": len(verdicts),
        "not_creditable": len(rows), "in_fleet": len(fleet_rows),
        "by_site": dict(sorted(collections.Counter(r["site"] for r in fleet_rows).items())),
        "wps": [r["wp"] for r in rows],
        "rows": rows,
        "exceptions_applied": applied,
        "restored": sorted(wp for wp, v in verdicts.items() if v["restored"]),
    }


def fmt_v(x):
    return f"{x:g}"


def render(d):
    from table_notes import render as tablenote
    F = lambda e, v: f'<span data-fig="{e}">{v}</span>'
    trs = []
    for i, r in enumerate(d["rows"]):
        b = f"NOCREDIT.rows[{i}]"
        par = "; ".join(f'{f["label"]} {F(f"{b}.failing[{j}].value", fmt_v(f["value"]))}&nbsp;{F(f"{b}.failing[{j}].unit", f["unit"])}'
                        f' <span class="muted">(fails at {f["op"]}&nbsp;{F(f"{b}.failing[{j}].limit", fmt_v(f["limit"]))})</span>'
                        for j, f in enumerate(r["failing"]))
        if r["retest"]["action"]:
            a = r["retest"]["action"]
            rt = (f'tracked as <a href="#{a}" class="mono">{a}</a>: '
                  + ("no retest on file yet" if r["retest"]["open"] else "retest condition met"))
        else:
            rt = "no retest on file, and no action tracks one"
        where = f'{r["district"]}{", " + r["commune"] if r["commune"] else ""}' if r["in_fleet"] \
            else '<span class="muted">not in the managed fleet</span>'
        trs.append(f'<tr data-rid="{r["response_id"]}"><td class="mono">{r["wp"]}</td><td>{where}</td>'
                   f'<td>{par}</td><td class="num">{r["result_date"]}</td><td>{rt}</td>'
                   f'<td><a href="{MWR}{r["response_id"]}" target="_blank" rel="noopener" '
                   f'title="Open this SDWS 3 result in mWater">{r["response"]}</a></td></tr>')
    exc = "".join(
        f'<li><span class="mono">{e["wp"]}</span>, response <span class="mono">{e["response"]}</span> of '
        f'{e["result_date"]}: {", ".join(x["label"] for x in e["ignored"]) or "nothing"} ignored. {F(f"NOCREDIT.exceptions_applied[{i}].reason", e["reason"])}</li>'
        for i, e in enumerate(d["exceptions_applied"]))
    words = {">": "above", ">=": "at or above"}
    lim = lambda i: (f'{d["rule"]["fail_if"][i]["label"].replace("E. coli", "E.&nbsp;coli")} '
                     f'{words[d["rule"]["fail_if"][i]["op"]]} '
                     f'{F(f"NOCREDIT.rule.fail_if[{i}].limit", fmt_v(d["rule"]["fail_if"][i]["limit"]))}'
                     f'&nbsp;{F(f"NOCREDIT.rule.fail_if[{i}].unit", d["rule"]["fail_if"][i]["unit"])}')
    restored = (f'<p class="note" style="margin:6px 0 0">Restored by a later passing retest: '
                f'{", ".join(d["restored"])}.</p>') if d["restored"] else ""
    return (
        f'<details class="panel" id="nocreditsec" data-scopes="all mad madx" style="padding:14px 0">'
        f'<summary style="cursor:pointer"><h2 class="sumh2">Not creditable: failed SDWS 3</h2></summary>'
        f'<p class="note" style="margin:10px 0 4px"><b>{F("NOCREDIT.in_fleet", d["in_fleet"])} managed water points '
        f'failed their SDWS 3 commissioning test and are not creditable.</b> They stay in the managed fleet and in every '
        f'managed figure, and are left out of the carbon portfolio: its point count, people served and the tonnes '
        f'checked against the annual cap. Decided by {d["rule"]["decided_by"]} on {d["rule"]["decided_on"]}. '
        f'Each point\'s latest final result on the SDWS 3 results form counts, by result date; a later passing retest '
        f'restores it. A result fails on {lim(0)}, {lim(1)}, {lim(2)} (the kit maximum, so a reading at the '
        f'maximum means over the range) or {lim(3)}. A point with no result is not affected.</p>'
        f'<div class="tablewrap" style="margin-top:6px"><table class="ind" data-table="nocredit" id="nocredittbl">'
        f'<thead><tr><th>Water point</th><th>District, commune</th><th>Failing parameter</th>'
        f'<th class="num">Result date</th><th>Retest</th><th>mWater result</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table></div>{tablenote("nocredit")}'
        f'<p class="note" style="margin:6px 0 0"><b>Named exceptions</b> (data/sdws3_rule.json):</p>'
        f'<ul class="note" style="margin:4px 0 0">{exc}</ul>{restored}'
        f'<p class="note" style="margin:6px 0 0"><span class="muted">The same rule, from the same file, takes these '
        f'points out of the SaniTap Sampler\'s survey frames (SDWS 18 and SDWS 26).</span></p>'
        f'</details>')


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    from prerender_figures import same
    if mode == "--write":
        d = compute()
        json.dump(d, open(OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False)
        open(OUT, "a", encoding="utf8").write("\n")
    d = json.load(open(OUT, encoding="utf8"))
    idx = open(PAGE, encoding="utf8").read()
    if BEGIN not in idx:
        idx = idx.replace(ANCHOR, BEGIN + "\n" + END + "\n" + ANCHOR, 1)
    a, z = idx.index(BEGIN) + len(BEGIN), idx.index(END)
    want = "\n" + render(d) + "\n"
    if mode == "--write":
        open(PAGE, "w", encoding="utf8").write(idx[:a] + want + idx[z:])
        print(f"sdws3 not creditable: {d['not_creditable']} point(s) ({d['in_fleet']} in the managed fleet, "
              f"{d['by_site']}) of {d['points_with_result']} with a result: {', '.join(d['wps'])}")
        return 0
    ok = same(idx[a:z], want)
    print("sdws3-not-creditable region " + ("matches its generator" if ok else "DRIFTED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
