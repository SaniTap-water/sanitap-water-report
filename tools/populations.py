# -*- coding: utf-8 -*-
"""What a population IS. One file, one definition each.

WHY THIS EXISTS
---------------
908, 773, 751, 738, 736, 732, 731, 727, 723 are not nine errors. They are nine
answers to a question nobody wrote down: which records are we counting? Every
time a figure moved, it moved because two parts of the page had silently
answered that question differently.

So each population below carries:
  id          a stable identifier a figure can name
  name        what a person calls it
  rule        the rule in plain English, for a MadAvance staff member
  members()   the same rule as executable code over the mWater extracts
  reads       the mWater form or register query it reads, with its id
  decided     the decision that set it, and when
  derives_from  the populations it is defined against

A population is a SET OF RECORD IDENTIFIERS, never a stored count. No
population is defined by subtracting a number from another number: it is a
predicate over records, and the count falls out of the set. That is the whole
point - a subtraction cannot be re-derived when the data moves, and a
predicate can.

    python3 tools/populations.py              # every population and its size
    python3 tools/populations.py --chain      # the reconciliation, step by step
    python3 tools/populations.py --json OUT   # for the page
"""
import argparse, csv, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS = os.path.expanduser("~/mwater-exports")
MW_FORM = "https://portal.mwater.co/#/forms/"
MW_GROUP = "group:aaaf0a14e4ce44eaa7a2bcfd1c74aa56"

# ---------------------------------------------------------------- sources ---
F_COMBINED = "86cf66efdd3749dd8a121314bab3675a"   # Première réhab / PM / réparation
F_PM = "de26d89a5c8a4452b42158c622be20d0"
F_CALL = "c08b3fe26d0f42c084074701f29eb75e"
F_MAR = "8764843c94484f5b984078c68f13b2ca"

Q_TYPE = "7f78d719b9f242d8886df7bb88640a80"       # "Type de travaux"
C_FIRST_REHAB = "DQcV1NT"                          # "Première réhabilitation"
Q_SUCCESS = "931b62d904ff4318bad8b65f9c5f131a"     # "...a réussi ?"
C_YES, C_NO = "89WB4MJ", "eEYBFCk"


def _rows(name):
    p = os.path.join(EXPORTS, name)
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf8") as fh:
        return list(csv.DictReader(fh))


def _combined():
    p = os.path.join(EXPORTS, "combined_rehab_raw.json")
    return json.load(open(p, encoding="utf8")) if os.path.isfile(p) else []


def _answer(r, q):
    v = (r.get("data") or {}).get(q)
    return v.get("value") if isinstance(v, dict) else v


def _point_of(r):
    for e in (r.get("entities") or []):
        if e.get("property") == "code":
            return e.get("value")
    return None


def _page_pumps():
    """PUMPS as the page holds it - the maintained fleet, built by the weekly
    build from the register and the works forms. It is an extract artefact,
    not a stored count: every member is a record."""
    h = open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    import re
    m = re.search(r"\bconst PUMPS\s*=\s*\[", h)
    i = h.index("[", m.start()); d = 0; j = i; instr = esc = False
    while j < len(h):
        c = h[j]
        if instr:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': instr = False
        elif c == '"': instr = True
        elif c == "[": d += 1
        elif c == "]":
            d -= 1
            if d == 0: break
        j += 1
    return json.loads(h[i:j + 1])


# ------------------------------------------------------------ populations ---
POPULATIONS = []


def population(**meta):
    def wrap(fn):
        meta["id"] = meta.get("id") or fn.__name__
        meta["members"] = fn
        POPULATIONS.append(meta)
        return fn
    return wrap


@population(
    name="Register records",
    rule="Every water-point record in the MadAvance group in mWater. This is "
         "everything MadAvance holds, most of which we do not maintain: "
         "surveys, points handed on, rope pumps, abandoned points.",
    reads=[("mWater register", "entities/water_point where _managed_by = "
            "group:aaaf0a14e4ce44eaa7a2bcfd1c74aa56", None)],
    decided="The group is the boundary of what MadAvance holds. Not a decision "
            "so much as a fact about the account.",
    decided_on="—",
    derives_from=[])
def register_records():
    return {r["code"] for r in _rows("wp_madavance.csv") if r.get("code")}


