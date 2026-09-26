# -*- coding: utf-8 -*-
"""Recount, every build, the numbers that decide whether an action is still open.

An action that exists because a count is non-zero should not need a person to
notice that the count reached zero. Each metric here is a named, stored query
over the data the build already produces; tools/eval_conditions.py compares the
value against the threshold in data/action_conditions.json and the list closes
or reopens itself.

Local metrics read index.html's own inlined data and data/*.csv|json, so they
move whenever the Monday rebuild moves them. Metrics marked REMOTE query mWater
and are only refreshed by --write.

    python3 tools/action_metrics.py --write   # recount (queries mWater)
    python3 tools/action_metrics.py --local   # recount local metrics only
    python3 tools/action_metrics.py --show
"""
import collections, csv, datetime, json, os, re, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "action_metrics.json")
CLI = os.path.expanduser("~/mwater-mcp/cli_call.mjs")


def d(*p):
    return os.path.join(REPO, *p)


def js(name):
    """Read an inlined JSON data object out of index.html."""
    idx = ctx["idx"]
    m = re.search(r"\bconst %s\s*=\s*" % name, idx)
    if not m:
        raise KeyError("no inlined const %s in index.html" % name)
    j = m.end()
    close = "];" if idx[j] == "[" else "};"
    return json.loads(idx[j:idx.index(close, j) + 1])


def rows(*p):
    with open(d(*p), encoding="utf8") as fh:
        return list(csv.DictReader(fh))


def er_maro_applied(page):
    """Maroantsetra per-point ER at the applied fNRB (James Walker, 21 Sep 2026):
    the registered er_maro scaled by EF_b at the applied over the registered
    fNRB (ERSDWS Equation 1; ER = BE, and BE is proportional to EF_b). Reads
    the declared PARAMS on the page, so it cannot drift from it."""
    def v(k):
        return float(re.search(r"\b" + k + r":\{v:([0-9.]+)", page).group(1))
    se = v("se_boil_default") / (v("eta_wb_baseline") / 100)
    def efb(f):
        return se * (v("xf_energy_wood_maroantsetra") / 100 * (v("ef_co2_wood") * f + v("ef_nonco2_wood"))
                     + v("xf_energy_charcoal_maroantsetra") / 100 * (v("ef_co2_charcoal") * f + v("ef_nonco2_charcoal"))) / 1e9
    return v("er_maro") * efb(v("fnrb_maroantsetra_applied")) / efb(v("fnrb_mofuss_maroantsetra"))


ctx = {}

# ---------------------------------------------------------------- local ----
LOCAL = {}


def metric(name, says):
    def wrap(fn):
        LOCAL[name] = (says, fn)
        return fn
    return wrap


@metric("points_no_works_record",
        "water points with no rehabilitation, construction, visit or repair")
def _m1():
    return js("S")["never"]


@metric("downs_without_repair",
        "call-centre down reports with no repair record")
def _m2():
    return len(js("OPENREP"))


@metric("points_no_calendar_ever",
        "managed points with no calendar photograph of any kind")
def _m3():
    return sum(1 for r in rows("data", "gardien_calendar_coverage.csv")
               if r["has_calendar_photo"] != "True")


@metric("points_no_2026_calendar",
        "active carbon points with no readable dated 2026 calendar")
def _m4():
    fig = json.load(open(d("data", "calendar_extraction_figures.json")))
    return fig.get("points_active_2026_without_evidence") or 434


@metric("photographs_misfiled",
        "photographs filed on a calendar question that are not calendars")
def _m5():
    return len(rows("data", "calendar_not_calendar.csv"))


@metric("points_without_readable_calendar",
        "points whose calendar photographs cannot be read")
def _m6():
    return json.load(open(d("data", "calendar_extraction_figures.json"))
                     )["points_without_readable"]


@metric("duplicate_question_codes",
        "question codes reused inside a single mWater form")
