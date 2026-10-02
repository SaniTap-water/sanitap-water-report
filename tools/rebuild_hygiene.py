#!/usr/bin/env python3
"""Hygiene promotion and gender, for the managed portfolio (1 Oct 2026).

Reads the mWater extracts (read-only pulls, tools/pull_extract.py):

  hygiene.json      "Clean Water || Formation et Suivi promotion de l'hygiène"
                    (283c5670...): one response per session held at a water
                    point - visit date (2.1), topics (2.2, among them gender
                    equality and menstrual hygiene), participants by sex (3.x);
  hygiene_san.json  "Clean Water || project Hygiene&San || Survey" (209cc5fc...):
                    the annual household survey that carries the WHO/UNICEF JMP
                    core hygiene questions - handwashing place observed (WS2.5),
                    water there (WS2.6), soap there (WS2.7);
  cbn_gender.json   "Clean Water || Project Cbn&Gender || Survey" (2eeb8682...):
                    the annual monitoring survey (respondent counts only here).

Only sessions and survey responses on a water point in the managed register
(PUMPS) count; each is attributed to the point's district, so the page can sum
the districts a scope covers. The as-of date is the activity tiles' own
(tools/rebuild_activity.py).

The obligation: v1.0 SDWS 20 / v2.0 SDWS 24, an annual water hygiene education
campaign; v2.0 adds that its impact "shall be assessed using the WHO/UNICEF
JMP Core questions for drinking water and hygiene". A year meets it here when
it has at least one recorded session on a managed point AND a JMP-question
survey of managed points' users.

Writes data/hygiene.json (HYG on the page).

    python3 tools/rebuild_hygiene.py [--write]
"""
import collections, datetime, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rebuild_activity as RA  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.expanduser("~/mwater-exports")
OUT = os.path.join(REPO, "data", "hygiene.json")
FORMS = {"sessions": ("hygiene.json", "283c5670de82489d833e986cb76a67d8",
                      "Clean Water || Formation et Suivi promotion de l'hygiène"),
         "jmp_survey": ("hygiene_san.json", "209cc5fc24e24463aff702c11b6bd18f",
                        "Clean Water || project Hygiene&San || Survey"),
         "cbn_gender": ("cbn_gender.json", "2eeb86824b4545eca33db9e7cf7dcbd4",
                        "Clean Water || Project Cbn&Gender || Survey")}
Q_WP, Q_DATE, Q_TOPIC = "9fab5048dccd44369d3179312d55e847", "98c3e8bc6b2c4a8a86cff2e9ffa9c0b3", "06b49acf19d24936829e8d4abd6d42ee"
MALE = ["b1ec4ef83e0341a2abb5e97cc1ed0d01", "382e699d92084a21830415ba777a78cd", "d98aefe8d76c4034bd80aa77e6619cdc",
        "bb4805e696f84a1d9cd029a64ae00d10", "bc1fe1ba004844dd93cbd69608180f77", "161e4e7eb2c24c1d8c11003544cae600",
        "2da4d00346244beca0095f911264c74d", "eda580b8d441421fbea3162a967243eb"]
FEMALE = ["f129a65a4e46445c80d854e129d29f7e", "d52b0dae77ab435392cd52e8c81a6044", "c182d889984a4618929ed8c35b691bbb",
          "cbc0d1a79c654e21a8895ee1435d1e50", "872dccefdea740e8b15c39688d1d5b90", "d312efef18774fdd873ed9576b1353e0",
          "f0c9c5900afb4f668253185ee6e8c101", "d2ad63e6f8d6493291a5088d29617b92"]
T_GENDER, T_MHM = "pJVXLkg", "4RZuhgp"
# the JMP core hygiene questions on the annual survey
J_WP, J_DATE, J_PLACE, J_WATER, J_SOAP = ("07e2aa4fa29b4a45b9357d67f049d2c2", "cba1b57c1ee44761bb6b74de8378990a",
                                          "f73e912ab8984ccbb375e1a2c11dd1c5", "294d34fbfd454b5fa06ed243cf040965",
                                          "994ec2dcdc2d40a5839992aa496d4a6a")
