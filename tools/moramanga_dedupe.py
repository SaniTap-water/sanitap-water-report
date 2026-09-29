# -*- coding: utf-8 -*-
"""Candidate duplicate system records for the four Moramanga piped systems.

Endur'O's mWater group holds more than one water_system record for some of the
Moramanga schemes: "AEPP AMBOHIBOLA" beside Ambohibola, "AEPP AMBOASARY GARE"
and "Forage Amboasary gare" beside Amboasary gara, and twin records for Amboanjo
and Andilanatoby. Which record is the system of record has to be settled before
the Moramanga taps are registered against one of them
(act-moramanga-system-dedupe).

Every build this recomputes, from the Endur'O systems extract
(~/mwater-exports/piped_systems.csv, read only), for each of the four systems:

  duplicates  every other Endur'O system record whose place name is the same
              (ignoring AEPP / AEPG / Forage / ECAR, case, accents and
              gare/gara), wherever it lies, with the distance between the two
              GPS points;
  nearby      every other Endur'O system record within NEARBY_M metres whatever
              its name: probably a tap or an institution entered as a system.
              Listed for checking; it does not hold the action open.

WITHIN 3 KM, WITH HISTORY. data/moramanga_system_history.json is a dated
snapshot of every water_system record within HISTORY_M of each of the four,
in ANY mWater group, with its creator, creation date, the water points that
name it as their system and the form responses that reference it. It comes
from tools/mwater/system_history.mjs (GET only) and takes ten minutes or more,
so it is refreshed by hand, not every build:

    python3 tools/moramanga_dedupe.py --history

A same-name record from another group found there counts as a duplicate too.
The RECORD OF RECORD recommended for each scheme is, among the system and its
same-name duplicates within HISTORY_M, the one with the most attached form
responses; then the most linked water points; then the one Endur'O's
registration forms (System 44044e27, Distribution Point 8a3af50c) reference;
then the original of the four.

STANDPOSTS. For each scheme, the public standposts and kiosks (Distribution
Point registration 1.5 = public tap stand or urban kiosk) registered final
with a parent (1.3) that is the scheme's record of record (a registration on a
duplicate does not count: it has to be moved), from ~/mwater-exports/piped_point_reg.json every build
(act-moramanga-register-standposts). Private connections and sources are not
counted.

DECISIONS AND THE INTERIM MAPPING (hand-edited, like "resolutions"):
"decisions" fixes a scheme's record of record whatever the recommendation
says; "interim_points" maps water points still linked in mWater to a duplicate
onto the record of record (Adriaan Mol, 29 Sep 2026: the 19 kiosks on WaterAid's
441839342 belong to 1108783583). The mapping is used by tools/rebuild_piped_wq.py
to classify piped water quality and NEVER counts toward closing
act-moramanga-register-standposts, which needs a submitted Distribution Point
registration whose parent is the record of record itself. "permissions" is a
dated read of who can edit those records.

OTHER ORGANISATIONS' RECORDS (Adriaan Mol, 29 Sep 2026). The management
contract for the Moramanga systems is with Endur'O/NatuRano. Records owned by
another organisation (WaterAid, MG MERL and others) are historical: never
edited, relinked, deleted or asked to be transferred. Such a duplicate carries
a resolution note of kind "other_organisation" and counts as resolved.
Endur'O's own duplicates stay open until Endur'O retires them or notes them.

CROSSWALK (data/moramanga_wp_crosswalk.json, written every build). Endur'O
registers every public standpost as a NEW Distribution Point under its own
system record, quoting the old mWater ID in the new point's description where
the standpost exists from an earlier project. Each new point (a final
Distribution Point registration whose parent is a record of record) is matched
to an earlier-project point (data/moramanga_earlier_points.json):

  confirmed   the old ID is quoted in the new point's description
              (~/mwater-exports/enduro_points.csv);
  suggested   failing that, the nearest old point within MATCH_M metres with
              a similar name.

Each old point matches at most one new point. The pairing uses the crosswalk so
that a sample at an old record counts for the new point, and physical
standposts = new points + unmatched old points, so none is counted twice.

ENDUR'O'S OWN DUPLICATES (Adriaan Mol, 29 Sep 2026). The "AEPP"/"Forage"
records that hold the existing borehole links are kept as history (note of kind
"endur_o_history"). The three accidental duplicates created alongside the
records of record (ACCIDENTAL) are for Endur'O to retire in mWater; each counts
as resolved once it is gone from the extract or its status is decommissioned
or disposed.

WRONG PARENT (a readout in publish.sh, never failing the build): any
Distribution Point registration whose parent (1.3) is one of Endur'O's six
duplicates, and any Endur'O water point created on or after DECIDED whose
water_system is one of them, rather than the record of record. The borehole
links that existed before the decision are history and are not flagged.

A duplicate is RESOLVED when it no longer appears in the extract (merged or
retired in mWater, which the build sees on its own) or when data/
moramanga_system_dedupe.json carries a note for it under "resolutions"
({"<code>": {"resolution": "merge into 1108783583" | "retire" | "keep: ...",
"date": "YYYY-MM-DD", "source": "..."}}). That block is edited by hand; the
rest of the file is output. The action closes when no duplicate is unresolved.

    python3 tools/moramanga_dedupe.py --write
    python3 tools/moramanga_dedupe.py --check
    python3 tools/moramanga_dedupe.py --history   # re-read the 3 km snapshot and the
                                                  # earlier-project points (slow)
"""
import csv, datetime, io, json, math, os, re, subprocess, sys, unicodedata

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "moramanga_system_dedupe.json")
EXTRACT = os.path.expanduser("~/mwater-exports/piped_systems.csv")
STATUS = os.path.join(REPO, "data", "piped_systems_status.json")
FOUR = ("1108783583", "1108783624", "1108783648", "1108783662")
NEARBY_M = 250
HISTORY_M = 3000
HISTORY = os.path.join(REPO, "data", "moramanga_system_history.json")
EARLIER = os.path.join(REPO, "data", "moramanga_earlier_points.json")
CROSSWALK = os.path.join(REPO, "data", "moramanga_wp_crosswalk.json")
ENDURO_POINTS = os.path.expanduser("~/mwater-exports/enduro_points.csv")
MATCH_M = 30
ACCIDENTAL = ("1108783569", "1108783631", "1108783655")
RETIRED_STATUS = {"decommissioned", "disposed"}   # water_system.status
DECIDED = "2026-09-29"
NAME_NOISE = {"kiosque", "kiosk", "kiosky", "borne", "fontaine", "bf", "bp", "point", "d", "eau",
              "de", "du", "la", "le", "aepp", "aepg", "amboasary", "gara", "gare", "ambohibola",
              "amboanjo", "andilanatoby", "tap", "robinet", "public", "publique"}