@population(
    name="First-rehabilitated points",
    rule="Water points with a first-rehabilitation record on the works form, "
         "whatever the outcome. One point can carry more than one such record; "
         "the point is counted once.",
    reads=[("Clean Water || Première réhabilitation / Entretien préventif / "
            "Réparation après panne", F_COMBINED,
            'question "Type de travaux" = "Première réhabilitation"')],
    decided="A first rehabilitation is what puts a point into the programme. "
            "The record is the evidence it happened.",
    decided_on="methodology 2.2.1(d) / SDWS 2",
    derives_from=["register_records"])
def first_rehabilitated():
    reg = register_records()
    return {_point_of(r) for r in _combined()
            if _answer(r, Q_TYPE) == C_FIRST_REHAB
            and _point_of(r) in reg}


@population(
    name="Successfully rehabilitated points",
    rule="Of the first-rehabilitated points, those whose record answers Yes to "
         "“Verify: did the repair or maintenance succeed?”. A point "
         "with any successful first-rehabilitation record counts as successful.",
    reads=[("Clean Water || Première réhabilitation / ...", F_COMBINED,
            'question "Vérifier : La réparation ou la maintenance a réussi ?" '
            '= Oui')],
    decided="A rehabilitation that did not succeed does not put a point into "
            "the maintained fleet.",
    decided_on="methodology 2.2.1(d)",
    derives_from=["first_rehabilitated"])
def rehabilitated_successfully():
    reg = register_records()
    return {_point_of(r) for r in _combined()
            if _answer(r, Q_TYPE) == C_FIRST_REHAB
            and _answer(r, Q_SUCCESS) == C_YES
            and _point_of(r) in reg}


@population(
    name="Managed fleet",
    rule="The water points MadAvance actively maintains today - the fleet this "
         "report is about. Every one has a maintenance history: it is visited, "
         "repaired and called about. This is the population behind “water "
         "points in scope”.",
    reads=[("the register, reconciled against the works and call forms by the "
            "weekly build", None, "tools/rebuild_activity.py")],
    decided="Adriaan Mol, COO SaniTap - the standing reconciliation recorded in "
            "data/register_corrections.json",
    decided_on="2026-09-15",
    derives_from=["register_records"])
def managed_fleet():
    return {p["wp"] for p in _page_pumps()}


@population(
    name="Marolinta",
    rule="The Marolinta boreholes. Deichmann-funded, and outside the carbon "
         "programme entirely - they enter no carbon figure.",
    reads=[("Clean Water || Suivi avancement nouveau forage et réhabilitation",
            F_MAR, "the Marolinta deployment of that form")],
    decided="Marolinta is funded separately and is not in the VPA.",
    decided_on="2026-09-10",
    derives_from=["managed_fleet"])
def marolinta():
    return {p["wp"] for p in _page_pumps() if p.get("site") == "Marolinta"}


@population(
    name="Carbon fleet",
    rule="The managed fleet less Marolinta. This is the denominator under every "
         "carbon figure on the page.",
    reads=[("as managed_fleet, less the Marolinta site", None, None)],
    decided="Marolinta is Deichmann-funded and enters no carbon figure, so it "
            "cannot be in a carbon denominator.",
    decided_on="2026-09-22",
    derives_from=["managed_fleet", "marolinta"])
def carbon_fleet():
    return {p["wp"] for p in _page_pumps() if p.get("site") != "Marolinta"}


@population(
    name="2026 calendar-evidenced points",
    rule="Carbon-fleet points with a readable gardien calendar sheet dated 2026, "
         "the year read off the sheet itself. This is what the days-operational "
         "evidence rests on.",
    reads=[("gardien calendar photographs, machine-read",
            None, "data/calendar_year_coverage.csv")],
    decided="The gardien calendar is the official record of days operational.",
    decided_on="2026-09-21",
    derives_from=["carbon_fleet"])
def calendar_evidenced_2026():
    carbon = carbon_fleet()
    p = os.path.join(REPO, "data", "calendar_year_coverage.csv")
    if not os.path.isfile(p):
        return set()
    with open(p, encoding="utf8") as fh:
        return {r["water_point"] for r in csv.DictReader(fh)
                if r.get("sheet_year") == "2026"} & carbon


@population(
    name="Points down now",
    rule="Managed points whose most recent record - call, maintenance visit or "
         "repair - says the pump is not working.",
    reads=[("Appel/signalement de pannes", F_CALL, None),
           ("Entretien préventif", F_PM, None)],
    decided="Status is the last thing anyone recorded about a pump.",
    decided_on="2026-09-21",
    derives_from=["managed_fleet"])
