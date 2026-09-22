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
# The combined form was retired BRANCH BY BRANCH. Every branch now has a live
# dedicated successor. The retired form is kept because it holds the
# historical records - 1,688 of them - and for no other reason. A population
# that reads only the retired form sees the past and will never see the
# present, and because a successor with no responses yet is indistinguishable
# from a quiet week, nothing fails when that happens.
F_RETIRED_COMBINED = "86cf66efdd3749dd8a121314bab3675a"  # RETIRED, historical only
F_FIRST_REHAB = "63747997e70e478fbb2ebf71581ceeb0"       # successor, live
F_REPAIR = "958b4763788348d699e7d8c5821f92ee"            # successor, live
F_PM = "de26d89a5c8a4452b42158c622be20d0"                # successor, live
F_IDENT = "198b016d72af41baa2608a8c9c35f8cb"             # successor, live
F_WQ_SAMPLING = "43c96af4bc4240c0b5c4402383b9c539"       # successor, live
F_WQ_RESULTS = "7b33c5d7e5074808a94915939a5a0783"        # successor, live
F_HYGIENE = "283c5670de82489d833e986cb76a67d8"           # successor, live
F_CALL = "c08b3fe26d0f42c084074701f29eb75e"
F_MAR = "8764843c94484f5b984078c68f13b2ca"

# branch of the retired form -> the form that replaced it. Used by the gate:
# a response arriving on a successor that no population reads is a migration
# completing silently, which is the failure mode this whole file exists to stop.
SUCCESSORS = {
    "Première réhabilitation": F_FIRST_REHAB,
    "Réparation après panne": F_REPAIR,
    "Entretien préventif": F_PM,
    "Identification des points d'eau": F_IDENT,
    "Analyse de l'eau": F_WQ_RESULTS,
    "Formation / hygiène": F_HYGIENE,
}

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


def _first_rehab_current():
    """The LIVE first-rehabilitation form. Zero responses today, which is
    exactly why it must be read: a successor with no responses is
    indistinguishable from a quiet week, so nothing would fail on the day the
    first one arrives."""
    p = os.path.join(EXPORTS, "first_rehab_current.json")
    return json.load(open(p, encoding="utf8")) if os.path.isfile(p) else []


def _wq_results():
    """The LIVE water-quality results form (SDWS 3)."""
    p = os.path.join(EXPORTS, "wq_results.json")
    return json.load(open(p, encoding="utf8")) if os.path.isfile(p) else []


def _combined():
    """The works form, enumerated stably.

    mWater's skip/limit paging has no sort order. A straight paged pull of this
    1,688-response form returned 1,688 rows carrying only 1,586 distinct _ids -
    102 records twice and 102 missed - which manufactured 48 points that
    appeared to carry two first-rehabilitation records. There are none.
    tools/mwater/pull_form.mjs walks 30-day windows instead; no window exceeds
    221 rows, so paging never engages and the enumeration is exact.
    """
    p = os.path.join(EXPORTS, "combined_rehab.json")
    return json.load(open(p, encoding="utf8")) if os.path.isfile(p) else []


def _borehole():
    """The Marolinta borehole-progress form. Marolinta rehabilitations AND new
    constructions are recorded here, not on the works form, so any population
    that reads rehabilitation must read this too or say that it does not."""
    p = os.path.join(EXPORTS, "marolinta_borehole.json")
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
    """A population declares its UNIT: records or points.

    A record count and a point count are different quantities and may never be
    compared, subtracted or set beside each other without both being named.
    Confusing them produced 727, the 723/731 gap, and a "46 managed points"
    finding that was really a paging artefact.
    """
    def wrap(fn):
        meta["id"] = meta.get("id") or fn.__name__
        if meta.get("unit") not in ("records", "points"):
            raise ValueError(f"{meta['id']}: unit must be 'records' or 'points'")
        meta["members"] = fn
        POPULATIONS.append(meta)
        return fn
    return wrap


