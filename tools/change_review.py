# -*- coding: utf-8 -*-
"""Changes this week: what moved the headline figures, and what needs approval.

Rule of 7 Oct 2026 (Adriaan Mol; docs/decision_log.md). Kept light: business
as usual goes live and is listed; only three kinds of mWater change of major
impact wait for Adriaan or Jan.

Each build compares the four headline figures - carbon credits (tCO2e), water
points in scope, people served and days operational - with the last edition of
the PREVIOUS week, and traces every point that moved to the mWater records
behind it, using each record's own history (created, and its draft / submit /
edit / approve / reject events, with who and when):

  new record         a record created since the baseline           live
  status record      a visit, repair or call record created since  live
                     (abandoned / removed / non-functional included)
  by Adriaan or Jan  every change since the baseline is theirs     live, ignored
  edited record      an existing record changed since the baseline live, unless (a)
  no mWater change   the point moved and no record did: a          live; needs a
                     repository edit (code, data file, PARAMS,     decision entry,
                     WorldPop run)                                 see below

Provisional until Adriaan or Jan approves (one Asana approval task per week,
"Approve: major changes [week NN]", tools/asana_setup.py --approval):

  (a) an existing record edited so that credits or eligibility go up: the
      point joins the portfolio, its test goes from fail or none to pass, its
      works or test date moves earlier, its 3-month control goes from No or
      blank to Yes, or a rejected record is set to final;
  (b) a record deleted: the row count of a headline extract fell by more than
      the records created since (data/record_ledger.json names them from the
      second week on);
  (c) a week-on-week move of more than build_config changes.major_move_pct in
      tCO2e, points in scope or people served carried by edited or deleted
      records - not by new records, status records, Adriaan or Jan, or a
      repository edit.

Repository edits are never held; they are made on Adriaan's or Jan's
instruction. But one that moves a headline figure must carry a decision in
data/decisions.json with "instructed_by" (Adriaan Mol or Jan de Graaf) and
"headline" before/after figures, logged on or after the baseline - --check
fails the build without one.

    python3 tools/change_review.py --compute   # browser + extracts -> data/change_review.json
    python3 tools/change_review.py --write     # render the page region from it
    python3 tools/change_review.py --check     # region current; repo moves decided; approvals real
    python3 tools/change_review.py --history A.html B.html ... [--since-commit C]
                                               # dry run over archived editions
"""
import csv, datetime, json, os, re, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
csv.field_size_limit(1 << 30)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS = os.path.expanduser("~/mwater-exports")
OUT = os.path.join(REPO, "data", "change_review.json")
LEDGER = os.path.join(REPO, "data", "record_ledger.json")
APPROVALS = os.path.join(REPO, "data", "approvals.json")
DECISIONS = os.path.join(REPO, "data", "decisions.json")
PAGE = os.path.join(REPO, "index.html")
BEGIN = "<!-- BEGIN GENERATED changes-this-week :: tools/change_review.py :: do not edit between these markers -->"
END = "<!-- END GENERATED changes-this-week -->"

# mWater accounts whose changes are ignored, confirmed 7 Oct 2026 by a read of
# the mWater users table: "AdriaanMol" and "Jan_Sanitap" (data/decisions.json
# rule-major-changes-approval-2026-10-07, exempt_mwater_accounts).
EXEMPT = {"a77264134a1d4e7486a04e8c8e07228e": "Adriaan Mol",
          "080b964a728a44758b86b8bd2afe6292": "Jan de Graaf"}
APPROVERS = {"Adriaan Mol", "Jan de Graaf"}
APPROVER_GIDS = {"1132514258683237": "Adriaan Mol", "1209565438602753": "Jan de Graaf"}

# the extracts behind the headline figures and the evidence they rest on
SOURCES = {"combined_rehab.json": "works", "marolinta_borehole.json": "works",
           "wq_results.json": "test", "repair.json": "status",
           "pm.csv": "status", "reparation_apres_panne.csv": "status",
           "appel_signalement_pannes.csv": "status"}
