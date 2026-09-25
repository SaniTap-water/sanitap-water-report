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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# a region that differs only in prerendered figure values is not drift
from prerender_figures import same as _same  # noqa: E402

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
 'SDWS26.answered_both': dict(pop='usage_survey_answered_both',
   arith='`${fmt(SDWS26.answered_both)}`',
   forms=[("Clean Water || Project Cbn&Gender (annual monitoring survey)", "2eeb86824b4545eca33db9e7cf7dcbd4", "WS1.18 dry season and WS1.39 rainy season, matched by choice id")]),
 'SDWS26.excluded_part_entries': dict(pop='usage_survey_answered_both',
   arith='`${fmt(SDWS26.excluded_part_entries)}`',
   forms=[("Clean Water || Project Cbn&Gender (annual monitoring survey)", "2eeb86824b4545eca33db9e7cf7dcbd4", "WS1.18 dry season and WS1.39 rainy season, matched by choice id")]),
 'SDWS26.min_clusters': dict(pop='usage_survey_answered_both',
   arith='`${fmt(SDWS26.min_clusters)}`',
   forms=[("Clean Water || Project Cbn&Gender (annual monitoring survey)", "2eeb86824b4545eca33db9e7cf7dcbd4", "WS1.18 dry season and WS1.39 rainy season, matched by choice id")]),
 'SDWS26.responses_total': dict(pop='usage_survey_answered_both',
   arith='`${fmt(SDWS26.responses_total)}`',
   forms=[("Clean Water || Project Cbn&Gender (annual monitoring survey)", "2eeb86824b4545eca33db9e7cf7dcbd4", "WS1.18 dry season and WS1.39 rainy season, matched by choice id")]),
 "SDWS26.scenarios['Fort-Dauphin'].answered_both": dict(pop='usage_survey_answered_both',
   arith="`${fmt(SDWS26.scenarios['Fort-Dauphin'].answered_both)}`",
   forms=[("Clean Water || Project Cbn&Gender (annual monitoring survey)", "2eeb86824b4545eca33db9e7cf7dcbd4", "WS1.18 dry season and WS1.39 rainy season, matched by choice id")]),
 "SDWS26.scenarios['Fort-Dauphin'].clusters": dict(pop='usage_survey_answered_both',
   arith="`${fmt(SDWS26.scenarios['Fort-Dauphin'].clusters)}`",
   forms=[("Clean Water || Project Cbn&Gender (annual monitoring survey)", "2eeb86824b4545eca33db9e7cf7dcbd4", "WS1.18 dry season and WS1.39 rainy season, matched by choice id")]),
 "SDWS26.scenarios['Fort-Dauphin'].hh_size_mean": dict(pop='usage_survey_answered_both',
   arith="`${fmt(SDWS26.scenarios['Fort-Dauphin'].hh_size_mean)}`",
   forms=[("Clean Water || Project Cbn&Gender (annual monitoring survey)", "2eeb86824b4545eca33db9e7cf7dcbd4", "WS1.18 dry season and WS1.39 rainy season, matched by choice id")]),
 "SDWS26.scenarios['Fort-Dauphin'].water_points": dict(pop='usage_survey_answered_both',
   arith="`${fmt(SDWS26.scenarios['Fort-Dauphin'].water_points)}`",
   forms=[("Clean Water || Project Cbn&Gender (annual monitoring survey)", "2eeb86824b4545eca33db9e7cf7dcbd4", "WS1.18 dry season and WS1.39 rainy season, matched by choice id")]),
 "SDWS26.scenarios['Maroantsetra'].answered_both": dict(pop='usage_survey_answered_both',
   arith="`${fmt(SDWS26.scenarios['Maroantsetra'].answered_both)}`",
   forms=[("Clean Water || Project Cbn&Gender (annual monitoring survey)", "2eeb86824b4545eca33db9e7cf7dcbd4", "WS1.18 dry season and WS1.39 rainy season, matched by choice id")]),
 "SDWS26.scenarios['Maroantsetra'].clusters": dict(pop='usage_survey_answered_both',
   arith="`${fmt(SDWS26.scenarios['Maroantsetra'].clusters)}`",
   forms=[("Clean Water || Project Cbn&Gender (annual monitoring survey)", "2eeb86824b4545eca33db9e7cf7dcbd4", "WS1.18 dry season and WS1.39 rainy season, matched by choice id")]),
 "SDWS26.scenarios['Maroantsetra'].clusters_short_by": dict(pop='usage_survey_answered_both',
   arith="`${fmt(SDWS26.scenarios['Maroantsetra'].clusters_short_by)}`",
   forms=[("Clean Water || Project Cbn&Gender (annual monitoring survey)", "2eeb86824b4545eca33db9e7cf7dcbd4", "WS1.18 dry season and WS1.39 rainy season, matched by choice id")]),
 "SDWS26.scenarios['Maroantsetra'].hh_size_mean": dict(pop='usage_survey_answered_both',
   arith="`${fmt(SDWS26.scenarios['Maroantsetra'].hh_size_mean)}`",
   forms=[("Clean Water || Project Cbn&Gender (annual monitoring survey)", "2eeb86824b4545eca33db9e7cf7dcbd4", "WS1.18 dry season and WS1.39 rainy season, matched by choice id")]),
 "SDWS26.scenarios['Maroantsetra'].water_points": dict(pop='usage_survey_answered_both',
   arith="`${fmt(SDWS26.scenarios['Maroantsetra'].water_points)}`",
   forms=[("Clean Water || Project Cbn&Gender (annual monitoring survey)", "2eeb86824b4545eca33db9e7cf7dcbd4", "WS1.18 dry season and WS1.39 rainy season, matched by choice id")]),

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
 "REG.total_first_rehab": dict(pop="first_rehabilitated",
   arith="`first-rehabilitation records on the works form: ${fmt(REG.total_first_rehab)}`",
   forms=[("Clean Water || Premi\\u00e8re r\\u00e9habilitation / Entretien pr\\u00e9ventif / R\\u00e9paration apr\\u00e8s panne",
           F_COMBINED, 'question "Type de travaux" = "Premi\\u00e8re r\\u00e9habilitation"')],
   caveat="A RECORD count: 773 records on 773 distinct points. It reconciles "
          "exactly with the form once the form is enumerated stably - a paged "
          "pull of it duplicates and drops rows."),
 "REG.succ": dict(pop="rehabilitated_successfully",
   arith="`water POINTS whose first rehabilitation is recorded successful: ${fmt(REG.succ)}`",
   forms=[("Clean Water || Premi\u00e8re r\u00e9habilitation / ...", F_COMBINED,
           'question "V\u00e9rifier : La r\u00e9paration ou la maintenance a r\u00e9ussi ?" = Oui'),
          ("Clean Water || Suivi avancement nouveau forage et r\u00e9habilitation", F_MAR,
           "the Marolinta works, recorded only here")],
   caveat="Supersedes 723, which was withdrawn on 22 September 2026 because it "
          "could not be reproduced from any data held. This is a POINT count; "
          "the RECORD count is 731 and is a different quantity."),
 "REG.succ_records": dict(pop="successful_first_rehabilitation_records",
   arith="`successful first-rehabilitation RECORDS: ${fmt(REG.succ_records)}`",
   forms=[("Clean Water || Premi\u00e8re r\u00e9habilitation / ...", F_COMBINED,
           'question "V\u00e9rifier : ... a r\u00e9ussi ?" = Oui')],
   caveat="A RECORD count. It equals 731, the same number as the carbon fleet, "
          "by coincidence: those are unrelated quantities and must never be "
          "set beside each other as a reconciliation."), "REG.dashboard_fdmar": dict(pop="register_records",
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
 "POPS.populations['repairs_since_aug_2024'].size": dict(pop="repairs_since_aug_2024",
   arith="`${fmt(POPS.populations['repairs_since_aug_2024'].size)} repair records, "
         "linked to a point, since 1 Aug 2024, one per point and date`",
   forms=[("R\\u00e9paration apr\\u00e8s panne", F_REP, None)]),
 "POPS.populations['repairs_time_measured'].size": dict(pop="repairs_time_measured",
   arith="`of ${fmt(POPS.populations['repairs_since_aug_2024'].size)} repairs, "
         "${fmt(POPS.populations['repairs_time_measured'].size)} carry both a "
         "notification and a completion date and can be timed`",
   forms=[("R\\u00e9paration apr\\u00e8s panne", F_REP, None),
          ("Appel / signalement de pannes", F_CALL, None)]),
 "WPOPMETA.points_with_a_barrier": dict(pop="managed_fleet",
   arith="`managed points whose 1 km circle is cut by a barrier: ${fmt(WPOPMETA.points_with_a_barrier)} of ${WPOPMETA.rows}`",
   forms=[("WorldPop R2025A run", None, "SDWS 1 barrier clip; " + "data/ WorldPop evidence folder")]),
 "WPOPMETA.run": dict(pop="managed_fleet",
   arith="`the WorldPop allocation run of ${WPOPMETA.run}, over ${fmt(WPOPMETA.rows)} water points, raster ${WPOPMETA.raster}`",
   forms=[("the SDWS 1 allocation run", None, "~/sdws1 run folder; summary copied to data/sdws1_summary_equal.json")],
   why="The date of the people-served run a table draws on. The run is repeated whenever a pump joins or leaves."),
 "WPOPMETA.points_cut_over_10pct": dict(pop="managed_fleet",
   arith="`of those, losing more than a tenth of the service area: ${fmt(WPOPMETA.points_cut_over_10pct)}`",
   forms=[("WorldPop R2025A run", None, "SDWS 1 barrier clip")]),
 "ENDURO.systems": dict(pop=None, manual="enduro",
   arith="`hand-entered: ${ENDURO.systems} piped systems`",
   forms=[]),
}
D["((PUMPS.filter(p=>p.site==='Fort-Dauphin').reduce((a,p)=>a+(p.wpop||0),0)*PARAMS.fnrb_toliary.v+PUMPS.filter(p=>p.site==='Maroantsetra').reduce((a,p)=>a+(p.wpop||0),0)*PARAMS.fnrb_mofuss_maroantsetra.v)/PUMPS.filter(p=>p.site!=='Marolinta').reduce((a,p)=>a+(p.wpop||0),0)).toFixed(3)"] = dict(pop="carbon_fleet",
    arith="`Fort-Dauphin ${fmt(PUMPS.filter(p=>p.site==='Fort-Dauphin').reduce((a,p)=>a+(p.wpop||0),0))} people at fNRB ${PARAMS.fnrb_toliary.v} + Maroantsetra ${fmt(PUMPS.filter(p=>p.site==='Maroantsetra').reduce((a,p)=>a+(p.wpop||0),0))} at ${PARAMS.fnrb_mofuss_maroantsetra.v}, over ${fmt(PUMPS.filter(p=>p.site!=='Marolinta').reduce((a,p)=>a+(p.wpop||0),0))} people served`",
    forms=[("the registered fNRB values, weighted by people served",
            None, "PARAMS.fnrb_toliary and PARAMS.fnrb_mofuss_maroantsetra")])

