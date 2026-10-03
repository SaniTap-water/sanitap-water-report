# -*- coding: utf-8 -*-
"""Pre-project eligibility: non-functional or non-potable before the project
(methodology 2.2.1(d), SDWS 12) - 3 Oct 2026.

Writes data/eligibility.json (ELIG on the page), read by
tools/render_eligibility.py and by the eligibility gate in
tools/check_consistency.py.

Hand pumps. For every pump in the managed fleet (PUMPS), its first-
rehabilitation record: the control "out of order for more than three months
before the works" (question ea3e342a), whether the photographs proving it are
present (a4d23938), the works date, and the response, so a verifier can open
it. Where a pump has several records the one that best evidences eligibility
is shown (Yes with photographs, then Yes, then the latest). The eight records
already flagged under 2.2.1(d) (data/register_corrections.json,
"eligibility_flags": three answered No, five left blank) are listed as gaps,
in the fleet or not.

Piped systems. For every system in data/piped_systems_status.json, its
pre-project results on the piped result form: those dated before the
tap-level protocol went live (build_config piped.pairing.protocol_live), or
before the system's works completion date where one is recorded, whichever is
earlier. A system is "eligible: non-potable shown" when at least one of them
fails the health-based rule (E. coli above the build's pass maximum, 0 per
100 ml). Pre-project results are evidence of need for a system whose works are
under way; they say nothing about a managed system's performance.

Exceptions. A point or system may stand in the managed or carbon figures
without eligibility evidence only if data/eligibility_exceptions.json lists it
(or the 2.2.1(d) flags do); the gate fails on anything else.

    python3 tools/rebuild_eligibility.py --write
"""
import datetime, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import populations as P  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS = os.path.expanduser("~/mwater-exports")
OUT = os.path.join(REPO, "data", "eligibility.json")
EXC = os.path.join(REPO, "data", "eligibility_exceptions.json")
CFG = json.load(open(os.path.join(REPO, "data", "build_config.json"), encoding="utf8"))
PASS_MAX = CFG["water_quality"]["ecoli_pass_max_cfu_per_100ml"]
PROTOCOL_LIVE = CFG["piped"]["pairing"]["protocol_live"]
Q_WORKS_DATE = "fd61cf9286954462a0fb1ab5de12e643"   # combined form, "Date de début des travaux"
PIPED_RESULT_FORM = "0ac68d8274d24f54af0c28b29119b77d"
Q_SYSTEM, Q_ECOLI, SAMPLED = "a3390d2e", "892f1d81", "630ccd46"
LABEL = {"yes_photo": "Yes, with photographs", "yes_no_photo": "Yes, no photograph",
         "no": "No", "blank": "left blank", "no_record": "no first-rehabilitation record",
         "borehole_form": "works on the borehole-progress form, which has no such control"}
EVIDENCED = ("yes_photo", "yes_no_photo")


def _q(r, prefix):
    for k, v in (r.get("data") or {}).items():
        if k.startswith(prefix):
            return (v or {}).get("value") if isinstance(v, dict) else v
    return None


def _pumps():
    idx = open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    return json.loads(re.search(r"const PUMPS\s*=\s*(\[.*?\]);", idx, re.S).group(1))


def _rank(r):
    yes = P._answer(r, P.Q_OUT_3M) == P.C_OUT_3M_YES
    ph = bool(P._answer(r, P.Q_OUT_PHOTOS))
    return (yes and ph, yes, str(r.get("submittedOn") or ""))


def _record(form, r):
    ans = P._answer(r, P.Q_OUT_3M)
    ph = P._answer(r, P.Q_OUT_PHOTOS) or []
    status = ("yes_photo" if ans == P.C_OUT_3M_YES and ph else
              "yes_no_photo" if ans == P.C_OUT_3M_YES else
              "blank" if ans in (None, "", []) else "no")
    d = str(P._answer(r, Q_WORKS_DATE) or "")[:10]
    return dict(status=status, photos=len(ph) if isinstance(ph, list) else int(bool(ph)),
                works_date=d if d[:2] == "20" else None,
                submitted=str(r.get("submittedOn") or "")[:10] or None,
                response=r["_id"], form=form, record_status=r.get("status"))


def hand_pumps():
    recs = {}
    for r in P._combined():
        if P._answer(r, P.Q_TYPE) == P.C_FIRST_REHAB and r.get("status") not in ("draft", "rejected"):
            recs.setdefault(P._point_of(r), []).append((P.F_RETIRED_COMBINED, r))
    for r in P._first_rehab_current():
        if r.get("status") not in ("draft", "rejected"):
            recs.setdefault(P._point_of(r), []).append((P.F_FIRST_REHAB, r))
    borehole = {P._point_of(r) for r in P._borehole()}
    rows = []
    for p in sorted(_pumps(), key=lambda p: (p["site"], p["wp"])):
        rs = recs.get(p["wp"]) or []
        if rs:
            form, r = max(rs, key=lambda x: _rank(x[1]))
            rec = _record(form, r)
            rec["records"] = len(rs)
        else:
            rec = dict(status="borehole_form" if p["wp"] in borehole else "no_record",
                       photos=0, works_date=None, submitted=None, response=None, form=None,
                       record_status=None, records=0)
        rows.append(dict(wp=p["wp"], site=p["site"], carbon=p["site"] != "Marolinta", **rec))
    return rows, recs


