# -*- coding: utf-8 -*-
"""Classify every record in the MadAvance mWater group, silently.

The report covers only the actively managed portfolio: water points we
maintain and that serve people (decided 23 September 2026, see
docs/decision_log.md). The rest of the group - survey and identification
records, failed rehabilitations, points handed on, abandoned points - is not
the portfolio and is not on the page. But the build still has to look at the
whole group every week, because that is where a new pump first appears.

Each record falls into exactly one class:

  in_fleet            already in the maintained fleet (PUMPS). A maintained
                      pump reported down stays in. Removed only by a recorded
                      exclusion (register_corrections), as a leaves record.
  leaves              in the fleet but excluded by a recorded decision: it is
                      removed from PUMPS, and tools/rerun_wpop.py drops its
                      allocation. (29 Sep 2026: four Marolinta survey points.)
  no_works_record     in the fleet with no programme works record - no
                      successful first rehabilitation, no recorded correction,
                      no record on the borehole-progress (new construction /
                      rehabilitation) form. A point enters the fleet only
                      through a works record, never through a survey record
                      (decision register-fleet-entry-rule, 29 Sep 2026), so
                      check_consistency fails the build on any of these.
  joins               a successful first rehabilitation (or a recorded
                      correction to one), not excluded by decision, with a
                      district that maps to a site, a coordinate, and a
                      register name that is a known pump model. Appended to
                      PUMPS; the rebuild steps that follow fill it in.
  excluded            excluded by a recorded decision (register_corrections)
  rehab_not_successful  a first rehabilitation recorded, not successful
  no_first_rehab      no first-rehabilitation record: survey, identification
                      or other entries
  review              anything else - chiefly a successful rehabilitation that
                      cannot join automatically. Logged in logs/publisher.log
                      for a person to look at; nothing about it is rendered.

A fleet point that has left the group is also logged for review, and stays in
the fleet until someone decides otherwise.

    python3 tools/classify_register.py            # report, write nothing
    python3 tools/classify_register.py --write    # join, record, log
"""
import collections, datetime, io, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
PAGE = os.path.join(REPO, "index.html")
OUT = os.path.join(REPO, "data", "register_classification.json")
LOG = os.path.join(REPO, "logs", "publisher.log")


def log(line):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    with io.open(LOG, "a", encoding="utf8") as fh:
        fh.write(f"{ts}  {line}\n")


BH_TYPE, BH_NEW, BH_REHAB = "660d59b922d843b1a6f51676ad2ccd14", "xl1VJVT", "TFTjqNm"
BH_STATUS, BH_FUNCTIONAL = "0a46051cee394b46ad1e7478dd40117a", "56EZb1R"
BH_PUMP_MODEL = "1e8f9bf782144b3ab2a703ccc8823ec9"


def works_points(P, corrected, today=None):
    """Points with a final programme works record - the fleet-entry rule
    (decision register-fleet-entry-rule, 29 Sep 2026): a point is in the
    managed fleet only through a successful rehabilitation or a completed new
    construction, never through a survey record.

      * a successful first rehabilitation (retired combined form or successor);
      * on the borehole-progress form, a FINAL rehabilitation whose status is
        "Fonctionnel", or a FINAL new construction with its hand-pump model
        recorded (the "drilling result" question was added after the 2026
        Marolinta records were filed; act-marolinta-drilling-result);
      * a recorded correction (register_corrections "corrected"). A correction
        that carries "expires_on" lapses on that date unless a final
        rehabilitation record for the point has appeared by then
        (782134540, the one recorded exception, 31 Oct 2026).
    """
    import datetime as _dt
    today = today or _dt.date.today().isoformat()
    bh = set()
    for r in P._borehole():
        if (r.get("status") or "final") != "final":
            continue
        t = P._answer(r, BH_TYPE)
        if (t == BH_REHAB and P._answer(r, BH_STATUS) == BH_FUNCTIONAL) or \
           (t == BH_NEW and P._answer(r, BH_PUMP_MODEL)):
            bh.add(P._point_of(r))
    succ = set(P.rehabilitated_successfully())
    _cp = os.path.join(REPO, "data", "register_corrections.json")
    c = json.load(open(_cp, encoding="utf8")) if os.path.isfile(_cp) else {}
    lapsed = {e["wp"] for e in c.get("corrected", [])
              if e.get("expires_on") and today > e["expires_on"] and e["wp"] not in succ | bh}
    return succ | (set(corrected) - lapsed) | bh


