# -*- coding: utf-8 -*-
"""The derivation behind every figure the page renders.

Every data-fig expression is mapped to the population it is over, the rule in
plain English, the mWater form(s) it reads, and the arithmetic that produced
that exact value. The page inlines this and expands it under any figure the
reader clicks.

A figure whose expression is not here has no derivation, and
tools/check_consistency.py says so.

    python3 tools/render_derivations.py --write
    python3 tools/render_derivations.py --check
"""
import json, os, re, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
OUT = os.path.join(REPO, "data", "derivations.json")
MW = "https://portal.mwater.co/#/forms/"

F_COMBINED = "86cf66efdd3749dd8a121314bab3675a"
F_PM = "de26d89a5c8a4452b42158c622be20d0"
F_CALL = "c08b3fe26d0f42c084074701f29eb75e"
F_REP = "958b4763788348d699e7d8c5821f92ee"
F_MAR = "8764843c94484f5b984078c68f13b2ca"
REGQ = ("mWater register: entities/water_point where _managed_by = "
        "group:aaaf0a14e4ce44eaa7a2bcfd1c74aa56")

# expression -> derivation. `arith` is a JS expression evaluated on the page so
# the working shown is the working that produced the value on screen.
D = {
 "S.n": dict(pop="managed_fleet",
   arith="`every record in the maintained register: ${fmt(PUMPS.length)} rows in PUMPS`",
   forms=[("the register, reconciled against the works and call forms", None, REGQ)]),
 "PUMPS.filter(p=>p.site!=='Marolinta').length": dict(pop="carbon_fleet",
   arith="`${fmt(PUMPS.length)} managed less ${PUMPS.filter(p=>p.site==='Marolinta').length} Marolinta = ${fmt(PUMPS.filter(p=>p.site!=='Marolinta').length)}`",
   forms=[("the register", None, REGQ)]),
 "CARBON.carbon_points": dict(pop="carbon_fleet",
   arith="`${fmt(PUMPS.length)} managed less ${PUMPS.filter(p=>p.site==='Marolinta').length} Marolinta = ${fmt(CARBON.carbon_points)}`",
   forms=[("the register", None, REGQ)]),
 "CARBON.carbon_points_with_2026_sheet": dict(pop="calendar_evidenced_2026",
   arith="`carbon-fleet points with a dated 2026 sheet: ${fmt(CARBON.carbon_points_with_2026_sheet)} of ${fmt(CARBON.carbon_points)}`",
   forms=[("gardien calendar photographs, machine-read", None,
           "data/calendar_year_coverage.csv, sheet year read off the sheet")]),
 "CARBON.carbon_points_without_2026_sheet": dict(pop="calendar_evidenced_2026",
   arith="`${fmt(CARBON.carbon_points)} carbon points less ${fmt(CARBON.carbon_points_with_2026_sheet)} with a dated 2026 sheet = ${fmt(CARBON.carbon_points_without_2026_sheet)}`",
   forms=[("gardien calendar photographs, machine-read", None,
           "data/calendar_year_coverage.csv")]),
 "CARBON.carbon_2026_coverage_pct": dict(pop="calendar_evidenced_2026",
   arith="`${fmt(CARBON.carbon_points_with_2026_sheet)} \\u00f7 ${fmt(CARBON.carbon_points)} = ${CARBON.carbon_2026_coverage_pct}%`",
   forms=[("gardien calendar photographs, machine-read", None,
           "data/calendar_year_coverage.csv")]),
 "S.by_site['Fort-Dauphin']": dict(pop="managed_fleet",
   arith="`managed points whose site is Fort-Dauphin: ${fmt(PUMPS.filter(p=>p.site==='Fort-Dauphin').length)}`",
   forms=[("the register", None, REGQ)]),
 "S.by_site['Maroantsetra']": dict(pop="managed_fleet",
   arith="`managed points whose site is Maroantsetra: ${fmt(PUMPS.filter(p=>p.site==='Maroantsetra').length)}`",
   forms=[("the register", None, REGQ)]),
 "REG.register_total": dict(pop="register_records",
   arith="`every water-point record in the MadAvance group: ${fmt(REG.register_total)}`",
   forms=[("the register", None, REGQ)]),
 "REG.total_first_rehab": dict(pop="first_rehabilitated",
   arith="`first-rehabilitation records on the works form: ${fmt(REG.total_first_rehab)}`",
   forms=[("Clean Water || Premi\\u00e8re r\\u00e9habilitation / Entretien pr\\u00e9ventif / R\\u00e9paration apr\\u00e8s panne",
           F_COMBINED, 'question "Type de travaux" = "Premi\\u00e8re r\\u00e9habilitation"')],
   caveat="This figure does not reconcile with the form it cites. The form "
          "yields 725 points today, not 773. See the chain."),
 "REG.succ": dict(pop="rehabilitated_successfully",
   arith="`first rehabilitations recorded successful: ${fmt(REG.succ)}`",
   forms=[("Clean Water || Premi\\u00e8re r\\u00e9habilitation / ...", F_COMBINED,
           'question "V\\u00e9rifier : La r\\u00e9paration ou la maintenance a r\\u00e9ussi ?" = Oui')],
   caveat="This figure does not reconcile with the form it cites. The form "
          "yields 686 points today, not 723. See the chain."),
 "REG.dashboard_fdmar": dict(pop="register_records",
   arith="`points on the MadAvance dashboard in Maroantsetra and Fort-Dauphin: ${fmt(REG.dashboard_fdmar)}`",
   forms=[("the register", None, REGQ)]),
 "SUCC_CORRECTED": dict(pop="rehabilitated_successfully",
   arith="`${fmt(REG.succ)} on file + ${CORR.corrected.length} corrections in the standing record = ${fmt(SUCC_CORRECTED)}`",
   forms=[("Clean Water || Premi\\u00e8re r\\u00e9habilitation / ...", F_COMBINED, None)]),
 "S.n+ENDURO.systems": dict(pop="managed_fleet",
   arith="`${fmt(S.n)} MadAvance hand pumps + ${ENDURO.systems} Endur'O piped systems = ${fmt(S.n+ENDURO.systems)}`",
   forms=[("the register", None, REGQ)],
   caveat="The Endur'O half is hand-entered and not in mWater; it carries its "
          "own as-at date and supplier."),
 "TTR.ttr_n": dict(pop="managed_fleet",
   arith="`repairs with both a notification and a completion date: ${fmt(TTR.ttr_n)}`",
   forms=[("R\\u00e9paration apr\\u00e8s panne", F_REP, None),
          ("Appel / signalement de pannes", F_CALL, None)]),
 "WPOPMETA.points_with_a_barrier": dict(pop="managed_fleet",
   arith="`managed points whose 1 km circle is cut by a barrier: ${fmt(WPOPMETA.points_with_a_barrier)} of ${WPOPMETA.rows}`",
   forms=[("WorldPop R2025A run", None, "SDWS 1 barrier clip; " + "data/ WorldPop evidence folder")]),
 "WPOPMETA.points_cut_over_10pct": dict(pop="managed_fleet",
   arith="`of those, losing more than a tenth of the service area: ${fmt(WPOPMETA.points_cut_over_10pct)}`",
   forms=[("WorldPop R2025A run", None, "SDWS 1 barrier clip")]),
 "ENDURO.systems": dict(pop=None, manual="enduro",
   arith="`hand-entered: ${ENDURO.systems} piped systems`",
   forms=[]),
}
# the chain table's own cells: each is the reconciliation step it reports
for _k in range(8):
    D[f"POPS.chain[{_k}].detail"] = dict(pop=None, chain=True,
        arith=f'`the counts on both sides of the relation: ${{POPS.chain[{_k}] ? POPS.chain[{_k}].detail : "-"}}`',
        forms=[])
    D[f"POPS.gaps[{_k}].what"] = dict(pop=None, chain=True,
        arith=f'`a step of the chain that does not hold: ${{POPS.gaps[{_k}] ? POPS.gaps[{_k}].what : "-"}}`',
        forms=[])

