# -*- coding: utf-8 -*-
"""Classify every record in the MadAvance mWater group, silently.

The report covers only the actively managed portfolio: water points we
maintain and that serve people (decided 23 September 2026, see
docs/decision_log.md). The rest of the group - survey and identification
records, failed rehabilitations, points handed on, abandoned points - is not
the portfolio and is not on the page. But the build still has to look at the
whole group every week, because that is where a new pump first appears.

Each record falls into exactly one class:

  in_fleet            already in the maintained fleet (PUMPS). Never removed
                      here: a maintained pump reported down stays in.
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

    cls, why = {}, {}
    for code in rows:
        if code in fleet:
            cls[code] = "in_fleet"
        elif code in excluded:
            cls[code] = "excluded"
        elif code in succ or code in corrected:
            a = reg.get(code) or {}
            missing = [k for k, ok in (
                ("its district does not map to a site", a.get("site")),
                ("it has no coordinate", a.get("lat") is not None),
                (f"its register name {a.get('pump')!r} is not a pump model "
                 f"({', '.join(sorted(models))})", a.get("pump") in models)) if not ok]
            if missing:
                cls[code] = "review"
                why[code] = ("successful first rehabilitation, but it cannot join "
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
    review = sorted(k for k, v in cls.items() if v == "review")
    for k in joins:
        print(f"  joins the portfolio: {k}")
    for k in review:
        print(f"  for review: {k} - {why[k]}")
    for k in gone:
        print(f"  for review: {k} is in the fleet but no longer in the mWater group")
    if not write:
        return 0

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
                              "why": "successful first rehabilitation, not excluded, "
                                     f"{reg[k]['site']}, {reg[k]['pump']}, located"})
    doc = {"note": "Every record in the MadAvance mWater group, classified by "
                   "tools/classify_register.py. Build-internal: nothing here is "
                   "rendered on the page.",
           "checked": datetime.date.today().isoformat(),
           "group_records": len(cls),
           "counts": dict(sorted(n.items())),
           "review": {k: why[k] for k in review},
           "fleet_points_not_in_group": gone,
           "joined": dict(sorted(joined.items())),
           "records": dict(sorted(cls.items()))}
    json.dump(doc, open(OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