def _m7():
    n = 0
    for f in json.load(open(d("data", "mwater_form_snapshot.json")))["forms"].values():
        c = collections.Counter(q["code"] for q in f["questions"] if q.get("code"))
        n += sum(v - 1 for v in c.values() if v > 1)
    return n


@metric("sites_without_route_plan",
        "sites with overdue pumps and no catch-up route plan")
def _m8():
    # a site counts as planned only if its plan actually has days with stops
    r = js("ROUTES")
    return len([s for s in ("Maroantsetra", "Fort-Dauphin", "Marolinta")
                if not any(day.get("stops")
                           for day in (r.get(s) or {}).get("days", []))])


@metric("register_dashboard_gap",
        "points the MadAvance dashboard counts that our register does not")
def _m9():
    reg = js("REG")
    s = js("S")["by_site"]
    ours = s.get("Maroantsetra", 0) + s.get("Fort-Dauphin", 0)
    return abs(reg["dashboard_fdmar"] - ours)


@metric("unsourced_figures",
        "rendered figures with no source of any kind")
def _m_unsourced():
    """The residue the figure gate allows through on a dated list. It may only
    shrink; the gate fails on anything not on it."""
    p = d("data", "figure_backlog.json")
    if not os.path.isfile(p):
        return 0
    return len(json.load(open(p, encoding="utf8")).get("values", {}))


@metric("calls_using_service_visit_choice",
        "calls recorded with the routine-service-visit choice")
def _m_service_choice():
    """The form carries the choice; this counts whether anyone uses it.
    A form change nobody adopts has changed nothing."""
    import csv as _csv
    p = os.path.expanduser("~/mwater-exports/appel_signalement_pannes.csv")
    if not os.path.isfile(p):
        return 0
    n = 0
    for r in _csv.DictReader(open(p, encoding="utf8")):
        if "RXSXFTT" in (r.get("data") or ""):
            n += 1
    return n


@metric("enduro_figures_age_days",
        "days since the hand-entered Endur'O figures were last confirmed")
def _m_enduro():
    """Endur'O is off mWater, so nothing here refreshes itself. The figures
    are allowed to be manual; they are not allowed to age unnoticed."""
    import datetime
    m = json.load(open(d("data", "enduro_manual.json"), encoding="utf8"))
    return (datetime.date.today()
            - datetime.date.fromisoformat(m["as_at"])).days


@metric("enduro_figures_unattributed",
        "hand-entered Endur'O figures with no document recorded behind them")
def _m_enduro_attr():
    """A figure whose source is 'not recorded' is not sourced, however long
    it has been carried. This counts them rather than trusting the block."""
    m = json.load(open(d("data", "enduro_manual.json"), encoding="utf8"))
    return sum(1 for f in m["figures"].values()
               if str(f.get("supplied_by", "")).strip().lower()
               in ("", "not recorded", "unknown", "none"))


@metric("extract_lag_days",
        "days the extract on this page runs behind mWater")
def _m10():
    return json.load(open(d("data", "data_freshness.json")))["lag_days"]


@metric("pm_visits_last_full_month",
        "preventive maintenance visits in the last full month")
def _m11():
    pm = js("S")["pm_month"]
    return pm[-2][1] if len(pm) > 1 else 0


@metric("points_over_6_months",
        "points with no maintenance visit for more than six months")
def _m12():
    return js("S")["over6"]


@metric("marolinta_points_no_admin",
        "Marolinta records carrying no district or commune")
def _m13():
    p = d("data", "marolinta_admin.json")
    if os.path.isfile(p):
        return json.load(open(p))["still_missing"]
    return None


@metric("marolinta_points_no_photograph",
        "Marolinta points with no photograph of any kind")
def _m14():
    p = d("data", "marolinta_admin.json")
    if os.path.isfile(p):
        return json.load(open(p)).get("no_photograph")
    return None


@metric("point_742896839_in_register",
        "is water point 742896839 absent from the maintained register (one while it is still absent, none once it is in)")
def _m23():
    return 0 if any(x.get("wp") == "742896839" for x in js("PUMPS")) else 1


