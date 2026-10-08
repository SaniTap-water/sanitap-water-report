# -*- coding: utf-8 -*-
"""Iron and manganese at the managed hand pumps, from the SDWS 3 results (8 Oct 2026).

Asked for after the Fabric review (Adriaan Mol, 8 Oct 2026): Fabric's
waterpoint summary carried an iron and manganese tag that the weekly report
did not. This brings the measurement in, on the report's own rules, and
leaves Fabric's tag behind.

SOURCE: the live SDWS 3 results form (wq_results.json, form 7b33c5d7...),
the extract the build already pulls. Iron (mg/L) and manganese (mg/L) are
optional questions on it, so most results carry neither.

RULE: managed portfolio only (PUMPS). For each pump, its latest result on
the form by result date (the rule of tools/rebuild_pump_inputs.py, drafts and
rejected responses excluded); the iron and manganese values on that result.
A pump whose latest result has no value, or that has no result, is "not
tested" for that metal.

THRESHOLDS, read from PARAMS on the page, where each carries its WHO citation:
  iron       wq_iron_accept        acceptability only (taste, staining);
                                   WHO sets no health-based value
  manganese  wq_manganese_accept   acceptability (discolouration, staining)
             wq_manganese_max      WHO provisional health-based value
A value above a threshold is "above" it; equal to it is within it.

    python3 tools/iron_manganese.py --write   # data/iron_manganese.json + the page region
    python3 tools/iron_manganese.py --check
"""
import collections, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "iron_manganese.json")
PAGE = os.path.join(REPO, "index.html")
MANIFEST = os.path.join(REPO, "data", "extract_manifest.json")
BEGIN = "<!-- BEGIN GENERATED iron-manganese :: tools/iron_manganese.py :: do not edit between these markers -->"
END = "<!-- END GENERATED iron-manganese -->"
ANCHOR = '<section data-scopes="all mad madx mar" id="pousec">'
MWR = "https://portal.mwater.co/#/responses/"

FORM = "7b33c5d7e5074808a94915939a5a0783"          # Water Quality Testing_SDWS 3 — Result
Q_DATE = "630ccd46f76f420692572e0db2d86ad8"         # WS7.10 result date & time
Q_IRON = "3ba8917797a7429aa31b69023c7f3c1f"         # Iron (mg/L), optional
Q_MN = "c0a900a9659e45c29acce3349e32f1fd"           # Manganese (mg/L), optional
SITE_DISTRICT = {"Maroantsetra": "Maroantsetra", "Fort-Dauphin": "Taolagnaro", "Marolinta": "Beloha"}
PARAM_KEYS = ("wq_iron_accept", "wq_manganese_accept", "wq_manganese_max")


def js_array(src, name):
    i = src.index(f"\nconst {name}=")
    return json.JSONDecoder().raw_decode(src[i + len(f"\nconst {name}="):])[0]


def params(src):
    """The three thresholds, as PARAMS on the page declares them."""
    out = {}
    for k in PARAM_KEYS:
        m = re.search(r"\n " + k + r":\{v:([0-9.]+),", src)
        if not m:
            sys.exit(f"PARAMS.{k} is missing from index.html; the iron and manganese "
                     "thresholds are declared there with their WHO citation.")
        out[k] = float(m.group(1))
    return out


def classify_fe(v, t):
    if v is None:
        return "not_tested"
    return "above_acceptability" if v > t["wq_iron_accept"] else "pass"


def classify_mn(v, t):
    if v is None:
        return "not_tested"
    if v > t["wq_manganese_max"]:
        return "above_health"
    return "above_acceptability" if v > t["wq_manganese_accept"] else "pass"


