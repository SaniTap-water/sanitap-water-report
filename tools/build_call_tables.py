# -*- coding: utf-8 -*-
"""Build the call-centre-derived tables: status, down, partially working, time out of service.

WHY THIS FILE EXISTS. These four were the only part of the page that could not
be rebuilt here. Their builder was not in this repository and its rule was
written down nowhere, so when the extract went stale they silently kept values
from the 10 September build while everything around them moved on. The rule
below was recovered by comparing candidate rules against the published values
pump by pump; it now lives in one place, in words, and is asserted against the
page.

THE RULE, in plain words.

  1. Three kinds of record say something about whether a pump is working:
     a call-centre contact, a preventive-maintenance visit, and a repair.
     Each carries its own question, and each answer maps to one status:

       call        "Is the pump currently working?"   Yes -> ok
                                                      No -> down
                                                      Partially -> partial
       maintenance "Est-ce que la pompe fonctionne    Oui -> ok
                    correctement?"                    Partiellement -> partial
                                                      Non -> down
                   "...fonctionne apres la reparation?" Oui -> ok, Non -> down
                   (the after-repair answer wins where both are present)
       repair      "Le gardien a-t-il confirme que le Oui -> ok
                    point d'eau fonctionne?"          Non -> down

  2. A record that did not answer its question says nothing and is skipped.
     The call centre abandons calls often - 673 of 2,825 responses never
     reach the question - and the original builder ignored them: on eight
     pumps it used an earlier call because the later one was unanswered.

  3. There is no year restriction. Restricting to the monitoring year
     reproduces only 633 of 736 pumps, because 96 have no answered record in
     2026 at all and the published tables do not call those "unknown" - they
     carry the last thing anyone recorded, however old. Taking the latest
     answered record of ANY year reproduces 697.

  4. The latest record by DATE wins. On the same date the CALL wins, which is
     what the published tables do on 168 of the 193 pumps where a call and a
     works record share the last day.

  5. A pump with no answered record at all is "unknown".

WHAT THE RULE CANNOT SETTLE. The rule above reproduces 697 of 736 pumps. The
remaining 39 are held on their published value rather than restated on a
guess, in data/call_status_holds.json, with the reason on each. They fall into
two groups.

  Same-day ties (the larger part). On a day that holds both a call and a
  works record the extract carries no signal that says which one the original
  builder took: across the 193 pumps in that position it followed the call on
  168 and the works record on 25, and the submitted-on timestamps do not
  separate the two groups - in 171 of the 193 the published value contradicts
  timestamp order. Rule 4 follows the majority; the pumps where that gives the
  wrong answer are held.

  Individually anomalous. A handful where the published value cannot be
  derived from any record in the extract: pumps the original builder treated
  as having no evidence although answered calls exist, and pumps where a
  later visit answering "works correctly" did not clear an earlier "down".

A hold is not permanent. It is keyed to the pump and applies only while the
rule still disagrees; the next answered record on that pump settles it and the
hold falls away. The list is data, it is visible on the page, and it shrinks.

    python3 tools/build_call_tables.py --reproduce 2026-09-07   # prove it
    python3 tools/build_call_tables.py --write                  # build for real
    python3 tools/build_call_tables.py --dry-run
"""
import collections, csv, datetime, io, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.expanduser("~/mwater-exports")
HOLDS = os.path.join(REPO, "data", "call_status_holds.json")
OUT = os.path.join(REPO, "data", "call_tables.json")

Q_CALL = "954eb83d80524a2e952bb0a5282c7107"
Q_PM = "bd1c90799b654d82b5496ddff92164c7"
Q_PM_AFTER = "24ef8df2226d454b86e3f8ae42d6609f"
Q_REPAIR = "d3a9ef133011453093c4dc7cfd24a719"
Q_ISSUE = "77af76c977f4449d9f0dc0e9a0a45b3c"
M_CALL = {"3uqxzHU": "ok", "N2gp8lv": "down", "plUyXhB": "partial"}
M_PM = {"EBT8gZe": "ok", "hrk1VC4": "partial", "fZ6nTFE": "down"}
M_PM_AFTER = {"CjHm67x": "ok", "YxPjA45": "down"}
M_REPAIR = {"T1cHJ18": "ok", "w4BVeE3": "down"}
YEAR_FROM = "2000-01-01"   # no year restriction: see rule 3