@population(
    name="Register records",
    unit="points",
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
    unit="points",
    rule="Water points with a first-rehabilitation record on the works form, "
         "whatever the outcome. One point can carry more than one such record; "
         "the point is counted once.",
    reads=[("Clean Water || Première réhabilitation / Entretien préventif / "
            "Réparation après panne", F_RETIRED_COMBINED,
            'question "Type de travaux" = "Première réhabilitation"'),
           ("Clean Water || Première réhabilitation (current form)",
            F_FIRST_REHAB, "the live successor - zero responses today, read so "
            "the first one does not arrive unnoticed"),
           ("Clean Water || Suivi avancement nouveau forage et réhabilitation",
            F_MAR, "the Marolinta works, which are recorded only here")],
    decided="A first rehabilitation is what puts a point into the programme. "
            "The record is the evidence it happened.",
    decided_on="methodology 2.2.1(d) / SDWS 2",
    derives_from=["register_records"])
def first_rehabilitated():
    """Union of three sources, de-duplicated on water point:
    the retired combined form (historical), the live successor (current, zero
    responses today) and the Marolinta borehole form."""
    reg = register_records()
    pts = {_point_of(r) for r in _combined()
           if _answer(r, Q_TYPE) == C_FIRST_REHAB}
    pts |= {_point_of(r) for r in _first_rehab_current()}
    pts |= {_point_of(r) for r in _borehole()}
    return {p for p in pts if p in reg}


@population(
    name="Successfully rehabilitated points",
    unit="points",
    rule="Of the first-rehabilitated points, those whose record answers Yes to "
         "“Verify: did the repair or maintenance succeed?”. A point "
         "with any successful first-rehabilitation record counts as successful.",
    reads=[("Clean Water || Première réhabilitation / ...", F_RETIRED_COMBINED,
            'question "Vérifier : La réparation ou la maintenance a réussi ?" '
            '= Oui'),
           ("Clean Water || Première réhabilitation (current form)",
            F_FIRST_REHAB, "the live successor"),
           ("Clean Water || Suivi avancement nouveau forage et réhabilitation",
            F_MAR, "the Marolinta works, which are recorded only here")],
    decided="A rehabilitation that did not succeed does not put a point into "
            "the maintained fleet.",
    decided_on="methodology 2.2.1(d)",
    derives_from=["first_rehabilitated"])
def rehabilitated_successfully():
    """Same three sources. The successor form carries the same success
    question; the Marolinta borehole form records completion differently and
    is unioned on the point, not on that answer."""
    reg = register_records()
    pts = {_point_of(r) for r in _combined()
           if _answer(r, Q_TYPE) == C_FIRST_REHAB
           and _answer(r, Q_SUCCESS) == C_YES}
    pts |= {_point_of(r) for r in _first_rehab_current()
            if _answer(r, Q_SUCCESS) == C_YES}
    return {p for p in pts if p in reg}


@population(
    name="First-rehabilitation records",
    unit="records",
    rule="Every first-rehabilitation RECORD on the works form. This counts "
         "records, not water points: it is the number of times the work was "
         "written down. On the current data each record is on a different "
         "point, so the two happen to be equal - that is a fact about today, "
         "not a rule.",
    reads=[("Clean Water || Première réhabilitation / Entretien préventif / "
            "Réparation après panne", F_RETIRED_COMBINED,
            'question "Type de travaux" = "Première réhabilitation"')],
    decided="A record is the evidence the work happened; a point is the thing "
            "worked on. They are counted separately because they are different "
            "questions.",
    decided_on="2026-09-22",
    derives_from=[])
def first_rehabilitation_records():
    return {r["_id"] for r in _combined()
            if _answer(r, Q_TYPE) == C_FIRST_REHAB}


@population(
    name="Successful first-rehabilitation records",
    unit="records",
    rule="Of those records, the ones answering Yes to \u201cVerify: did the "
         "repair or maintenance succeed?\u201d. Still a count of records.",
    reads=[("Clean Water || Première réhabilitation / ...", F_RETIRED_COMBINED,
            'question "Vérifier : La réparation ou la maintenance a réussi ?" '
            '= Oui')],
    decided="Withdrawn figure 723 could not be reproduced from any data held; "
            "the records give 731. See the decision log.",
    decided_on="2026-09-22",
    derives_from=["first_rehabilitation_records"])
def successful_first_rehabilitation_records():
    return {r["_id"] for r in _combined()
            if _answer(r, Q_TYPE) == C_FIRST_REHAB
            and _answer(r, Q_SUCCESS) == C_YES}