# every "nearest other point" distance in the corrections log
for _wp in json.load(open(os.path.join(REPO, "data", "nearest_point_distances.json"),
                          encoding="utf8"))["distances"]:
    D[f"NEAREST.distances['{_wp}'].metres"] = dict(pop="located_register_points",
        arith=f"`haversine from {_wp} to the nearest other located register point, "
              f"${{NEAREST.distances['{_wp}'].nearest}}: ${{fmt(NEAREST.distances['{_wp}'].metres)}} m`",
        forms=[("the register", None, REGQ + ", records carrying a coordinate")],
        caveat="Recomputed by tools/check_distances.py on every build and asserted "
               "against the distance the corrections log states.")

# people-served allocations by site: a sum over the WorldPop run
for _site, _lab in (("Fort-Dauphin", "Fort-Dauphin"),
                    ("Maroantsetra", "Maroantsetra")):
    D[f"PUMPS.filter(p=>p.site==='{_site}').reduce((a,p)=>a+(p.wpop||0),0)"] = dict(
        pop="managed_fleet",
        arith=f'`the capped WorldPop allocation summed over the {_lab} points: '
              f'${{fmt(PUMPS.filter(p=>p.site===\'{_site}\').reduce((a,p)=>a+(p.wpop||0),0))}} '
              f'over ${{PUMPS.filter(p=>p.site===\'{_site}\').length}} points`',
        forms=[("WorldPop R2025A run, capped per pump type", None,
                "SDWS 1 barrier clip applied; caps from PARAMS")])