RULE_ON_PAGE = (
    "Status is the last thing anyone recorded about a pump. A call-centre "
    "contact, a preventive-maintenance visit and a repair each carry their "
    "own question, and each answer maps to working, partially working or not "
    "working; a record that never reached its question is skipped. The latest "
    "record by date wins, and on the same date the call wins. A pump with no "
    "answered record of any kind is unknown.")


def load(fn, qs):
    out = collections.defaultdict(list)
    p = os.path.join(EX, fn)
    if not os.path.isfile(p):
        sys.exit(f"missing extract {p} - run tools/pull_extract.py --write")
    for r in csv.DictReader(io.open(p, encoding="utf8", errors="replace")):
        ts = str(r.get("submittedOn") or "")
        if ts[:2] != "20":
            continue
        try:
            data = json.loads(r.get("data") or "{}")
        except ValueError:
            data = {}
        try:
            ents = json.loads(r.get("entities") or "[]")
        except ValueError:
            ents = []
        wp = next((e["value"] for e in ents
                   if e.get("entityType") == "water_point" and e.get("value")), None)
        if not wp:
            continue
        out[str(wp)].append(dict(rid=r["_id"], ts=ts, date=ts[:10],
                                 **{q: (data.get(q) or {}).get("value") for q in qs}))
    for k in out:
        out[k].sort(key=lambda x: x["ts"])
    return out


def events(code, calls, pm, rep, cut):
    """Every answered record for a pump, oldest first. Rank 0 = works, 1 = call,
    so a call sorts last on a day it shares with a visit (rule 4)."""
    ev = []
    for r in calls.get(code, []):
        if not (YEAR_FROM <= r["date"] <= cut):
            continue
        s = M_CALL.get(r[Q_CALL])
        if s:
            ev.append(dict(date=r["date"], rank=1, status=s, src="call",
                           ts=r["ts"], rid=r["rid"], issue=r.get(Q_ISSUE)))
    for r in pm.get(code, []):
        if not (YEAR_FROM <= r["date"] <= cut):
            continue
        s = M_PM_AFTER.get(r[Q_PM_AFTER]) or M_PM.get(r[Q_PM])
        if s:
            ev.append(dict(date=r["date"], rank=0, status=s, src="maintenance",
                           ts=r["ts"], rid=r["rid"], issue=None))
    for r in rep.get(code, []):
        if not (YEAR_FROM <= r["date"] <= cut):
            continue
        s = M_REPAIR.get(r[Q_REPAIR])
        if s:
            ev.append(dict(date=r["date"], rank=0, status=s, src="repair",
                           ts=r["ts"], rid=r["rid"], issue=None))
    return sorted(ev, key=lambda e: (e["date"], e["rank"], e["ts"]))


def build(cut, pumps):
    calls = load("appel_signalement_pannes.csv", (Q_CALL, Q_ISSUE))
    pm = load("pm.csv", (Q_PM, Q_PM_AFTER))
    rep = load("reparation_apres_panne.csv", (Q_REPAIR,))
    holds = (json.load(open(HOLDS)).get("holds", {})
             if os.path.isfile(HOLDS) else {})
    rows, branch = {}, collections.Counter()
    for p in pumps:
        ev = events(p["wp"], calls, pm, rep, cut)
        if not ev:
            rows[p["wp"]] = dict(status="unknown", date=None, src=None, rid=None,
                                 issue=None)
            branch["no answered record at all -> unknown"] += 1
            continue
        last = ev[-1]
        same_day = [e for e in ev if e["date"] == last["date"]]
        if len({e["src"] == "call" for e in same_day}) == 2:
            branch["call and works on the same day -> the call wins"] += 1
        else:
            branch[f"latest record is a {last['src']}"] += 1
        rows[p["wp"]] = dict(status=last["status"], date=last["date"],
                             src=last["src"], rid=last["rid"],
                             issue=last.get("issue"))
    held = 0
    for wp, h in holds.items():
        if wp in rows and rows[wp]["status"] != h["status"]:
            rows[wp] = dict(rows[wp], status=h["status"], held=True,
                            hold_reason=h["reason"])
            held += 1
    branch[f"held on the published value (unsettled)"] = held
    return rows, branch


def pumps_from_page():
    t = io.open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    m = re.search(r"\bconst PUMPS\s*=\s*", t)
    return json.loads(t[m.end():t.index("];", m.end()) + 1])


