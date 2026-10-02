#!/usr/bin/env python3
"""The 2025 household water-quality round (SDWS 18), computed from the survey.

Form db0bcbf2 ("Clean Water || project SDWS18 || Survey || Active"). The round
is its FINAL records on the deployments "SDWS18 (Fort-Dauphin)" and "SDWS18
(Maroantsetra)"; drafts are left out. Every figure the section renders comes
from here, into data/sdws18.json.

PASS RULE (Water Quality Protocol v2.1 s.5.1; ERSDWS v2.0 s.3.2.3.2): a
household (point-of-use) sample passes at fewer than 10 E. coli per 100 ml,
the WHO low-risk band; a pump or tap (point-of-collection) sample passes only
at 0. The 2025 records carry no test-type answer - the question was added in
the 2026 revision - but every one is linked to a household and carries the
household's GPS, so all 140 are household samples. The stricter "0 E. coli"
rate is computed as information only; it is NOT the pass rule. The form's own
pass field (f8fac23f) still checks against 0 (act-pou-form-threshold).

Intervals are exact (Clopper-Pearson), two-sided 90%, by bisection on the
binomial tail, so no statistics library is needed.

The six-month rule is reported both ways while James Walker rules on which
start date it counts from (act-sdws18-james-rulings): per pump, from that
pump's first passing SDWS 3 result; and from the programme start, the first
passing SDWS 3 result anywhere in the fleet.

Household-to-pump distances are computed from the household GPS and the
register position and published only as kilometres, never as coordinates.

    python3 tools/rebuild_sdws18.py            # show
    python3 tools/rebuild_sdws18.py --write
"""
import collections, csv, datetime, json, math, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import populations as P

REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "data", "sdws18.json")
SRC = os.path.expanduser("~/mwater-exports/pou_survey.json")
FORM = "db0bcbf2e7ea44b280aed653a715553e"
DEPLOY = {"29e0af71ad54476b9f9983d6881edcff": "Fort-Dauphin",
          "1db2bb644ef741b2b95598a34c66020e": "Maroantsetra"}
Q_ECOLI = "d1c45da19c6d4cc5b895f6270e2631d7"      # E. coli per 100 ml (result)
Q_DATE = "9cba772b36884254b52dbc1295741213"       # date of sample collection
Q_HH_GPS = "84b2d344cc9f4f9a8c816d21feb89377"     # household GPS
Q_COMMENT = "59974805f47348658142d966d8a54c2b"
POU_PASS_LT = 10          # per 100 ml, household sample
FAR_KM = 1.0              # a household this far from its pump is flagged
SDWS3_RESULT_DATE = "630ccd46f76f"                # SDWS 3 result form, prefixes
SDWS3_ECOLI = "892f1d81bf1a"


def binom_cdf(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def ci90(k, n):
    """Exact two-sided 90% interval for k of n (Clopper-Pearson)."""
    def solve(f):
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) else (lo, mid)
        return (lo + hi) / 2
    low = 0.0 if k == 0 else solve(lambda p: 1 - binom_cdf(k - 1, n, p) < 0.05)
    high = 1.0 if k == n else solve(lambda p: binom_cdf(k, n, p) > 0.05)
    return [round(100 * low, 1), round(100 * high, 1)]


def val(r, q):
    v = (r.get("data") or {}).get(q)
    return v.get("value") if isinstance(v, dict) else v


def entity(r, etype):
    for e in r.get("entities") or []:
        if e.get("entityType") == etype:
            return e.get("value")
    return None


def km(a_lat, a_lon, b_lat, b_lon):
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def register_positions():
    out = {}
    with open(os.path.expanduser("~/mwater-exports/wp_madavance.csv"), encoding="utf8",
              errors="replace") as fh:
        for r in csv.DictReader(fh):
            try:
                c = json.loads(r.get("location") or "null")["coordinates"]
                out[str(r["code"])] = (c[1], c[0])
            except (KeyError, TypeError, ValueError, IndexError):
                pass
    return out


# James Walker, "Re: Water program dashboard & actions", 1 Oct 2026 09:33 UTC:
# the six-month rule counts per pump from its installation or rehabilitation
# date, and applies in every annual round. The date is the works record's:
# "Date de début des travaux" on the first-rehabilitation record (a successful
# one first), or the works date on the borehole-progress form for a point
# built or rehabilitated there.
Q_WORKS_DATE = "fd61cf9286954462a0fb1ab5de12e643"     # combined form, "Date de début des travaux"
Q_BOREHOLE_DATE = "86fc2a6da162"                     # borehole-progress form, 1.2 date of works (prefix)