@metric("enduro_sites_outside_mwater",
        "Endur'O managed sites not yet represented in mWater")
def _m24():
    # ENDURO is a JS object literal with unquoted keys, so read its numbers
    # rather than trying to parse it as JSON
    src = ctx["idx"]
    i = src.index("const ENDURO")
    seg = src[i:src.index("};", i)]
    tot = int(re.search(r"systems:(\d+)", seg).group(1))
    inm = int(re.search(r"reg:\{[^}]*?systems:(\d+)", seg).group(1))
    return max(0, tot - inm)


@metric("marolinta_rehabs_final",
        "final Réhabilitation records on the Marolinta deployment")
def _mw1():
    w = json.load(open(d("data", "marolinta_works.json")))
    return w["marolinta"]["by_type_final"].get("Réhabilitation", 0)


@metric("marolinta_new_final",
        "final Nouvelle construction records on the Marolinta deployment")
def _mw2():
    w = json.load(open(d("data", "marolinta_works.json")))
    return w["marolinta"]["by_type_final"].get("Nouvelle construction", 0)


@metric("marolinta_blank_status",
        "Marolinta records leaving the functional status blank")
def _mw3():
    return json.load(open(d("data", "marolinta_works.json"))
                     )["marolinta"]["blank_functional_status"]


@metric("moramanga_draft_records",
        "borehole-progress records on the Moramanga deployment never submitted")
def _mw4():
    return json.load(open(d("data", "marolinta_works.json"))
                     )["moramanga"]["draft"]


@metric("transcription_sheets_done",
        "calendars transcribed in the validation round")
def _m15():
    p = d("transcription", "transcripts.json")
    if not os.path.isfile(p):
        return 0
    return len(json.load(open(p)))


@metric("er_percent_of_type3_cap",
        "annual emission reductions as a percentage of the 60,000 tCO2e cap")
def _m17():
    s = js("S")["by_site"]
    # Anosy as registered; Maroantsetra at its applied fNRB (36%, 21 Sep 2026)
    er = (s.get("Fort-Dauphin", 0) * 31.3
          + s.get("Maroantsetra", 0) * er_maro_applied(ctx["idx"]))
    return round(100 * er / 60000.0, 1)


@metric("pumps_reduced_performance",
        "pumps reported with a mechanical or yield fault, still counted working")
def _m18():
    return sum(1 for p in js("PARTIAL") if p.get("kind") == "reduced performance")


@metric("water_quality_failures_unretested",
        "pumps with a failed E. coli result and no retest on file")
def _m19():
    return len(js("S")["wq_fail"])


@metric("marolinta_new_borehole_records",
        "new-borehole records on the Marolinta progress form")
def _m20():
    m = re.search(r"\bconst REG\s*=\s*", ctx["idx"])
    reg = json.loads(ctx["idx"][m.end():ctx["idx"].index("};", m.end()) + 1])
    return reg["marolinta_new"]


@metric("marolinta_points_without_wq",
        "Marolinta records with no E. coli result on file")
def _m21():
    m = re.search(r"\bconst REG\s*=\s*", ctx["idx"])
    reg = json.loads(ctx["idx"][m.end():ctx["idx"].index("};", m.end()) + 1])
    return len(reg["marolinta"])


@metric("piped_form_hand_pump_results",
        "hand-pump water-quality results filed on the piped result form 0ac68d82")
def _m_piped_misfiled():
    return json.load(open(d("data", "piped_wq.json"), encoding="utf8"))[
        "excluded"]["hand_pump_on_piped_form"]["n"]


@metric("piped_systems_in_process",
        "piped systems in process: works or post-rehabilitation tests not yet done")
def _m_piped_in_process():
    return json.load(open(d("data", "piped_wq.json"), encoding="utf8"))[
        "status_counts"]["in_process"]


EXPORTS = os.path.expanduser("~/mwater-exports")


@metric("sdws26_2025_round_unapproved",
        "final responses of the November 2025 usage round with no approval in mWater")
