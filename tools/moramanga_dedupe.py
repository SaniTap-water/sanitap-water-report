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

A duplicate is RESOLVED when it no longer appears in the extract (merged or
retired in mWater, which the build sees on its own) or when data/
moramanga_system_dedupe.json carries a note for it under "resolutions"
({"<code>": {"resolution": "merge into 1108783583" | "retire" | "keep: ...",
"date": "YYYY-MM-DD", "source": "..."}}). That block is edited by hand; the
rest of the file is output. The action closes when no duplicate is unresolved.

    python3 tools/moramanga_dedupe.py --write
    python3 tools/moramanga_dedupe.py --check
"""
import csv, io, json, math, os, re, sys, unicodedata

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "moramanga_system_dedupe.json")
EXTRACT = os.path.expanduser("~/mwater-exports/piped_systems.csv")
STATUS = os.path.join(REPO, "data", "piped_systems_status.json")
FOUR = ("1108783583", "1108783624", "1108783648", "1108783662")
NEARBY_M = 250
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


def build(old):
    with io.open(EXTRACT, encoding="utf8") as fh:
        rows = {r["code"]: r for r in csv.DictReader(fh) if r.get("code")}
    status = json.load(open(STATUS, encoding="utf8"))["systems"]
    res = old.get("resolutions") or {}
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
                 "status": (status.get(c) or {}).get("status")}
            if pl and place(r.get("name")) == pl:
                e["resolution"] = res.get(c)
                dups.append(e)
                dup_codes.add(c)
            elif m is not None and m <= NEARBY_M:
                near.append(e)
        systems.append({"code": code, "name": (me.get("name") or "").strip(),
                        "in_extract": True, "duplicates": dups,
                        "nearby": sorted(near, key=lambda x: x["distance_m"])})
    unresolved = sorted(c for c in dup_codes if not res.get(c))
    # a note for a record that has left the extract is history, kept as is
    return {
        "note": "Written by tools/moramanga_dedupe.py from ~/mwater-exports/piped_systems.csv "
                "(read only). Only 'resolutions' is edited by hand: {code: {resolution, date, "
                "source}}. A duplicate that leaves the extract is resolved in mWater.",
        "nearby_m": NEARBY_M,
        "resolutions": res,
        "systems": systems,
        "duplicates": len(dup_codes),
        "unresolved": len(unresolved),
        "unresolved_codes": unresolved,
        "nearby": sum(len(s["nearby"]) for s in systems),
        "resolved_by_absence": sorted(c for c in res if c not in rows),
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
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
          f"{doc['unresolved']} unresolved; {doc['nearby']} other record(s) within {NEARBY_M} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