FIGS = ("tco2e", "points", "people", "days_operational")
HELD_FIGS = ("tco2e", "points", "people")          # case (c) applies to these
LABEL = {"tco2e": "carbon credits (tCO2e a year)", "points": "water points in scope",
         "people": "people served", "days_operational": "days operational (applied)"}


def cfg():
    c = json.load(open(os.path.join(REPO, "data", "build_config.json"), encoding="utf8"))
    return c["changes"]


def git(*a):
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout


# ------------------------------------------------------------------ page ----
SNAP_JS = """() => {
  const ev = e => { try { return eval(e) } catch (x) { return null } };
  const er = {"Fort-Dauphin": ev("PARAMS.er_anosy.v"),
              "Maroantsetra": ev("PARAMS.er_maro.v*efbMaro(PARAMS.fnrb_maroantsetra_applied.v)/efbMaro(PARAMS.fnrb_mofuss_maroantsetra.v)")};
  const pts = {};
  (ev("HP") || ev("PUMPS") || []).forEach(p => { pts[p.wp] = {site: p.site, wpop: p.wpop == null ? null : p.wpop,
      wq: p.wq || null, wq_date: p.wq_date || null, comm: p.comm || null,
      status: p.status || null, status_src: p.status_src || null, status_date: p.status_date || null}; });
  const gaps = {};
  (ev("ELIG.gaps") || []).forEach(g => { gaps[g.wp] = g.status || g.issue || 'gap'; });
  return {figures: {
      tco2e: ev("Math.round(S.by_site['Fort-Dauphin']*PARAMS.er_anosy.v+S.by_site['Maroantsetra']*PARAMS.er_maro.v*efbMaro(PARAMS.fnrb_maroantsetra_applied.v)/efbMaro(PARAMS.fnrb_mofuss_maroantsetra.v))"),
      points: ev("S.n"), people: ev("agg(HP).wpop"), days_operational: ev("PARAMS.do_cap.v")},
    er, points: pts, gaps: ev("ELIG.gaps") ? gaps : null};
}"""


def snapshot(paths):
    """Headline figures and per-point inputs of each page, evaluated exactly as
    the page computes them (headless Chromium, default scope)."""
    from render_check import chromium_path
    from playwright.sync_api import sync_playwright
    out = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=chromium_path())
        for p in paths:
            pg = b.new_page()
            pg.goto("file://" + os.path.abspath(p), wait_until="load", timeout=180000)
            out.append(pg.evaluate(SNAP_JS))
            pg.close()
        b.close()
    return out


def page_at(commit):
    """A commit's index.html, written beside the live one so relative links resolve."""
    fd, path = tempfile.mkstemp(prefix=".change-baseline-", suffix=".html", dir=REPO)
    os.write(fd, git("show", f"{commit}:index.html").encode("utf8"))
    os.close(fd)
    return path


# --------------------------------------------------------------- records ----
def _j(v):
    if isinstance(v, str):
        try:
            return json.loads(v) if v[:1] in "[{" else v
        except ValueError:
            return v
    return v


def records():
    """Every record of the headline extracts, with its history."""
    out = []
    for f, kind in SOURCES.items():
        p = os.path.join(EXPORTS, f)
        if not os.path.isfile(p):
            continue
        rows = json.load(open(p)) if f.endswith(".json") else list(csv.DictReader(open(p, encoding="utf8")))
        for r in rows:
            cr, md = _j(r.get("created")) or {}, _j(r.get("modified")) or {}
            out.append({"id": r["_id"], "file": f, "kind": kind, "status": r.get("status"),
                        "created": cr.get("on"), "created_by": cr.get("by"),
                        "wps": [e.get("value") for e in (_j(r.get("entities")) or []) if e.get("property") == "code"],
                        "events": [(e.get("type"), e.get("on"), e.get("by")) for e in (_j(r.get("events")) or [])],
                        "modified": md.get("on"), "modified_by": md.get("by")})
    return out


def rowcounts():
    return {f: sum(1 for _ in _iter(f)) for f in SOURCES if os.path.isfile(os.path.join(EXPORTS, f))}


