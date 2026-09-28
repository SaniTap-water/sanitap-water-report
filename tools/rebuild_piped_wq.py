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

PAIRING (Adriaan Mol, 28 September 2026). Each result is paired with its record
on the piped sampling form (ef8cf735) by site and sampling date, and nothing
else: the same water point (result 1.2b = sample 1.1b) or, for a system-level
sample, the same water system (result 1.2 = sample 1.1), AND the same day
(result 1.2.2 = the date of sample 1.4, in Madagascar time). A pair takes the
GPS, sample type and photo from the sampling record. The sampling code (1.2.1)
is a cross-check only and the GPS copied onto the result (1.2.3) is ignored.
Flagged for pairing by hand, never failing the build: a result with no sample;
a sample with no result 7 days after it was taken; a site and day with more
than one sample or more than one result. Coordinates are not published (some
samples are household connections): the pairs with their GPS go to
~/mwater-exports/piped_wq_pairs.json, and the page says only whether a pair
has one.

    python3 tools/rebuild_piped_wq.py --pairing   # print the flags (exit 0)

    python3 tools/rebuild_piped_wq.py --write
    python3 tools/rebuild_piped_wq.py --check
"""
import csv, datetime, io, json, os, statistics, sys

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
# the Endur'O registrations (onboarding progress)
SYS_REG_FORM, SR_SYSTEM = "44044e27c0f24cc4a432a38b09886684", "1c1893f3"
PT_REG_FORM, PR_POINT, PR_SYSTEM, PR_TAPS, PR_TESTED = (
    "8a3af50ceec84cda85d454d96079991d", "8f174aec", "e5380235", "44faf0f2", "ebf4c6ec")
# the piped sampling form (ef8cf735): each result is paired with its sample
SAMPLING_FORM = "ef8cf7353a974cf984d34860dcf2952d"
S_WHERE, S_SYSTEM, S_POINT, S_GPS, S_TYPE, S_SAMPLED, S_PHOTO = (
    "4e8d00a7", "a7f6f9e1", "51eca87b", "b2875c48", "bf966f97", "630ccd46", "e14d9d8b")
Q_CODE = "680e7b71"      # 1.2.1 sampling record code: a cross-check only
S_WHERE_LABEL = {"kPcXJl9": "source or system", "Qqs6cuQ": "tap or kiosk"}
S_TYPE_LABEL = {"4hbaZYA": "public tapstand", "YZhKDk3": "water kiosk",
                "YLudYMc": "household connection", "zevJvCr": "institutional connection",
                "KMB99ey": "other"}
LOCAL_UTC_OFFSET_H = 3   # Madagascar (EAT, no daylight saving): the field's day
NO_RESULT_AFTER_DAYS = 7
PAIRS_OUT = os.path.join(EXPORTS, "piped_wq_pairs.json")
TESTED_YES = "mXEQQFB"   # 3.1 commissioning test dispenses done: Yes
# the Moramanga carbon baseline survey: main fuel for boiling, dry season
BASELINE_FORM, Q_DRY_FUEL = "3ef4385a619244c7ad129169ac1ec71f", "7c45cdb3523e404b93c9d8c64a485393"


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


def local_day(v):
    """The Madagascar calendar day of a stored UTC datetime, or a date as is."""
    if not isinstance(v, str) or v[:2] != "20":
        return None
    if len(v) <= 10:
        return v[:10]
    t = datetime.datetime.fromisoformat(v.replace("Z", "+00:00"))
    if t.tzinfo is None:
        return v[:10]
    return (t + datetime.timedelta(hours=LOCAL_UTC_OFFSET_H)).date().isoformat()


def result_site(r):
    tap = site_code(answer(r, Q_TAP))
    return ("point", tap) if tap else (("system", site_code(answer(r, Q_SYSTEM)))
                                       if site_code(answer(r, Q_SYSTEM)) else None)


def sample_site(s):
    pt = site_code(answer(s, S_POINT))
    return ("point", pt) if pt else (("system", site_code(answer(s, S_SYSTEM)))
                                     if site_code(answer(s, S_SYSTEM)) else None)


def pair(results, samples, as_of):
    """Pair results with samples on (site, sampling day). Returns the published
    summary and the private pairs (with coordinates). as_of is the day the
    results were pulled: a sample older than NO_RESULT_AFTER_DAYS by then with
    no result is flagged."""
    res = [r for r in results if r.get("status") == "final"]
    smp = [s for s in samples if s.get("form") == SAMPLING_FORM and s.get("status") == "final"]
    r_by, s_by, r_nokey, s_nokey = {}, {}, [], []
    for r in res:
        site, day = result_site(r), local_day(answer(r, Q_SAMPLED))
        (r_by.setdefault((site, day), []).append(r) if site and day
         else r_nokey.append((r, site, "no sampling date (1.2.2)" if site
                              else "no water point or water system")))
    for s in smp:
        site, day = sample_site(s), local_day(answer(s, S_SAMPLED))
        (s_by.setdefault((site, day), []).append(s) if site and day
         else s_nokey.append((s, site, "no water point or water system" if not site
                              else "no sampling date (1.4)")))

    def lbl(site):
        return f"{site[0]} {site[1]}" if site else None

    def cands(site, before):
        """Samples a person might pair by hand: same site, taken in the
        NO_RESULT_AFTER_DAYS days up to the result's reading."""
        if not site or not before:
            return []
        lo = (datetime.date.fromisoformat(before)
              - datetime.timedelta(days=NO_RESULT_AFTER_DAYS)).isoformat()
        return sorted(s["code"] for (st, d), ss in s_by.items() if st == site
                      and lo <= d <= before for s in ss)

    pairs, flags = [], {"result_without_sample": [], "sample_without_result": [],
                        "more_than_one": [], "code_mismatch": []}
    pending = 0
    for key in sorted(set(r_by) | set(s_by), key=lambda k: (k[1], lbl(k[0]))):
        rs, ss = r_by.get(key, []), s_by.get(key, [])
        site, day = key
        if len(rs) > 1 or len(ss) > 1:
            flags["more_than_one"].append({
                "site": lbl(site), "day": day,
                "results": sorted(r["code"] for r in rs),
                "samples": sorted(s["code"] for s in ss)})
        elif rs and ss:
            r, s = rs[0], ss[0]
            gps = answer(s, S_GPS) if isinstance(answer(s, S_GPS), dict) else None
            photos = [p.get("id") for p in (answer(s, S_PHOTO) or []) if isinstance(p, dict)]
            typed = str(answer(r, Q_CODE) or "").strip()
            pairs.append({"result": r["code"], "result_id": r["_id"], "sample": s["code"],
                          "sample_id": s["_id"], "site": lbl(site), "day": day,
                          "where": S_WHERE_LABEL.get(answer(s, S_WHERE)),
                          "point_type": S_TYPE_LABEL.get(answer(s, S_TYPE)),
                          "photos": photos, "gps": gps})
            if typed and typed.upper() != str(s["code"]).upper():
                flags["code_mismatch"].append({"site": lbl(site), "day": day,
                                               "result": r["code"], "typed": typed,
                                               "sample": s["code"]})
        elif rs:
            rd = local_day(answer(rs[0], Q_RESULT))
            flags["result_without_sample"].append({
                "result": rs[0]["code"], "site": lbl(site), "day": day,
                "why": "no sample at this site on this day",
                "candidates": cands(site, rd or day)})
        else:
            if (datetime.date.fromisoformat(as_of) - datetime.date.fromisoformat(day)).days \
                    > NO_RESULT_AFTER_DAYS:
                flags["sample_without_result"].append({"sample": ss[0]["code"],
                                                       "site": lbl(site), "day": day})
            else:
                pending += 1
    for r, site, why in r_nokey:
        rd = local_day(answer(r, Q_RESULT))
        flags["result_without_sample"].append({"result": r["code"], "site": lbl(site),
                                               "day": None, "result_day": rd, "why": why,
                                               "candidates": cands(site, rd)})
    for s, site, why in s_nokey:
        flags["sample_without_result"].append({"sample": s["code"], "site": lbl(site),
                                               "day": local_day(answer(s, S_SAMPLED)),
                                               "why": why})
    for k in ("result_without_sample", "sample_without_result"):
        flags[k].sort(key=lambda x: (x.get("day") or x.get("result_day") or "",
                                     x.get("result") or x.get("sample")))
    published = {
        "rule": "result 1.2b = sample 1.1b (tap or kiosk) or result 1.2 = sample 1.1 "
                "(system), and result 1.2.2 = the Madagascar day of sample 1.4",
        "sampling_form": SAMPLING_FORM,
        "as_of": as_of, "after_days": NO_RESULT_AFTER_DAYS,
        "results": len(res), "samples": len(smp),
        "paired": len(pairs),
        "paired_with_gps": sum(1 for p in pairs if p["gps"]),
        "paired_with_photo": sum(1 for p in pairs if p["photos"]),
        "samples_pending": pending,
        "results_without_sampling_date": sum(1 for _r, _s, w in r_nokey if "1.2.2" in w),
        "flagged": {k: len(v) for k, v in flags.items()},
        "flagged_total": sum(len(v) for k, v in flags.items() if k != "code_mismatch"),
        "flags": flags,
        "pairs": [{k: v for k, v in p.items() if k not in ("gps", "result_id", "sample_id")}
                  | {"gps": bool(p["gps"])} for p in pairs],
    }
    return published, pairs


