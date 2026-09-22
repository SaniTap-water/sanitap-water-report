# -*- coding: utf-8 -*-
"""Which generator writes each field of the page's embedded data.

Established by experiment, not by reading the code: every numeric and free-text
leaf in the embedded objects was perturbed, the whole generator chain was run,
and a field that came back has a generator that computes it. A field that kept
the perturbation has none - nothing in the build can move it. That is the
S.wq_tested fault, and it was true of 71 fields when this was written.

GENERATED   the tool that recomputes it every build.
POPULATION  a population in populations.py reproduces it exactly; the gate
            asserts the stored value against the population size.
UNTESTABLE  the perturbation was a no-op (a date, an id, a hash, a boolean),
            so this method cannot decide. Listed, not excused.

Anything absent from all three is unregistered and the gate fails.
"""

GENERATED = {
    'ACTN.act': 'render_datasets',
    'ACTN.closed': 'render_datasets',
    'ACTN.nodate': 'render_datasets',
    'ACTN.open': 'render_datasets',
    'ACTN.overdue': 'render_datasets',
    'ACTN.rows': 'render_datasets',
    'ACTN.watch': 'render_datasets',
    'CALX.basis': 'render_datasets',
    'CALX.days_illegible': 'render_datasets',
    'CALX.days_not_operational': 'render_datasets',
    'CALX.days_unobserved': 'render_datasets',
    'CALX.images_readable': 'render_datasets',
    'CALX.images_with_day_calls': 'render_datasets',
    'CALX.implied_days_not_operational': 'render_datasets',
    'CALX.implied_true_marked_pct': 'render_datasets',
    'CALX.implied_uptime_days': 'render_datasets',
    'CALX.impossible_cells': 'render_datasets',
    'CALX.median_confidence': 'render_datasets',
    'CALX.observed_cells': 'render_datasets',
    'CALX.observed_illegible': 'render_datasets',
    'CALX.observed_illegible_pct': 'render_datasets',
    'CALX.observed_marked': 'render_datasets',
    'CALX.observed_marked_pct': 'render_datasets',
    'CALX.photographs_excluded_not_calendar': 'render_datasets',
    'CALX.photographs_held': 'render_datasets',
    'CALX.photographs_total': 'render_datasets',
    'CALX.points_total': 'render_datasets',
    'CALX.points_without_readable': 'render_datasets',
    'CALX.probe_cells': 'render_datasets',
    'CALX.probe_marked_pct': 'render_datasets',
    'CALX.pump_periods': 'render_datasets',
    'CALX.sheets_by_year': 'render_datasets',
    'CALX.sheets_dated_from_the_sheet': 'render_datasets',
    'CALX.sheets_not_dated': 'render_datasets',
    'CALX.unobserved_called_illegible': 'render_datasets',
    'CALX.unobserved_called_marked': 'render_datasets',
    'CALX.unobserved_cells': 'render_datasets',
    'CALX.visits_total': 'render_datasets',
    'CALX.visits_with_readable': 'render_datasets',
    'CALX.visits_without_readable': 'render_datasets',
    'CALX.water_points': 'render_datasets',
    'CARBON.basis': 'render_datasets',
    'CARBON.carbon_2026_coverage_pct': 'render_datasets',
    'CARBON.carbon_points': 'render_datasets',
    'CARBON.carbon_points_with_2026_sheet': 'render_datasets',
    'CARBON.carbon_points_without_2026_sheet': 'render_datasets',
    'CARBON.sheets_2026_outside_the_fleet': 'render_datasets',
    'CARBON.supersedes': 'render_datasets',
    'DOWN.[].days_down': 'build_call_tables',
    'DOWN.[].status': 'build_call_tables',
    'DOWN.[].status_src': 'build_call_tables',
    'ENDURO.people': 'render_enduro',
    'ENDURO.reg': 'render_enduro',
    'ENDURO.systems': 'render_enduro',
    'ENDURO_SRC.age': 'render_enduro',
    'ENDURO_SRC.by': 'render_enduro',
    'ENDURO_SRC.doc': 'render_enduro',
    'ENDURO_SRC.max': 'render_enduro',
    'ENDURO_SRC.people_by': 'render_enduro',
    'FRESH.blocking_lag_days': 'render_datasets',
    'FRESH.files_age_days': 'render_datasets',
    'FRESH.lag_days': 'render_datasets',
    'FRESH.page_age_days': 'render_datasets',
    'FRESH.page_behind_files_days': 'render_datasets',
    'FRESH.per_source': 'render_datasets',
    'FRESH.worst_source': 'render_datasets',
    'FRESH.worst_source_lag_days': 'render_datasets',
    'METRICS.calls_using_service_visit_choice': 'render_datasets',
    'METRICS.consent_question_answers': 'render_datasets',
    'METRICS.downs_without_repair': 'render_datasets',
    'METRICS.duplicate_question_codes': 'render_datasets',
    'METRICS.enduro_figures_age_days': 'render_datasets',
    'METRICS.enduro_figures_unattributed': 'render_datasets',
    'METRICS.er_percent_of_type3_cap': 'render_datasets',
    'METRICS.extract_lag_days': 'render_datasets',
    'METRICS.marolinta_blank_status': 'render_datasets',
    'METRICS.marolinta_new_borehole_records': 'render_datasets',
    'METRICS.marolinta_new_final': 'render_datasets',
    'METRICS.marolinta_points_no_admin': 'render_datasets',
    'METRICS.marolinta_points_no_photograph': 'render_datasets',
    'METRICS.marolinta_points_without_wq': 'render_datasets',
    'METRICS.marolinta_rehabs_final': 'render_datasets',
    'METRICS.marolinta_three_points_no_photograph': 'render_datasets',
    'METRICS.moramanga_draft_records': 'render_datasets',
    'METRICS.photographs_misfiled': 'render_datasets',
    'METRICS.point_742896839_in_register': 'render_datasets',
    'METRICS.points_no_2026_calendar': 'render_datasets',
    'METRICS.points_no_calendar_ever': 'render_datasets',
    'METRICS.points_without_readable_calendar': 'render_datasets',
    'METRICS.pumps_reduced_performance': 'render_datasets',
    'METRICS.register_chain_unresolved': 'render_datasets',
    'METRICS.register_dashboard_gap': 'render_datasets',
    'METRICS.sites_without_route_plan': 'render_datasets',
    'METRICS.stroke_test_responses': 'render_datasets',
    'METRICS.transcription_sheets_done': 'render_datasets',
    'METRICS.unapproved_works_records': 'render_datasets',
    'METRICS.unsourced_figures': 'render_datasets',
    'METRICS.usage_question_answers': 'render_datasets',
    'METRICS.usage_survey_responses': 'render_datasets',
    'METRICS.water_quality_failures_unretested': 'render_datasets',
    'PARTIAL.[].comments': 'build_call_tables',
    'PARTIAL.[].commune': 'build_call_tables',
    'PARTIAL.[].kind': 'build_call_tables',
    'PARTIAL.[].site': 'build_call_tables',
    'PARTIAL.[].status': 'build_call_tables',
    'POPS.chain': 'render_derivations',
    'POPS.gaps': 'render_derivations',
    'POPS.populations': 'render_derivations',
    'PUMPS.[].days': 'rebuild_activity',
    'PUMPS.[].status': 'build_call_tables',
    'PUMPS.[].status_src': 'build_call_tables',
    'S.over6': 'rebuild_activity',
    'S.over6_site': 'rebuild_activity',
    'S.status': 'build_call_tables',
    'S.week': 'rebuild_activity',
}