# the definitions table's own size cells: each is the population it names
for _pid in ("register_records", "first_rehabilitated", "rehabilitated_successfully",
             "managed_fleet", "carbon_fleet", "marolinta",
             "calendar_evidenced_2026", "down_now"):
    D[f"POPS.populations['{_pid}'].size"] = dict(
        pop=_pid,
        arith=f'`the number of records the rule selects: ${{fmt(POPS.populations[\'{_pid}\'].size)}}`',
        forms=[])

for k in ("act", "watch", "closed", "rows", "nodate", "open"):
    D[f"ACTN.{k}"] = dict(pop=None, actions=True,
      arith=f"`counted from the action list every build: ${{ACTN.{k}}}`",
      forms=[])

BEGIN = ("/* BEGIN GENERATED derivations :: tools/render_derivations.py :: "
         "do not edit between these markers */")
END = "/* END GENERATED derivations */"


def block():
    pops = json.load(open(os.path.join(REPO, "data", "populations.json"),
                          encoding="utf8"))
    return (f"{BEGIN}\n"
            "// What every figure is over, in plain English, with its working.\n"
            f"const POPS={json.dumps(pops, separators=(',', ':'), ensure_ascii=False)};\n"
            f"const DERIV={json.dumps(D, separators=(',', ':'), ensure_ascii=False)};\n"
            f"{END}")


def apply(write):
    page = open(PAGE, encoding="utf8").read()
    new = block()
    if BEGIN in page:
        i, j = page.index(BEGIN), page.index(END) + len(END)
    else:
        anchor = "/* BEGIN GENERATED datasets"
        i = j = page.index(anchor)
        new = new + "\n"
    if page[i:j].strip() == new.strip():
        print("index.html derivations match their generator")
        return 0
    if not write:
        print("index.html derivations DIFFER from their generator")
        return 1
    open(PAGE, "w", encoding="utf8").write(page[:i] + new + page[j:])
    print(f"index.html derivations rewritten ({len(D)} expressions, "
          f"{len(pops_count())} populations)")
    return 0


def pops_count():
    return json.load(open(os.path.join(REPO, "data", "populations.json"),
                          encoding="utf8"))["populations"]


if __name__ == "__main__":
    sys.exit(apply("--write" in sys.argv))