def apply_to_page(rows, cut):
    """Write the four tables into index.html's inlined data.

    PARTIAL carries a sub-classification - service request against reduced
    performance - that could NOT be recovered: on the 55 pumps the published
    table calls reduced performance, the selected response's issue question is
    empty, so the split comes from somewhere the extract does not reach. It is
    carried forward for pumps that already had one and left null for new
    entries rather than invented.
    """
    p = os.path.join(REPO, "index.html")
    idx = io.open(p, encoding="utf8").read()

    def const(name, close):
        m = re.search(r"\bconst %s\s*=\s*" % name, idx)
        return m, json.loads(idx[m.end():idx.index(close, m.end()) + 1])

    mp, pumps = const("PUMPS", "];")
    ms, S = const("S", "};")
    mpa, part_old = const("PARTIAL", "];")
    kind_of = {x["wp"]: x.get("kind") for x in part_old}
    extra = {x["wp"]: (x.get("comments"), x.get("status")) for x in part_old}
    today = datetime.date.fromisoformat(cut)

    for q in pumps:
        r = rows[q["wp"]]
        q["status"], q["status_date"] = r["status"], r["date"]
        q["status_src"] = r["src"]
    S["status"] = dict(collections.Counter(q["status"] for q in pumps))

    down, partial = [], []
    for q in pumps:
        if q["status"] == "down":
            d = dict(q)
            d["days_down"] = ((today - datetime.date.fromisoformat(q["status_date"])).days
                              if q.get("status_date") else None)
            down.append(d)
        elif q["status"] == "partial":
            c, st = extra.get(q["wp"], ("", None))
            partial.append({"wp": q["wp"], "site": q["site"],
                            "commune": q.get("commune"), "date": q["status_date"],
                            "kind": kind_of.get(q["wp"]), "comments": c or "",
                            "rid": rows[q["wp"]].get("rid"),
                            "status": st or "not classified"})
    out = idx
    for m, val, close in ((mp, pumps, "];"), (ms, S, "};")):
        mm = re.search(r"\bconst %s\s*=\s*" % ("PUMPS" if close == "];" and val is pumps else "S"), out)
        out = (out[:mm.end()] + json.dumps(val, separators=(", ", ": "))
               + out[out.index(close, mm.end()) + 1:])
    for name, val in (("DOWN", down), ("PARTIAL", partial)):
        mm = re.search(r"\bconst %s\s*=\s*" % name, out)
        out = (out[:mm.end()] + json.dumps(val, separators=(", ", ": "))
               + out[out.index("];", mm.end()) + 1:])
    io.open(p, "w", encoding="utf8").write(out)
    return len(down), len(partial)


def main():
    argv = sys.argv[1:]
    pumps = pumps_from_page()
    if "--reproduce" in argv:
        cut = argv[argv.index("--reproduce") + 1]
        # against the FROZEN baseline, not against the page: once the page has
        # been rebuilt it would be reproducing itself, which proves nothing.
        base_p = os.path.join(REPO, "data", "call_status_baseline.json")
        if not os.path.isfile(base_p):
            sys.exit("no data/call_status_baseline.json to reproduce against")
        base = json.load(open(base_p))["status"]
        rows, branch = build(cut, pumps)
        bad = [(wp, base[wp], rows[wp]["status"]) for wp in base
               if wp in rows and rows[wp]["status"] != base[wp]]
        n = len(base)
        print(f"reproduction against the published tables, extract cut at {cut}")
        for k, v in branch.most_common():
            print(f"   {v:5d}  {k}")
        print(f"\n   {n - len(bad)}/{n} pumps reproduce the published status")
        if bad:
            print(f"   {len(bad)} DISAGREE:")
            for wp, was, got in bad[:12]:
                print(f"     {wp} published={was} rule={got}")
            return 1
        print("   exact match")
        return 0
    cut = datetime.date.today().isoformat()
    rows, branch = build(cut, pumps)
    split = collections.Counter(r["status"] for r in rows.values())
    print(f"built to {cut}: " + ", ".join(f"{k} {v}" for k, v in sorted(split.items())))
    for k, v in branch.most_common():
        print(f"   {v:5d}  {k}")
    if "--write" in argv:
        json.dump({"built": cut, "rule": RULE_ON_PAGE, "status": rows,
                   "branches": dict(branch), "split": dict(split)},
                  open(OUT, "w"), indent=1, sort_keys=True)
        nd, np_ = apply_to_page(rows, cut)
        print(f"\nwrote {OUT} and patched index.html: "
              f"{nd} down, {np_} partially working")
    else:
        print("\n--dry-run: nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
