# -*- coding: utf-8 -*-
"""The piped water-quality figures, from the piped SDWS 3 result form.

Until 25 September the piped-scheme result form (0ac68d82, "Piped Water ||
Water Quality Testing_SDWS 3__Result") was read by nothing: the page had no
water-quality figure for a piped system at all. This reads every response the
build pulled and keeps the ones that belong to the actively managed piped
estate, by the rule in data/build_config.json ("piped"):

  - the response is final;
  - the site it names (question 1.2, "Water System ID") is a water system in
    Endur'O's mWater group, placed by data from the same build
    (piped_systems.csv, pulled by tools/pull_extract.py);
  - that system lies outside Antananarivo, whose kiosks the page keeps out of
    scope as diagnosed and not under management.

Everything else is counted and named, never dropped silently. A site that is a
MadAvance hand pump is reported as filed on the wrong form: its result belongs
on the hand-pump result form, where the hand-pump figures would see it.

E. coli is question 1.4, in CFU/100 ml; a sample passes at or below the
build's threshold (water_quality.ecoli_pass_max_cfu_per_100ml), the same rule
the hand-pump figures apply.

    python3 tools/rebuild_piped_wq.py --write
    python3 tools/rebuild_piped_wq.py --check
"""
import csv, io, json, math, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS = os.path.expanduser("~/mwater-exports")
OUT = os.path.join(REPO, "data", "piped_wq.json")
CFG = json.load(open(os.path.join(REPO, "data", "build_config.json"), encoding="utf8"))
PIPED = CFG["piped"]
ECOLI_PASS_MAX = CFG["water_quality"]["ecoli_pass_max_cfu_per_100ml"]

Q_TEST = "10269a22"      # 1.1 which test: Complet / Partial
Q_SYSTEM = "a3390d2e"    # 1.2 Water System ID
Q_TAP = "7d0fce72"       # 1.2b Water point ID
Q_ECOLI = "892f1d81"     # 1.4 E. coli, CFU/100 ml
Q_CHLORINE = "0594065a"  # free residual chlorine (no question code on the form)
TEST_LABEL = {"SMzfGnP": "complete", "yackNP9": "partial"}


def answer(resp, prefix):
    for k, v in (resp.get("data") or {}).items():
        if k.startswith(prefix):
            return (v or {}).get("value")
    return None


def site_code(v):
    return str(v.get("code")) if isinstance(v, dict) and v.get("code") else None


def km(a, b):
    (la1, lo1), (la2, lo2) = [(math.radians(x), math.radians(y)) for x, y in (a, b)]
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def systems():
    out = {}
    with io.open(os.path.join(EXPORTS, "piped_systems.csv"), encoding="utf8") as fh:
        for r in csv.DictReader(fh):
            if r.get("_managed_by") != PIPED["operator_group"] or not r.get("code"):
                continue
            loc = json.loads(r["location"]) if r.get("location") else None
            lon, lat = (loc or {}).get("coordinates", [None, None])[:2]
            out[r["code"]] = {"name": (r.get("name") or "").strip() or None,
                              "lat": lat, "lon": lon}
    return out


def register_codes():
    with io.open(os.path.join(EXPORTS, "wp_madavance.csv"), encoding="utf8") as fh:
        return {r["code"] for r in csv.DictReader(fh) if r.get("code")}