D["PUMPS.filter(p=>p.site!=='Marolinta').reduce((a,p)=>a+(p.wpop||0),0)"] = dict(
    pop="carbon_fleet",
    arith='`the capped WorldPop allocation summed over the carbon fleet: '
          '${fmt(PUMPS.filter(p=>p.site!==\'Marolinta\').reduce((a,p)=>a+(p.wpop||0),0))} '
          'over ${PUMPS.filter(p=>p.site!==\'Marolinta\').length} points`',
    forms=[("WorldPop R2025A run, capped per pump type", None,
            "SDWS 1 barrier clip applied; Marolinta excluded")])

# ---- figures converted from typed prose on 2026-09-23 ----------------------
_PPWHY = "Drives maintenance cost per credit: cost scales with pumps, credits with people."
_WBASIS = ("WorldPop R2025A 100 m, 1 km service area, SDWS 1 barrier clip, "
           "overlap split equally, capacity cap per pump type")
F_WQ = "7b33c5d7e5074808a94915939a5a0783"
D["HP.filter(p=>p.days!=null&&p.days>182).length"] = dict(pop="overdue_six_months",
    arith="`managed points in this scope whose last visit, repair or commissioning is more than 182 days old: ${HP.filter(p=>p.days!=null&&p.days>182).length}`",
    forms=[("Entretien préventif", F_PM, None), ("Réparation après panne", F_REP, None)])
for _k, _pop, _what in (("h", "first_rehabilitated", "a first-rehabilitation record to open"),
                        ("v", "managed_fleet", "a preventive-maintenance or repair record behind the last-visit date"),
                        ("q", "water_quality_tested", "an E. coli result behind the water-quality date")):
    D[f"Object.values(RESP).filter(e=>e.{_k}).length"] = dict(pop=_pop,
        arith=f"`water points with {_what}: ${{Object.values(RESP).filter(e=>e.{_k}).length}}`",
        forms=[])
_ER = "S.by_site['Fort-Dauphin']*PARAMS.er_anosy.v+S.by_site['Maroantsetra']*PARAMS.er_maro.v"
D[f"Math.round({_ER})"] = dict(pop="carbon_fleet",
    arith="`${S.by_site['Fort-Dauphin']} Fort-Dauphin points × ${PARAMS.er_anosy.v} + ${S.by_site['Maroantsetra']} Maroantsetra points × ${PARAMS.er_maro.v} tCO2e = ${fmt(Math.round(" + _ER + "))} tCO2e a year`",
    forms=[("the register and the registered per-point emission reductions", None, "PARAMS.er_anosy, PARAMS.er_maro")])
D[f"Math.floor(PARAMS.cap_t.v/(({_ER})/(S.by_site['Fort-Dauphin']+S.by_site['Maroantsetra'])))"] = dict(pop="carbon_fleet",
    arith="`${fmt(PARAMS.cap_t.v)} tCO2e cap ÷ the current mean per point = ${fmt(Math.floor(PARAMS.cap_t.v/((" + _ER + ")/(S.by_site['Fort-Dauphin']+S.by_site['Maroantsetra']))))} points`",
    forms=[("the register and PARAMS", None, "PARAMS.cap_t, er_anosy, er_maro")])
for _s in ("Maroantsetra", "Fort-Dauphin"):
    _e = (f"(ROUTES.{_s}.n/ROUTES.{_s}.days.length).toFixed(1)" if _s == "Maroantsetra"
          else "(ROUTES['Fort-Dauphin'].n/ROUTES['Fort-Dauphin'].days.length).toFixed(1)")
    _r = "ROUTES.Maroantsetra" if _s == "Maroantsetra" else "ROUTES['Fort-Dauphin']"
    D[_e] = dict(pop=None, arith=f"`${{{_r}.n}} pumps over ${{{_r}.days.length}} route days = ${{{_e}}} a day`",
        forms=[("the catch-up route plan for " + _s, None, "ROUTES, drawn from the overdue list and road time")])
    for _f, _lab in (("wpop", "the capped WorldPop allocation"), ("benef", "the roof-count census")):
        D[f"HP.filter(p=>p.site==='{_s}').reduce((a,p)=>a+(p.{_f}||0),0)"] = dict(pop="managed_fleet",
            arith=f"`{_lab} summed over the {_s} points in this scope: ${{fmt(HP.filter(p=>p.site==='{_s}').reduce((a,p)=>a+(p.{_f}||0),0))}}`",
            forms=[])
    D[f"Math.round(PUMPS.filter(p=>p.site==='{_s}').reduce((a,p)=>a+(p.wpop||0),0)/PUMPS.filter(p=>p.site==='{_s}').length)"] = dict(pop="carbon_fleet",
        arith=f"`people served in {_s} ${{fmt(PUMPS.filter(p=>p.site==='{_s}').reduce((a,p)=>a+(p.wpop||0),0))}} \u00f7 ${{PUMPS.filter(p=>p.site==='{_s}').length}} maintained pumps = ${{fmt(Math.round(PUMPS.filter(p=>p.site==='{_s}').reduce((a,p)=>a+(p.wpop||0),0)/PUMPS.filter(p=>p.site==='{_s}').length))}} per pump`",
        forms=[("WorldPop R2025A run", None, _WBASIS)],
        why=_PPWHY)
