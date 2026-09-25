# -*- coding: utf-8 -*-
"""The piped water-quality figures, from the piped SDWS 3 result form.

The rule (Adriaan Mol, 25 September 2026): a piped system joins the managed
portfolio only when its rehabilitation works are complete AND its
post-rehabilitation water-quality tests are done. Which systems are where is
data/piped_systems_status.json, one entry per Endur'O water system.

For each system:

  works    the works_complete date in the status file (None until known);
  post     results dated AFTER works completion - post-rehabilitation tests;
  baseline results dated on or before it, or every result while works are
           not complete. A baseline result NEVER counts toward a managed
           figure, whatever happens to the system later.

A system is MANAGED when works is set and it has a post-rehabilitation test
(a result in the extract, or post_rehab_test in the status file). An
in-process system moves to managed on its own the build after both hold. A
not_managed system never moves by itself. A system declared managed that does
not meet the rule fails the build, as does any system in the extract that the
status file does not list.

A result's date is its sampling date (question 1.2.2), else its result date
(1.3), else the day it was submitted. E. coli is question 1.4 in CFU per
100 mL; a result meets the rule at or below the build's threshold
(water_quality.ecoli_pass_max_cfu_per_100ml), as for the hand pumps.

Everything outside the managed and baseline sets is counted and named: a site
that is a MadAvance hand pump is a result filed on the wrong form.

    python3 tools/rebuild_piped_wq.py --write
    python3 tools/rebuild_piped_wq.py --check
"""
import csv, io, json, os, statistics, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS = os.path.expanduser("~/mwater-exports")
OUT = os.path.join(REPO, "data", "piped_wq.json")
CFG = json.load(open(os.path.join(REPO, "data", "build_config.json"), encoding="utf8"))
PIPED = CFG["piped"]
STATUS = os.path.join(REPO, PIPED["status_file"])
ECOLI_PASS_MAX = CFG["water_quality"]["ecoli_pass_max_cfu_per_100ml"]
STATES = ("managed", "in_process", "not_managed")

Q_SYSTEM = "a3390d2e"    # 1.2 Water System ID
Q_TAP = "7d0fce72"       # 1.2b Water point ID
Q_SAMPLED = "b25338d8"   # 1.2.2 sampling date & time
Q_RESULT = "630ccd46"    # 1.3 result date & time
Q_ECOLI = "892f1d81"     # 1.4 E. coli, CFU/100 ml
Q_CHLORINE = "0594065a"  # free residual chlorine (no question code on the form)


class RuleBroken(Exception):
    pass


def answer(resp, prefix):
    for k, v in (resp.get("data") or {}).items():
        if k.startswith(prefix):
            return (v or {}).get("value")
    return None


def site_code(v):
    return str(v.get("code")) if isinstance(v, dict) and v.get("code") else None


def qty(resp, prefix):
    v = answer(resp, prefix)
    return v.get("quantity") if isinstance(v, dict) else None


def result_date(resp):
    for p in (Q_SAMPLED, Q_RESULT):
        v = answer(resp, p)
        if isinstance(v, str) and v[:2] == "20":
            return v[:10]
    return str(resp.get("submittedOn") or "")[:10] or None


def extract_systems():
    with io.open(os.path.join(EXPORTS, "piped_systems.csv"), encoding="utf8") as fh:
        return {r["code"]: (r.get("name") or "").strip() or None
                for r in csv.DictReader(fh)
                if r.get("_managed_by") == PIPED["operator_group"] and r.get("code")}


def status_problems(status, in_extract):
    """Why the status file does not cover the extract or breaks its own
    vocabulary. The build fails on any of these."""
    bad = []
    missing = sorted(set(in_extract) - set(status))
    if missing:
        bad.append(f"{len(missing)} Endur'O system(s) in the extract have no status in "
                   f"{PIPED['status_file']}: {', '.join(missing[:6])}")
    for code, e in sorted(status.items()):
        if e.get("status") not in STATES:
            bad.append(f"{code}: status {e.get('status')!r} is not one of {', '.join(STATES)}")
        for k in ("works_complete", "post_rehab_test"):
            v = e.get(k)
            if v is not None and not (isinstance(v, str) and len(v) == 10 and v[:2] == "20"):
                bad.append(f"{code}: {k} {v!r} is not a YYYY-MM-DD date")
    return bad


def summary(results):
    cfu = sorted(q for q in (qty(r, Q_ECOLI) for _c, r, _d in results) if q is not None)
    chl = [qty(r, Q_CHLORINE) for _c, r, _d in results]
    dates = sorted(d for _c, _r, d in results if d)
    meets = sum(1 for q in cfu if q <= ECOLI_PASS_MAX)
    return {"results": len(results),
            "systems": len({c for c, _r, _d in results}),
            "meets": meets, "exceeds": len(cfu) - meets,
            "no_result": len(results) - len(cfu),
            "meets_pct": round(100 * meets / len(cfu), 1) if cfu else None,
            "median_cfu": statistics.median(cfu) if cfu else None,
            "max_cfu": cfu[-1] if cfu else None,
            "chlorine_measured": sum(1 for c in chl if c is not None),
            "chlorine_zero": sum(1 for c in chl if c == 0),
            "rounds": len(set(dates)),
            "first": dates[0] if dates else None, "last": dates[-1] if dates else None,
            "tap_recorded": sum(1 for _c, r, _d in results if site_code(answer(r, Q_TAP)))}