def works_dates():
    """water point -> (date, source) of the works that put it into service."""
    succ, any_ = {}, {}
    for r in P._combined():
        if (r.get("status") or "final") != "final" or P._answer(r, P.Q_TYPE) != P.C_FIRST_REHAB:
            continue
        w = P._point_of(r)
        d = str(val(r, Q_WORKS_DATE) or "")[:10]
        if not (w and d[:2] == "20"):
            continue
        if not any_.get(w) or d < any_[w]:
            any_[w] = d
        if P._answer(r, P.Q_SUCCESS) == P.C_YES and (not succ.get(w) or d < succ[w]):
            succ[w] = d
    out = {w: (d, "first rehabilitation, successful") for w, d in succ.items()}
    out.update({w: (d, "first rehabilitation") for w, d in any_.items() if w not in out})
    for r in P._borehole():
        if (r.get("status") or "final") != "final":
            continue
        w = P._point_of(r)
        d = next((str((v.get("value") if isinstance(v, dict) else v) or "")[:10]
                  for k, v in (r.get("data") or {}).items() if k.startswith(Q_BOREHOLE_DATE)), "")
        if w and d[:2] == "20" and w not in out:
            out[w] = (d, "borehole works")
    return out


def six_months_after(d):
    y, m = d.year + (d.month + 5) // 12, (d.month + 5) % 12 + 1
    return datetime.date(y, m, min(d.day, 28))


def pulled_on():
    """The date the survey extract was pulled, from the extract manifest."""
    try:
        m = json.load(open(os.path.join(REPO, "data", "extract_manifest.json"), encoding="utf8"))
        e = (m.get("files") or {}).get("pou_survey.json") or {}
        return str(e.get("written") or "")[:10] or None
    except (OSError, ValueError, AttributeError):
        return None


def records():
    return [r for r in json.load(open(SRC, encoding="utf8"))
            if r.get("status") == "final" and r.get("deployment") in DEPLOY]