def gaps(recs, fleet):
    rc = json.load(open(os.path.join(REPO, "data", "register_corrections.json"), encoding="utf8"))
    out = []
    for f in rc.get("eligibility_flags", []):
        rs = recs.get(f["wp"]) or []
        rec = _record(*max(rs, key=lambda x: _rank(x[1]))) if rs else {}
        out.append(dict(wp=f["wp"], issue=f["issue"], action=f["action"], in_fleet=f["wp"] in fleet,
                        status=rec.get("status"), photos=rec.get("photos", 0),
                        works_date=rec.get("works_date"), response=rec.get("response"),
                        form=rec.get("form")))
    return out


def piped():
    st = json.load(open(os.path.join(REPO, "data", "piped_systems_status.json"), encoding="utf8"))["systems"]
    results = json.load(open(os.path.join(EXPORTS, "wq_results_piped.json"), encoding="utf8"))
    out = []
    for code, s in sorted(st.items(), key=lambda kv: ({"managed": 0, "in_process": 1}.get(kv[1]["status"], 2), kv[0])):
        cutoff = PROTOCOL_LIVE
        if s.get("works_complete") and s["works_complete"] < cutoff[:10]:
            cutoff = s["works_complete"] + "T00:00:00Z"
        mine = []
        for r in results:
            if r.get("status") != "final" or (_q(r, Q_SYSTEM) or {}).get("code") != code:
                continue
            when = str(_q(r, SAMPLED) or r.get("submittedOn") or "")
            if not when or when >= cutoff:
                continue
            e = (_q(r, Q_ECOLI) or {}).get("quantity")
            mine.append(dict(response=r["_id"], day=when[:10], ecoli=e,
                             fails=e is not None and e > PASS_MAX))
        mine.sort(key=lambda x: (x["day"], x["response"]))
        n, fails = len(mine), sum(x["fails"] for x in mine)
        out.append(dict(code=code, name=s.get("name"), status=s["status"],
                        works_complete=s.get("works_complete"), cutoff=cutoff,
                        results=n, first=mine[0]["day"] if mine else None,
                        last=mine[-1]["day"] if mine else None, ecoli_present=fails,
                        ecoli_present_pct=round(100 * fails / n) if n else None,
                        eligibility=("eligible: non-potable shown" if fails else
                                     "pre-project results, none failing" if n else "no pre-project test"),
                        eligible=fails > 0, responses=[x["response"] for x in mine]))
    return out


def main():
    if "--write" not in sys.argv:
        sys.exit("usage: rebuild_eligibility.py --write")
    rows, recs = hand_pumps()
    fleet = {r["wp"] for r in rows}
    exc = json.load(open(EXC, encoding="utf8"))
    by_site = {}
    for r in rows:
        b = by_site.setdefault(r["site"], {k: 0 for k in LABEL})
        b[r["status"]] += 1
        b["total"] = b.get("total", 0) + 1
        b["evidenced"] = b.get("evidenced", 0) + (r["status"] in EVIDENCED)
    g = gaps(recs, fleet)
    sysrows = piped()
    doc = dict(
        note="Written by tools/rebuild_eligibility.py. Pre-project eligibility under methodology 2.2.1(d) "
             "(hand pumps: out of order for more than three months before the works) and SDWS 12 (piped "
             "systems: non-potable before the works).",
        labels=LABEL, evidenced=list(EVIDENCED), pass_max=PASS_MAX, protocol_live=PROTOCOL_LIVE,
        protocol_live_text=datetime.datetime.fromisoformat(PROTOCOL_LIVE.replace("Z", "+00:00"))
        .strftime("%-d %b %Y %H:%M UTC"),
        forms=dict(combined=P.F_RETIRED_COMBINED, current=P.F_FIRST_REHAB, piped_result=PIPED_RESULT_FORM),
        hp=dict(rows=rows, by_site=by_site, total=len(rows),
                evidenced=sum(r["status"] in EVIDENCED for r in rows)),
        gaps=g, gaps_in_fleet=sum(x["in_fleet"] for x in g),
        gaps_no=sum(x["issue"].endswith("answered No") for x in g),
        gaps_blank=sum(x["issue"].endswith("left blank") for x in g),
        piped=sysrows,
        piped_rule=dict(pass_max=PASS_MAX, protocol_live=PROTOCOL_LIVE,
                        protocol_live_text=datetime.datetime.fromisoformat(PROTOCOL_LIVE.replace("Z", "+00:00"))
                        .strftime("%-d %b %Y %H:%M UTC")),
        piped_counts=dict(systems=len(sysrows), eligible=sum(s["eligible"] for s in sysrows),
                          no_test=sum(s["results"] == 0 for s in sysrows),
                          managed=sum(s["status"] == "managed" for s in sysrows)),
        exceptions=exc)
    json.dump(doc, open(OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    open(OUT, "a").write("\n")
    print(f"eligibility: {doc['hp']['evidenced']} of {doc['hp']['total']} managed pumps evidenced; "
          f"by site {json.dumps(by_site)}")
    print(f"  2.2.1(d) gaps: {len(g)} ({doc['gaps_no']} No, {doc['gaps_blank']} blank), {doc['gaps_in_fleet']} in the fleet")
    for s in sysrows:
        if s["results"] or s["status"] != "not_managed":
            print(f"  piped {s['code']} {s['name']} [{s['status']}]: {s['results']} pre-project results, "
                  f"{s['ecoli_present']} with E. coli -> {s['eligibility']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
