# -*- coding: utf-8 -*-
"""Tests for the SDWS 3 creditable rule (tools/sdws3_creditable.py).

The cases are data/sdws3_rule_cases.json, byte-identical in sanitap-sampler,
whose own implementation must give the same verdicts. A point with no final
result has no verdict at all: the rule does not touch it.

    python3 tools/test_sdws3_creditable.py
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sdws3_creditable as SC  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def response(r, rule):
    data = {rule["form"]["site_q"]: {"value": {"code": r["wp"]}},
            rule["form"]["date_q"]: {"value": r["date"] + "T09:00:00Z"}}
    q = {t["key"]: t["q"] for t in rule["fail_if"]}
    for k, v in r["values"].items():
        data[q[k]] = {"value": v}
    return {"_id": r["code"].lower(), "code": r["code"], "form": rule["form"]["id"],
            "status": r.get("status", "final"), "submittedOn": r.get("submitted", r["date"] + "T10:00:00Z"),
            "data": data}


def main():
    rule, _ = SC.load_rule()
    cases = json.load(open(os.path.join(REPO, "data", "sdws3_rule_cases.json"), encoding="utf8"))["cases"]
    bad = 0
    for c in cases:
        got = SC.evaluate([response(r, rule) for r in c["results"]], rule)
        got = {wp: {"creditable": v["creditable"], "failing": sorted(f["key"] for f in v["failing"])}
               for wp, v in got.items()}
        ok = got == c["expect"]
        bad += not ok
        print(("ok    " if ok else "FAIL  ") + c["name"] + ("" if ok else f"\n      want {c['expect']}\n      got  {got}"))
    # the exception names its reason, and the rule names its decision
    exc = rule["exceptions"][0]
    for name, ok in (("the exception carries its reason", bool(exc.get("reason"))),
                     ("the rule names its decision", rule["decision"]["by"].startswith("James Walker"))):
        bad += not ok
        print(("ok    " if ok else "FAIL  ") + name)
    print(f"{len(cases) + 2 - bad} passed, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