def down_now():
    return {p["wp"] for p in _page_pumps() if p.get("status") == "down"}


BY_ID = None


def get(pid):
    global BY_ID
    if BY_ID is None:
        BY_ID = {p["id"]: p for p in POPULATIONS}
    return BY_ID[pid]


def sizes():
    return {p["id"]: len(p["members"]()) for p in POPULATIONS}


# --------------------------------------------------------- reconciliation ---
def chain():
    """The reconciliation the page states, produced here rather than asserted.

    Each step is a set relation that either holds or does not. A step that does
    not hold is reported as a gap - the definition is NOT adjusted to close it.
    """
    reg = register_records()
    fr = first_rehabilitated()
    ok = rehabilitated_successfully()
    fleet = managed_fleet()
    mar = marolinta()
    carbon = carbon_fleet()
    cal = calendar_evidenced_2026()
    steps = [
        ("register_records ⊇ first_rehabilitated", fr <= reg,
         f"{len(fr)} of {len(reg)}"),
        ("first_rehabilitated ⊇ rehabilitated_successfully", ok <= fr,
         f"{len(ok)} of {len(fr)}"),
        ("managed_fleet ⊆ register_records", fleet <= reg,
         f"{len(fleet)} of {len(reg)}"),
        ("marolinta ⊆ managed_fleet", mar <= fleet,
         f"{len(mar)} of {len(fleet)}"),
        ("carbon_fleet + marolinta = managed_fleet",
         carbon | mar == fleet and not (carbon & mar),
         f"{len(carbon)} + {len(mar)} = {len(carbon | mar)} vs {len(fleet)}"),
        ("calendar_evidenced_2026 ⊆ carbon_fleet", cal <= carbon,
         f"{len(cal)} of {len(carbon)}"),
    ]
    # the step the page asserts but the records do not support
    gaps = []
    orphan = fleet - reg
    if orphan:
        gaps.append({
            "step": "managed_fleet is a subset of register_records",
            "n": len(orphan),
            "what": (f"{len(orphan)} managed point(s) are not in the register "
                     f"export: {', '.join(sorted(orphan))}"),
            "known": ("already tracked as act-742896839"
                      if orphan == {"742896839"} else None)})
    unsupported = (fleet - ok) - mar
    if unsupported:
        gaps.append({
            "step": "managed_fleet against rehabilitated_successfully",
            "n": len(unsupported),
            "what": (f"the register-chain note on this page says the fleet is "
                     f"the successfully rehabilitated points plus a handful "
                     f"never rehabilitated. The works form supports "
                     f"{len(ok)} successful, which leaves "
                     f"{len(unsupported)} managed non-Marolinta points with no "
                     f"successful first-rehabilitation record - far more than "
                     f"the note allows for."),
            "known": None})
    return steps, gaps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.json:
        steps, gaps = chain()
        doc = {"populations": {p["id"]: {k: v for k, v in p.items()
                                         if k != "members"}
                               | {"size": len(p["members"]())}
                               for p in POPULATIONS},
               "chain": [{"step": n, "holds": ok, "detail": d}
                         for n, ok, d in steps],
               "gaps": gaps,
               "form_base": MW_FORM}
        json.dump(doc, open(a.json, "w", encoding="utf8"),
                  indent=1, ensure_ascii=False, sort_keys=True)
        print(f"{len(doc['populations'])} populations, "
              f"{len(doc['gaps'])} gap(s) -> {a.json}")
        return 0
    print()
    print("  POPULATIONS - every one a set of records, none a stored count")
    print("  " + "-" * 92)
    for p in POPULATIONS:
        n = len(p["members"]())
        print(f"  {p['id']:28} {n:>6}   {p['name']}")
        print(f"  {'':28}          {p['rule'][:78]}")
    if a.chain:
        steps, gaps = chain()
        print()
        print("  THE CHAIN")
        print("  " + "-" * 92)
        for name, ok, detail in steps:
            print(f"  {'holds ' if ok else 'BROKEN'}  {name:52} {detail}")
        if gaps:
            print()
            print("  DOES NOT RECONCILE - reported, not closed")
            for g in gaps:
                print(f"    [{g['step']}]")
                print(f"      {g['what']}")
                if g.get("known"):
                    print(f"      already {g['known']}")
        return 1 if (gaps or any(not ok for _, ok, _ in steps)) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