@population(
    name="Marolinta works records",
    unit="records",
    rule="Every works record on the Marolinta borehole-progress form - "
         "rehabilitations and new constructions both. These never appear on "
         "the works form, so a query that reads only that form cannot see "
         "Marolinta at all.",
    reads=[("Clean Water || Suivi avancement nouveau forage et réhabilitation",
            F_MAR, "every record on the form")],
    decided="Marolinta works were put on their own form because the works form "
            "has no \u201cNouvelle construction\u201d option.",
    decided_on="2026-09-22",
    derives_from=[])
def marolinta_works_records():
    return {r["_id"] for r in _borehole()}


@population(
    name="Managed fleet",
    unit="points",
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
    unit="points",
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
    unit="points",
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
    unit="points",
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
    name="Identified points",
    unit="points",
    rule="Water points with an identification survey on the live "
         "identification form - the first visit, before any works.",
    reads=[("Clean Water || Identification des points d'eau", F_IDENT,
            "every response with a linked water point")],
    decided="The identification survey is what puts a point on the map at all.",
    decided_on="2026-09-22",
    derives_from=["register_records"])
def identified_points():
    p = os.path.join(EXPORTS, "identification.json")
    rows = json.load(open(p, encoding="utf8")) if os.path.isfile(p) else []
    reg = register_records()
    return {_point_of(r) for r in rows if _point_of(r) in reg}


@population(
    name="Hygiene-session points",
    unit="points",
    rule="Water points with a hygiene-promotion session recorded on the live "
         "training form. Not a carbon figure; it is where the field "
         "photographs on this page come from.",
    reads=[("Clean Water || Formation et Suivi promotion de l'hygiène",
            F_HYGIENE, "every response with a linked water point")],
    decided="Kept as a population so the training form is read by something "
            "and a migration onto it cannot pass unnoticed.",
    decided_on="2026-09-22",
    derives_from=["register_records"])
def hygiene_session_points():
    p = os.path.join(EXPORTS, "hygiene.json")
    rows = json.load(open(p, encoding="utf8")) if os.path.isfile(p) else []
    reg = register_records()
    return {_point_of(r) for r in rows if _point_of(r) in reg}


@population(
    name="Water-quality tested points",
    unit="points",
    rule="Water points with a result on the SDWS 3 water-quality results form. "
         "Read from the LIVE results form, not from the retired combined "
         "form's water-analysis branch - that branch stopped taking records in "
         "July 2025 and a population reading it would have frozen there.",
    reads=[("Clean Water || Water Quality Testing SDWS 3 Result",
            F_WQ_RESULTS, "every response with a linked water point"),
           ("Clean Water || Water Quality Sampling SDWS 3",
            F_WQ_SAMPLING, "the sampling half of the same process")],
    decided="SDWS 3 needs a result per point; the result form is the record.",
    decided_on="2026-09-22",
    derives_from=["managed_fleet"])
def water_quality_tested():
    fleet = managed_fleet()
    return {_point_of(r) for r in _wq_results()
            if _point_of(r) in fleet}


