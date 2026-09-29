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
  6-7. a system admitted by decision, and its date from the dispensing feed;
  8-14. pairing by the 72-hour rule, on made-up responses: the pair and what
     it takes from the sample; the window; each sample once, most recent
     first; the date cross-check; outside protocol; pre-completion; baseline
     and the 7-day flag;
  15. the interim kiosk mapping: pre-completion, never closure, flagged as
      an earlier-project record;
  16. the crosswalk: confirmed, suggested, unmatched;
  17. a sample at an old kiosk pairs with the result at its Endur'O point.

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

    # 8-14. pairing by the 72-hour rule (Adriaan Mol, 28 Sep 2026), on made-up
    # responses filed after the tap-level protocol went live
    W, F = R.PIPED["wq_form"], R.SAMPLING_FORM
    TAP, SYS, SAMPLED, RESDATE = ("7d0fce72f2b5eba64004b41c210566af",
                                  "a3390d2e97494b3da193e5c015a879d1",
                                  "b25338d820d94639adb3bcf4c67e4c33",
                                  "630ccd46f76f420692572e0db2d86ad8")
    S_PT, S_SYS, S_T, S_GPS, S_TYPE, S_PHOTO, S_WHERE = (
        "51eca87b7bbbe1ea541070490d4bc186", "a7f6f9e14497435f8601e26ecf4f59ab",
        "630ccd46f76f420692572e0db2d86ad8", "b2875c48657f4173bb7f5783ef3add7c",
        "bf966f97c48b4a4191a5e577be76054f", "e14d9d8b2d7f4acab6edfe6dec57d718",
        "4e8d00a7547c73897fd05e985d236dcf")

    def resp(form, code, data, submitted):
        return {"_id": code, "code": code, "form": form, "status": "final",
                "submittedOn": submitted,
                "data": {k: {"value": v} for k, v in data.items()}}

    def sample(code, point, taken, **extra):
        d = {S_T: taken, S_WHERE: "Qqs6cuQ", S_TYPE: extra.pop("kind", "4hbaZYA")}
        if point:
            d[S_PT] = {"code": point}
        d.update(extra.pop("data", {}))
        return resp(F, code, d, taken)

    def result(code, point, submitted, day=None):
        d = {TAP: {"code": point}} if point else {}
        if day:
            d[SAMPLED] = day
        return resp(W, code, d, submitted)

    def check(n, label, ok, detail):
        print(f"{n}. {label}: {detail}")
        if not ok:
            fails.append(f"case {n}: {label}")

    # 8. a result pairs with its sample and takes GPS, type and photo from it;
    # no coordinates are published
    pub, priv = R.pair(
        [result("R8", "900", "2026-10-02T09:00:00Z", "2026-10-02")],
        [sample("S8", "900", "2026-10-02T06:00:00Z", kind="YZhKDk3",
                data={S_GPS: {"type": "Point", "coordinates": [48.4, -18.9]},
                      S_PHOTO: [{"id": "img1"}]})], "2026-10-03")
    check(8, "pairs on the same water point and takes the sample's GPS, type and photo",
          pub["paired"] == 1 and priv[0]["gps"] and priv[0]["photos"] == ["img1"]
          and priv[0]["point_type"] == "water kiosk" and "coordinates" not in json.dumps(pub),
          f"paired {pub['paired']}, coordinates published: {'coordinates' in json.dumps(pub)}")

    # 9. the 72-hour window: 71 h before pairs, 73 h before does not, and a
    # sample taken after the result was submitted never does
    pub, priv = R.pair(
        [result("R9a", "901", "2026-10-05T11:00:00Z"),
         result("R9b", "902", "2026-10-05T13:00:00Z"),
         result("R9c", "903", "2026-10-05T09:00:00Z")],
        [sample("S9a", "901", "2026-10-02T12:00:00Z"),      # 71 h before
         sample("S9b", "902", "2026-10-02T12:00:00Z"),      # 73 h before
         sample("S9c", "903", "2026-10-05T10:00:00Z")],     # after submission
        "2026-10-06")
    got = sorted(p["result"] for p in priv)
    check(9, f"{R.WINDOW_H} h window", got == ["R9a"]
          and sorted(x["result"] for x in pub["flags"]["result_without_sample"]) == ["R9b", "R9c"],
          f"paired {got}, unpaired {[x['result'] for x in pub['flags']['result_without_sample']]}")

    # 10. each sample pairs once, and a result takes the MOST RECENT unpaired
    # sample: two results and two samples at one tap pair one-to-one
    pub, priv = R.pair(
        [result("R10a", "904", "2026-10-06T08:00:00Z"),
         result("R10b", "904", "2026-10-06T09:00:00Z"),
         result("R10c", "904", "2026-10-06T10:00:00Z")],
        [sample("S10old", "904", "2026-10-05T07:00:00Z"),
         sample("S10new", "904", "2026-10-06T07:00:00Z")], "2026-10-07")
    got = {p["result"]: p["sample"] for p in priv}
    check(10, "each sample pairs once; the most recent unpaired one is taken",
          got == {"R10a": "S10new", "R10b": "S10old"}
          and [x["result"] for x in pub["flags"]["result_without_sample"]] == ["R10c"],
          f"pairs {got}, unpaired {[x['result'] for x in pub['flags']['result_without_sample']]}")

    # 11. result 1.2.2 is a cross-check: two days off keeps the pair with a
    # note, one day off is no mismatch
    pub, priv = R.pair(
        [result("R11a", "905", "2026-10-07T08:00:00Z", "2026-10-04"),
         result("R11b", "906", "2026-10-07T08:00:00Z", "2026-10-05")],
        [sample("S11a", "905", "2026-10-06T08:00:00Z"),
         sample("S11b", "906", "2026-10-06T08:00:00Z")], "2026-10-08")
    check(11, "date mismatch kept as a note", pub["paired"] == 2 and pub["date_mismatch"] == 1
          and pub["flags"]["date_mismatch"][0]["result"] == "R11a",
          f"paired {pub['paired']}, date mismatch {pub['date_mismatch']}")

    # 12. a sample at system level or at a household is flagged outside
    # protocol and never paired, even with a result at the same point
    pub, priv = R.pair(
        [result("R12", "907", "2026-10-08T09:00:00Z")],
        [sample("S12sys", None, "2026-10-08T07:00:00Z", data={S_SYS: {"code": "800"},
                                                               S_WHERE: "kPcXJl9"}),
         sample("S12hh", "907", "2026-10-08T08:00:00Z", kind="YLudYMc")], "2026-10-09")
    check(12, "outside protocol: system-level and household samples",
          pub["paired"] == 0 and sorted(x["sample"] for x in pub["flags"]["outside_protocol"])
          == ["S12hh", "S12sys"],
          f"paired {pub['paired']}, outside protocol {pub['outside_protocol']}")

    # 13. a standpost on a system whose build is under way: a pre-completion
    # test, counted apart
    pub, priv = R.pair(
        [result("R13", "908", "2026-10-09T09:00:00Z")],
        [sample("S13", "908", "2026-10-09T07:00:00Z"),
         sample("S13b", "909", "2026-10-09T07:00:00Z")], "2026-10-10",
        {"908": "1108783583", "909": "1125843376"}, {"1108783583"})
    check(13, "pre-completion classification",
          priv[0]["pre_completion"] and pub["pre_completion"]["paired"] == 1
          and pub["pre_completion"]["samples"] == 1,
          f"pre-completion paired {pub['pre_completion']['paired']}, samples "
          f"{pub['pre_completion']['samples']}")

    # 14. results and samples submitted before the protocol went live are
    # baseline: not paired, flagged or counted, and listed as baseline; a
    # sample with no result after 7 days stays flagged, a recent one waits
    pub, priv = R.pair(
        [result("R14old", "910", "2026-09-01T09:00:00Z")],
        [sample("S14old", "910", "2026-09-01T07:00:00Z"),
         sample("S14late", "911", "2026-10-01T07:00:00Z"),
         sample("S14new", "912", "2026-10-09T07:00:00Z")], "2026-10-10")
    check(14, f"baseline before {R.PROTOCOL_LIVE[:10]}; no result after 7 days",
          pub["results"] == 0 and pub["baseline"]["results"] == 1
          and pub["baseline"]["samples"] == 1
          and [x["result"] for x in pub["baseline"]["result_list"]] == ["R14old"]
          and [x["sample"] for x in pub["flags"]["sample_without_result"]] == ["S14late"]
          and pub["samples_pending"] == 1 and not pub["flags"]["result_without_sample"],
          f"counted results {pub['results']}, baseline {pub['baseline']['results']} result(s) "
          f"and {pub['baseline']['samples']} sample(s), flagged "
          f"{[x['sample'] for x in pub['flags']['sample_without_result']]}")

    # 15. the interim mapping (Adriaan Mol, 29 Sep 2026): a kiosk still linked
    # in mWater to WaterAid's duplicate 441839342 counts for Amboasary gara, so
    # a sample there pairs by water point and is a pre-completion test; the
    # mapping never counts toward registering the standposts
    ps = R.point_systems(REAL["systems"])
    dd = json.load(open(os.path.join(R.REPO, "data", "moramanga_system_dedupe.json"),
                        encoding="utf8"))
    kiosks = [x["code"] for x in dd["interim_points"]["1108783583"]["points"]]
    k = kiosks[0]
    pub, priv = R.pair([result("R15", k, "2026-10-12T09:00:00Z")],
                       [sample("S15", k, "2026-10-11T08:00:00Z")], "2026-10-13",
                       ps, {c for c, e in REAL["systems"].items() if e["status"] == "in_process"},
                       {}, set(kiosks))
    sy = next(x for x in dd["systems"] if x["code"] == "1108783583")
    check(15, f"interim kiosk {k} on Amboasary gara",
          all(ps.get(c) == "1108783583" for c in kiosks) and pub["paired"] == 1
          and priv[0]["pre_completion"] and sy["standposts_n"] == 0
          and [x["sample"] for x in pub["flags"]["earlier_project_record"]] == ["S15"],
          f"{sum(1 for c in kiosks if ps.get(c) == '1108783583')} of {len(kiosks)} kiosks mapped, "
          f"paired {pub['paired']}, pre-completion {priv[0]['pre_completion'] if priv else None}, "
          f"counted toward closure {sy['standposts_n']}")

    # 16. the crosswalk (Adriaan Mol, 29 Sep 2026): an old ID quoted in the new
    # point's description is confirmed; failing that, GPS within 30 m and a
    # similar name is suggested; a far or unlike point stays unmatched; an old
    # point matches once
    import moramanga_dedupe as D
    old = [{"code": "441839397", "name": "KIOSQUE TERRAIN AMBOASARY", "location": [-18.44, 48.27]},
           {"code": "441839483", "name": "KIOSQUE AMPITANOMBY AMBOASARY", "location": [-18.45, 48.28]},
           {"code": "441839490", "name": "KIOSQUE BARRIERE AMBOASARY", "location": [-18.46, 48.29]},
           {"code": "441839500", "name": "KIOSQUE ANTSAPANANA", "location": [-18.47, 48.30]}]
    new = [{"code": "1300000001", "name": "BF Terrain", "desc": "ancien ID mWater 441839397",
            "location": [-18.4403, 48.27]},                      # quoted, 33 m away
           {"code": "1300000002", "name": "Borne fontaine Ampitanomby",
            "desc": "", "location": [-18.45015, 48.28]},        # 17 m, similar name
           {"code": "1300000003", "name": "BF Marché", "desc": "",
            "location": [-18.46010, 48.29]},                    # 11 m, unlike name
           {"code": "1300000004", "name": "BF Antsapanana", "desc": "",
            "location": [-18.4710, 48.30]}]                     # like name, 111 m
    cw = D.crosswalk(new, old)
    got = {r["new"]: (r["old"], r["status"]) for r in cw["crosswalk"]}
    check(16, "crosswalk: quoted ID confirmed, GPS + name suggested, others unmatched",
          got == {"1300000001": ("441839397", "confirmed"), "1300000002": ("441839483", "suggested")}
          and [x["code"] for x in cw["unmatched_old"]] == ["441839490", "441839500"]
          and cw["counts"]["physical_standposts"] == 6,
          f"links {got}, unmatched old {[x['code'] for x in cw['unmatched_old']]}, "
          f"physical standposts {cw['counts']['physical_standposts']}")

    # 17. one physical standpost is one water point: a stray sample at the old
    # kiosk pairs with a result filed at the new Endur'O point, flagged
    pub, priv = R.pair([result("R17", "1300000001", "2026-10-15T09:00:00Z")],
                       [sample("S17", "441839397", "2026-10-15T07:00:00Z")], "2026-10-16",
                       {"1300000001": "1108783583", "441839397": "1108783583"}, {"1108783583"},
                       {"441839397": "1300000001"}, {"441839397"})
    check(17, "a sample at an old kiosk pairs with the result at its Endur'O point",
          pub["paired"] == 1 and priv[0]["point"] == "1300000001" and priv[0]["pre_completion"]
          and pub["flags"]["earlier_project_record"][0]["endur_o_point"] == "1300000001",
          f"paired {pub['paired']} on {priv[0]['point'] if priv else None}, "
          f"flag {pub['flags']['earlier_project_record'][0]['why'] if pub['flags']['earlier_project_record'] else None}")

    if fails:
        print("\nTEST FAILED:\n  " + "\n  ".join(fails)); return 1
    print("\nthe join rule holds: baseline never counts, a system joins only after "
          "works and a later test, and the status file must cover the extract.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