def _iter(f):
    p = os.path.join(EXPORTS, f)
    return json.load(open(p)) if f.endswith(".json") else csv.DictReader(open(p, encoding="utf8"))


def ledger(recs):
    led = {}
    for r in recs:
        led.setdefault(r["file"], {})[r["id"]] = r["wps"][0] if r["wps"] else ""
    return {"note": "Record ids of the headline extracts at this build (tools/change_review.py), so the next "
                    "week can name a deleted record. Generated; do not edit.",
            "files": {f: dict(sorted(v.items())) for f, v in sorted(led.items())}}


# --------------------------------------------------------------- compare ----
def _up_wq(a, b):
    rank = {"Pass": 2, "Fail": 1}
    return rank.get(b or "", 0) > rank.get(a or "", 0)


def classify(prev, cur, recs, t0, t1, prev_counts=None, cur_counts=None, prev_ledger=None, cur_ledger=None):
    """Compare two snapshots over the record window (t0, t1]."""
    c = cfg()
    by_wp = {}
    for r in recs:
        for w in r["wps"]:
            by_wp.setdefault(w, []).append(r)

    def activity(wp):
        new, status_new, edited, events = [], [], [], []
        for r in by_wp.get(wp, []):
            if r["created"] and t0 < r["created"] <= t1:
                (status_new if r["kind"] == "status" else new).append(r)
                events += [(r, e) for e in r["events"] if e[1] and t0 < e[1] <= t1]
                continue
            ev = [e for e in r["events"] if e[1] and t0 < e[1] <= t1 and e[0] in ("edit", "submit", "approve", "reject")]
            if ev:
                edited.append(r)
                events += [(r, e) for e in ev]
        return new, status_new, edited, events

    def reject_to_final(r):
        before = [e for e in r["events"] if e[1] and e[1] <= t0]
        return bool(before) and before[-1][0] == "reject" and r["status"] == "final"

    pp, cp = prev["points"], cur["points"]
    er_prev, er_cur = prev.get("er") or {}, cur.get("er") or {}
    gp, gc = prev.get("gaps"), cur.get("gaps")
    rows = []
    for wp in sorted(set(pp) | set(cp)):
        a, b = pp.get(wp), cp.get(wp)
        moves, up = [], []
        if a is None:
            moves.append("joined the portfolio"); up.append("joined the portfolio")
        elif b is None:
            moves.append("left the portfolio")
        else:
            if (a.get("wpop") or 0) != (b.get("wpop") or 0):
                moves.append("people served")
            if a.get("wq") != b.get("wq") or a.get("wq_date") != b.get("wq_date"):
                moves.append(f"water test {a.get('wq') or 'none'} ({a.get('wq_date') or '-'}) → {b.get('wq') or 'none'} ({b.get('wq_date') or '-'})")
                if _up_wq(a.get("wq"), b.get("wq")) or (b.get("wq") == "Pass" and a.get("wq_date") and b.get("wq_date") and b["wq_date"] < a["wq_date"]):
                    up.append("water test improved or dated earlier")
            if a.get("comm") != b.get("comm"):
                moves.append(f"works date {a.get('comm')} → {b.get('comm')}")
                if a.get("comm") and b.get("comm") and b["comm"] < a["comm"]:
                    up.append("works date moved earlier")
            if a.get("status") != b.get("status"):
                moves.append(f"status {a.get('status')} → {b.get('status')}")
        if gp is not None and gc is not None and wp in gp and wp not in gc and b is not None:
            moves.append(f"eligibility gap cleared ({gp[wp]})"); up.append("3-month control or eligibility gap cleared")
        if not moves:
            continue
        new, status_new, edited, events = activity(wp)
        others = [e for _r, e in events if e[2] not in EXEMPT]
        rtf = [r for r in edited if reject_to_final(r)]
        if moves == ["people served"]:
            cause = "no mWater change"           # people served comes from the WorldPop run of record
        elif events and not others:
            cause = "by Adriaan or Jan"
        elif new:
            cause = "new record"
        elif status_new and all(m.startswith("status") for m in moves):
            cause = "status record"
        elif edited:
            cause = "edited record"
        elif status_new:
            cause = "status record"
        else:
            cause = "no mWater change"
        if rtf and cause == "edited record":
            up.append("rejected record set to final")
        site = (b or a).get("site")
        d = {"tco2e": 0.0, "points": 0, "people": 0}
        if a is None or b is None:
            sign = 1 if a is None else -1
            d["points"] = sign
            d["tco2e"] = sign * (er_cur.get(site) or er_prev.get(site) or 0)
            d["people"] = sign * ((b or a).get("wpop") or 0)
        else:
            d["people"] = (b.get("wpop") or 0) - (a.get("wpop") or 0)
        if cause != "no mWater change" and d["people"] and a is not None and b is not None:
            # a record can move a point's status or test, never its WorldPop allocation
            rows.append({"wp": wp, "site": site, "moves": ["people served"],
                         "wpop": [a.get("wpop"), b.get("wpop")],
                         "cause": "no mWater change", "case_a": False, "up": [], "records": [], "by": [],
                         "delta": {"tco2e": 0.0, "points": 0, "people": d["people"]}})
            moves = [m for m in moves if m != "people served"]
            d = {"tco2e": 0.0, "points": 0, "people": 0}
        rows.append({"wp": wp, "site": site, "moves": moves, "cause": cause,
                     "wpop": [a.get("wpop") if a else None, b.get("wpop") if b else None],
                     "case_a": bool(up) and cause == "edited record", "up": up, "delta": d,
                     "records": sorted({r["id"] for r in new + status_new + edited}),
                     "by": sorted({EXEMPT.get(e[2], e[2] or "") for _r, e in events})})

    # (b) deleted records
    deleted = []
    if prev_counts is not None and cur_counts is not None:
        for f in SOURCES:
            if f not in prev_counts or f not in cur_counts:
                continue
            made = sum(1 for r in recs if r["file"] == f and r["created"] and t0 < r["created"] <= t1)
            gone = prev_counts[f] + made - cur_counts[f]
            if gone > 0:
                ids = []
                if prev_ledger and cur_ledger:
                    ids = sorted(set(prev_ledger["files"].get(f, {})) - set(cur_ledger["files"].get(f, {})))
                deleted.append({"file": f, "count": gone, "ids": ids,
                                "wps": sorted({prev_ledger["files"][f][i] for i in ids if prev_ledger["files"][f].get(i)}) if ids else []})

    # figure moves, and the share carried by edited or deleted records
    pf, cf = prev["figures"], cur["figures"]
    moves = {k: {"before": pf.get(k), "after": cf.get(k)} for k in FIGS}
    by_cause = {}
    for r in rows:
        for k, v in r["delta"].items():
            by_cause.setdefault(r["cause"], {}).setdefault(k, 0)
            by_cause[r["cause"]][k] += v
    params_changed = (er_prev != er_cur) or pf.get("days_operational") != cf.get("days_operational")
    case_c = []
    for k in HELD_FIGS:
        base = pf.get(k) or 0
        carried = (by_cause.get("edited record", {}).get(k, 0))
        if base and abs(carried) / base * 100 > c["major_move_pct"]:
            case_c.append({"figure": k, "carried": round(carried, 1), "pct": round(100 * carried / base, 2)})
    repo = {k: round(by_cause.get("no mWater change", {}).get(k, 0), 1) for k in ("tco2e", "points", "people")}
    repo_moved = any(repo.values()) or params_changed
    counts = {}
    for r in rows:
        counts[r["cause"]] = counts.get(r["cause"], 0) + 1
    return {"window": [t0, t1], "figures": moves, "points": rows, "deleted": deleted, "counts": counts,
            "by_cause": {k: {kk: round(vv, 1) for kk, vv in v.items()} for k, v in by_cause.items()},
            "case_a": [r for r in rows if r["case_a"]], "case_b": deleted, "case_c": case_c,
            "repo_moved": repo_moved, "repo": repo, "params_changed": params_changed}