def build():
    pos = register_positions()
    fleet = {p["wp"] for p in P._page_pumps()}
    works = works_dates()
    by = collections.defaultdict(list)
    for r in records():
        by[DEPLOY[r["deployment"]]].append(r)
    out = {}
    for site in ("Fort-Dauphin", "Maroantsetra"):
        R = by.get(site, [])
        vals = [val(r, Q_ECOLI) for r in R]
        n = len(R)
        passing = sum(1 for v in vals if isinstance(v, (int, float)) and v < POU_PASS_LT)
        zero = sum(1 for v in vals if v == 0)
        dates = sorted(str(val(r, Q_DATE) or "")[:10] for r in R)
        wps = sorted({entity(r, "water_point") for r in R} - {None})
        hhs = {entity(r, "household") for r in R} - {None}
        dist, far = [], []
        for r in R:
            g, w = val(r, Q_HH_GPS), entity(r, "water_point")
            c = ((g.get("latitude"), g.get("longitude")) if isinstance(g, dict)
                 and g.get("latitude") is not None else None)
            if c and w in pos:
                d = km(c[0], c[1], *pos[w])
                dist.append(d)
                if d > FAR_KM:
                    far.append({"code": r.get("code"), "rid": r.get("_id"), "water_point": w,
                                "km": round(d, 2)})
        positives = [{"code": r.get("code"), "rid": r.get("_id"), "date": str(val(r, Q_DATE) or "")[:10],
                      "water_point": entity(r, "water_point"), "ecoli": val(r, Q_ECOLI),
                      "passes": val(r, Q_ECOLI) < POU_PASS_LT,
                      "comment": val(r, Q_COMMENT)}
                     for r in R if isinstance(val(r, Q_ECOLI), (int, float)) and val(r, Q_ECOLI) > 0]
        # the six-month rule, per pump (James Walker, 1 Oct 2026): from that pump's
        # installation or rehabilitation date to the first household sample at it
        first_sample = {}
        for r in R:
            w, d = entity(r, "water_point"), str(val(r, Q_DATE) or "")[:10]
            if w and d and (w not in first_sample or d < first_sample[w]):
                first_sample[w] = d
        per_pump = {}
        for w in wps:
            wd, src = works.get(w, (None, None))
            s = first_sample.get(w)
            ok = (None if not (wd and s) else
                  datetime.date.fromisoformat(s) >= six_months_after(datetime.date.fromisoformat(wd)))
            per_pump[w] = {"works_date": wd, "works_source": src, "first_sample": s,
                           "days_after_works": ((datetime.date.fromisoformat(s) - datetime.date.fromisoformat(wd)).days
                                                if wd and s else None),
                           "six_months": ok}
        out[site] = {
            "tests": n, "first": dates[0] if dates else None, "last": dates[-1] if dates else None,
            "water_points": len(wps), "households": len(hhs),
            "in_managed_fleet": sum(1 for w in wps if w in fleet),
            "ecoli": {"0": sum(1 for v in vals if v == 0),
                      "1-9": sum(1 for v in vals if isinstance(v, (int, float)) and 0 < v < 10),
                      "10+": sum(1 for v in vals if isinstance(v, (int, float)) and v >= 10)},
            "pass": passing, "pass_pct": round(100 * passing / n, 1) if n else None,
            "pass_ci90": ci90(passing, n) if n else None,
            "zero": zero, "zero_pct": round(100 * zero / n, 1) if n else None,
            "zero_ci90": ci90(zero, n) if n else None,
            "positives": positives,
            "distance_median_km": round(statistics.median(dist), 2) if dist else None,
            "far_households": far,
            "six_months_inside": sum(1 for v in per_pump.values() if v["six_months"] is True),
            "six_months_outside": sum(1 for v in per_pump.values() if v["six_months"] is False),
            "six_months_no_works_date": sum(1 for v in per_pump.values() if v["six_months"] is None),
            "pumps": per_pump,
        }
    rec_rows = []
    for site in ("Fort-Dauphin", "Maroantsetra"):
        far_ids = {f["rid"] for f in out[site]["far_households"]}
        far_km = {f["rid"]: f["km"] for f in out[site]["far_households"]}
        for r in by.get(site, []):
            e = val(r, Q_ECOLI)
            rec_rows.append({"district": site, "rid": r.get("_id"), "code": r.get("code"),
                             "water_point": entity(r, "water_point"),
                             "household": entity(r, "household"),
                             "date": str(val(r, Q_DATE) or "")[:10] or None,
                             "ecoli": e,
                             "pass": isinstance(e, (int, float)) and e < POU_PASS_LT,
                             "positive": isinstance(e, (int, float)) and e > 0,
                             "gps_flag": r.get("_id") in far_ids,
                             "km": far_km.get(r.get("_id")),
                             "comment": val(r, Q_COMMENT)})
    tot_n = sum(v["tests"] for v in out.values())
    tot_pass = sum(v["pass"] for v in out.values())
    tot_zero = sum(v["zero"] for v in out.values())
    return {
        "note": "Written by tools/rebuild_sdws18.py from the household water-quality survey. "
                "No coordinates: distances only.",
        "form": FORM, "round": "2025",
        "pass_rule": {"pou_lt_per_100ml": POU_PASS_LT, "poc_eq": 0,
                      "source": "Water Quality Protocol v2.1 section 5.1; ERSDWS v2.0 section 3.2.3.2"},
        "six_month_rule": {"from": "each pump's installation or rehabilitation date (works record)",
                           "applies": "every annual round",
                           "source": "James Walker, \"Re: Water program dashboard & actions\", 1 Oct 2026 09:33 UTC"},
        "ci_level_pct": 90,
        "far_km": FAR_KM,
        "districts": out,
        "total": {"tests": tot_n, "pass": tot_pass,
                  "pass_pct": round(100 * tot_pass / tot_n, 1) if tot_n else None,
                  "pass_ci90": ci90(tot_pass, tot_n) if tot_n else None,
                  "zero": tot_zero, "zero_pct": round(100 * tot_zero / tot_n, 1) if tot_n else None},
        # every record of the round, for the record table: one row per response,
        # linked to it in mWater. No coordinates, no respondent names.
        "records": sorted(rec_rows, key=lambda x: (x["district"], x["date"] or "", x["water_point"] or "", x["household"] or "")),
        "extract_pulled": pulled_on(),
        "not_recorded": ["kit and lot", "test method", "sample source (stored container or not)",
                         "a paired pump (point-of-collection) sample", "field blanks", "duplicates"],
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--show"
    doc = build()
    txt = json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    for s, v in doc["districts"].items():
        print(f"  {s}: {v['tests']} tests {v['first']}..{v['last']}, {v['water_points']} points, "
              f"{v['households']} households; pass {v['pass']} ({v['pass_pct']}%, 90% CI {v['pass_ci90']}); "
              f"0 E. coli {v['zero']} ({v['zero_pct']}%); positives {[p['ecoli'] for p in v['positives']]}; "
              f"far {[f['km'] for f in v['far_households']]}; six-month rule inside {v['six_months_inside']}, outside {v['six_months_outside']}, no works date {v['six_months_no_works_date']} of {v['water_points']}")
    if mode == "--write":
        open(OUT, "w", encoding="utf8").write(txt)
        print("data/sdws18.json written")
        return 0
    if mode == "--check":
        ok = os.path.isfile(OUT) and open(OUT, encoding="utf8").read() == txt
        print("data/sdws18.json " + ("matches the extract" if ok else "is stale"))
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
