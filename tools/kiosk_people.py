# -*- coding: utf-8 -*-
"""People served at the managed Tana kiosk, from its card data (7 Oct 2026).

Rules (Adriaan Mol, 7 Oct 2026), stated in the derivation on the page:
  household size  the census (INSTAT RGPH-3, Analamanga urban, 3.9) until a
                  project survey measures it; when the piped-system survey
                  (act-piped-usage-survey) records household size for the kiosk,
                  its mean replaces the census value automatically
  cards           one registered card is one household until the contrary is
                  proved; two cards with the same registration details (name,
                  phone or ID) are flagged, count as one household, and are
                  listed on the report

Card data: a Curtech/Zoho export (getNFCcards) filed at build_config
kiosk.card_export in the Central Data Hub. Without it the recorded count (126
cards, Ralf van Veenendaal, 1 Oct 2026) stands and the page says the duplicate
check has not run.

    python3 tools/kiosk_people.py --write
"""
import csv, json, os, re, statistics, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HUB = "/mnt/c/Users/bushp/OneDrive - SaniTap/Central Data Hub - Water Documents"
OUT = os.path.join(REPO, "data", "kiosk_people.json")


def cards(path):
    if path.lower().endswith(".json"):
        d = json.load(open(path, encoding="utf8"))
        return d if isinstance(d, list) else d.get("data") or d.get("cards") or []
    return list(csv.DictReader(open(path, encoding="utf8")))


def norm(v, kind):
    v = str(v or "").strip().lower()
    if kind == "phone":
        v = re.sub(r"\D", "", v)[-9:]
    elif kind == "name":
        v = re.sub(r"\s+", " ", v)
    return v or None


def duplicates(rows):
    """Pairs of cards sharing a name, phone or ID; union-find gives households."""
    key = {"name": ("name", "customer", "customer_name", "Name"), "phone": ("phone", "mobile", "Phone"),
           "id": ("id_number", "national_id", "cin", "ID")}
    card_id = lambda r: str(r.get("card") or r.get("card_id") or r.get("NFC_ID") or r.get("id") or "")
    parent = {card_id(r): card_id(r) for r in rows}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    seen, pairs = {}, []
    for r in rows:
        for kind, names in key.items():
            v = norm(next((r.get(n) for n in names if r.get(n)), None), kind)
            if not v:
                continue
            k = (kind, v)
            if k in seen and seen[k] != card_id(r):
                pairs.append({"cards": [seen[k], card_id(r)], "same": kind})
                parent[find(card_id(r))] = find(seen[k])
            seen.setdefault(k, card_id(r))
    households = len({find(c) for c in parent})
    return pairs, households


def main():
    cfg = json.load(open(os.path.join(REPO, "data", "build_config.json"), encoding="utf8"))["kiosk"]
    old = json.load(open(OUT, encoding="utf8")) if os.path.isfile(OUT) else {}
    # household size: the piped-system survey once it measures it, else the census
    hh, hh_src = cfg["census_hh_size"], cfg["census_hh_size_source"]
    sv = cfg.get("survey_hh_sizes")
    if sv and os.path.isfile(os.path.join(REPO, sv)):
        sizes = [x for x in json.load(open(os.path.join(REPO, sv), encoding="utf8")).get(cfg["water_point"], []) if x]
        if sizes:
            hh, hh_src = round(statistics.mean(sizes), 2), f"the piped-system survey ({len(sizes)} households)"
    # cards: the export when filed, else the recorded count
    path = os.path.join(HUB, cfg["card_export"])
    if os.path.isfile(path):
        rows = cards(path)
        pairs, households = duplicates(rows)
        registered, check = len(rows), "run"
    else:
        pairs, registered, households, check = [], cfg["cards_recorded"], cfg["cards_recorded"], "not run"
    doc = dict(old)
    doc.update(cards_registered=registered, households=households, flagged_pairs=pairs, duplicate_check=check,
               card_export=cfg["card_export"], hh_size=hh, hh_size_source=hh_src, people=round(households * hh),
               rules=("Household size: the census (INSTAT RGPH-3, Analamanga urban) until a project survey measures it; "
                      "the piped-system survey's value replaces it automatically. Cards: one registered card is one household "
                      "until the contrary is proved; cards sharing a name, phone or ID are flagged, count as one household "
                      "and are listed."),
               duplicate_note=(f"duplicate check run on {registered} cards: {len(pairs)} flagged pair(s)" if check == "run"
                               else "duplicate check not run: no card export with registration details is on file "
                                    f"(Water Documents/{cfg['card_export']})"))
    json.dump(doc, open(OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    print(f"kiosk: {doc['people']} people = {households} households x {hh} ({hh_src}); {doc['duplicate_note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