def build():
    rows = json.load(open(os.path.join(EXPORTS, "wq_results_piped.json"), encoding="utf8"))
    man = json.load(open(os.path.join(REPO, "data", "extract_manifest.json"), encoding="utf8"))["files"]
    status = json.load(open(STATUS, encoding="utf8"))["systems"]
    ext = extract_systems()
    bad = status_problems(status, ext)
    if bad:
        raise RuleBroken("; ".join(bad))
    with io.open(os.path.join(EXPORTS, "wp_madavance.csv"), encoding="utf8") as fh:
        reg = {r["code"] for r in csv.DictReader(fh) if r.get("code")}

    by_sys, excl = {}, {"not_final": [], "no_site": [], "hand_pump_on_piped_form": [],
                        "not_an_operator_system": []}
    for r in rows:
        if r.get("form") != PIPED["wq_form"]:
            continue
        code = site_code(answer(r, Q_SYSTEM))
        if r.get("status") != "final":
            excl["not_final"].append(r["_id"]); continue
        if not code:
            excl["no_site"].append(r["_id"]); continue
        if code not in status:
            (excl["hand_pump_on_piped_form"] if code in reg
             else excl["not_an_operator_system"]).append((code, r["_id"]))
            continue
        by_sys.setdefault(code, []).append((code, r, result_date(r)))

    systems, managed_res, baseline_res, not_managed_res = {}, [], [], []
    for code, e in sorted(status.items()):
        res = by_sys.get(code, [])
        works = e.get("works_complete")
        post = [x for x in res if works and x[2] and x[2] > works]
        base = [x for x in res if x not in post]
        tested = bool(post) or bool(e.get("post_rehab_test"))
        if e["status"] == "not_managed":
            eff = "not_managed"
        elif works and tested:
            eff = "managed"          # joins by the rule, whatever was declared
        elif e["status"] == "managed":
            raise RuleBroken(f"{code} ({e.get('name')}) is declared managed but "
                             + ("has no works_complete date" if not works
                                else "has no post-rehabilitation test after " + works))
        else:
            eff = "in_process"
        systems[code] = {"name": e.get("name") or ext.get(code), "declared": e["status"],
                         "status": eff, "works_complete": works,
                         "post_rehab_first": (min(d for _c, _r, d in post) if post
                                              else e.get("post_rehab_test")),
                         "results_post": len(post), "results_baseline": len(base)}
        if eff == "managed":
            managed_res += post
            baseline_res += base          # the system's own baseline stays baseline
        elif eff == "in_process":
            baseline_res += base
        else:
            not_managed_res += res

    counts = {s: sum(1 for v in systems.values() if v["status"] == s) for s in STATES}
    b_by = {}
    for code, r, d in baseline_res:
        q = qty(r, Q_ECOLI)
        x = b_by.setdefault(code, {"name": systems[code]["name"], "results": 0,
                                   "meets": 0, "exceeds": 0, "first": d, "last": d})
        x["results"] += 1
        if q is not None:
            x["meets" if q <= ECOLI_PASS_MAX else "exceeds"] += 1
        x["first"], x["last"] = min(x["first"], d), max(x["last"], d)
    return {
        "note": "Written by tools/rebuild_piped_wq.py. Managed = post-rehabilitation results "
                "of systems that met the join rule; baseline = results dated on or before a "
                "system's works completion, which never count toward a managed figure.",
        "form": PIPED["wq_form"],
        "pulled": str((man.get("wq_results_piped.json") or {}).get("written") or "")[:10] or None,
        "responses": len(rows),
        "status_counts": counts,
        "in_process_names": [v["name"] for v in systems.values() if v["status"] == "in_process"],
        "managed": summary(managed_res),
        "baseline": {**summary(baseline_res), "by_system": dict(sorted(b_by.items()))},
        "not_managed_results": len(not_managed_res),
        "systems": systems,
        "excluded": {
            "not_final": {"n": len(excl["not_final"])},
            "no_site": {"n": len(excl["no_site"])},
            "hand_pump_on_piped_form": {
                "n": len(excl["hand_pump_on_piped_form"]),
                "codes": sorted({c for c, _i in excl["hand_pump_on_piped_form"]}),
                "responses": sorted(i for _c, i in excl["hand_pump_on_piped_form"])},
            "not_an_operator_system": {
                "n": len(excl["not_an_operator_system"]),
                "codes": sorted({c for c, _i in excl["not_an_operator_system"]})}},
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    try:
        doc = build()
    except RuleBroken as e:
        print(f"rebuild_piped_wq: REFUSED - {e}")
        return 1
    new = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    old = open(OUT, encoding="utf8").read() if os.path.isfile(OUT) else ""
    if new == old:
        print("data/piped_wq.json unchanged")
        return 0
    if mode != "--write":
        print("data/piped_wq.json DIFFERS from the extract")
        return 1
    open(OUT, "w", encoding="utf8").write(new)
    c = doc["status_counts"]
    print(f"data/piped_wq.json: managed {c['managed']}, in process {c['in_process']}, "
          f"not managed {c['not_managed']}; {doc['managed']['results']} managed result(s), "
          f"{doc['baseline']['results']} baseline, "
          f"{doc['excluded']['hand_pump_on_piped_form']['n']} filed on the wrong form")
    return 0


if __name__ == "__main__":
    sys.exit(main())
