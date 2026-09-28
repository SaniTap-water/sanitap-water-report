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
with a parent (1.3) that is the system, one of its duplicates or its record of
record, from ~/mwater-exports/piped_point_reg.json every build
(act-moramanga-register-standposts). Private connections and sources are not
counted.

A duplicate is RESOLVED when it no longer appears in the extract (merged or
retired in mWater, which the build sees on its own) or when data/
moramanga_system_dedupe.json carries a note for it under "resolutions"
({"<code>": {"resolution": "merge into 1108783583" | "retire" | "keep: ...",
"date": "YYYY-MM-DD", "source": "..."}}). That block is edited by hand; the
rest of the file is output. The action closes when no duplicate is unresolved.

    python3 tools/moramanga_dedupe.py --write
    python3 tools/moramanga_dedupe.py --check
    python3 tools/moramanga_dedupe.py --history   # re-read the 3 km snapshot (slow)
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
        systems.append(sysrec)
    unresolved = sorted(c for c in dup_codes if not res.get(c))

    # standposts: public tap stands and kiosks registered on each scheme
    regs = json.load(open(POINT_REG, encoding="utf8")) if os.path.isfile(POINT_REG) else []
    for sy in systems:
        scheme = {sy["code"]} | {d["code"] for d in sy["duplicates"]} \
            | ({sy["record_of_record"]["code"]} if sy.get("record_of_record") else set())
        pts = sorted({code_of(answer(r, PR_POINT)) for r in regs
                      if r.get("form") == PT_REG_FORM and r.get("status") == "final"
                      and code_of(answer(r, PR_SYSTEM)) in scheme
                      and answer(r, PR_TYPE) in PUBLIC_TYPES} - {None})
        sy["standposts"] = pts
        sy["standposts_n"] = len(pts)
    return {
        "note": "Written by tools/moramanga_dedupe.py from ~/mwater-exports/piped_systems.csv, "
                "~/mwater-exports/piped_point_reg.json and the dated 3 km snapshot "
                "data/moramanga_system_history.json (all read only). Only 'resolutions' is edited "
                "by hand: {code: {resolution, date, source}}. A duplicate that leaves the extract "
                "is resolved in mWater.",
        "nearby_m": NEARBY_M,
        "history_m": HISTORY_M,
        "history_read": (hist or {}).get("read_on", "")[:10] or None,
        "resolutions": res,
        "systems": systems,
        "duplicates": len(dup_codes),
        "unresolved": len(unresolved),
        "unresolved_codes": unresolved,
        "nearby": sum(len(s["nearby"]) for s in systems),
        "resolved_by_absence": sorted(c for c in res if c not in rows),
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


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if mode == "--history":
        refresh_history()
        mode = "--write"
    old = json.load(open(OUT, encoding="utf8")) if os.path.isfile(OUT) else {}
    doc = build(old)
    new = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    cur = open(OUT, encoding="utf8").read() if os.path.isfile(OUT) else ""
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