OBSERVED = {"6F1ejqh", "lNLLl6b"}          # fixed facility / mobile object, observed
NO_PERMISSION = "TmhJtxp"


def load(name):
    p = os.path.join(EX, name)
    if not os.path.isfile(p):
        return None
    return json.load(open(p, encoding="utf8"))


def val(r, q):
    v = (r.get("data") or {}).get(q)
    return v.get("value") if isinstance(v, dict) else v


def wp_of(r, q):
    v = val(r, q)
    if isinstance(v, dict):                    # a site answer: {"code": "742895845"}
        v = v.get("code")
    if v:
        return str(v)
    for e in r.get("entities") or []:
        if e.get("entityType") == "water_point" and e.get("value"):
            return str(e["value"])
    return None


def main():
    write = "--write" in sys.argv
    idx = open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    mp = re.search(r"\bconst PUMPS\s*=\s*", idx)
    pumps = json.loads(idx[mp.end():idx.index("];", mp.end()) + 1])
    site = {p["wp"]: p["site"] for p in pumps}
    sites = sorted(set(site.values()))
    pm = RA.by_point(RA.FORMS["pm"])
    rep = RA.by_point(RA.FORMS["repair"])
    all_d = [d for v in list(pm.values()) + list(rep.values()) for d in v]
    all_d += [str(r.get("submittedOn") or "")[:10] for r in RA.rows(RA.FORMS["call"])]
    asof = datetime.date.fromisoformat(max(d for d in all_d if d[:2] == "20"))
    since12 = (asof - datetime.timedelta(days=365)).isoformat()

    res = {"note": "Written by tools/rebuild_hygiene.py: hygiene-promotion sessions and the JMP-question survey "
                   "on water points in the managed register, by the point's district.",
           "asof": asof.isoformat(), "since_12m": since12, "window_months": 12, "forms": {}, "by_site": {}, "months": {},
           "years": {}, "sites": sites}
    S = {s: {"sessions": 0, "sessions_12m": 0, "points_12m": set(), "points_ever": set(), "male": 0, "female": 0,
             "with_counts": 0, "gender_sessions": 0, "mhm_sessions": 0, "last": None, "first": None,
             "outside": 0} for s in sites}
    months = collections.defaultdict(lambda: collections.Counter())
    years = collections.defaultdict(lambda: {s: {"sessions": 0, "points": set(), "jmp_n": 0, "jmp_basic": 0,
                                                 "jmp_first": None, "jmp_last": None} for s in sites})
    outside = 0

    sess = load(FORMS["sessions"][0]) or []
    final = [r for r in sess if (r.get("status") or "final") in RA.SUBMITTED]
    for r in final:
        wp = wp_of(r, Q_WP)
        d = str(val(r, Q_DATE) or r.get("submittedOn") or "")[:10]
        if wp not in site:
            outside += 1
            continue
        s = site[wp]; x = S[s]
        x["sessions"] += 1
        x["points_ever"].add(wp)
        if d > since12:
            x["sessions_12m"] += 1; x["points_12m"].add(wp)
        m, f = sum(float(val(r, q) or 0) for q in MALE), sum(float(val(r, q) or 0) for q in FEMALE)
        if any(val(r, q) is not None for q in MALE + FEMALE):
            x["with_counts"] += 1
        x["male"] += int(m); x["female"] += int(f)
        topics = val(r, Q_TOPIC) or []
        topics = topics if isinstance(topics, list) else [topics]
        x["gender_sessions"] += T_GENDER in topics
        x["mhm_sessions"] += T_MHM in topics
        x["last"] = max(x["last"] or d, d); x["first"] = min(x["first"] or d, d)
        months[d[:7]][s] += 1
        years[d[:4]][s]["sessions"] += 1; years[d[:4]][s]["points"].add(wp)

    jmp = load(FORMS["jmp_survey"][0])
    jmp_outside = 0
    for r in (jmp or []):
        if (r.get("status") or "final") not in RA.SUBMITTED:
            continue
        wp = wp_of(r, J_WP)
        d = str(val(r, J_DATE) or r.get("submittedOn") or "")[:10]
        if wp not in site:
            jmp_outside += 1
            continue
        place = val(r, J_PLACE)
        if place is None or place == NO_PERMISSION:
            continue                               # not a community household, or no permission to see
        y = years[d[:4]][site[wp]]
        y["jmp_n"] += 1
        y["jmp_basic"] += (place in OBSERVED and val(r, J_WATER) == "zduUnyY" and val(r, J_SOAP) == "3NdqmVe")
        y["jmp_first"] = min(y["jmp_first"] or d, d); y["jmp_last"] = max(y["jmp_last"] or d, d)

    for k, (fn, fid, name) in FORMS.items():
        rows = load(fn)
        sub = [r for r in (rows or []) if (r.get("status") or "final") in RA.SUBMITTED]
        ds = sorted(str(r.get("submittedOn") or "")[:10] for r in sub if str(r.get("submittedOn") or "")[:2] == "20")
        res["forms"][k] = {"file": fn, "form_id": fid, "name": name, "pulled": rows is not None,
                           "responses": len(sub), "first": ds[0] if ds else None, "last": ds[-1] if ds else None}
    res["forms"]["sessions"]["outside_managed"] = outside
    res["forms"]["jmp_survey"]["outside_managed"] = jmp_outside

    for s, x in S.items():
        res["by_site"][s] = {"sessions": x["sessions"], "sessions_12m": x["sessions_12m"],
                             "points_12m": len(x["points_12m"]), "points_ever": len(x["points_ever"]),
                             "fleet": sum(1 for v in site.values() if v == s),
                             "male": x["male"], "female": x["female"], "with_counts": x["with_counts"],
                             "gender_sessions": x["gender_sessions"], "mhm_sessions": x["mhm_sessions"],
                             "first": x["first"], "last": x["last"]}
    res["months"] = {m: {s: months[m].get(s, 0) for s in sites} for m in sorted(months)}
    for y in sorted(set(years) | {"2025", "2026"}):
        res["years"][y] = {s: {"sessions": years[y][s]["sessions"], "points": len(years[y][s]["points"]),
                               "jmp_n": years[y][s]["jmp_n"], "jmp_basic": years[y][s]["jmp_basic"],
                               "jmp_first": years[y][s]["jmp_first"], "jmp_last": years[y][s]["jmp_last"]}
                           for s in sites}
    txt = json.dumps(res, indent=1, ensure_ascii=False) + "\n"
    if write:
        open(OUT, "w", encoding="utf8").write(txt)
        print("  ->", os.path.relpath(OUT, REPO))
    elif not os.path.isfile(OUT) or open(OUT, encoding="utf8").read() != txt:
        print("rebuild_hygiene: data/hygiene.json is out of date (run --write)")
        return 1
    for s, b in res["by_site"].items():
        print(f"  {s:13s} sessions {b['sessions']} (12 m {b['sessions_12m']}), points reached 12 m {b['points_12m']} "
              f"of {b['fleet']}, men/boys {b['male']} women/girls {b['female']}, gender {b['gender_sessions']}, "
              f"MHM {b['mhm_sessions']}, last {b['last']}")
    for y, v in res["years"].items():
        print(f"  {y}: sessions {sum(x['sessions'] for x in v.values())}, JMP survey n "
              f"{sum(x['jmp_n'] for x in v.values())} (basic {sum(x['jmp_basic'] for x in v.values())})")
    print(f"  forms: {json.dumps({k: (v['responses'], v['first'], v['last']) for k, v in res['forms'].items()})}")
    print(f"  sessions on points outside the managed register: {outside}; JMP survey responses outside: {jmp_outside}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