D["Math.round(PUMPS.filter(p=>p.site!=='Marolinta').reduce((a,p)=>a+(p.wpop||0),0)/PUMPS.filter(p=>p.site!=='Marolinta').length)"] = dict(pop="carbon_fleet",
    arith="`people served across the carbon portfolio ${fmt(PUMPS.filter(p=>p.site!=='Marolinta').reduce((a,p)=>a+(p.wpop||0),0))} \u00f7 ${PUMPS.filter(p=>p.site!=='Marolinta').length} maintained pumps = ${fmt(Math.round(PUMPS.filter(p=>p.site!=='Marolinta').reduce((a,p)=>a+(p.wpop||0),0)/PUMPS.filter(p=>p.site!=='Marolinta').length))} per pump; Marolinta is outside the carbon programme and not counted`",
    forms=[("WorldPop R2025A run", None, _WBASIS)],
    why=_PPWHY)
for _f, _lab in (("wpop", "the capped WorldPop allocation"), ("benef", "the roof-count census")):
    D[f"HP.reduce((a,p)=>a+(p.{_f}||0),0)"] = dict(pop="managed_fleet",
        arith=f"`{_lab} summed over every point in this scope: ${{fmt(HP.reduce((a,p)=>a+(p.{_f}||0),0))}}`", forms=[])
D["HP.filter(p=>p.site==='Marolinta').reduce((a,p)=>a+(p.wpop||0),0)"] = dict(pop="marolinta",
    arith="`the capped allocation summed over the Marolinta points: ${fmt(HP.filter(p=>p.site==='Marolinta').reduce((a,p)=>a+(p.wpop||0),0))}`", forms=[])
D["HP.filter(p=>p.site==='Marolinta').reduce((a,p)=>a+(p.benef||0),0)"] = dict(pop="marolinta",
    arith="`the roof-count census summed over the Marolinta points: ${fmt(HP.filter(p=>p.site==='Marolinta').reduce((a,p)=>a+(p.benef||0),0))}`", forms=[])
D["Math.round(PUMPS.filter(p=>p.site==='Fort-Dauphin'&&WPOP[p.wp]).reduce((a,p)=>a+WPOP[p.wp][0],0)/PUMPS.filter(p=>p.site==='Fort-Dauphin'&&WPOP[p.wp]).length)"] = dict(pop="managed_fleet",
    arith="`the WorldPop allocation BEFORE the capacity cap, averaged over the Fort-Dauphin points`",
    forms=[("WorldPop R2025A run", None, "WPOP[wp][0], the allocation before the cap")])
D["S.by_site['Maroantsetra']+S.by_site['Fort-Dauphin']"] = dict(pop="carbon_fleet",
    arith="`Maroantsetra ${S.by_site['Maroantsetra']} + Fort-Dauphin ${S.by_site['Fort-Dauphin']} = ${S.by_site['Maroantsetra']+S.by_site['Fort-Dauphin']} managed points in the two carbon districts`", forms=[])
D["REG.dashboard_fdmar-(S.by_site['Maroantsetra']+S.by_site['Fort-Dauphin'])"] = dict(pop="carbon_fleet",
    arith="`the MadAvance dashboard's ${REG.dashboard_fdmar} less our ${S.by_site['Maroantsetra']+S.by_site['Fort-Dauphin']} in the same two districts = ${REG.dashboard_fdmar-(S.by_site['Maroantsetra']+S.by_site['Fort-Dauphin'])}`",
    forms=[("the MadAvance dashboard (REG.dashboard_fdmar, read off the dashboard)", None, None)])
D["PUMPS.filter(p=>p.wpop!=null).length"] = dict(pop="managed_fleet",
    arith="`managed points carrying a WorldPop allocation: ${PUMPS.filter(p=>p.wpop!=null).length} of ${PUMPS.length}`", forms=[])
D["pairsWithin(PARAMS.close_pair_m.v)"] = dict(pop="managed_fleet",
    arith="`pairs of managed points within ${PARAMS.close_pair_m.v} m of each other, by haversine over PUMPS: ${fmt(pairsWithin(PARAMS.close_pair_m.v))}`", forms=[])
for _st in ("Maroantsetra", "Fort-Dauphin"):
    for _k, _w in (("overlap_mean", "the mean number of other managed points whose service area overlaps a point's own (centres within twice the service radius)"),
                   ("overlap_max", "the most other managed points any one point's service area overlaps"),
                   ("alloc_mean", "the mean WorldPop allocation per point before the capacity cap"),
                   ("capped", "points whose allocation reaches the capacity cap"),
                   ("points", "points carrying a WorldPop allocation")):
        D[f"siteStats('{_st}').{_k}"] = dict(pop="managed_fleet",
            arith=f"`{_st}: {_w}: ${{fmt(siteStats('{_st}').{_k})}}`",
            forms=[("the SDWS 1 WorldPop allocation run", None, "WPOP on this page: allocation, capped value and cap per point")])
for _e, _a in (("(PARAMS.people_per_cws_exante.v/PARAMS.hh_size_anosy.v).toFixed(1)", "people per CWS ÷ Anosy household size"),
               ("(PARAMS.people_per_cws_exante.v/PARAMS.hh_size_analanjirofo.v).toFixed(1)", "people per CWS ÷ Analanjirofo household size"),
               ("(PARAMS.premises_per_cws_maroantsetra.v*PARAMS.hh_size_analanjirofo.v).toFixed(1)", "Maroantsetra premises per CWS × Analanjirofo household size"),
               ("(PARAMS.premises_per_cws_anosy.v*PARAMS.hh_size_anosy.v).toFixed(1)", "Anosy premises per CWS × Anosy household size"),
               ("(PARAMS.er_maro.v*(365/PARAMS.do_cap.v-1)).toFixed(2)", "Maroantsetra ER per point × (365 ÷ the 347-day cap − 1)")):
    D[_e] = dict(pop=None, arith=f"`{_a} = ${{{_e}}}`",
        forms=[("declared parameters, each with its VPA-DD citation", None, "see the parameters table")])