POINT_REG = os.path.expanduser("~/mwater-exports/piped_point_reg.json")
PT_REG_FORM, PR_POINT, PR_SYSTEM, PR_TYPE = (
    "8a3af50ceec84cda85d454d96079991d", "8f174aec", "e5380235", "59fa54b3")
PUBLIC_TYPES = {"9nHrfX7": "public tap stand", "FVRCE79": "urban kiosk"}
REG_FORMS = ("44044e27c0f24cc4a432a38b09886684", "8a3af50ceec84cda85d454d96079991d")
PREFIX = re.compile(r"\b(aepp|aepg|forage|ecar)\b")


def place(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = PREFIX.sub(" ", s).replace("gare", "gara")
    return " ".join(s.split())


def latlon(r):
    try:
        c = json.loads(r.get("location") or "")["coordinates"]
        return float(c[1]), float(c[0])
    except (ValueError, KeyError, TypeError, IndexError):
        return None


def metres(a, b):
    if not a or not b:
        return None
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2)
    return round(2 * 6371000 * math.asin(math.sqrt(h)))


def answer(resp, prefix):
    for k, v in (resp.get("data") or {}).items():
        if k.startswith(prefix):
            return (v or {}).get("value")
    return None


def code_of(v):
    return str(v.get("code")) if isinstance(v, dict) and v.get("code") else None


def history():
    return json.load(open(HISTORY, encoding="utf8")) if os.path.isfile(HISTORY) else None