def sampling_rows():
    p = os.path.join(EXPORTS, "wq_sampling_piped.json")
    return json.load(open(p, encoding="utf8")) if os.path.isfile(p) else None


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
        if e.get("admitted_by_decision") and not e.get("works_complete"):
            bad.append(f"{code}: admitted by decision but has no operational date "
                       "(works_complete)")
        for k in ("works_complete", "post_rehab_test"):
            v = e.get(k)
            if v is not None and not (isinstance(v, str) and len(v) == 10 and v[:2] == "20"):
                bad.append(f"{code}: {k} {v!r} is not a YYYY-MM-DD date")
    return bad


def dispensing_events():
    """The Curtech dispensing-events extract, or None until the build writes it.
    Each event: device_id, timestamp, litres, card, credits, shopkeeper."""
    p = os.path.join(REPO, PIPED["dispensing_events"]["path"])
    if not os.path.isfile(p):
        return None
    doc = json.load(open(p, encoding="utf8"))
    return doc.get("events", doc) if isinstance(doc, dict) else doc


def operational(e, events):
    """(date, source, from_feed) for a system admitted by decision. Once the
    dispensing-events feed exists, the date is the first dispense on one of the
    system's devices that is not a test (test shopkeepers and test cards are
    excluded); until then the recorded date stands."""
    recorded = (e.get("works_complete"),
                "the date of commissioning recorded on its mWater registration", False)
    if events is None:
        return recorded
    cfg = PIPED["dispensing_events"]
    devices = {str(x) for x in (e.get("devices") or [])}
    test_sk = set(cfg.get("test_shopkeepers") or [])
    test_cards = {str(x) for x in (cfg.get("test_cards") or [])}
    real = sorted((str(ev.get("timestamp") or ""), str(ev.get("device_id")))
                  for ev in events
                  if str(ev.get("device_id")) in devices
                  and ev.get("shopkeeper") not in test_sk
                  and str(ev.get("card")) not in test_cards
                  and str(ev.get("timestamp") or "")[:2] == "20")
    if not real:
        return (recorded[0], recorded[1] + "; the Curtech feed holds no non-test dispense on "
                + ("its devices" if devices else "a device recorded for it"), False)
    ts, dev = real[0]
    return (ts[:10], f"its first non-test dispense, on device {dev} at {ts[:16].replace('T', ' ')}, "
            "from the Curtech dispensing-events feed", True)


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

    # a result may name a kiosk's water point rather than its system
    point_of = {wp: c for c, e in status.items() for wp in (e.get("water_points") or [])}
    by_sys, excl = {}, {"not_final": [], "no_site": [], "hand_pump_on_piped_form": [],
                        "not_an_operator_system": []}
    for r in rows:
        if r.get("form") != PIPED["wq_form"]:
            continue
        code = site_code(answer(r, Q_SYSTEM))
        code = point_of.get(code, code)
        if r.get("status") != "final":
            excl["not_final"].append(r["_id"]); continue
        if not code:
            excl["no_site"].append(r["_id"]); continue
        if code not in status:
            (excl["hand_pump_on_piped_form"] if code in reg
             else excl["not_an_operator_system"]).append((code, r["_id"]))
            continue
        by_sys.setdefault(code, []).append((code, r, result_date(r)))

    events = dispensing_events()
    systems, managed_res, baseline_res, not_managed_res = {}, [], [], []
    for code, e in sorted(status.items()):
        res = by_sys.get(code, [])
        works = e.get("works_complete")
        op_source, op_from_feed = None, False
        if e.get("admitted_by_decision"):
            works, op_source, op_from_feed = operational(e, events)
        post = [x for x in res if works and x[2] and x[2] > works]
        base = [x for x in res if x not in post]
        tested = bool(post) or bool(e.get("post_rehab_test"))
        if e["status"] == "not_managed":
            eff = "not_managed"
        elif e["status"] == "managed" and e.get("admitted_by_decision"):
            eff = "managed"          # by decision; the rule applies to the rest
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
                         "admitted_by_decision": e.get("admitted_by_decision"),
                         "operational_source": op_source,
                         "operational_from_feed": op_from_feed,
                         "water_points": e.get("water_points") or [],
                         "wq_on_record": bool(post),
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
    # onboarding progress, from the Endur'O registrations (drafts named apart:
    # a draft is not a registration until it is submitted)
    def regs(name, form):
        p = os.path.join(EXPORTS, name)
        return [r for r in json.load(open(p, encoding="utf8")) if r.get("form") == form] \
            if os.path.isfile(p) else []
    sreg, preg = regs("piped_system_reg.json", SYS_REG_FORM), regs("piped_point_reg.json", PT_REG_FORM)
    fin = lambda rs, q: {site_code(answer(r, q)) for r in rs
                         if r.get("status") == "final" and site_code(answer(r, q))}
    drf = lambda rs, q: {site_code(answer(r, q)) for r in rs
                         if r.get("status") != "final" and site_code(answer(r, q))}
    taps = lambda rs: sum(int(answer(r, PR_TAPS) or 0) for r in rs)
    bound = [r for r in preg if answer(r, PR_TESTED) == TESTED_YES]
    kiosk_points = {wp for c, v in systems.items()
                    if v["status"] == "managed" and v.get("admitted_by_decision")
                    for wp in v["water_points"]}
    on_point = [r for r in rows if r.get("form") == PIPED["wq_form"] and r.get("status") == "final"
                and ({site_code(answer(r, Q_TAP)), site_code(answer(r, Q_SYSTEM))} & kiosk_points)]
    onboarding = {
        "systems_registered": len(fin(sreg, SR_SYSTEM)),
        "systems_registered_draft": len(drf(sreg, SR_SYSTEM) - fin(sreg, SR_SYSTEM)),
        "points_registered": len(fin(preg, PR_POINT)),
        "points_registered_draft": len(drf(preg, PR_POINT) - fin(preg, PR_POINT)),
        "taps_installed": taps(preg),
        "taps_bound": taps(bound),
        "taps_unbound": taps(preg) - taps(bound),
        "managed_kiosk_points": sorted(kiosk_points),
        "managed_kiosk_wq_results": len(on_point),
    }
    # the baseline cooking-fuel split for the Moramanga piped systems (in
    # process, not registered): the main fuel for boiling water in the dry
    # season, question 4.1.2.2.4.1 of the carbon baseline survey, every response
    bpath = os.path.join(EXPORTS, "baseline_moramanga.json")
    FUEL = {"d37St9W": "wood", "9rRkPfv": "charcoal", "rQLUjXQ": "lpg",
            "CUA2RaV": "electricity", "pZ19akx": "agricultural_waste", "aV9ZKFx": "other"}
    baseline_fuel = None
    if os.path.isfile(bpath):
        brs = [r for r in json.load(open(bpath, encoding="utf8"))
               if r.get("form") == BASELINE_FORM and r.get("status") == "final"]
        fuel = {k: 0 for k in FUEL.values()}
        for r in brs:
            v = ((r.get("data") or {}).get(Q_DRY_FUEL) or {}).get("value")
            if v in FUEL:
                fuel[FUEL[v]] += 1
        baseline_fuel = {"form": BASELINE_FORM, "question": "4.1.2.2.4.1",
                         "responses": len(brs), "answered": sum(fuel.values()),
                         "counts": fuel}
    # every result paired with its sample (site and sampling day); the flags
    # are for pairing by hand and never fail the build
    samples = sampling_rows()
    if samples is None:
        raise RuleBroken("no ~/mwater-exports/wq_sampling_piped.json: run "
                         "tools/pull_extract.py --write")
    as_of = str((man.get("wq_results_piped.json") or {}).get("written") or "")[:10]
    pairing, private_pairs = pair([r for r in rows if r.get("form") == PIPED["wq_form"]],
                                  samples, as_of)
    pairing["samples_pulled"] = str((man.get("wq_sampling_piped.json") or {})
                                    .get("written") or "")[:10] or None
    build.private_pairs = private_pairs
    return {
        "pairing": pairing,
        "baseline_fuel": baseline_fuel,
        "onboarding": onboarding,
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


def show_pairing(p):
    """The pairing gate's readout: counts, then every flag with its codes.
    Never fails the build: the flags are Cathy's to pair by hand."""
    f = p["flagged"]
    print(f"piped results paired with their samples: {p['paired']} of {p['results']} "
          f"({p['samples']} samples); flagged {p['flagged_total']}: "
          f"{f['result_without_sample']} result(s) with no sample, "
          f"{f['sample_without_result']} sample(s) with no result after {p['after_days']} days, "
          f"{f['more_than_one']} site-day(s) with more than one; "
          f"{f['code_mismatch']} typed sampling code(s) disagree")
    for x in p["flags"]["more_than_one"]:
        print(f"  more than one  {x['site']} {x['day']}: results {', '.join(x['results']) or '-'}"
              f" | samples {', '.join(x['samples']) or '-'}")
    for x in p["flags"]["result_without_sample"]:
        print(f"  no sample      {x['result']} ({x['site']}, {x['day'] or x.get('result_day')}: "
              f"{x['why']}){' - near: ' + ', '.join(x['candidates']) if x['candidates'] else ''}")
    for x in p["flags"]["sample_without_result"]:
        print(f"  no result      {x['sample']} ({x['site']}, {x['day']}"
              f"{': ' + x['why'] if x.get('why') else ''})")
    for x in p["flags"]["code_mismatch"]:
        print(f"  code differs   {x['result']} typed {x['typed']}, paired with {x['sample']}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    try:
        doc = build()
    except RuleBroken as e:
        print(f"rebuild_piped_wq: REFUSED - {e}")
        return 2 if mode == "--pairing" else 1
    if mode == "--pairing":
        show_pairing(doc["pairing"])
        return 0
    if mode == "--write":
        # the pairs with their coordinates stay beside the extracts, unpublished
        json.dump({"note": "Written by tools/rebuild_piped_wq.py; not published (GPS).",
                   "pairs": getattr(build, "private_pairs", [])},
                  open(PAIRS_OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False)
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