def classify():
    import populations as P
    import rebuild_summary as RS
    pumps = P._page_pumps()
    fleet = {p["wp"] for p in pumps}
    import build_config
    models = set(build_config.load()["portfolio"]["pump_models"])
    rows = {r["code"]: r for r in P._rows("wp_madavance.csv") if r.get("code")}
    reg = RS.register(set())                  # attributes, for every record
    succ = P.get("rehabilitated_successfully")["members"]()
    c = json.load(open(os.path.join(REPO, "data", "register_corrections.json"),
                       encoding="utf8"))
    corrected = {e["wp"] for e in c.get("corrected", [])}
    excluded = ({e["wp"] for e in c.get("excluded", [])}
                | {e.get("wp") for e in (c.get("excluded_from_map") or [])
                   if isinstance(e, dict)})
    any_rehab = {P._point_of(r) for r in P._combined()
                 if P._answer(r, P.Q_TYPE) == P.C_FIRST_REHAB}
    works = works_points(P, corrected)

    cls, why = {}, {}
    for code in rows:
        if code in fleet and (code in excluded or (code in corrected and code not in works)):
            # excluded by decision, or a recorded exception whose deadline has
            # passed with no rehabilitation record (register_corrections expires_on)
            cls[code] = "leaves"
        elif code in fleet and code not in works:
            cls[code] = "no_works_record"
            why[code] = "in the fleet with no rehabilitation, new-construction or corrected record"
        elif code in fleet:
            cls[code] = "in_fleet"
        elif code in excluded:
            cls[code] = "excluded"
        elif code in works:
            a = reg.get(code) or {}
            missing = [k for k, ok in (
                ("its district does not map to a site", a.get("site")),
                ("it has no coordinate", a.get("lat") is not None),
                (f"its register name {a.get('pump')!r} is not a pump model "
                 f"({', '.join(sorted(models))})", a.get("pump") in models)) if not ok]
            if missing:
                cls[code] = "review"
                why[code] = ("a final works record, but it cannot join "
                             "automatically: " + "; ".join(missing))
            else:
                cls[code] = "joins"
        elif code in any_rehab:
            cls[code] = "rehab_not_successful"
        else:
            cls[code] = "no_first_rehab"
    gone = sorted(fleet - set(rows))
    return cls, why, gone, reg, pumps


def main():
    write = "--write" in sys.argv
    cls, why, gone, reg, pumps = classify()
    n = collections.Counter(cls.values())
    print("register classification: "
          + ", ".join(f"{k} {v}" for k, v in sorted(n.items())))
    joins = sorted(k for k, v in cls.items() if v == "joins")
    review = sorted(k for k, v in cls.items() if v in ("review", "no_works_record"))
    leaves = sorted(k for k, v in cls.items() if v == "leaves")
    for k in leaves:
        print(f"  leaves the portfolio by recorded decision: {k}")
    for k in joins:
        print(f"  joins the portfolio: {k}")
    for k in review:
        print(f"  for review: {k} - {why[k]}")
    for k in gone:
        print(f"  for review: {k} is in the fleet but no longer in the mWater group")
    if not write:
        return 0

    if leaves:
        src = open(PAGE, encoding="utf8").read()
        m = re.search(r"\bconst PUMPS\s*=\s*", src)
        i = m.end()
        j = src.index("];", i) + 1
        arr = [r for r in json.loads(src[i:j]) if r["wp"] not in leaves]
        open(PAGE, "w", encoding="utf8").write(
            src[:i] + json.dumps(arr, ensure_ascii=False) + src[j:])
        for k in leaves:
            log(f"register: {k} left the portfolio (excluded by recorded decision)")
    if joins:
        src = open(PAGE, encoding="utf8").read()
        m = re.search(r"\bconst PUMPS\s*=\s*", src)
        i = m.end()
        j = src.index("];", i) + 1
        arr = json.loads(src[i:j])
        tmpl = {k: None for k in arr[0]}
        for k in joins:
            row = dict(tmpl, wp=k, **{c: reg[k][c] for c in
                                      ("site", "commune", "fkt", "pump", "lat", "lon")})
            row["nocomm"] = False
            arr.append(row)
        open(PAGE, "w", encoding="utf8").write(
            src[:i] + json.dumps(arr, ensure_ascii=False) + src[j:])
        for k in joins:
            log(f"register: {k} joined the portfolio (successful first "
                f"rehabilitation, {reg[k]['site']}, {reg[k]['pump']})")
    for k in review:
        log(f"register: {k} needs review and is not in the portfolio: {why[k]}")
    for k in gone:
        log(f"register: {k} is in the fleet but no longer in the mWater group; "
            "it stays in the portfolio until someone decides otherwise")

    # joins are recorded for good: once in the fleet a pump is "in_fleet",
    # so this ledger is what explains, later, how it got there
    prev = json.load(open(OUT, encoding="utf8")) if os.path.isfile(OUT) else {}
    joined = dict(prev.get("joined") or {})
    for k in joins:
        joined.setdefault(k, {"on": datetime.date.today().isoformat(),
                              "why": "final works record (rehabilitation or new construction), not excluded, "
                                     f"{reg[k]['site']}, {reg[k]['pump']}, located"})
    left = dict(prev.get("left") or {})
    for k in leaves:
        left.setdefault(k, {"on": datetime.date.today().isoformat(),
                            "why": "excluded by recorded decision (data/register_corrections.json)"})
    doc = {"note": "Every record in the MadAvance mWater group, classified by "
                   "tools/classify_register.py. Build-internal: nothing here is "
                   "rendered on the page.",
           "checked": datetime.date.today().isoformat(),
           "group_records": len(cls),
           "counts": dict(sorted(n.items())),
           "review": {k: why[k] for k in review},
           "fleet_points_not_in_group": gone,
           "joined": dict(sorted(joined.items())),
           "left": dict(sorted(left.items())),
           "records": dict(sorted(cls.items()))}
    json.dump(doc, open(OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
