#!/usr/bin/env python3
"""The proposed India Mark capacity rule, evaluated per pump (29 Sep 2026).

PROPOSED - awaiting James Walker's confirmation (email 28 Sep 2026). Nothing
here enters a carbon figure: the applied India Mark cap stays PARAMS.im_cap
(300) until James confirms in writing (act-india-mark-cap-james). The page
shows the proposed figures beside the current ones, read from this file.

THE RULE. 500 people per India Mark pump where the water depth is 20 m or
less, or a measured discharge test shows at least 16.6 l/min; otherwise 300.
Evidence: the Sphere Handbook (500 people per hand pump at 16.6 l/min, about
8 hours a day) and the India Mark II rated-flow table (30 l/min at 10 m, 21.7
at 15 m, 16.7 at 20 m, 15.0 at 25 m) - 20 m is the depth at which the rated
flow still meets Sphere's 16.6 l/min.

WHAT THE RECORDS CAN SHOW. No form records the water depth itself. The works
form (retired combined form 86cf66ef) records the pump installation depth,
"Profondeur de la pompe en metre" (ea5221c7, required). The pump cylinder is
set below the water level, so a pump installed at 20 m or less means water at
20 m or less: that side of the rule is decided from the record. A pump set
deeper may still draw from shallower water, but the record cannot show it, so
it stays at 300 until a depth or discharge is measured. The discharge side is
not evaluated: the form's "Debit" (4a73f824) carries no unit and is not a
timed hand-pump discharge test, so no pump qualifies on it. The latest final
works record with a pump depth governs.

    python3 tools/india_mark_cap.py --write   # data/india_mark_cap.json
    python3 tools/india_mark_cap.py --check   # exit 1 if the file is stale
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import populations as P

REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "data", "india_mark_cap.json")
Q_PUMP_DEPTH = "ea5221c7353448f6a3d6d8c5338ac7f8"
DEPTH_MAX_M = 20
FLOW_MIN_LPM = 16.6
CAP_PROPOSED, CAP_CURRENT = 500, 300


def build():
    im = {p["wp"] for p in P._page_pumps() if p.get("pump") == "IndiaMark"}
    latest = {}
    for r in P._combined():
        wp = P._point_of(r)
        if wp not in im or (r.get("status") or "final") != "final":
            continue
        d = P._answer(r, Q_PUMP_DEPTH)
        if not isinstance(d, (int, float)):
            continue
        when = str(r.get("submittedOn") or "")[:10]
        if wp not in latest or when > latest[wp]["date"]:
            latest[wp] = {"pump_depth_m": d, "date": when, "rid": r.get("_id")}
    points = {}
    for wp in sorted(im):
        e = latest.get(wp)
        if e and e["pump_depth_m"] <= DEPTH_MAX_M:
            basis = "pump installed at %g m, so water at 20 m or less" % e["pump_depth_m"]
            cap = CAP_PROPOSED
        elif e:
            basis = "pump installed at %g m: water depth not shown, no discharge test" % e["pump_depth_m"]
            cap = CAP_CURRENT
        else:
            basis = "no pump depth on record, no discharge test"
            cap = CAP_CURRENT
        points[wp] = dict(e or {}, proposed_cap=cap, basis=basis)
    n = len(points)
    return {
        "note": "Written by tools/india_mark_cap.py. PROPOSED rule, not applied to any carbon figure.",
        "status": "proposed - awaiting James Walker's confirmation (email 28 Sep 2026)",
        "action": "act-india-mark-cap-james",
        "rule": ("500 people per India Mark pump where the water depth is 20 m or less, or a "
                 "measured discharge test shows at least 16.6 l/min; otherwise 300"),
        "evidence": ["Sphere Handbook: 500 people per hand pump at 16.6 l/min, about 8 hours a day",
                     "India Mark II rated flow: 30 l/min at 10 m, 21.7 at 15 m, 16.7 at 20 m, 15.0 at 25 m"],
        # the evidence as figures, so the page renders them from here
        "sphere": {"people_per_hand_pump": 500, "flow_lpm": 16.6, "hours_per_day": 8,
                   "source": "Sphere Handbook, water supply standard: 500 people per hand pump, "
                             "flow 16.6 l/min, about 8 hours a day"},
        "rated_flow": {"source": "India Mark II rated-flow table", "unit": "l/min at pumping depth (m)",
                       "rows": [[10, 30], [15, 21.7], [20, 16.7], [25, 15.0]]},
        "depth_max_m": DEPTH_MAX_M, "flow_min_lpm": FLOW_MIN_LPM,
        "cap_proposed": CAP_PROPOSED, "cap_current": CAP_CURRENT,
        "depth_source": "retired combined works form 86cf66ef, question ea5221c7 (pump installation depth, m)",
        "counts": {"india_mark": n,
                   "with_pump_depth": sum(1 for p in points.values() if "pump_depth_m" in p),
                   "qualify_depth": sum(1 for p in points.values() if p["proposed_cap"] == CAP_PROPOSED),
                   "qualify_discharge": 0,
                   "stay_300": sum(1 for p in points.values() if p["proposed_cap"] == CAP_CURRENT)},
        "points": points,
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    want = json.dumps(build(), indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    have = open(OUT, encoding="utf8").read() if os.path.isfile(OUT) else ""
    if mode == "--write":
        open(OUT, "w", encoding="utf8").write(want)
        c = json.loads(want)["counts"]
        print(f"data/india_mark_cap.json: {c['qualify_depth']} of {c['india_mark']} India Mark pumps "
              f"qualify for 500 on pump depth; {c['stay_300']} stay at 300 (proposed only)")
        return 0
    if want == have:
        print("data/india_mark_cap.json matches the extract")
        return 0
    print("data/india_mark_cap.json is stale: python3 tools/india_mark_cap.py --write")
    return 1


if __name__ == "__main__":
    sys.exit(main())