def recommend(cands):
    """The record of record among a scheme's candidates, with the reason."""
    key = lambda c: (c["responses"], c["points_n"], c["registration_uses"], c["original"])
    best = sorted(cands, key=key, reverse=True)
    top, why = best[0], []
    rivals = [c for c in best[1:]]
    if not rivals:
        return top, "the only record for this scheme"
    r = rivals[0]
    if top["responses"] > r["responses"]:
        why.append(f"most attached form responses ({top['responses']} against {r['responses']} "
                   f"for {r['code']})")
    elif top["points_n"] > r["points_n"]:
        why.append(f"tied on responses ({top['responses']}); most linked water points "
                   f"({top['points_n']} against {r['points_n']})")
    elif top["registration_uses"] > r["registration_uses"]:
        why.append(f"tied on responses and points; Endur'O's registration forms reference it "
                   f"({top['registration_uses']} registration response(s))")
    else:
        why.append("tied on responses, points and registration use; the original record")
    more = [c for c in rivals if c["points_n"] > top["points_n"]]
    if more:
        m = max(more, key=lambda c: c["points_n"])
        why.append(f"but {m['code']} ({m['group']}) carries {m['points_n']} linked water points, "
                   "which move to the record of record or keep a link to it")
    return top, "; ".join(why)


def name_tokens(n):
    s = unicodedata.normalize("NFKD", n or "").encode("ascii", "ignore").decode().lower()
    return {t for t in re.findall(r"[a-z]+|\d+", s) if t not in NAME_NOISE and len(t) > 1}


def similar(a, b):
    """Two point names share a meaningful word, or read alike overall."""
    import difflib
    ta, tb = name_tokens(a), name_tokens(b)
    if ta & tb:
        return True
    return difflib.SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio() >= 0.6 \
        if ta and tb else False


def crosswalk(new_points, old_points):
    """Match Endur'O's new points to earlier-project points. new_points and
    old_points are lists of {code, name, desc?, location?}. Returns the
    crosswalk document (without the build's own note)."""
    old_by = {o["code"]: o for o in old_points}
    taken_old, links = set(), {}
    # confirmed: the old ID quoted in the new point's description
    for n in sorted(new_points, key=lambda x: x["code"]):
        for c in re.findall(r"\b(\d{6,12})\b", n.get("desc") or ""):
            if c in old_by and c not in taken_old:
                links[n["code"]] = (c, "confirmed", "old ID quoted in the new point's description",
                                    metres(tuple(n["location"]) if n.get("location") else None,
                                           tuple(old_by[c]["location"]) if old_by[c].get("location") else None))
                taken_old.add(c)
                break
    # suggested: nearest old point within MATCH_M with a similar name
    cands = []
    for n in new_points:
        if n["code"] in links or not n.get("location"):
            continue
        for o in old_points:
            if o["code"] in taken_old or not o.get("location"):
                continue
            m = metres(tuple(n["location"]), tuple(o["location"]))
            if m is not None and m <= MATCH_M and similar(n.get("name"), o.get("name")):
                cands.append((m, n["code"], o["code"]))
    for m, nc, oc in sorted(cands):
        if nc in links or oc in taken_old:
            continue
        links[nc] = (oc, "suggested", f"GPS within {MATCH_M} m and a similar name", m)
        taken_old.add(oc)
    rows = [{"old": oc, "old_name": old_by[oc].get("name"), "old_owner": old_by[oc].get("owner"),
             "new": nc, "new_name": next((n.get("name") for n in new_points if n["code"] == nc), None),
             "status": st, "method": how, "distance_m": m}
            for nc, (oc, st, how, m) in sorted(links.items(), key=lambda kv: kv[1][0])]
    unmatched = [{"code": o["code"], "name": o.get("name"), "owner": o.get("owner")}
                 for o in sorted(old_points, key=lambda x: x["code"]) if o["code"] not in taken_old]
    return {"match_m": MATCH_M, "crosswalk": rows,
            "old_to_new": {r["old"]: r["new"] for r in rows},
            "unmatched_old": unmatched,
            "new_unmatched": sorted(n["code"] for n in new_points if n["code"] not in links),
            "counts": {"old": len(old_points), "new": len(new_points),
                       "confirmed": sum(1 for r in rows if r["status"] == "confirmed"),
                       "suggested": sum(1 for r in rows if r["status"] == "suggested"),
                       "unmatched_old": len(unmatched),
                       "physical_standposts": len(new_points) + len(unmatched)}}


