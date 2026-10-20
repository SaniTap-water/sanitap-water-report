# -*- coding: utf-8 -*-
"""Fill district and commune for the Marolinta records from the register.

The Marolinta table showed "no district" against 11 of 13 records. That was
read off admin_div1..5, which the survey and prospection entries never carry.
They DO carry admin_region, a numeric region id, and every located water point
with region 418299 resolves to exactly one place:

    418299 -> Androy / Beloha / Marolinta / Mahafaly Centre / Marolinta

so district and commune are recoverable from the register for every record
carrying that region. Fokontany is not: admin_div4 varies between fokontany
and only the located points hold it. Where the technician typed a fokontany
into the record description it is carried here as a description hint, marked
as such, and never presented as a register value.

    python3 tools/marolinta_admin.py --write   # from the register extract, rewrite the JSON
    python3 tools/marolinta_admin.py --show
"""
import datetime, json, os, re, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "marolinta_admin.json")
FKT = re.compile(r"FKT\s*_?\s*([A-Za-zÀ-ÿ' ]+?)(?:_|$|\()", re.I)


REGISTER = os.path.expanduser("~/mwater-exports/wp_madavance.csv")


def register():
    """The register rows from the run's extract (20 Oct 2026: no live read).
    JSON-valued columns (photos) come back decoded."""
    import csv
    csv.field_size_limit(10 ** 9)
    if not os.path.isfile(REGISTER):
        sys.exit(f"marolinta_admin: no {REGISTER}")
    rows = list(csv.DictReader(open(REGISTER, encoding="utf8", newline="")))
    for r in rows:
        try:
            r["photos"] = json.loads(r.get("photos") or "[]")
        except ValueError:
            r["photos"] = []
        for k in list(r):
            if r[k] == "":
                r[k] = None
        if (r.get("admin_region") or "").isdigit():
            r["admin_region"] = int(r["admin_region"])
    return rows


def codes():
    idx = open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    m = re.search(r"\bconst REG\s*=\s*", idx)
    reg = json.loads(idx[m.end():idx.index("};", m.end()) + 1])
    return [r["wp"] for r in reg["marolinta"]], reg


def fokontany_hint(desc):
    if not desc:
        return None
    m = FKT.search(desc)
    if m:
        return " ".join(w.capitalize() for w in m.group(1).split())
    # descriptions that name the place without the FKT marker
    for cand in ("Mahafaly Sud", "Mahafaly Centre", "Sasavisoa", "Mahatsara",
                 "Antsasavy Soa", "Tanambao"):
        if cand.lower().replace(" ", "") in desc.lower().replace(" ", ""):
            return cand
    return None


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--show"
    if mode == "--show":
        print(json.dumps(json.load(open(OUT)), indent=1) if os.path.isfile(OUT)
              else "no data/marolinta_admin.json yet")
        return 0
    if mode != "--write":
        sys.exit("usage: marolinta_admin.py --write | --show")
    wanted, _ = codes()
    reg = register()
    ents = [e for e in reg if e.get("code") in set(wanted)]
    # learn region -> place from every located point in the register
    regions = {}
    for r in {e.get("admin_region") for e in ents if e.get("admin_region")}:
        got = [g for g in reg if g.get("admin_region") == r and g.get("admin_div1")]
        names = {tuple(g.get(f"admin_div{i}") for i in range(1, 4)) for g in got}
        regions[str(r)] = ({"region": list(names)[0][0], "district": list(names)[0][1],
                            "commune": list(names)[0][2], "from": len(got)}
                           if len(names) == 1 else None)
    out, missing, nophoto = [], 0, 0
    for e in sorted(ents, key=lambda x: x["code"]):
        reg_id = e.get("admin_region")
        place = regions.get(str(reg_id))
        own = e.get("admin_div2")
        rec = {"code": e["code"], "name": e.get("name"),
               "admin_region": reg_id,
               "district": e.get("admin_div2") or (place or {}).get("district"),
               "commune": e.get("admin_div3") or (place or {}).get("commune"),
               "fokontany": e.get("admin_div4"),
               "fokontany_from_description": None if e.get("admin_div4")
               else fokontany_hint(e.get("desc")),
               "source": "register" if own else
                         ("admin_region" if place else "unresolved"),
               "photos": len(e.get("photos") or [])}
        if not rec["district"]:
            missing += 1
            rec["why_empty"] = (
                f"the register holds region {reg_id} for this record and no "
                "located water point shares it, so there is nothing to read a "
                "district from" if reg_id else
                "the record carries no region at all, which is what a "
                "prospection entry looks like before it is registered")
        if not rec["photos"]:
            nophoto += 1
        out.append(rec)
    doc = {"checked": datetime.date.today().isoformat(),
           "region_map": regions,
           "records": out,
           "resolved_from_register": sum(1 for r in out if r["source"] == "register"),
           "resolved_from_region": sum(1 for r in out if r["source"] == "admin_region"),
           "still_missing": missing,
           "no_photograph": nophoto}
    json.dump(doc, open(OUT, "w"), indent=1, sort_keys=True)
    print(json.dumps({k: v for k, v in doc.items() if k != "records"},
                     indent=1, sort_keys=True))
    for r in out:
        print(f'  {r["code"]:11s} {r["source"]:12s} '
              f'{(r["district"] or "-"):10s} {(r["commune"] or "-"):12s} '
              f'fkt={r["fokontany"] or r["fokontany_from_description"] or "-"}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