# the "How this is worked out" footnotes: every number they state is a value
# of the build configuration, which check_consistency holds to what was applied
for _e in ("BUILDCFG.portfolio.pump_models.join(', ')",
           "BUILDCFG.water_quality.ecoli_pass_max_cfu_per_100ml",
           "BUILDCFG.worldpop.release",
           "BUILDCFG.worldpop.raster_sha256.slice(0,12)+'…'",
           "BUILDCFG.worldpop.service_radius_m",
           "BUILDCFG.worldpop.caps.Canzee",
           "BUILDCFG.worldpop.caps.IndiaMark",
           "BUILDCFG.worldpop.neighbourhood_radius_m",
           "BUILDCFG.roof_count.roofs_per_household",
           "BUILDCFG.roof_count.people_per_household"):
    D[_e] = dict(pop=None,
        arith="`from the build configuration, data/build_config.json - the value the "
              "build applies, checked against the tools and the SDWS1 pipeline on every "
              "build: ${" + _e + "}`",
        forms=[])

D["CALS.evidenced_by.first_recorded['2024'].evidenced"] = dict(pop="managed_fleet",
    arith="`managed points first recorded in the register in 2024 that the calendar stratum evidences: ${CALS.evidenced_by.first_recorded['2024'].evidenced}`",
    forms=[("the calendar stratum, tools/calendar_stratum.py", None,
            "data/gardien_calendar_coverage.csv against the register's _created_on year")])

# the chain table's own cells: each is the reconciliation step it reports
for _k in range(12):
    D[f"POPS.chain[{_k}].detail"] = dict(pop=None, chain=True,
        arith=f'`the counts on both sides of the relation: ${{POPS.chain[{_k}] ? POPS.chain[{_k}].detail : "-"}}`',
        forms=[])
    D[f"POPS.gaps[{_k}].what"] = dict(pop=None, chain=True,
        arith=f'`a step of the chain that does not hold: ${{POPS.gaps[{_k}] ? POPS.gaps[{_k}].what : "-"}}`',
        forms=[])

# the definitions table's own size cells: each is the population it names
import json as _json, os as _os
_popfile = _os.path.join(REPO, "data", "populations.json")
for _pid in _json.load(open(_popfile, encoding="utf8"))["populations"]:
    D[f"POPS.populations['{_pid}'].size"] = dict(
        pop=_pid,
        arith=f'`the number of records the rule selects: ${{fmt(POPS.populations[\'{_pid}\'].size)}}`',
        forms=[])
    # the same figure written with a dot, for text that sits inside a
    # single-quoted JavaScript string (the TRACE rows)
    D[f"POPS.populations.{_pid}.size"] = D[f"POPS.populations['{_pid}'].size"]

# SDWS 26. The served share is the AVERAGE of the dry-season (WS1.18) and
# rainy-season (WS1.39) served shares - James Walker's ruling of 23 September
# 2026. The both-seasons and either-season readings appear here, in the
# working under each average, and nowhere else on the page.
_SDWS26_FORMS = [("Clean Water || Project Cbn&Gender (annual monitoring survey)",
                  "2eeb86824b4545eca33db9e7cf7dcbd4",
                  "WS1.18 dry season and WS1.39 rainy season, matched by choice id")]
_SDWS26_RULE = ("SDWS 26 seasonal rule: the served share is the average of the "
                "dry-season and rainy-season served shares, not the share served in "
                "both seasons - James Walker, Carbon Lead, 23 September 2026, "
                "\u201cRe: Water program dashboard & actions\u201d. Served = every "
                "day, more than once a day or every two days, by choice id; "
                "confirmed in the same email.")
_AVG = ("`dry season ${fmt(§.served_dry)} of ${fmt(§.answered_both)} = "
        "${(100*§.served_dry/§.answered_both).toFixed(1)}%; rainy season "
        "${fmt(§.served_rain)} of ${fmt(§.answered_both)} = "
        "${(100*§.served_rain/§.answered_both).toFixed(1)}%; average = "
        "${((100*§.served_dry/§.answered_both+100*§.served_rain/§.answered_both)/2).toFixed(1)}%"
        " \u2014 sensitivity only, not the reading: served in both seasons "
        "${fmt(§.served_both_seasons)} = "
        "${(100*§.served_both_seasons/§.answered_both).toFixed(1)}%, served in "
        "either season ${fmt(§.served_either_season)} = "
        "${(100*§.served_either_season/§.answered_both).toFixed(1)}%`")
for _p in ("SDWS26", "SDWS26.scenarios['Fort-Dauphin']",
           "SDWS26.scenarios['Maroantsetra']"):
    D[f"((100*{_p}.served_dry/{_p}.answered_both+100*{_p}.served_rain/{_p}.answered_both)/2).toFixed(1)"] = dict(
        pop='usage_survey_answered_both', arith=_AVG.replace("§", _p),
        forms=_SDWS26_FORMS, why=_SDWS26_RULE)
    for _k, _pid, _season in (("served_dry", "usage_served_dry_season", "dry season"),
                              ("served_rain", "usage_served_rainy_season", "rainy season")):
        D[f"{_p}.{_k}"] = dict(pop=_pid, arith=f"`${{fmt({_p}.{_k})}}`",
                               forms=_SDWS26_FORMS)
        D[f"(100*{_p}.{_k}/{_p}.answered_both).toFixed(1)"] = dict(
            pop=_pid,
            arith=(f"`${{fmt({_p}.{_k})}} of ${{fmt({_p}.answered_both)}} premises "
                   f"answering both seasons = ${{(100*{_p}.{_k}/{_p}.answered_both)"
                   f".toFixed(1)}}% served in the {_season}`"),
            forms=_SDWS26_FORMS)