def new_endur_points(systems):
    """Endur'O's new points: final Distribution Point registrations whose
    parent is a record of record, with name, description and GPS from the
    Endur'O water-point extract."""
    ror = {(s.get("record_of_record") or {}).get("code") or s["code"] for s in systems}
    regs = json.load(open(POINT_REG, encoding="utf8")) if os.path.isfile(POINT_REG) else []
    codes = {code_of(answer(r, PR_POINT)) for r in regs
             if r.get("form") == PT_REG_FORM and r.get("status") == "final"
             and code_of(answer(r, PR_SYSTEM)) in ror} - {None}
    ents = {}
    if os.path.isfile(ENDURO_POINTS):
        with io.open(ENDURO_POINTS, encoding="utf8") as fh:
            ents = {r["code"]: r for r in csv.DictReader(fh) if r.get("code")}
    return [{"code": c, "name": (ents.get(c, {}).get("name") or "").strip() or None,
             "desc": ents.get(c, {}).get("desc") or "", "location": latlon(ents[c]) if c in ents else None}
            for c in sorted(codes)]


def wrong_parent(regs, points, dups):
    """New Moramanga points hung on a duplicate system record rather than the
    record of record. regs: Distribution Point registrations; points: rows of
    the Endur'O water-point extract; dups: {duplicate code: its mWater _id}."""
    by_id = {i: c for c, i in dups.items() if i}
    wrong = []
    for r in regs:
        if r.get("form") != PT_REG_FORM:
            continue
        par = code_of(answer(r, PR_SYSTEM))
        if par in dups:
            wrong.append({"kind": "Distribution Point registration", "record": r.get("code"),
                          "point": code_of(answer(r, PR_POINT)), "parent": par,
                          "status": r.get("status"),
                          "on": str(r.get("submittedOn") or r.get("startedOn") or "")[:10]})
    for p in points:
        par = by_id.get(p.get("water_system") or "")
        # the borehole links that existed before the decision are history
        if par and (p.get("_created_on") or "")[:10] >= DECIDED:
            wrong.append({"kind": (p.get("type") or "").strip() or "water point",
                          "record": None, "point": p.get("code"), "parent": par,
                          "status": None, "on": (p.get("_created_on") or "")[:10]})
    return wrong