def build():
    rows = json.load(open(os.path.join(EXPORTS, "wq_results_piped.json"), encoding="utf8"))
    man = json.load(open(os.path.join(REPO, "data", "extract_manifest.json"), encoding="utf8"))["files"]
    sy, reg = systems(), register_codes()
    centre, radius = PIPED["antananarivo_centre_lat_lon"], PIPED["antananarivo_radius_km"]
    kept, excl = [], {"not_final": [], "no_site": [], "hand_pump_on_piped_form": [],
                      "not_an_operator_system": [], "antananarivo": []}
    for r in rows:
        if r.get("form") != PIPED["wq_form"]:
            continue
        code = site_code(answer(r, Q_SYSTEM))
        if r.get("status") != "final":
            excl["not_final"].append(r["_id"]); continue
        if not code:
            excl["no_site"].append(r["_id"]); continue
        if code not in sy:
            excl["hand_pump_on_piped_form" if code in reg
                 else "not_an_operator_system"].append(code); continue
        s = sy[code]
        if s["lat"] is not None and km(centre, (s["lat"], s["lon"])) <= radius:
            excl["antananarivo"].append(code); continue
        kept.append((code, r))

    per = {}
    for code, r in kept:
        e = answer(r, Q_ECOLI)
        q = e.get("quantity") if isinstance(e, dict) else None
        d = str(r.get("submittedOn") or "")[:10]
        p = per.setdefault(code, {"name": sy[code]["name"], "samples": 0, "pass": 0,
                                  "fail": 0, "no_result": 0, "complete": 0,
                                  "partial": 0, "first": d, "last": d,
                                  "km_from_antananarivo": round(km(centre, (sy[code]["lat"], sy[code]["lon"])))})
        p["samples"] += 1
        if q is None:
            p["no_result"] += 1
        elif q <= ECOLI_PASS_MAX:
            p["pass"] += 1
        else:
            p["fail"] += 1
        p[TEST_LABEL.get(answer(r, Q_TEST), "partial")] += 1
        p["first"], p["last"] = min(p["first"], d), max(p["last"], d)
    tot = {k: sum(v[k] for v in per.values()) for k in ("samples", "pass", "fail", "no_result", "complete", "partial")}
    tap = sum(1 for _c, r in kept if site_code(answer(r, Q_TAP)))
    cfu = sorted(q for q in ((answer(r, Q_ECOLI) or {}).get("quantity") for _c, r in kept
                             if isinstance(answer(r, Q_ECOLI), dict)) if q is not None)
    chl = [(answer(r, Q_CHLORINE) or {}).get("quantity") for _c, r in kept
           if isinstance(answer(r, Q_CHLORINE), dict)]
    rounds = sorted({str(r.get("submittedOn") or "")[:10] for _c, r in kept})
    dates = [v["first"] for v in per.values()] + [v["last"] for v in per.values()]
    return {
        "note": "Written by tools/rebuild_piped_wq.py from the piped SDWS 3 result form; "
                "the rule is data/build_config.json 'piped'.",
        "form": PIPED["wq_form"],
        "pulled": str((man.get("wq_results_piped.json") or {}).get("written") or "")[:10] or None,
        "responses": len(rows),
        "in_portfolio": tot["samples"],
        "systems_sampled": len(per),
        "operator_systems": len(sy),
        **{k: tot[k] for k in ("pass", "fail", "no_result", "complete", "partial")},
        "pass_pct": round(100 * tot["pass"] / (tot["pass"] + tot["fail"]), 1) if tot["pass"] + tot["fail"] else None,
        "tap_recorded": tap,
        "rounds": len(rounds),
        "median_cfu": (cfu[len(cfu) // 2] if len(cfu) % 2
                       else (cfu[len(cfu) // 2 - 1] + cfu[len(cfu) // 2]) / 2) if cfu else None,
        "max_cfu": cfu[-1] if cfu else None,
        "chlorine_measured": len([c for c in chl if c is not None]),
        "chlorine_zero": sum(1 for c in chl if c == 0),
        "first": min(dates) if dates else None, "last": max(dates) if dates else None,
        "by_system": dict(sorted(per.items())),
        "excluded": {k: {"n": len(v), "codes": sorted(set(v))[:10] if k != "not_final" and k != "no_site" else []}
                     for k, v in excl.items()},
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    doc = build()
    new = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    old = open(OUT, encoding="utf8").read() if os.path.isfile(OUT) else ""
    if new == old:
        print("data/piped_wq.json unchanged")
        return 0
    if mode != "--write":
        print("data/piped_wq.json DIFFERS from the extract")
        return 1
    open(OUT, "w", encoding="utf8").write(new)
    print(f"data/piped_wq.json: {doc['in_portfolio']} of {doc['responses']} samples in the "
          f"managed piped estate, {doc['systems_sampled']} system(s); "
          + ", ".join(f"{k} {v['n']}" for k, v in doc["excluded"].items() if v["n"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