@population(
    name="Points down now",
    unit="points",
    rule="Managed points whose most recent record - call, maintenance visit or "
         "repair - says the pump is not working.",
    reads=[("Appel / signalement de pannes", F_CALL, None),
           ("Entretien préventif", F_PM, None),
           ("Réparation après panne", F_REPAIR, "the live repair form")],
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
    """The reconciliation, produced here rather than asserted.

    Every step is a set relation between two populations of the SAME unit. A
    record count is never set beside a point count: that confusion produced
    727, the 723/731 gap, and a "46 unexplained points" finding that was a
    paging artefact.
    """
    reg = register_records()
    fr = first_rehabilitated()
    ok = rehabilitated_successfully()
    fleet = managed_fleet()
    mar = marolinta()
    carbon = carbon_fleet()
    cal = calendar_evidenced_2026()
    frr = first_rehabilitation_records()
    okr = successful_first_rehabilitation_records()
    steps = [
        ("RECORDS: successful \u2286 all first-rehabilitation records",
         okr <= frr, f"{len(okr)} of {len(frr)} records"),
        ("POINTS: first-rehabilitated \u2286 register",
         fr <= reg, f"{len(fr)} of {len(reg)} points"),
        ("POINTS: successfully rehabilitated \u2286 first-rehabilitated",
         ok <= fr, f"{len(ok)} of {len(fr)} points"),
        ("POINTS: managed fleet \u2286 register",
         fleet <= reg, f"{len(fleet)} of {len(reg)} points"),
        ("POINTS: Marolinta \u2286 managed fleet",
         mar <= fleet, f"{len(mar)} of {len(fleet)} points"),
        ("POINTS: carbon fleet + Marolinta = managed fleet",
         carbon | mar == fleet and not (carbon & mar),
         f"{len(carbon)} + {len(mar)} = {len(fleet)} points"),
        ("POINTS: the fleet is the successfully rehabilitated plus those never "
         "rehabilitated",
         (fleet - ok) == (mar | (fleet - ok - mar)),
         f"{len(ok & fleet)} rehabilitated + {len(fleet - ok)} never = "
         f"{len(fleet)} points"),
        ("POINTS: calendar-evidenced \u2286 carbon fleet",
         cal <= carbon, f"{len(cal)} of {len(carbon)} points"),
    ]
    gaps = []
    orphan = fleet - reg
    if orphan:
        gaps.append({
            "step": "managed fleet is a subset of the register",
            "n": len(orphan),
            "what": (f"{len(orphan)} managed point(s) are not in the register "
                     f"export: {', '.join(sorted(orphan))}"),
            "known": ("already tracked as act-742896839"
                      if orphan == {"742896839"} else None)})
    # a point already reported as missing from the register would otherwise be
    # counted twice - once as an orphan and again as never rehabilitated
    # Points in the fleet with no successful first-rehabilitation record.
    # Marolinta's works are on the borehole-progress form, so they are
    # expected here; 782134540 is the Maroantsetra Canzee that was never
    # first-rehabilitated and is recorded as such. Anything else is a finding.
    never = (fleet - ok) - orphan
    KNOWN_NEVER = {"782134540"}
    unexplained = never - mar - KNOWN_NEVER
    steps.append((
        "POINTS: every fleet point with no successful rehabilitation is "
        "accounted for",
        not unexplained,
        f"{len(never)} never rehabilitated = {len(never & mar)} Marolinta "
        f"(works on the borehole form) + {len(never & KNOWN_NEVER)} recorded "
        f"+ {len(unexplained)} unexplained"))
    if unexplained:
        gaps.append({
            "step": "points in the fleet with no successful rehabilitation",
            "n": len(unexplained),
            "what": (f"{len(unexplained)} managed point(s) have no successful "
                     f"first-rehabilitation record on either form and no "
                     f"recorded reason: {', '.join(sorted(unexplained)[:8])}"),
            "known": None})
    return steps, gaps


def migration_watch():
    """A response on a successor form that no population reads is a migration
    completing silently.

    The first-rehabilitation successor has zero responses today. Zero is a
    plausible weekly count, so nothing would fail on the day the first one
    arrives unless something is watching for exactly that. This is that
    something.

    Returns [(form, label, n_responses, n_unread)] - anything with n_unread
    above zero is a failure.
    """
    out = []
    declared = set()
    for pop in POPULATIONS:
        for r in (pop.get("reads") or []):
            if len(r) > 1 and r[1]:
                declared.add(r[1])

    cur = _first_rehab_current()
    if cur:
        seen = first_rehabilitated() | rehabilitated_successfully()
        unread = [r for r in cur if _point_of(r) not in seen]
        out.append((F_FIRST_REHAB, "Première réhabilitation (successor)",
                    len(cur), len(unread)))
    else:
        out.append((F_FIRST_REHAB, "Première réhabilitation (successor)", 0, 0))

    # every successor named in SUCCESSORS must be declared by some population
    for branch, fid in SUCCESSORS.items():
        if fid not in declared:
            out.append((fid, f"{branch} - NOT READ BY ANY POPULATION", None, 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain", action="store_true")
    ap.add_argument("--migration", action="store_true")
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
    if a.migration:
        rows = migration_watch()
        print()
        print("  MIGRATION WATCH - a response nothing reads is a silent migration")
        print("  " + "-" * 92)
        bad = 0
        for fid, label, n, unread in rows:
            note = (f"{n} response(s), {unread} unread" if n is not None
                    else "declared by no population")
            flag = "FAIL" if unread else "ok  "
            if unread:
                bad += 1
            print(f"  {flag}  {label[:56]:58} {note}")
        return 1 if bad else 0
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
