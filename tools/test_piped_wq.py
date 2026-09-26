# -*- coding: utf-8 -*-
"""The piped join rule, proved on doctored copies of the status file.

A rule that has never been seen to move a system is not known to work. This
leaves data/piped_systems_status.json untouched: each case writes a copy with
one change, points tools/rebuild_piped_wq.py at it, and checks the outcome
against the real extract.

  1. today's file: nothing managed, every result baseline;
  2. works complete mid-way through the sampled period: the system joins by
     itself, results after that date count as managed, and results on or
     before it stay baseline;
  3. works complete after the last result: still in process, nothing counts;
  4. a system declared managed with no works date: the build fails;
  5. a system in the extract missing from the file: the build fails.

    python3 tools/test_piped_wq.py
"""
import copy, json, os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rebuild_piped_wq as R  # noqa: E402

REAL = json.load(open(R.STATUS, encoding="utf8"))


def run(doc):
    p = os.path.join(tempfile.gettempdir(), "piped_status_test.json")
    json.dump(doc, open(p, "w", encoding="utf8"))
    R.STATUS = p
    try:
        return R.build(), None
    except R.RuleBroken as e:
        return None, str(e)


def main():
    fails = []
    out, err = run(REAL)
    base0 = out["baseline"]["results"] if out else 0
    by_decision = sum(1 for e in REAL["systems"].values()
                      if e["status"] == "managed" and e.get("admitted_by_decision"))
    print(f"1. today: managed {out['status_counts']['managed']} "
          f"({by_decision} by decision), managed results {out['managed']['results']}, "
          f"baseline {base0}")
    if err or out["status_counts"]["managed"] != by_decision:
        fails.append("today's file should manage only the systems admitted by decision")
    sampled = [c for c, v in out["systems"].items() if v["results_baseline"]]
    if not sampled:
        print("no sampled system to test with"); return 2
    code = sampled[0]
    dates = sorted(d for d in (R.result_date(r) for r in json.load(open(
        os.path.join(R.EXPORTS, "wq_results_piped.json"), encoding="utf8"))
        if R.site_code(R.answer(r, R.Q_SYSTEM)) == code) if d)
    mid = dates[len(dates) // 2]
    after = sum(1 for d in dates if d > mid)

    doc = copy.deepcopy(REAL); doc["systems"][code]["works_complete"] = mid
    out, err = run(doc)
    s = out["systems"][code]
    print(f"2. works complete {mid}: {code} is {s['status']}; managed results "
          f"{out['managed']['results']} (expected {after}), baseline "
          f"{out['baseline']['results']} (expected {base0 - after})")
    if s["status"] != "managed" or out["managed"]["results"] != after \
            or out["baseline"]["results"] != base0 - after:
        fails.append("works completion mid-period did not split the results by date")

    doc = copy.deepcopy(REAL); doc["systems"][code]["works_complete"] = dates[-1]
    out, err = run(doc)
    s = out["systems"][code]
    print(f"3. works complete on the last result ({dates[-1]}): {s['status']}, "
          f"managed results {out['managed']['results']}")
    if s["status"] != "in_process" or out["managed"]["results"]:
        fails.append("a system with no result after works completion joined")

    doc = copy.deepcopy(REAL); doc["systems"][code]["status"] = "managed"
    out, err = run(doc)
    print(f"4. declared managed, no works date -> {'REFUSED' if err else 'accepted'}")
    if not err:
        fails.append("a system declared managed without meeting the rule was accepted")

    doc = copy.deepcopy(REAL); doc["systems"].pop(code)
    out, err = run(doc)
    print(f"5. {code} removed from the file -> {'REFUSED' if err else 'accepted'}"
          + (f": {err[:90]}" if err else ""))
    if not err:
        fails.append("a system missing from the status file was accepted")

    # 6. admitted by decision: managed at once, but only results after its
    # operational date count; results before it stay baseline
    doc = copy.deepcopy(REAL)
    doc["systems"][code].update({"status": "managed", "admitted_by_decision": "test",
                                 "works_complete": mid})
    out, err = run(doc)
    s = out["systems"][code] if out else {}
    print(f"6. {code} admitted by decision, operational {mid}: {s.get('status')}; "
          f"managed results {out['managed']['results'] if out else '-'} (expected {after}), "
          f"its baseline kept apart {s.get('results_baseline')} (expected {len(dates) - after})")
    if err or s.get("status") != "managed" or out["managed"]["results"] != after \
            or s.get("results_baseline") != len(dates) - after:
        fails.append("a system admitted by decision counted results from before its operational date")

    # 7. once the Curtech dispensing-events feed exists, a system admitted by
    # decision takes its operational date from the first NON-TEST dispense on
    # its device: a test shopkeeper and a test card are both skipped
    kid = next((c for c, e in REAL["systems"].items() if e.get("admitted_by_decision")), None)
    if kid:
        feed = os.path.join(tempfile.gettempdir(), "dispensing_events_test.json")
        json.dump({"events": [
            {"device_id": "DEV-T", "timestamp": "2026-09-08T09:00:00", "shopkeeper": "SK01", "card": "C1", "litres": 20},
            {"device_id": "DEV-T", "timestamp": "2026-09-09T10:00:00", "shopkeeper": "SK03", "card": "TESTCARD", "litres": 20},
            {"device_id": "OTHER", "timestamp": "2026-09-05T08:00:00", "shopkeeper": "SK03", "card": "C9", "litres": 20},
            {"device_id": "DEV-T", "timestamp": "2026-09-16T07:45:00", "shopkeeper": "SK03", "card": "C2", "litres": 20}]},
            open(feed, "w", encoding="utf8"))
        cfg = R.PIPED["dispensing_events"]
        saved = (cfg["path"], list(cfg["test_cards"]))
        cfg["path"], cfg["test_cards"] = feed, ["TESTCARD"]
        doc = copy.deepcopy(REAL); doc["systems"][kid]["devices"] = ["DEV-T"]
        out, err = run(doc)
        cfg["path"], cfg["test_cards"] = saved
        s = out["systems"][kid] if out else {}
        print(f"7. feed present: {kid} operational {s.get('works_complete')} (expected 2026-09-16), "
              f"from the feed: {s.get('operational_from_feed')}")
        if err or s.get("works_complete") != "2026-09-16" or not s.get("operational_from_feed"):
            fails.append("the operational date was not re-derived from the first non-test dispense")

    if fails:
        print("\nTEST FAILED:\n  " + "\n  ".join(fails)); return 1
    print("\nthe join rule holds: baseline never counts, a system joins only after "
          "works and a later test, and the status file must cover the extract.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