def compute():
    import populations as P
    src = open(PAGE, encoding="utf8").read()
    pumps = js_array(src, "PUMPS")
    t = params(src)
    res = collections.defaultdict(list)
    for r in P._wq_results():
        if r.get("status") in ("draft", "rejected"):
            continue
        d = str(P._answer(r, Q_DATE) or r.get("submittedOn") or "")[:10]
        fe, mn = P._answer(r, Q_IRON), P._answer(r, Q_MN)
        res[P._point_of(r)].append((d, r.get("_id") or "",
                                    fe if isinstance(fe, (int, float)) else None,
                                    mn if isinstance(mn, (int, float)) else None))
    counts = {"fe": collections.Counter(), "mn": collections.Counter()}
    rows = []
    for p in sorted(pumps, key=lambda p: (p["site"], p["wp"])):
        rs = sorted(res.get(p["wp"], []))
        d, rid, fe, mn = rs[-1] if rs else (None, None, None, None)
        cf, cm = classify_fe(fe, t), classify_mn(mn, t)
        counts["fe"][cf] += 1
        counts["mn"][cm] += 1
        if cf == "above_acceptability" or cm in ("above_acceptability", "above_health"):
            rows.append(dict(wp=p["wp"], site=p["site"], district=SITE_DISTRICT.get(p["site"], p["site"]),
                             commune=p.get("commune") or "", fe=fe, mn=mn, fe_class=cf, mn_class=cm,
                             date=d, rid=rid))
    keys = ("pass", "above_acceptability", "above_health", "not_tested")
    man = json.load(open(MANIFEST, encoding="utf8"))["files"].get("wq_results.json", {})
    return {
        "note": "Iron and manganese at the managed hand pumps: latest SDWS 3 result per pump. "
                "Written by tools/iron_manganese.py; thresholds from PARAMS.",
        "form": FORM, "extract": "wq_results.json", "extracted": (man.get("written") or "")[:10],
        "thresholds": t, "pumps": len(pumps),
        "fe": {k: counts["fe"][k] for k in keys if k != "above_health"},
        "mn": {k: counts["mn"][k] for k in keys},
        "rows": rows,
        "fabric_rule": "Fabric's iron_manganese_tag (Reporting_Waterpoint_Summary.sql) tested only points whose "
                       "donor string contains 'MedAir - Phase 2', and took pass/fail precomputed in mWater: iron "
                       "passes to 0.30 mg/L and fails from 0.32 (consistent with 0.3); manganese passes every "
                       "value on file up to 0.19 mg/L, so its threshold is above the WHO provisional 0.08.",
    }