def _m_sdws26_unapproved():
    rs = json.load(open(os.path.join(EXPORTS, "cbn_gender.json"), encoding="utf8"))
    return sum(1 for r in rs if r.get("status") == "final" and not r.get("approvals")
               and "2025-11-11" <= str(r.get("submittedOn") or "")[:10] <= "2025-11-22")


@metric("marolita_spelling_records",
        "works-form records that spell the village Marolita")
def _m_marolita():
    rs = json.load(open(os.path.join(EXPORTS, "combined_rehab.json"), encoding="utf8"))
    return sum(1 for r in rs if re.search(r"\bMarolita\b",
                                          json.dumps(r.get("data"), ensure_ascii=False)))


@metric("test_kiosks_in_register",
        "of the two test records 924119262 and 927104201, how many sit in the MadAvance register as a kiosk")
def _m_test_kiosks():
    reg = {r["code"]: r for r in csv.DictReader(open(os.path.join(EXPORTS, "wp_madavance.csv"),
                                                     encoding="utf8"))}
    return sum(1 for c in ("924119262", "927104201")
               if c in reg and (reg[c].get("type") or "").lower() == "kiosk")


def _onb():
    return json.load(open(d("data", "piped_wq.json"), encoding="utf8"))["onboarding"]


@metric("enduro_sites_unregistered",
        "managed Endur'O sites with no submitted System registration in mWater")
def _m_onb_sites():
    return js("ENDURO")["disp"]["managed"] - _onb()["systems_registered"]


@metric("smart_taps_unbound",
        "installed smart taps not yet bound to their water point by a test dispense")
def _m_onb_taps():
    o = _onb()
    return o["taps_unbound"] if o["taps_installed"] else None


@metric("smart_meters_without_certificate",
        "installed smart-tap meters with no calibration certificate on file")
def _m_onb_cert():
    o = _onb()
    if not o["taps_installed"]:
        return None
    certs = json.load(open(d("data", "meter_calibration_certificates.json"),
                           encoding="utf8"))["certificates"]
    return max(0, o["taps_installed"] - len({c.get("device_id") for c in certs if c.get("device_id")}))


@metric("managed_kiosk_wq_results",
        "water-quality results bound to the managed kiosk's water point")
def _m_onb_wq():
    return _onb()["managed_kiosk_wq_results"]


# --------------------------------------------------------------- remote ----
def remote():
    """REMOTE: counts that can only come from mWater."""
    snap = json.load(open(d("data", "mwater_form_snapshot.json")))["forms"]
    out = {}

    def call(tool, args):
        r = subprocess.run(["node", CLI, tool, json.dumps(args)],
                           capture_output=True, text=True,
                           cwd=os.path.dirname(CLI))
        s = r.stdout
        return json.loads(s[s.index("["):]) if "[" in s else []

    # records submitted but never approved, on the two works forms
    unapproved = 0
    import build_config as _bc
    since = (datetime.date.today() - datetime.timedelta(
        days=_bc.load()["approvals"]["window_days"])).isoformat()
    for key in ("repair-after-breakdown", "preventive-maintenance"):
        fid = snap.get(key, {}).get("id")
        if not fid:
            continue
        rs = call("mwater_responses",
                  {"form_id": fid, "limit": 3000,
                   "filter_json": json.dumps({"submittedOn": {"$gte": since}})})
        unapproved += sum(1 for r in rs if not r.get("approvals"))
    out["unapproved_works_records"] = unapproved

    # household responses on the point-of-use survey
    # SDWS 26 needs the usage question ANSWERED, not merely present: a survey
    # round that leaves A9 blank evidences nothing
    fid = snap.get("point-of-use-survey", {}).get("id")
    A9 = "6147470c7521437f8cdbe1bfa3bea6b0"
    A4 = "5a9278cdb8234d8da870bc3a9709f6e0"
    rs = call("mwater_responses", {"form_id": fid, "limit": 3000}) if fid else []
    answered = lambda q: sum(
        1 for r in rs if (r.get("data") or {}).get(q, {}).get("value") not in
        (None, "", [], {}))
    out["usage_survey_responses"] = len(rs)
    out["usage_question_answers"] = answered(A9)
    out["consent_question_answers"] = answered(A4)

    # the three named Marolinta points, by photograph
    named = ["987623517", "987623256", "987623115"]
    ents = call("mwater_query_entities",
                {"entity_type": "water_point",
                 "filter_json": json.dumps({"code": {"$in": named}}),
                 "limit": 10})
    got = {e["code"]: e for e in ents}
    fid_s = snap.get("stroke-meter", {}).get("id")
    out["stroke_test_responses"] = (
        len(call("mwater_responses", {"form_id": fid_s, "limit": 2000}))
        if fid_s else None)

    out["marolinta_three_points_no_photograph"] = sum(
        1 for c in named if not (got.get(c, {}).get("photos") or []))

    # Endur'O onboarding: the Tana enumerator team, and SDWS 27 records on
    # the managed piped systems (both GET-only scripts through api.mjs)
    def node_json(script, *args):
        r = subprocess.run(["node", d("tools", "mwater", script), *args],
                           capture_output=True, text=True, cwd=REPO)
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
    team = node_json("group_members.mjs", "58b57544a8f94313acd87ad79eae598d")
    out["enduro_tana_enumerators"] = team["members"] if team else None
    pw = json.load(open(d("data", "piped_wq.json"), encoding="utf8"))
    managed = [c for c, v in pw["systems"].items() if v["status"] == "managed"]
    codes = managed + [wp for c in managed for wp in pw["systems"][c]["water_points"]]
    recs = node_json("piped_record_forms.mjs", ",".join(codes)) if codes else None
    out["piped_sdws27_record_types_missing"] = recs["missing"] if recs else None
    return out


