# -*- coding: utf-8 -*-
"""Count the Marolinta works from the borehole-progress form, by deployment.

The Marolinta scope used to report 5 water points and 1,441 people. Both
measured the wrong thing: 5 is the intersection of Marolinta with the actively
managed register - the five boreholes that appear in the 736 reconciliation as
"actively managed but never first-rehabilitated" - and 1,441 was a WorldPop
allocation over those five. Neither counts the work.

The form is deployed twice, and that matters: an earlier project note assumed
all 18 responses were Marolinta. They are not.

    2b408dd532e944ad91c0bb77cd6ad576  Marolinta   13 responses, all final
    e8bbe3b104bb4b599132c435013ab219  Moramanga    5 responses, 1 final + 4 draft

So the four drafts and one of the "new construction" records belong to
Moramanga, not Marolinta, and are owned by the Moramanga section.

    python3 tools/marolinta_works.py --write | --show
"""
import collections, datetime, json, os, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "marolinta_works.json")
CLI = os.path.expanduser("~/mwater-mcp/cli_call.mjs")
FORM = "8764843c94484f5b984078c68f13b2ca"
Q_TYPE = "660d59b922d843b1a6f51676ad2ccd14"
Q_STATUS = "0a46051cee394b46ad1e7478dd40117a"
TYPES = {"xl1VJVT": "Nouvelle construction", "TFTjqNm": "Réhabilitation"}
STATUS = {"56EZb1R": "Fonctionnel", "7fhSPYA": "Partiellement fonctionnel",
          "Xs6NRnN": "Non fonctionnel", "gKAG9hH": "En construction"}
DEPLOY = {"2b408dd532e944ad91c0bb77cd6ad576": "Marolinta",
          "e8bbe3b104bb4b599132c435013ab219": "Moramanga"}
# what Jan reported to date, against which the shortfall is measured
REPORTED = {"Nouvelle construction": 10, "Réhabilitation": 10}


def call(tool, args):
    r = subprocess.run(["node", CLI, tool, json.dumps(args)],
                       capture_output=True, text=True, cwd=os.path.dirname(CLI))
    s = r.stdout
    return json.loads(s[s.index("["):]) if "[" in s else []


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--show"
    if mode == "--show":
        print(json.dumps(json.load(open(OUT)), indent=1, ensure_ascii=False)
              if os.path.isfile(OUT) else "no data/marolinta_works.json yet")
        return 0
    if mode != "--write":
        sys.exit("usage: marolinta_works.py --write | --show")
    rs = call("mwater_responses", {"form_id": FORM, "limit": 200})
    recs = []
    for r in rs:
        d = r.get("data") or {}
        code = next((e.get("value") for e in (r.get("entities") or [])
                     if e.get("property") == "code"), None)
        recs.append({
            "code": code,
            "deployment": DEPLOY.get(r.get("deployment"), r.get("deployment")),
            "record_status": r.get("status"),
            "type": TYPES.get((d.get(Q_TYPE) or {}).get("value")),
            "functional_status": STATUS.get((d.get(Q_STATUS) or {}).get("value")),
            "submitted": (r.get("submittedOn") or "")[:10] or None,
            "by": r.get("username"),
        })
    out = {"checked": datetime.date.today().isoformat(),
           "form": FORM, "responses": len(recs),
           "deployments": DEPLOY, "reported_to_date": REPORTED,
           "records": sorted(recs, key=lambda x: (x["deployment"] or "",
                                                  x["type"] or "",
                                                  x["code"] or ""))}
    for dep in set(DEPLOY.values()):
        sub = [x for x in recs if x["deployment"] == dep]
        fin = [x for x in sub if x["record_status"] == "final"]
        dra = [x for x in sub if x["record_status"] == "draft"]
        by_type = collections.Counter(x["type"] for x in fin)
        out[dep.lower()] = {
            "responses": len(sub),
            "final": len(fin), "draft": len(dra),
            "points_final": len({x["code"] for x in fin if x["code"]}),
            "points_draft": len({x["code"] for x in dra if x["code"]}),
            "by_type_final": dict(by_type),
            "shortfall": {k: max(0, v - by_type.get(k, 0))
                          for k, v in REPORTED.items()} if dep == "Marolinta" else {},
            "blank_functional_status": sum(
                1 for x in sub if not x["functional_status"]),
            "codes_final": sorted({x["code"] for x in fin if x["code"]}),
            "codes_draft": sorted({x["code"] for x in dra if x["code"]}),
        }
    json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False, sort_keys=True)
    for dep in ("Marolinta", "Moramanga"):
        s = out[dep.lower()]
        print(f"{dep}: {s['responses']} responses, {s['final']} final, "
              f"{s['draft']} draft, {s['points_final']} point(s) delivered, "
              f"by type {s['by_type_final']}, "
              f"{s['blank_functional_status']} blank functional status")
        if s["shortfall"]:
            print(f"   shortfall against {REPORTED}: {s['shortfall']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