def render(d):
    from table_notes import render as tablenote
    F = lambda e, v: f'<span data-fig="{e}">{v}</span>'
    P = lambda k, v: f'<span data-param="{k}">{v:g}</span>'
    t = d["thresholds"]
    pill = {("fe", "above_acceptability"): '<span class="pill warn">iron: aesthetic</span>',
            ("mn", "above_acceptability"): '<span class="pill warn">manganese: aesthetic</span>',
            ("mn", "above_health"): '<span class="pill crit">manganese: above WHO health-based value</span>'}
    trs = []
    for i, r in enumerate(d["rows"]):
        b = f"FEMN.rows[{i}]"
        fe = F(b + ".fe", f'{r["fe"]:g}') if r["fe"] is not None else "&mdash;"
        mn = F(b + ".mn", f'{r["mn"]:g}') if r["mn"] is not None else "&mdash;"
        flags = " ".join(pill[k] for k in (("mn", r["mn_class"]), ("fe", r["fe_class"])) if k in pill)
        cls = ' class="flagged"' if r["mn_class"] == "above_health" else ""
        trs.append(f'<tr{cls} data-rid="{r["rid"]}"><td class="mono">{r["wp"]}</td><td>{r["district"]}</td>'
                   f'<td>{r["commune"]}</td><td class="num">{fe}</td><td class="num">{mn}</td>'
                   f'<td class="num">{r["date"] or "&mdash;"}</td><td>{flags}</td>'
                   f'<td><a href="{MWR}{r["rid"]}" target="_blank" rel="noopener" '
                   f'title="Open this SDWS 3 result in mWater">result</a></td></tr>')
    cnt = lambda m, k: F(f"FEMN.{m}.{k}", d[m][k])
    return (
        f'<details class="panel" id="ironmnsec" data-scopes="all mad madx mar" style="padding:14px 0">'
        f'<summary style="cursor:pointer"><h2 class="sumh2">Iron and manganese (taste and colour)</h2></summary>'
        f'<p class="note" style="margin:10px 0 4px"><b>These are aesthetic findings &mdash; taste, colour and staining &mdash; '
        f'except manganese above {P("wq_manganese_max", t["wq_manganese_max"])}&nbsp;mg/L, which is above the WHO health-based value.</b> '
        f'Managed hand pumps only (all {F("FEMN.pumps", d["pumps"])}, whatever scope is selected): each pump\'s latest result on '
        f'the SDWS 3 results form, where iron and manganese are optional questions, so most results carry neither.</p>'
        f'<ul class="note" style="margin:4px 0 0">'
        f'<li><b>Iron</b>: WHO sets no health-based guideline value (&ldquo;not of health concern at levels found in drinking-water&rdquo;); '
        f'above about {P("wq_iron_accept", t["wq_iron_accept"])}&nbsp;mg/L it affects taste and stains laundry and fittings. '
        f'Within {F("FEMN.fe.pass", d["fe"]["pass"])}, above acceptability {F("FEMN.fe.above_acceptability", d["fe"]["above_acceptability"])}, '
        f'not tested {F("FEMN.fe.not_tested", d["fe"]["not_tested"])}.</li>'
        f'<li><b>Manganese</b>: WHO provisional health-based guideline value {P("wq_manganese_max", t["wq_manganese_max"])}&nbsp;mg/L; '
        f'above {P("wq_manganese_accept", t["wq_manganese_accept"])}&nbsp;mg/L it has caused complaints of discoloured water and staining. '
        f'Within {cnt("mn", "pass")}, above acceptability {cnt("mn", "above_acceptability")}, '
        f'above the health-based value {cnt("mn", "above_health")}, not tested {cnt("mn", "not_tested")}.</li></ul>'
        f'<p class="note" style="margin:6px 0 0">The pumps above a threshold for either metal:</p>'
        f'<div class="tablewrap" style="margin-top:6px"><table class="ind" data-table="ironmn" id="ironmntbl">'
        f'<thead><tr><th>Water point</th><th>District</th><th>Commune</th><th class="num">Iron, mg/L</th>'
        f'<th class="num">Manganese, mg/L</th><th class="num">Result date</th><th>Reading</th><th>mWater record</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table></div>{tablenote("ironmn")}'
        f'<p class="note" style="margin:6px 0 0"><span class="muted">Sources: WHO Guidelines for drinking-water quality, 4th edition '
        f'incorporating the first and second addenda, chemical fact sheets for iron and for manganese (2022); the iron acceptability level is in '
        f'chapter 10 (acceptability aspects), to which the iron fact sheet refers. Fabric\'s earlier iron and manganese tag tested only MedAir '
        f'Phase&nbsp;2 points and passed manganese well above the WHO value; it is not used here.</span></p>'
        f'</details>')


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    from prerender_figures import same
    if mode == "--write":
        d = compute()
        json.dump(d, open(OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    d = json.load(open(OUT, encoding="utf8"))
    idx = open(PAGE, encoding="utf8").read()
    if BEGIN not in idx:
        idx = idx.replace(ANCHOR, BEGIN + "\n" + END + "\n" + ANCHOR, 1)
    a, z = idx.index(BEGIN) + len(BEGIN), idx.index(END)
    want = "\n" + render(d) + "\n"
    if mode == "--write":
        open(PAGE, "w", encoding="utf8").write(idx[:a] + want + idx[z:])
        print(f"iron and manganese: iron {d['fe']}, manganese {d['mn']}, {len(d['rows'])} pumps listed")
        return 0
    ok = same(idx[a:z], want)
    print("iron-manganese region " + ("matches its generator" if ok else "DRIFTED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