# Each extract's pull date, as the table footnotes state it (25 September 2026).
_MANIFEST = json.load(open(os.path.join(REPO, "data", "extract_manifest.json"),
                           encoding="utf8")).get("files", {})
for _f, _m in sorted(_MANIFEST.items()):
    D[f"PULLS['{_f}'].pulled"] = dict(
        pop=None,
        arith=f"`pulled from mWater on ${{PULLS['{_f}'].pulled}}: ${{fmt(PULLS['{_f}'].rows)}} rows, newest submission ${{PULLS['{_f}'].newest||'none'}}`",
        forms=[(_f, _m.get("form_id"), "pulled by tools/pull_extract.py; recorded in data/extract_manifest.json")],
        why="The date this extract was read out of mWater for this build. A table footnote states it so a reader "
            "knows how current the table's rows are.")

# shares of one population in another, as the action list states them
for _num, _den in (("pm_visits_calendar_photo", "pm_visits"), ("pm_visits_calendar_of_record", "pm_visits")):
    D[f"Math.round(100*POPS.populations.{_num}.size/POPS.populations.{_den}.size)"] = dict(
        pop=_num, arith=f"`${{fmt(POPS.populations.{_num}.size)}} of ${{fmt(POPS.populations.{_den}.size)}} = ${{Math.round(100*POPS.populations.{_num}.size/POPS.populations.{_den}.size)}}%`",
        forms=[("Entretien préventif (preventive maintenance)", F_PM, None)])

D["(100*8579/13715217).toFixed(3)"] = dict(pop=None,
    arith="`8,579 days discounted ÷ 13,715,217 technology days × 100 = ${(100*8579/13715217).toFixed(3)}%`",
    forms=[("Improved Cooking VPA monitoring report, first monitoring period", None, "both figures quoted on this page")],
    why="Arithmetic on two figures another VPA reports, to show the size of its downtime discount.")

for _k in ("sample_min_v1", "sample_min_v2"):
    D[f"PARAMS.{_k}.v*2"] = dict(pop=None,
        arith=f"`${{PARAMS.{_k}.v}} per district × the two carbon districts, Maroantsetra and Fort-Dauphin = ${{PARAMS.{_k}.v*2}}`",
        forms=[("declared parameters", None, "see the parameters table")])

for k in ("act", "watch", "closed", "rows", "nodate", "open"):
    D[f"ACTN.{k}"] = dict(pop=None, actions=True,
      arith=f"`counted from the action list every build: ${{ACTN.{k}}}`",
      forms=[])