def build(old):
    with io.open(EXTRACT, encoding="utf8") as fh:
        rows = {r["code"]: r for r in csv.DictReader(fh) if r.get("code")}
    status = json.load(open(STATUS, encoding="utf8"))["systems"]
    res = old.get("resolutions") or {}
    hist = history()
    systems, dup_codes = [], set()
    for code in FOUR:
        me = rows.get(code)
        if not me:
            systems.append({"code": code, "name": (status.get(code) or {}).get("name"),
                            "in_extract": False, "duplicates": [], "nearby": []})
            continue
        here, pl = latlon(me), place(me.get("name"))
        dups, near = [], []
        for c, r in sorted(rows.items()):
            if c == code:
                continue
            m = metres(here, latlon(r))
            e = {"code": c, "name": (r.get("name") or "").strip() or None, "distance_m": m,
                 "status": (status.get(c) or {}).get("status"), "group": None}
            if pl and place(r.get("name")) == pl:
                e["resolution"] = res.get(c)
                dups.append(e)
                dup_codes.add(c)
            elif m is not None and m <= NEARBY_M:
                near.append(e)
        sysrec = {"code": code, "name": (me.get("name") or "").strip(), "in_extract": True,
                  "duplicates": dups, "nearby": sorted(near, key=lambda x: x["distance_m"])}
        # within 3 km, any group, from the dated snapshot
        if hist and (hist.get("systems") or {}).get(code):
            within = []
            for h in hist["systems"][code]:
                m = metres(here, tuple(h["location"]) if h.get("location") else None)
                reg = sum(n for f, n in (h.get("responses_by_form") or {}).items() if f in REG_FORMS)
                w = {"code": h["code"], "name": h.get("name"), "distance_m": m,
                     "group": h.get("managed_by_name") or h.get("managed_by"),
                     "created_on": (h.get("created_on") or "")[:10] or None,
                     "created_by": h.get("created_by_name") or (h.get("created_by") or "")[:8] or None,
                     "points": [p["code"] for p in h.get("points") or []],
                     "points_n": len(h.get("points") or []),
                     "responses": h.get("responses", 0),
                     "responses_final": h.get("responses_final", 0),
                     "registration_uses": reg,
                     "same_name": h["code"] == code or place(h.get("name")) == pl,
                     "original": h["code"] == code}
                within.append(w)
                # another group's same-name record is a duplicate too
                if w["same_name"] and not w["original"] and w["code"] not in rows:
                    e = {"code": w["code"], "name": w["name"], "distance_m": m,
                         "status": None, "group": w["group"], "resolution": res.get(w["code"])}
                    dups.append(e)
                    dup_codes.add(w["code"])
            within.sort(key=lambda x: (x["distance_m"] is None, x["distance_m"] or 0))
            sysrec["within"] = within
            cands = [w for w in within if w["same_name"]]
            if cands:
                top, why = recommend(cands)
                sysrec["record_of_record"] = {"code": top["code"], "name": top["name"],
                                              "group": top["group"], "reason": why}
        dec = (old.get("decisions") or {}).get(code)
        if dec:
            ror = dec["record_of_record"]
            w = next((x for x in sysrec.get("within") or [] if x["code"] == ror), None)
            sysrec["record_of_record"] = {
                "code": ror, "name": (w or {}).get("name") or sysrec["name"],
                "group": (w or {}).get("group"),
                "reason": "decided: " + dec["source"]
                          + ("" if not sysrec.get("record_of_record")
                             or sysrec["record_of_record"]["code"] == ror
                             else f" (the rule would have picked {sysrec['record_of_record']['code']})"),
                "decided": True}
        interim = (old.get("interim_points") or {}).get(code)
        if interim:
            sysrec["interim"] = {"from_system": interim["from_system"], "source": interim["source"],
                                 "points": interim["points"], "n": len(interim["points"])}
        systems.append(sysrec)
    retired = sorted(c for c in dup_codes if c in rows
                     and (rows[c].get("status") or "").strip() in RETIRED_STATUS)
    unresolved = sorted(c for c in dup_codes if not res.get(c) and c not in retired
                        and not (c in ACCIDENTAL and c not in rows))

    # standposts: public tap stands and kiosks registered on each scheme
    regs = json.load(open(POINT_REG, encoding="utf8")) if os.path.isfile(POINT_REG) else []
    for sy in systems:
        scheme = {(sy.get("record_of_record") or {}).get("code") or sy["code"]}
        pts = sorted({code_of(answer(r, PR_POINT)) for r in regs
                      if r.get("form") == PT_REG_FORM and r.get("status") == "final"
                      and code_of(answer(r, PR_SYSTEM)) in scheme
                      and answer(r, PR_TYPE) in PUBLIC_TYPES} - {None})
        sy["standposts"] = pts
        sy["standposts_n"] = len(pts)
    # wrong parent: a new point hung on one of Endur'O's own duplicates
    own_dups = sorted(c for c in dup_codes if c in rows)
    pts = []
    if os.path.isfile(ENDURO_POINTS):
        with io.open(ENDURO_POINTS, encoding="utf8") as fh:
            pts = list(csv.DictReader(fh))
    wrong = wrong_parent(regs, pts, {c: rows[c].get("_id") for c in own_dups})
    return {
        "retired_in_mwater": retired,
        "accidental": list(ACCIDENTAL),
        "accidental_open": [c for c in ACCIDENTAL if c in unresolved],
        "wrong_parent": wrong,
        "wrong_parent_n": len(wrong),
        "note": "Written by tools/moramanga_dedupe.py from ~/mwater-exports/piped_systems.csv, "
                "~/mwater-exports/piped_point_reg.json and the dated 3 km snapshot "
                "data/moramanga_system_history.json (all read only). Only 'resolutions' is edited "
                "by hand: resolutions {code: {resolution, date, source}}, decisions, interim_points "
                "and the dated permissions read. A duplicate that leaves the extract is resolved "
                "in mWater.",
        "nearby_m": NEARBY_M,
        "history_m": HISTORY_M,
        "history_read": (hist or {}).get("read_on", "")[:10] or None,
        "resolutions": res,
        "decisions": old.get("decisions") or {},
        "interim_points": old.get("interim_points") or {},
        "permissions": old.get("permissions") or {},
        "systems": systems,
        "duplicates": len(dup_codes),
        "unresolved": len(unresolved),
        "unresolved_codes": unresolved,
        "nearby": sum(len(s["nearby"]) for s in systems),
        "resolved_by_absence": sorted(c for c, v in res.items() if c not in rows
                                      and (v or {}).get("kind") != "other_organisation"),
        "resolved_other_organisation": sorted(c for c in dup_codes
                                              if (res.get(c) or {}).get("kind") == "other_organisation"),
        "resolved_endur_o_history": sorted(c for c in dup_codes
                                           if (res.get(c) or {}).get("kind") == "endur_o_history"),
        "standposts": sum(s.get("standposts_n", 0) for s in systems),
        "systems_without_standpost": sum(1 for s in systems if not s.get("standposts_n")),
    }