POPULATION = {
    'S.n': 'managed_fleet',
    'S.wq_tested': 'water_quality_tested',
}

# Perturbation could not move these, so the experiment is silent on them.
UNTESTABLE = {
    'CORR.version',
    'DOWN.[].comm',
    'DOWN.[].due',
    'DOWN.[].last_pm',
    'DOWN.[].last_repair',
    'DOWN.[].last_visit',
    'DOWN.[].last_visit_real',
    'DOWN.[].nocomm',
    'DOWN.[].status_date',
    'DOWN.[].wp',
    'DOWN.[].wq_date',
    'ENDURO_SRC.as_at',
    'ENDURO_SRC.people_as_at',
    'ENDURO_SRC.reg_as_at',
    'ENDURO_SRC.stale',
    'FRESH.checked',
    'FRESH.extract_newest',
    'FRESH.files_newest',
    'FRESH.known_gaps',
    'FRESH.latest_in_extract',
    'FRESH.latest_in_extract_files',
    'FRESH.latest_in_mwater',
    'FRESH.mwater_newest',
    'METRICS.enduro_sites_outside_mwater',
    'OPENREP.[].date',
    'OPENREP.[].wp',
    'PARTIAL.[].date',
    'PARTIAL.[].rid',
    'PARTIAL.[].wp',
    'POPS.form_base',
    'PUMPS.[].comm',
    'PUMPS.[].due',
    'PUMPS.[].last_pm',
    'PUMPS.[].last_repair',
    'PUMPS.[].last_visit',
    'PUMPS.[].last_visit_real',
    'PUMPS.[].nocomm',
    'PUMPS.[].status_date',
    'PUMPS.[].wp',
    'PUMPS.[].wq_date',
    'RESP.{*}.h',
    'RESP.{*}.p',
    'RESP.{*}.q',
    'RESP.{*}.v',
    'S.wq_fail',
    'WPOPMETA.barriers_applied',
    'WPOPMETA.folder',
    'WPOPMETA.raster_sha256',
    'WPOPMETA.run',
}


def resolve(obj, field):
    """The generator for one field, or None when nothing writes it."""
    key = f"{obj}.{field}"
    if key in GENERATED:
        g = GENERATED[key]
        return g if isinstance(g, str) else "+".join(g)
    if key in POPULATION:
        return f"population:{POPULATION[key]}"
    if key in UNTESTABLE:
        return "untestable"
    return None


GENERATORS = GENERATED  # legacy name