# --------------------------------------------------------------- compute ----
def iso_week(d):
    return d.isocalendar()[1]


def baseline_commit(today):
    monday = today - datetime.timedelta(days=today.weekday())
    sha = git("log", "-1", "--format=%H", f"--before={monday.isoformat()}T00:00:00+04:00", "--", "index.html").strip()
    when = git("show", "-s", "--format=%cI", sha).strip()
    return sha, when


def _utc(iso):
    return datetime.datetime.fromisoformat(iso).astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def compute():
    today = datetime.date.today()
    sha, when = baseline_commit(today)
    base_page = page_at(sha)
    try:
        prev, cur = snapshot([base_page, PAGE])
    finally:
        os.remove(base_page)
    recs = records()
    t0 = _utc(when)
    try:
        prev_counts = json.loads(git("show", f"{sha}:data/extract_rowcounts.json"))["counts"]
    except ValueError:
        prev_counts = None
    cur_counts = rowcounts()
    try:
        prev_ledger = json.loads(git("show", f"{sha}:data/record_ledger.json"))
    except ValueError:
        prev_ledger = None
    cur_ledger = ledger(recs)
    res = classify(prev, cur, recs, t0, "9999", prev_counts, cur_counts, prev_ledger, cur_ledger)
    week = iso_week(today)
    res.update(week=week, year=today.isocalendar()[0], computed=today.isoformat(),
               baseline={"commit": sha[:7], "published": when[:16].replace("T", " ")},
               deletions_named=prev_ledger is not None)
    # approvals: this week's flags, and every earlier week still waiting
    appr = json.load(open(APPROVALS, encoding="utf8")) if os.path.isfile(APPROVALS) else {"weeks": {}}
    key = f"{res['year']}-W{week:02d}"
    flagged = bool(res["case_a"] or res["case_b"] or res["case_c"])
    if flagged:
        w = appr["weeks"].setdefault(key, {"status": "pending"})
        w["flags"] = {"a": [{"wp": r["wp"], "up": r["up"], "records": r["records"]} for r in res["case_a"]],
                      "b": res["case_b"], "c": res["case_c"]}
        w["figures"] = res["figures"]
    elif key in appr["weeks"] and appr["weeks"][key].get("status") == "pending" and not appr["weeks"][key].get("task"):
        del appr["weeks"][key]                       # flagged earlier this week, no longer
    _read_approval_status(appr)
    res["provisional"] = sorted(k for k, v in appr["weeks"].items() if v.get("status") != "approved")
    res["provisional_items"] = sum(len((appr["weeks"][k].get("flags") or {}).get(x) or []) for k in res["provisional"] for x in "abc")
    json.dump(appr, open(APPROVALS, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    json.dump(cur_ledger, open(LEDGER, "w", encoding="utf8"), indent=0, sort_keys=True)
    json.dump(res, open(OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    _log_approvals(appr)
    print(f"change review, week {week} against {sha[:7]} ({when[:10]}): "
          + ", ".join(f"{k} {v['before']} -> {v['after']}" for k, v in res["figures"].items()))
    print(f"  points moved {len(res['points'])}; case a {len(res['case_a'])}, b {len(res['case_b'])}, "
          f"c {len(res['case_c'])}; repository moves {res['repo']}{' + PARAMS' if res['params_changed'] else ''}")
    return 0


def _read_approval_status(appr):
    """The approval task's state, read from Asana (read-only)."""
    pend = [w for w in appr["weeks"].values() if w.get("task") and w.get("status") != "approved"]
    if not pend:
        return
    try:
        import asana_api as A
    except Exception:
        return
    for w in pend:
        t = A.get(f"/tasks/{w['task']}", {"opt_fields": "approval_status,completed,completed_at,completed_by.gid,completed_by.name"})
        st = t.get("approval_status")
        stories = A.get(f"/tasks/{w['task']}/stories", {"opt_fields": "resource_subtype,text,created_at,created_by.gid,created_by.name"})
        verdict = [s for s in stories if s.get("resource_subtype") in ("approved", "rejected", "changes_requested")]
        last = verdict[-1] if verdict else None
        who = APPROVER_GIDS.get(((last or {}).get("created_by") or {}).get("gid"))
        comments = [s["text"] for s in stories if s.get("resource_subtype") == "comment_added"]
        if st == "approved" and who in APPROVERS:
            w.update(status="approved", approved_by=who, approved_at=last["created_at"][:10])
        elif st == "approved":
            w.update(status="pending", note="approved by someone other than Adriaan or Jan: not accepted")
        elif st in ("rejected", "changes_requested"):
            w.update(status=st, by=who or ((last or {}).get("created_by") or {}).get("name"),
                     at=(last or {}).get("created_at", "")[:10], comment=comments[-1] if comments else "")


def _log_approvals(appr):
    dec = json.load(open(DECISIONS, encoding="utf8"))
    changed = False
    for key, w in appr["weeks"].items():
        did = f"approval-major-changes-{key}"
        if w.get("status") == "approved" and did not in dec["decisions"]:
            dec["decisions"][did] = {
                "answer": f"Major changes of {key} approved: " + json.dumps(w.get("flags"), ensure_ascii=False),
                "decided_by": w["approved_by"], "decided_on": w["approved_at"],
                "source": f"Asana approval task {w['task']}", "headline": w.get("figures"),
                "logged_on": datetime.date.today().isoformat(), "logged_by": "tools/change_review.py, from the Asana approval"}
            changed = True
    if changed:
        raw = open(DECISIONS, encoding="utf8").read()
        json.dump(dec, open(DECISIONS, "w", encoding="utf8"), indent=1, ensure_ascii=False)
        if raw.endswith("\n"):
            open(DECISIONS, "a").write("\n")


# ---------------------------------------------------------------- render ----
CAUSE_TXT = {"new record": "new mWater records", "status record": "visit, repair or call records (status changes)",
             "by Adriaan or Jan": "changes made by Adriaan or Jan", "edited record": "edits to existing records",
             "no mWater change": "repository edits: code, data files, PARAMS, the WorldPop run"}


def render(res):
    from table_notes import render as tablenote
    F = lambda e, v: f'<span data-fig="{e}">{v}</span>'

    def fmt(v):
        return f"{v:,}" if isinstance(v, int) else ("" if v is None else str(v))
    figrows = "".join(
        f'<tr><td>{LABEL[k]}</td><td class="num">{F(f"CHG.figures.{k}.before", fmt(res["figures"][k]["before"]))}</td>'
        f'<td class="num">{F(f"CHG.figures.{k}.after", fmt(res["figures"][k]["after"]))}</td></tr>' for k in FIGS)
    causerows = "".join(f'<tr><td>{CAUSE_TXT[c]}</td><td class="num">{F("CHG.counts[&apos;" + c + "&apos;]", n)}</td></tr>'
                        for c, n in sorted((res.get("counts") or {}).items()))

    def moved(p):
        return "; ".join(f'people served {fmt(p["wpop"][0])} &rarr; {fmt(p["wpop"][1])}' if m == "people served"
                         else m.replace("→", "&rarr;") for m in p["moves"])
    ptrows = "".join(
        f'<tr><td class="mono">{p["wp"]}</td><td>{p["site"] or ""}</td><td>{moved(p)}</td><td>{p["cause"]}'
        + (' <span class="pill warn">provisional (a)</span>' if p["case_a"] else "") + "</td></tr>"
        for p in res["points"][:200])
    appr = (json.load(open(APPROVALS, encoding="utf8")) if os.path.isfile(APPROVALS) else {"weeks": {}})["weeks"]
    flagrows = []
    for key in res.get("provisional") or []:
        w = appr[key]
        st = {"pending": "awaiting approval by Adriaan or Jan",
              "rejected": f"rejected by {w.get('by')}: {w.get('comment', '')}",
              "changes_requested": f"changes requested by {w.get('by')}: {w.get('comment', '')}"}.get(w.get("status"), w.get("status"))
        link = f' (<a href="https://app.asana.com/0/0/{w["task"]}">Asana approval task</a>)' if w.get("task") else ""
        fl = w.get("flags") or {}
        what = [f'(a) <span class="mono">{r["wp"]}</span>: {", ".join(r["up"])}, on an edited record' for r in fl.get("a", [])]
        what += [f'(b) {d["count"]} record(s) deleted from <span class="mono">{d["file"]}</span>' for d in fl.get("b", [])]
        what += [f'(c) {LABEL[c["figure"]]}: {c["carried"]} carried by edited records ({c["pct"]}%)' for c in fl.get("c", [])]
        flagrows.append(f'<tr><td class="mono">{key}</td><td><span class="pill warn">provisional</span> {st}{link}</td>'
                        f'<td>{"<br>".join(what)}</td></tr>')
    # (Adriaan Mol, 7 Oct 2026) one closed line under the headline tiles; a single
    # visible banner only when something waits for approval. Gate logic unchanged.
    inside = ('<p class="note muted">Against the edition of ' + res["baseline"]["published"] + '.</p>'
              '<div class="tablewrap"><table class="ind" data-table="chgfig"><thead><tr><th>Headline figure</th>'
              f'<th class="num">Last week</th><th class="num">This week</th></tr></thead><tbody>{figrows}</tbody></table></div>'
              f'{tablenote("chgfig")}'
              '<details class="expl"><summary>What moved, and why</summary>'
              '<div class="tablewrap"><table class="ind" data-table="chgcause"><thead><tr><th>Cause</th>'
              f'<th class="num">Water points</th></tr></thead><tbody>{causerows}</tbody></table></div>{tablenote("chgcause")}'
              '<div class="tablewrap"><table class="ind" data-table="chgpts"><thead><tr><th>Water point</th><th>Site</th>'
              f'<th>What changed</th><th>Cause</th></tr></thead><tbody>{ptrows}</tbody></table></div>{tablenote("chgpts")}'
              '<p class="note muted">Business as usual goes live. Provisional until Adriaan or Jan approves: (a) an existing record '
              'edited so that credits or eligibility go up; (b) a record deleted; (c) a large week-on-week move in carbon credits, '
              'points in scope or people served carried by edited records. Abandoned, removed or non-functional pumps with a '
              'supporting record pass without approval. A repository edit that moves a headline figure carries a decision in '
              'data/decisions.json naming who instructed it (rule of 7 Oct 2026).</p>'
              '</details>')
    if flagrows:
        n = res.get("provisional_items") or len(flagrows)
        task = next((appr[k].get("task") for k in res.get("provisional") or [] if appr[k].get("task")), None)
        link = f' <a href="https://app.asana.com/0/0/{task}">see the Asana task</a>' if task else ""
        banner = (f'<p class="note" id="changes-banner"><span class="pill warn">provisional</span> '
                  f'<b><span data-fig="CHG.provisional_items">{n}</span> change(s) wait for approval</b>,{link}.</p>')
        inside = ('<div class="tablewrap"><table class="ind" data-table="chgflags"><thead><tr><th>Week</th><th>Status</th>'
                  f'<th>What waits</th></tr></thead><tbody>{"".join(flagrows)}</tbody></table></div>{tablenote("chgflags")}' + inside)
        summary = "Changes since last week: details of what waits"
    else:
        banner = ""
        summary = "Changes since last week: none waiting for approval"
    return (f'<div id="changes" data-scopes="all mad madx mar" style="margin-top:8px">{banner}'
            f'<details class="expl"><summary>{summary}</summary>{inside}</details></div>')


def region(idx, body):
    a = idx.index(BEGIN) + len(BEGIN)
    z = idx.index(END)
    return idx[:a], idx[a:z], idx[z:], "\n" + body + "\n"


# ----------------------------------------------------------------- check ----
def check():
    from prerender_figures import same
    fails = []
    res = json.load(open(OUT, encoding="utf8"))
    if res.get("computed") != datetime.date.today().isoformat():
        fails.append(f"data/change_review.json was computed {res.get('computed')}, not today: run --compute (needs the headless browser)")
    idx = open(PAGE, encoding="utf8").read()
    if BEGIN not in idx:
        fails.append("index.html has no changes-this-week markers")
    else:
        _h, cur, _t, want = region(idx, render(res))
        if not same(cur, want):
            fails.append("changes-this-week region differs from its generator (run --write)")
    # repository moves need a decision naming who instructed them
    if res.get("repo_moved"):
        since = res["window"][0][:10]
        dec = json.load(open(DECISIONS, encoding="utf8"))["decisions"]
        ok = [k for k, v in dec.items() if v.get("headline") and v.get("instructed_by") in APPROVERS
              and (v.get("decided_on") or "") >= since]
        if not ok:
            fails.append(f"a repository edit moved a headline figure ({res['repo']}"
                         f"{', PARAMS' if res.get('params_changed') else ''}) and no decision since {since} in "
                         "data/decisions.json carries 'instructed_by' (Adriaan Mol or Jan de Graaf) and 'headline' before/after")
    # nothing approved without an approval from Adriaan or Jan, and nothing flagged shown as final
    appr = json.load(open(APPROVALS, encoding="utf8")) if os.path.isfile(APPROVALS) else {"weeks": {}}
    dec = json.load(open(DECISIONS, encoding="utf8"))["decisions"]
    for key, w in appr["weeks"].items():
        if w.get("status") == "approved":
            d = dec.get(f"approval-major-changes-{key}")
            if w.get("approved_by") not in APPROVERS or not d or d.get("decided_by") not in APPROVERS:
                fails.append(f"{key}: marked approved without a recorded approval by Adriaan or Jan")
        elif key not in (res.get("provisional") or []):
            fails.append(f"{key}: not approved, but not shown as provisional")
        if w.get("status") != "approved" and (res.get("case_a") or res.get("case_b") or res.get("case_c")) \
                and not w.get("task"):
            fails.append(f"{key}: flagged changes with no Asana approval task")
    for f in fails:
        print("FAIL", f)
    print("change review: " + ("OK" if not fails else f"{len(fails)} failure(s)"))
    return 1 if fails else 0


# --------------------------------------------------------------- history ----
def history(pages, recs):
    """Dry run over archived editions: each consecutive pair is one week."""
    dates = [re.search(r"(\d{4}-\d\d-\d\d)", os.path.basename(p)).group(1) if re.search(r"\d{4}-\d\d-\d\d", os.path.basename(p))
             else datetime.date.today().isoformat() for p in pages]
    snaps = snapshot(pages)
    counts = {}
    for d in dates:
        sha = git("log", "-1", "--format=%H", f"--before={d}T23:59:59+04:00", "--", "data/extract_rowcounts.json").strip()
        counts[d] = None                     # row counts are on record from 22 Sep 2026 only
        if sha:
            try:
                counts[d] = json.loads(git("show", f"{sha}:data/extract_rowcounts.json"))["counts"]
            except ValueError:
                pass
    out = []
    for i in range(1, len(pages)):
        t0, t1 = dates[i - 1] + "T20:00:00", dates[i] + "T20:00:00"
        res = classify(snaps[i - 1], snaps[i], recs, t0, t1, counts[dates[i - 1]], counts[dates[i]])
        out.append({"from": os.path.basename(pages[i - 1]), "to": os.path.basename(pages[i]), **res})
    return out


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if mode == "--compute":
        return compute()
    if mode == "--write":
        res = json.load(open(OUT, encoding="utf8"))
        idx = open(PAGE, encoding="utf8").read()
        head, cur, tail, want = region(idx, render(res))
        open(PAGE, "w", encoding="utf8").write(head + want + tail)
        print("index.html: changes-this-week region written")
        return 0
    if mode == "--check":
        return check()
    if mode == "--history":
        pages = [p for p in sys.argv[2:] if not p.startswith("--")]
        res = history(pages, records())
        json.dump(res, sys.stdout, indent=1, ensure_ascii=False, default=str)
        return 0
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main())