def refresh_history():
    r = subprocess.run(["node", os.path.join(REPO, "tools", "mwater", "system_history.mjs"),
                        ",".join(FOUR), str(HISTORY_M)],
                       capture_output=True, text=True, cwd=REPO)
    if r.returncode != 0 or not r.stdout.strip():
        sys.exit("moramanga_dedupe: the 3 km snapshot could not be read: "
                 + (r.stderr or r.stdout)[-300:])
    doc = json.loads(r.stdout)
    doc["note"] = ("Written by tools/moramanga_dedupe.py --history through "
                   "tools/mwater/system_history.mjs (GET only). A dated snapshot, refreshed by hand.")
    json.dump(doc, open(HISTORY, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    open(HISTORY, "a", encoding="utf8").write("\n")
    print(f"data/moramanga_system_history.json: read {doc['read_on'][:16]}")
    codes = [p["code"] for m in (json.load(open(OUT, encoding="utf8")).get("interim_points") or {}).values()
             for p in m.get("points") or []]
    if codes:
        r = subprocess.run(["node", os.path.join(REPO, "tools", "mwater", "earlier_points.mjs"),
                            ",".join(codes)], capture_output=True, text=True, cwd=REPO)
        if r.returncode == 0 and r.stdout.strip():
            ep = json.loads(r.stdout)
            prev = json.load(open(EARLIER, encoding="utf8")) if os.path.isfile(EARLIER) else {}
            ep["note"] = prev.get("note", "Earlier-project water points (GET only).")
            ep["points"] = sorted(ep["points"], key=lambda p: p["code"])
            json.dump(ep, open(EARLIER, "w", encoding="utf8"), indent=1, ensure_ascii=False)
            open(EARLIER, "a", encoding="utf8").write("\n")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if mode == "--wrong-parent":
        d = json.load(open(OUT, encoding="utf8"))
        print(f"Moramanga points on a duplicate system record instead of the record of record "
              f"(counted, never failing): {d.get('wrong_parent_n', 0)}")
        for x in d.get("wrong_parent") or []:
            print(f"  {x['kind']} {x['point'] or '-'} ({x['record'] or 'entity'}, {x['on']}) "
                  f"on {x['parent']}")
        return 0
    if mode == "--history":
        refresh_history()
        mode = "--write"
    old = json.load(open(OUT, encoding="utf8")) if os.path.isfile(OUT) else {}
    doc = build(old)
    old_pts = (json.load(open(EARLIER, encoding="utf8")) if os.path.isfile(EARLIER) else {}).get("points") or []
    cw = {"note": "Written every build by tools/moramanga_dedupe.py: Endur'O's new Distribution "
                  "Points on the Moramanga records of record, matched to earlier-project points "
                  "(data/moramanga_earlier_points.json). confirmed = the old ID is quoted in the new "
                  "point's description; suggested = GPS within match_m and a similar name. Old "
                  "records are other organisations' history and are never edited in mWater.",
          **crosswalk(new_endur_points(doc["systems"]), old_pts)}
    cw_new = json.dumps(cw, indent=1, ensure_ascii=False) + "\n"
    cw_cur = open(CROSSWALK, encoding="utf8").read() if os.path.isfile(CROSSWALK) else ""
    new = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    cur = open(OUT, encoding="utf8").read() if os.path.isfile(OUT) else ""
    if cw_new != cw_cur:
        if mode != "--write":
            print("data/moramanga_wp_crosswalk.json DIFFERS from the extract")
            return 1
        open(CROSSWALK, "w", encoding="utf8").write(cw_new)
        c = cw["counts"]
        print(f"data/moramanga_wp_crosswalk.json: {c['new']} new point(s), {c['old']} earlier-project; "
              f"{c['confirmed']} confirmed, {c['suggested']} suggested, {c['unmatched_old']} old unmatched")
    if new == cur:
        print("data/moramanga_system_dedupe.json unchanged")
        return 0
    if mode != "--write":
        print("data/moramanga_system_dedupe.json DIFFERS from the extract")
        return 1
    open(OUT, "w", encoding="utf8").write(new)
    print(f"data/moramanga_system_dedupe.json: {doc['duplicates']} duplicate record(s), "
          f"{doc['unresolved']} unresolved; {doc['nearby']} other record(s) within {NEARBY_M} m; "
          f"{doc['standposts']} public standpost(s) registered, "
          f"{doc['systems_without_standpost']} system(s) with none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