REMOTE_SAYS = {
    "unapproved_works_records":
        "submitted works records with no approval, last 180 days",
    "usage_survey_responses":
        "household responses on the point-of-use survey",
    "stroke_test_responses":
        "results recorded on the stroke-meter form",
    "usage_question_answers":
        "point-of-use responses that actually answer the usage question A9",
    "consent_question_answers":
        "point-of-use responses that actually answer the consent question A4",
    "marolinta_three_points_no_photograph":
        "of the three named Marolinta points, how many still have no photograph",
    "enduro_tana_enumerators":
        "members of the mWater team Enduro > EndurO Tana > Enumerators",
    "piped_sdws27_record_types_missing":
        "of maintenance, repair and days-not-operational, the record types with no final "
        "piped record on a managed system in mWater",
}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--show"
    if mode == "--show":
        print(json.dumps(json.load(open(OUT)), indent=1, sort_keys=True)
              if os.path.isfile(OUT) else "no data/action_metrics.json yet")
        return 0
    ctx["idx"] = open(d("index.html"), encoding="utf8").read()
    doc = json.load(open(OUT)) if os.path.isfile(OUT) else {}
    # rebuild the table rather than updating it, so a metric that is renamed
    # or removed cannot linger with a stale value
    old = doc.get("metrics", {})
    doc["metrics"] = {k: v for k, v in old.items() if v.get("source") == "mWater"}
    for name, (says, fn) in sorted(LOCAL.items()):
        try:
            v = fn()
        except Exception as e:                                # noqa: BLE001
            v, says = None, f"{says} (not computable: {e})"
        doc["metrics"][name] = {"value": v, "says": says, "source": "local"}
    if mode == "--write":
        for name, v in remote().items():
            doc["metrics"][name] = {"value": v, "says": REMOTE_SAYS.get(name, name),
                                    "source": "mWater"}
    doc["counted"] = datetime.date.today().isoformat()
    json.dump(doc, open(OUT, "w"), indent=1, sort_keys=True)
    n_ok = sum(1 for m in doc["metrics"].values() if m["value"] is not None)
    print(f"{len(doc['metrics'])} metrics, {n_ok} computed")
    for k, m in sorted(doc["metrics"].items()):
        print(f"  {str(m['value']):>8}  {k:34s} {m['says'][:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