# ---------------------------------------------------------------------------
# Derivation RULES (25 September 2026). A figure the page's own scripts
# compute for the selected scope - agg(HP).over6, marBasis().points - has as
# many expressions as the page has renderers, and each is the same kind of
# thing. A rule states that kind once: the population, the forms, what it is.
# The page resolves a figure through DERIV first and then the first rule whose
# pattern matches; the arithmetic shown is the expression's own value. The
# census, check_consistency and the panel all resolve the same way.
# ---------------------------------------------------------------------------
_PM = ("Entretien préventif (preventive maintenance)", F_PM, None)
_REP = ("Réparation après panne (repair)", F_REP, None)
_CALL = ("Appel / signalement de pannes (call centre)", F_CALL, None)
_REGF = (REGQ, None, None)
RULES = [
 dict(re=r"ENDURO\.", pop=None,
      what="includes the hand-entered Endur'O figure from the dated manual file (ENDURO), added to the live hand-pump figure where the scope covers both",
      forms=[("Endur'O manual figures", None, "data/enduro_manual.json, supplier and date in the Endur'O block")],
      why="Endur'O is not on mWater yet, so its part of any combined figure is hand-entered and dated."),
 dict(re=r"^agg\(HP\)\.(n|st\.|over6|never|gap|wqp|wqf|site|pump|benef)", pop="managed_fleet",
      what="computed by agg() over the managed pumps in the selected scope",
      forms=[_REGF, _PM, _REP, _CALL],
      why="The same aggregate the headline tiles, donuts and partner table read, so no two of them can disagree."),
 dict(re=r"^agg\(HP\)\.wpop", pop="managed_fleet",
      what="the WorldPop allocation summed by agg() over the managed pumps in the selected scope, each after its capacity cap",
      forms=[_REGF, ("the SDWS 1 WorldPop allocation run", None, "WPOP on this page")],
      why="People served in this scope on the method of record."),
 dict(re=r"^(Math\.round\()?\(*agg\(HP\)", pop="managed_fleet",
      what="computed by agg() over the managed pumps in the selected scope (a sum, or a whole-number percentage of such sums)",
      forms=[_REGF, _PM, _REP, _CALL], why=None),
 dict(re=r"^(Math\.round\()?schedCounts\(\)", pop="managed_fleet",
      what="the preventive-maintenance schedule over the managed pumps in scope: each pump is due the overdue interval after its last visit or repair, and is counted in the window its due date falls in",
      forms=[_PM, _REP], why="Tells the field teams how much is due and how fast the backlog must be cleared."),
 dict(re=r"^photoPool\(\)", pop="managed_fleet",
      what="water points in the selected scope with field photographs on file in mWater (PHOTOS)",
      forms=[("hygiene-promotion, repair and borehole-progress forms", None, "photograph questions")], why=None),
 dict(re=r"^reconShown\(\)", pop="first_rehabilitation_records",
      what="rows of the reconciliation set shown under the reason buttons that are pressed",
      forms=[], why=None),
 dict(re=r"^GEN\.calendar\.", pop="managed_fleet",
      what="computed by tools/render_block.py on every build from the gardien-calendar reader's outputs: data/calendar_extraction_figures.json, data/calendar_not_calendar.csv, data/calendar_no_usable_image.csv, data/calendar_year_coverage.csv, transcription/validation_selection.csv, and the reader's sheet-year and day-level files in ~/sdws1/calendar_extract",
      forms=[("gardien calendar photographs", F_PM, "questions 2.15.5, 2.15.6 and repair 1.3.1.3, machine-read")],
      why="Machine extraction, internal only: none of these is a figure of record."),
 dict(re=r"^GEN\.cparams\.", pop=None,
      what="counted by tools/render_carbon_params.py on every build over data/carbon_parameters.json, each parameter's readiness derived from the populations and the extract manifest",
      forms=[("data/carbon_parameters.json", None, "the register of what the methodology requires us to evidence")], why=None),
 dict(re=r"^GEN\.marolinta\.", pop="marolinta_works_records",
      what="computed by tools/render_marolinta.py on every build from the Marolinta deployment of the borehole-progress form (data/marolinta_works.json), the beneficiary counts on those records (data/marolinta_benef.json) and the register's administrative fields (data/marolinta_admin.json); a shortfall is measured against the SLT minutes of 14 September 2026",
      forms=[("Marolinta borehole-progress form", F_MAR, "Marolinta and Moramanga deployments")],
      why="Marolinta is outside the carbon programme; these count the works, not the register."),
 dict(re=r"^marBasis\(\)\.", pop="marolinta_works_records",
      what="computed by marBasis() from the Marolinta works records and the register",
      forms=[("Marolinta borehole-progress form", F_MAR, "the Marolinta deployment")],
      why="The Marolinta scope is based on the work, not the register; both counts are shown so neither is mistaken for the other."),
 dict(re=r"^(HP|PUMPS)\.(filter|length|reduce)", pop="managed_fleet",
      what="counted in the browser over the managed pumps",
      forms=[_REGF, _PM, _REP],
      why=None),
 dict(re=r"^(DOWNS|DOWN)\b", pop="down_now",
      what="counted over the pumps whose latest answered status is down",
      forms=[_CALL, _PM, _REP], why=None),
 dict(re=r"^(PARTS|PARTIAL)\b", pop="managed_fleet",
      what="counted over the pumps whose latest answered status is partially working",
      forms=[_CALL, _PM, _REP], why=None),
 dict(re=r"^(OPENS|OPENREP)\b", pop="managed_fleet",
      what="counted over the open down-reports with no repair recorded since (stored in the page; on the ungenerated backlog)",
      forms=[_CALL, _REP], why=None),
 dict(re=r"^S\.(n|by_site|by_pump|status|over6|never|wq_|week|pm_month|rep_month|down_list)", pop="managed_fleet",
      what="a summary field of S, rewritten from the extracts on every build",
      forms=[_REGF, _PM, _REP, _CALL], why=None),
 dict(re=r"^S\.(oos|oos_site)\b", pop="repairs_time_measured",
      what="time out of service by band and by site, as stored in the page when last computed; no build step recomputes it (on the recorded ungenerated backlog)",
      forms=[_REP, _CALL], why=None),
 dict(re=r"^S\.visits_per_day[.\[]", pop="pm_visits",
      what="preventive-maintenance visits per field day, by submission date, as stored in the page when last computed; no build step recomputes it (on the recorded ungenerated backlog)",
      forms=[_PM], why=None),
 dict(re=r"^SITES\.map\(x=>\(ROUTES", pop="overdue_six_months",
      what="technician-days in the catch-up route plans for the sites in scope",
      forms=[("the catch-up route plan", None, "ROUTES")], why=None),
 dict(re=r"^CORR\.(corrected|excluded)\.length$", pop="rehabilitated_successfully",
      what="entries in the standing register corrections, data/register_corrections.json",
      forms=[], why=None),
 dict(re=r"^REG\.", pop="first_rehabilitation_records",
      what="a register-chain field of REG, from the register and the first-rehabilitation records",
      forms=[_REGF, ("Première réhabilitation / Entretien préventif / Réparation après panne (combined, retired)", F_COMBINED, None)],
      why=None),
 dict(re=r"^(TTR|TTRQ)\b", pop="repairs_time_measured",
      what="time from breakdown notified to repair completed, over the repairs with both dates",
      forms=[_REP], why="Repair speed is the only lever on days operational."),
 dict(re=r"^ROUTES\b", pop="overdue_six_months",
      what="from the catch-up route plan drawn over the overdue pumps (stored in the page; on the ungenerated backlog)",
      forms=[("the catch-up route plan", None, "ROUTES: OpenStreetMap road time plus time on site")], why=None),
 dict(re=r"^METRICS\.", pop=None,
      what="an action metric recounted by tools/action_metrics.py on every build",
      forms=[("data/action_metrics.json", None, "each metric is a named, stored query over the build's data")],
      why="The count that decides whether an action is still open."),
 dict(re=r"^ACTCOND\[", pop=None,
      what="the closing threshold of the action, declared in data/action_conditions.json",
      forms=[("data/action_conditions.json", None, "the stored closing condition")],
      why="An action closes itself when its metric reaches this threshold."),
 dict(re=r"^BUILDCFG\.", pop=None,
      what="from the build configuration, data/build_config.json - the value the build applies, checked against the tools on every build",
      forms=[], why=None),
 dict(re=r"^(CALX|CALS)\b", pop="managed_fleet",
      what="from the gardien-calendar reader's outputs (data/calendar_extraction_figures.json, data/calendar_stratum_figures.json)",
      forms=[("gardien calendar photographs", F_PM, "machine-read by tools/read_year_ocr.py")], why=None),
 dict(re=r"^(WPOP|WPOPMETA|WPOPX)\b", pop="managed_fleet",
      what="from the SDWS 1 WorldPop allocation run",
      forms=[("the SDWS 1 allocation run", None, "summary in data/sdws1_summary_equal.json")], why=None),
 dict(re=r"^CARBON\.", pop="carbon_fleet",
      what="from the carbon denominator, data/carbon_denominator.json, computed on every build",
      forms=[_REGF], why=None),
 dict(re=r"^FRESH\.", pop=None,
      what="from the freshness check, data/data_freshness.json, computed on every build",
      forms=[], why=None),
 dict(re=r"^(CORR|SUCC_CORRECTED)\b", pop="rehabilitated_successfully",
      what="from the standing register corrections, data/register_corrections.json",
      forms=[], why=None),
 dict(re=r"^SDWS26\.", pop="usage_survey_answered_both",
      what="from the annual monitoring survey (tools/rebuild_sdws26.py)",
      forms=[("Clean Water || Project Cbn&Gender (annual monitoring survey)", "2eeb86824b4545eca33db9e7cf7dcbd4", "WS1.18 and WS1.39")],
      why=None),
 dict(re=r"^PARAMS\.", pop=None,
      what="computed from declared parameters, each with its citation in the parameters table",
      forms=[("declared parameters", None, "see the parameters table")], why=None),
 dict(re=r"^EDITION\b", pop=None, what="the edition number, read from the masthead", forms=[], why=None),
 dict(re=r"^wpopAt\(", pop="managed_fleet",
      what="the people-served total the register would give under a different pair of capacity ceilings, recomputed by wpopAt() from each point's WorldPop allocation before the cap",
      forms=[("the SDWS 1 WorldPop allocation run", None, "WPOP on this page: allocation, capped value and cap per point")],
      why="How much of the people-served figure rests on the choice of capacity ceiling."),
 dict(re=r"^NOTCAL\.", pop="pm_visits_calendar_photo",
      what="counted from data/calendar_not_calendar.csv: every calendar photograph on file inspected by eye, those that are not calendars, by what they show and by the question they sit on",
      forms=[("Entretien préventif (preventive maintenance)", F_PM, "calendar questions 2.15.5 and 2.15.6"), ("Réparation après panne (repair)", F_REP, "calendar question 1.3.1.3")], why=None),
 dict(re=r"^NOUSABLE\.", pop="managed_fleet",
      what="counted from data/calendar_no_usable_image.csv: points none of whose calendar photographs can be read, by cause",
      forms=[("gardien calendar photographs", F_PM, "machine-read")], why=None),
 dict(re=r"^document\.querySelectorAll\('#act-flat tbody tr", pop=None,
      what="rows of the action list shown under the current filter, counted in the page",
      forms=[], why=None),
 dict(re=r"^Object\.values\(RESP\)", pop="managed_fleet",
      what="water points with a record of that kind to open in mWater (RESP: the first-rehabilitation, last-visit and water-quality response behind each point)",
      forms=[_PM, _REP, ("Water Quality Testing_SDWS 3 — Result", "7b33c5d7e5074808a94915939a5a0783", None)], why=None),
 dict(re=r"^VMAP\.", pop=None,
      what="counted from the machine-readable index of docs/methodology_version_map.md, the register of divergences between ERSDWS v1.0 and v2.0 that touch what we collect, compute or evidence: its rows, and those marked action_now = yes",
      forms=[], why=None),
 dict(re=r"^HOLDS\.", pop="managed_fleet",
      what="from data/call_status_holds.json: pumps whose published status the recovered status rule cannot reproduce, held on that value until the next answered record settles them",
      forms=[_CALL, _PM, _REP], why=None),
 dict(re=r"^(Object\.keys\(PULLS\)|VINTAGE\.)", pop=None,
      what="from the extract manifest and the vintage check (data/extract_manifest.json, data/extract_vintage.json), written on every build",
      forms=[("tools/pull_extract.py and tools/check_vintage.py", None, None)], why=None),
 dict(re=r"^Object\.(keys|values)\(FRESH\.", pop=None,
      what="from the freshness check, data/data_freshness.json, computed on every build",
      forms=[], why=None),
 dict(re=r"^document\.querySelectorAll\('#gapsec tbody tr'\)\.length$", pop=None,
      what="the number of rows in the carbon data gaps list below",
      forms=[("claude/carbon-data-gaps-what-we-still-must-gather-2026-09-18.md", None, "the list Jan drives")], why=None),
 # fallbacks, unanchored, for arithmetic that starts with Math. or a bracket
 # but reads the same objects; tried only after every specific rule
 dict(re=r"\bSDWS26\.", pop="usage_survey_answered_both",
      what="computed from the annual monitoring survey (tools/rebuild_sdws26.py)",
      forms=[("Clean Water || Project Cbn&Gender (annual monitoring survey)", "2eeb86824b4545eca33db9e7cf7dcbd4", "WS1.18 and WS1.39")], why=None),
 dict(re=r"\bROUTES\b", pop="overdue_six_months",
      what="from the catch-up route plan drawn over the overdue pumps (stored in the page; on the ungenerated backlog)",
      forms=[("the catch-up route plan", None, "ROUTES: OpenStreetMap road time plus time on site")], why=None),
 dict(re=r"\bCALS\.", pop="managed_fleet",
      what="computed from the calendar stratum (data/calendar_stratum_figures.json)",
      forms=[("gardien calendar photographs", F_PM, "machine-read by tools/read_year_ocr.py")], why=None),
 dict(re=r"\b(PUMPS|HP)\.(filter|reduce|length)|\bS\.(n|by_site)\b", pop="managed_fleet",
      what="computed in the browser over the managed pumps",
      forms=[_REGF, ("the SDWS 1 WorldPop allocation run", None, "WPOP on this page")], why=None),
 dict(re=r"\bPARAMS\.", pop=None,
      what="computed from declared parameters, each with its citation in the parameters table",
      forms=[("declared parameters", None, "see the parameters table")], why=None),
]

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
            f"const DERIV_RULES={json.dumps(RULES, separators=(',', ':'), ensure_ascii=False)};\n"
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
    if _same(page[i:j], new):
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
