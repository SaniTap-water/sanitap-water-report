#!/usr/bin/env python3
"""Consistency checker for the SaniTap weekly water report.

Takes index.html and portfolio.html and fails, loudly and with a non-zero exit,
if the two pages disagree with each other, with the SDWS 1 summary of record, or
with themselves.

It exists because the figures in these two files are produced by different build
steps: index.html carries the per-point WorldPop data inline, portfolio.html
carries a hand-written summary table. Nothing but this script has been checking
that the second still describes the first.

Usage:
    python3 tools/check_consistency.py index.html portfolio.html
    python3 tools/check_consistency.py index.html portfolio.html \
        --summary ~/sdws1/runs/r2025a_barriers/sdws1_summary_equal.json

Exit status: 0 all checks pass, 1 at least one failed, 2 could not run a check.

LIMITATIONS
-----------
The retired-figure test is a keyword test over the rendered source. For figures
that are simply wrong everywhere (134,463 and friends) that is exact. For 908,
which is a real and quotable number - the mWater register record count - the
test can only check that an occurrence sits near wording that marks it as the
register count. A sentence that used 908 as a management figure while happening
to contain the word "register" would pass. Treat a 908 PASS as "nothing obviously
wrong", not as proof.
"""
import argparse, collections, datetime, json, os, re, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exclude_retired import (RETIRED_NAME_PREFIX, KNOWN_RETIRED_CODES,  # noqa: E402
                             KNOWN_RETIRED_NAMES)

FULL_SCALE = 4000          # water points at full programme scale
CARBON_EXCLUDES = "Marolinta"

# Figures retired in a previous edition. If one of these reappears anywhere, the
# page has been built from a stale source. Each entry: (needle, why, context
# words that make an occurrence legitimate).
DENY = [
    ("134,463", "January roof-count population, superseded by the R2025A run", ()),
    ("176,513", "January WorldPop figure, never reproduced; retired", ()),
    ("93,178",  "population from the wrong (2020) raster", ()),
    ("41,285",  "Fort-Dauphin figure from the wrong (2020) raster", ()),
    ("24.5%",   "cookstove overlap computed on the wrong denominator", ()),
    # 908 was the whole MadAvance mWater group's record count. Since
    # 2026-09-23 the page covers the actively managed portfolio only and the
    # group count appears nowhere, labelled or not. The CURRENT group count is
    # asserted absent from the rendered page by tools/render_check.py.
    ("908", "the whole mWater group count; the page covers the portfolio only", ()),
]

RESULTS = []


def check(name, ok, expected, actual, note=""):
    RESULTS.append((name, bool(ok), str(expected), str(actual), note))
    return bool(ok)


def fail_hard(msg):
    print(f"\n  CANNOT RUN: {msg}", file=sys.stderr)
    sys.exit(2)


def read(p):
    with open(p, encoding="utf8", errors="replace") as f:
        return f.read()


# ---------------------------------------------------------------- extraction
def js_const(src, name):
    """Pull `const NAME = <json>;` out of the page."""
    m = re.search(r"const\s+" + re.escape(name) + r"\s*=\s*('?)(\{.*?\}|\[.*?\])\1\s*;", src, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(2))
    except Exception:
        return None


def num(s):
    return int(str(s).replace(",", "").strip())


def portfolio_tables(src):
    """Per-site rows: {label: (points, people)} plus the carbon subtotal."""
    rows = {}
    for m in re.finditer(
            r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td class=\"num\">([\d,]+)</td>\s*"
            r"<td class=\"num\">([\d,]+)</td>\s*</tr>", src, re.S):
        label = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        label = re.sub(r"\s+", " ", label)
        rows[label] = (num(m.group(2)), num(m.group(3)))
    return rows


# Where the SDWS 1 summary of record lives, tried in order. The model is not in
# this repo, so the path cannot be relative to it alone - but nothing here may
# depend on one machine's home directory either.
SUMMARY_ENV = "SDWS1_SUMMARY"
SUMMARY_REL = os.path.join("runs", "r2025a_barriers", "sdws1_summary_equal.json")


def summary_candidates(repo_root):
    """In order: explicit env var, a copy kept beside the repo, then the model
    checkout next to or above it. Absolute machine paths are the last resort."""
    env = os.environ.get(SUMMARY_ENV)
    if env:
        yield env
    yield os.path.join(repo_root, "data", "sdws1_summary_equal.json")
    yield os.path.join(repo_root, "..", "sdws1", SUMMARY_REL)
    yield os.path.join(repo_root, "..", "..", "sdws1", SUMMARY_REL)
    yield os.path.expanduser(os.path.join("~", "sdws1", SUMMARY_REL))


def find_summary(explicit, repo_root):
    if explicit:
        return explicit
    for c in summary_candidates(repo_root):
        if c and os.path.exists(c):
            return os.path.normpath(c)
    return None


# ---------------------------------------------------------------- the checks
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("index")
    ap.add_argument("portfolio")
    ap.add_argument("--summary", default=None,
                    help=f"sdws1_summary_*.json of record. Default: ${SUMMARY_ENV}, then "
                         f"<repo>/data/, then a sibling ~/sdws1 checkout.")
    a = ap.parse_args()

    idx = read(a.index)

    # The action detail used to live in two tables in the body, one <tr> per
    # action. It is now data/action_details.json, rendered collapsed inside the
    # single consolidated list. These checks address an action by its id, so the
    # old shape is reconstructed here and they read that instead of the page -
    # the content is identical, only its home moved.
    _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _det_p = os.path.join(_here, "data", "action_details.json")
    _det = json.load(open(_det_p)) if os.path.isfile(_det_p) else {}
    ACTSRC = "".join(
        f'<tr id="{k}">{v["detail"]}</td><td>{v["schedule"]}</td>'
        f'<td>{v["owner"]}</td></tr>'
        for k, v in sorted(_det.items()))

    prt = read(a.portfolio)

    WPOP = js_const(idx, "WPOP")
    META = js_const(idx, "WPOPMETA")
    PUMPS = js_const(idx, "PUMPS")
    if WPOP is None or META is None:
        fail_hard("could not parse WPOP / WPOPMETA out of index.html")
    if PUMPS is None:
        fail_hard("could not parse PUMPS out of index.html")

    site_of = {str(p["wp"]): p.get("site") for p in PUMPS if isinstance(p, dict) and "wp" in p}
    per_site_people, per_site_points = {}, {}
    unmapped = 0
    for code, v in WPOP.items():
        s = site_of.get(str(code))
        if s is None:
            unmapped += 1
            continue
        per_site_people[s] = per_site_people.get(s, 0) + int(v[1])
        per_site_points[s] = per_site_points.get(s, 0) + 1
    idx_total = sum(int(v[1]) for v in WPOP.values())

    # ---- 1. the SDWS 1 summary of record ---------------------------------
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sp = find_summary(a.summary, repo_root)
    if not sp or not os.path.exists(sp):
        fail_hard("no sdws1_summary_*.json of record found. Tried:\n    "
                  + "\n    ".join(os.path.normpath(c) for c in summary_candidates(repo_root) if c)
                  + f"\n  Set ${SUMMARY_ENV} or pass --summary.")
    S = json.load(open(sp))
    check("population: index total vs summary of record",
          idx_total == S["reported_after_cap"], S["reported_after_cap"], idx_total,
          os.path.basename(sp))
    check("points: index WPOP rows vs summary of record",
          len(WPOP) == S["points"], S["points"], len(WPOP))
    check("points: WPOPMETA.rows vs summary of record",
          META.get("rows") == S["points"], S["points"], META.get("rows"))
    check("raster sha256: index WPOPMETA vs summary of record",
          META.get("raster_sha256") == S.get("raster_sha256"),
          str(S.get("raster_sha256"))[:16] + "...",
          str(META.get("raster_sha256"))[:16] + "...")
    check("points at cap: index vs summary of record",
          META.get("points_at_the_cap") == S.get("points_at_the_cap"),
          S.get("points_at_the_cap"), META.get("points_at_the_cap"))
    check("every WPOP point maps to a site in PUMPS", unmapped == 0, 0, unmapped)

    # ---- 2. raster sha quoted in the map ---------------------------------
    m = re.search(r"([0-9a-f]{8})&hellip;|([0-9a-f]{8})…", prt)
    quoted = (m.group(1) or m.group(2)) if m else None
    check("raster sha256: prefix quoted on the map vs summary of record",
          quoted is not None and S.get("raster_sha256", "").startswith(quoted),
          str(S.get("raster_sha256"))[:8], quoted)

    # ---- 3. headline figures that appear in both files --------------------
    rows = portfolio_tables(prt)
    alias = {"Maroantsetra": "Maroantsetra",
             "Anosy (Fort-Dauphin)": "Fort-Dauphin",
             "Androy (Marolinta), separately funded": "Marolinta"}
    seen_sites = []
    for label, site in alias.items():
        if label not in rows:
            check(f"map table row present: {label}", False, "row", "missing")
            continue
        pts, ppl = rows[label]
        seen_sites.append(site)
        check(f"people served, {site}: map vs index",
              ppl == per_site_people.get(site), per_site_people.get(site), ppl)
        check(f"points, {site}: map vs index",
              pts == per_site_points.get(site), per_site_points.get(site), pts)

    # ---- 4. point counts sum correctly -----------------------------------
    carbon = rows.get("Carbon portfolio")
    if carbon is None:
        check("map carries a carbon portfolio subtotal", False, "row", "missing")
    else:
        cpts, cppl = carbon
        parts_pts = sum(rows[l][0] for l in alias if l in rows and alias[l] != CARBON_EXCLUDES)
        parts_ppl = sum(rows[l][1] for l in alias if l in rows and alias[l] != CARBON_EXCLUDES)
        check("carbon portfolio points = sum of its sites", cpts == parts_pts, parts_pts, cpts)
        check("carbon portfolio people = sum of its sites", cppl == parts_ppl, parts_ppl, cppl)
        mar_label = [l for l in alias if alias[l] == CARBON_EXCLUDES]
        mar = rows.get(mar_label[0]) if mar_label else None
        check(f"carbon portfolio excludes {CARBON_EXCLUDES}",
              mar is not None and cppl + mar[1] == idx_total and cpts + mar[0] == len(WPOP),
              f"{CARBON_EXCLUDES} outside; carbon+{CARBON_EXCLUDES}={idx_total}",
              f"carbon={cppl} + {CARBON_EXCLUDES}={mar[1] if mar else '?'} = "
              f"{cppl + (mar[1] if mar else 0)}")
        check("all sites sum to the in-scope total",
              cpts + (mar[0] if mar else 0) == len(WPOP), len(WPOP),
              cpts + (mar[0] if mar else 0))

    # ---- 5. phasing percentage -------------------------------------------
    mp = re.search(r"<b>([\d,]+) today</b>", prt)
    mw = re.search(r'class="bar"><i style="width:([\d.]+)%"', prt)
    ms = re.search(r"([\d.]+)% of target programme scale", prt)
    if not (mp and mw and ms):
        check("phasing block parsed", False, "in-scope, bar width, caption", "not found")
    else:
        inscope = num(mp.group(1))
        want = round(100.0 * inscope / FULL_SCALE, 1)
        check("phasing: bar width = in-scope / 4,000",
              abs(float(mw.group(1)) - want) < 0.05, f"{want}%", f"{mw.group(1)}%",
              f"{inscope}/{FULL_SCALE}")
        check("phasing: caption = in-scope / 4,000",
              abs(float(ms.group(1)) - want) < 0.05, f"{want}%", f"{ms.group(1)}%")

    # ---- 6. retired figures ----------------------------------------------
    for needle, why, allow in DENY:
        bad = []
        for f, src in (("index.html", idx), ("portfolio.html", prt)):
            for m in re.finditer(r"(?<![0-9A-Za-z,._-])" + re.escape(needle) + r"(?![0-9A-Za-z,._-])", src):
                ctx = re.sub(r"\s+", " ", src[max(0, m.start() - 160):m.start() + 90]).lower()
                if allow and any(w in ctx for w in allow):
                    continue
                bad.append(f)
                break
        check(f"retired figure absent: {needle}", not bad, "absent",
              "found in " + ", ".join(bad) if bad else "absent", why)

    # ---- 7. retired records must not reach the published pages -----------
    # mWater permissions leave no writable status field, so a retired record is
    # marked only by its name prefix. See tools/exclude_retired.py. These are the
    # backstop: if the build's filter is missing or was applied too late, a
    # retired record's code or name shows up here.
    for f, src in (("index.html", idx), ("portfolio.html", prt)):
        found = [n for n in KNOWN_RETIRED_NAMES if n.upper() in src.upper()]
        check(f"{f}: no {RETIRED_NAME_PREFIX!r} record present", not found,
              "absent", "FOUND: " + ", ".join(found) if found else "absent",
              "retired records must be filtered out in the build")
    # A retired code must not appear in any DATA structure - that is what
    # "included in a published figure" means. It MAY appear in prose: the report
    # names these two codes in the Moramanga actions table, which is the report
    # doing its job. So the hard assertion is on the data, and prose mentions are
    # surfaced separately rather than failing the build.
    data_names = ("WPOP", "PUMPS", "RESP", "PHOTOS", "DOWN", "OPENREP", "PARTIAL")
    data_blobs = []
    for n in data_names:
        m = re.search(r"const\s+" + n + r"\s*=\s*('?)(\{.*?\}|\[.*?\])\1\s*;", idx, re.S)
        if m:
            data_blobs.append((n, m.group(2)))
    # portfolio.html embeds its marker data inline; treat the whole file as data
    # except for the prose blocks, which is close enough to catch a stray code.
    for code in KNOWN_RETIRED_CODES:
        inside = [n for n, b in data_blobs if code in b]
        if code in prt:
            inside.append("portfolio.html")
        check(f"retired code in no data structure: {code}", not inside,
              "in no data object", "in " + ", ".join(inside) if inside else "in no data object",
              "a retired record must not reach any figure")
    for code in KNOWN_RETIRED_CODES:
        n_prose = len(re.findall(r"(?<![0-9A-Za-z])" + re.escape(code) + r"(?![0-9A-Za-z])", idx))
        n_data = sum(1 for _, b in data_blobs if code in b)
        check(f"retired code {code}: prose mentions only", n_data == 0,
              "0 in data", f"{n_prose - n_data} in prose, {n_data} in data",
              "prose mentions are expected - the report documents the correction")

    # Point counts must be of the filtered set. The register holds more records
    # than the published figures use; any published count landing on the raw
    # register total is a sign the filter was skipped.
    reg_total_with_retired = len(WPOP) + len(KNOWN_RETIRED_CODES)
    check("published point count is not the unfiltered register count",
          len(WPOP) != reg_total_with_retired, f"!= {reg_total_with_retired}", len(WPOP),
          f"{len(KNOWN_RETIRED_CODES)} retired records excluded")

    # ---- 7b. every parameter/method figure must carry its source --------
    # A figure in a parameter or method statement is only usable to a verifier if
    # the page says where it came from. These are the sources the report's own
    # statements rest on; if a figure block loses its citation the source string
    # disappears with it, so their presence is the tripwire.
    REQUIRED_SOURCES = [
        ("INSTAT RGPH-3", "people per premises, SDWS 25"),
        ("WorldPop R2025A", "the population basis, SDWS 1"),
        ("fNRB Application for GS4GG Certification", "fNRB applied basis, SDWS 21"),
        ("MoFuSS", "the fNRB source of data as registered"),
        ("VPA-DD", "the registered design document"),
    ]
    both = idx + prt
    for needle, why in REQUIRED_SOURCES:
        pat = re.escape(needle).replace(r"\-", r"[-\u2010-\u2015]").replace(r"\ ", r"(?:\s|&nbsp;)+")
        n = len(re.findall(pat, both))
        check(f"source cited: {needle}", n > 0, "cited at least once",
              f"{n} mention(s)" if n else "MISSING", why)

    # An fNRB value statement must carry a TOOL33 citation, and TOOL30 may be
    # named only as a withdrawn tool. Both are scoped to the ENCLOSING SECTION,
    # not to a character window: a window wide enough to be useful also reaches
    # into the neighbouring section's citation, which makes the test vacuous.
    def enclosing_section(src, pos):
        """(start, end) of the <section> containing pos, or the whole document."""
        a = src.rfind("<section", 0, pos)
        if a == -1:
            return (0, len(src))
        b = src.find("</section>", pos)
        return (a, b + len("</section>") if b != -1 else len(src))

    def section_label(src, a):
        m = re.search(r'id="([^"]+)"', src[a:a + 300])
        if m:
            return m.group(1)
        h = re.search(r"<h2>(.*?)</h2>", src[a:a + 900])
        return re.sub(r"<[^>]+>", "", h.group(1))[:32] if h else f"offset {a}"

    # The registered fNRB authority is the Gold Standard rule update, and the
    # source of data is MoFuSS - not A6.4-AMT-009, which the rule update does
    # not name. An earlier edition cited the tool and applied 36% to
    # Maroantsetra where the registered value is 34%.
    AUTH = "fNRB Application for GS4GG Certification"
    bad = []
    for f, src in (("index.html", idx), ("portfolio.html", prt)):
        for m in re.finditer(r"fNRB", src):
            a, b = enclosing_section(src, m.start())
            if AUTH not in src[a:b] and "MoFuSS" not in src[a:b]:
                lab = f"{f}:{section_label(src, a)}"
                if lab not in bad:
                    bad.append(lab)
    check("every fNRB statement cites the rule update or MoFuSS", not bad,
          "rule update or MoFuSS in each section naming fNRB",
          "uncited in " + ", ".join(bad[:3]) if bad else "all cited",
          "GS Rule Update fNRB Application for GS4GG Certification V1.0 s2.3.1")
    amt = re.findall(r"A6\.4-AMT-009[^.<]{0,60}(?:applied basis|is the basis|basis we apply)", idx, re.I)
    check("A6.4-AMT-009 not claimed as the fNRB applied basis", not amt,
          "absent", f"{len(amt)} found" if amt else "absent",
          "the rule update does not name it; the registered source is MoFuSS")
    check("the registered Maroantsetra fNRB value is applied",
          "MoFuSS 0.34 Maroantsetra" in idx and "0.418" not in idx,
          "0.34 applied, 0.418 gone",
          "0.418 still present" if "0.418" in idx else "0.34 applied, 0.418 gone",
          "registered SDWS 21: Anosy 54%, Maroantsetra 34%")

    stale = []
    for f, src in (("index.html", idx), ("portfolio.html", prt)):
        for m in re.finditer(r"TOOL\s*30", src):
            a, b = enclosing_section(src, m.start())
            if not any(w in src[a:b].lower() for w in ("discontinu", "withdrawn", "superseded")):
                lab = f"{f}:{section_label(src, a)}"
                if lab not in stale:
                    stale.append(lab)
    check("TOOL30 never cited as a live source", not stale,
          "every section naming TOOL30 marks it discontinued",
          "unmarked in " + ", ".join(stale[:3]) if stale else "all marked discontinued",
          "discontinued with effect from 1 January 2026, EB 125")

    # ---- 7c. the document skeleton -----------------------------------
    # Edition 10 shipped with two <section> blocks spliced between "<!doctype"
    # and " html>", so the page began mid-declaration. Browsers rendered it
    # anyway and every other check passed. These assert the skeleton itself.
    for f, src in (("index.html", idx), ("portfolio.html", prt)):
        head = src.lstrip()[:200].lower()
        check(f"{f}: starts with a complete doctype", head.startswith("<!doctype html>"),
              "<!doctype html>", repr(src.lstrip()[:32]),
              "a split doctype still renders - only this catches it")
        i_body = src.lower().find("<body")
        i_sec = src.lower().find("<section")
        check(f"{f}: no content before <body>", i_body != -1 and (i_sec == -1 or i_sec > i_body),
              "<section> after <body>",
              f"body@{i_body} section@{i_sec}" if i_body != -1 else "no <body>")
        for tag in ("<html", "<head", "</head>", "</body>", "</html>"):
            check(f"{f}: has {tag}", tag in src.lower(), "present",
                  "present" if tag in src.lower() else "MISSING")

    # ---- 7b-5. a migration must not complete silently ----------------------
    # The combined form was retired branch by branch. Its first-rehabilitation
    # successor has zero responses, and zero is a plausible weekly count - so
    # nothing would fail on the day the first one arrives unless something
    # watches for exactly that.
    try:
        sys.path.insert(0, os.path.join(repo_root, "tools"))
        import populations as _pops_mod
        _mig = _pops_mod.migration_watch()
    except Exception as e:                                     # noqa: BLE001
        _mig = None
        check("the migration watch runs", False, "runs", f"failed: {e}",
              "a response nothing reads is a silent migration")
    if _mig is not None:
        _bad = [(f, lab) for f, lab, n, unread in _mig if unread]
        check("no successor form carries a response nothing reads",
              not _bad, "none",
              "; ".join(lab[:44] for _, lab in _bad[:2]) if _bad else "none",
              "the retired combined form was replaced branch by branch; every "
              "successor must be read by a population")
        check("the retired combined form is named as retired on the page",
              "RETIRED, superseded" in idx, "named",
              "named" if "RETIRED, superseded" in idx else "MISSING",
              "a verifier following that link lands on a dead form")
        check("the live first-rehabilitation form is read by a population",
              "63747997e70e478fbb2ebf71581ceeb0" in read(
                  os.path.join(repo_root, "tools", "populations.py")),
              "read", "read", "zero responses today; read so the first is seen")

    # ---- 7b-6. no link to a route that does not exist ----------------------
    rt = os.path.join(repo_root, "data", "mwater_routes.json")
    if os.path.exists(rt):
        _routes = json.loads(read(rt))
        check("the portal route table is on file",
              _routes.get("count", 0) >= 50, ">=50 routes",
              _routes.get("count"),
              "read from the portal bundle; tools/check_links.py checks "
              "every emitted link against it")
    _wp_links = sum(f.count("#/water_point/") for f in (idx, prt))
    check("no link points at the non-existent water_point route",
          _wp_links == 0, "none", f"{_wp_links} link(s)",
          "the portal has no route to an individual entity; link to the "
          "RESPONSE that references the point")

    # ---- 7b-7. a record count is not a point count -------------------------
    # This confusion produced 727, the 723/731 gap, and a "46 unexplained
    # points" finding that was really unstable paging. Every population
    # declares its unit, and no chain step may relate two populations of
    # different units.
    pop_pp = os.path.join(repo_root, "data", "populations.json")
    _pops = json.loads(read(pop_pp)) if os.path.exists(pop_pp) else {}
    _P = _pops.get("populations") or {}
    nounit = [k for k, v in _P.items() if v.get("unit") not in ("records", "points")]
    check("every population declares whether it counts records or points",
          not nounit, "all declared",
          f"missing on {', '.join(nounit[:3])}" if nounit else "all declared",
          "a record count and a point count are different quantities")
    mixed = [c["step"] for c in _pops.get("chain", [])
             if not (c["step"].startswith("RECORDS:") or c["step"].startswith("POINTS:"))]
    check("every chain step names the unit it relates",
          not mixed, "all named",
          f"unnamed: {'; '.join(mixed[:2])}" if mixed else "all named",
          "a step relating records to points is not a reconciliation")
    # 723 is withdrawn as a LIVE figure. Quoting it to say it is withdrawn,
    # or quoting a document that carries it, is allowed and is not the fault.
    _regm = re.search(r"\bconst REG\s*=\s*(\{.*?\});", idx, re.S)
    _reg = json.loads(_regm.group(1)) if _regm else {}
    check("723 is withdrawn as a live figure",
          _reg.get("succ") != 723 and _reg.get("succ_withdrawn") == 723,
          "withdrawn, recorded",
          f"REG.succ={_reg.get('succ')}, withdrawn={_reg.get('succ_withdrawn')}",
          "it could not be reproduced from any data held; superseded by the "
          "derived point count. See docs/decision_log.md")
    check("the successful-rehabilitation figure is the derived point count",
          _reg.get("succ") == (_P.get("rehabilitated_successfully") or {}).get("size"),
          (_P.get("rehabilitated_successfully") or {}).get("size"),
          _reg.get("succ"),
          "REG.succ must equal the population tools/populations.py computes")
    _succ_pts = (_P.get("rehabilitated_successfully") or {}).get("size")
    _carbon = (_P.get("carbon_fleet") or {}).get("size")
    _succ_rec = (_P.get("successful_first_rehabilitation_records") or {}).get("size")
    check("the successful-record count is not treated as the carbon fleet",
          _succ_rec != _carbon or (
              _P.get("successful_first_rehabilitation_records", {}).get("unit")
              != _P.get("carbon_fleet", {}).get("unit")),
          "different units",
          f"both {_succ_rec} but units differ"
          if _succ_rec == _carbon else "different values",
          "731 successful RECORDS equals 731 carbon POINTS by coincidence; "
          "they are unrelated quantities")

    # ---- 7b-8. every figure shows its working ------------------------------
    # A figure that cannot be expanded into its derivation is a figure the
    # reader has to take on trust. Every data-fig expression must be in
    # DERIV, and every population it names must exist.
    pop_p = os.path.join(repo_root, "data", "populations.json")
    der_p = os.path.join(repo_root, "data", "derivations.json")
    pops = json.loads(read(pop_p)) if os.path.exists(pop_p) else {}
    check("the semantic layer exists and defines the chain",
          len(pops.get("populations", {})) >= 7, ">=7 populations",
          len(pops.get("populations", {})),
          "tools/populations.py - every one a set of records, none a stored count")
    for pid, pop in (pops.get("populations") or {}).items():
        missing = [k for k in ("name", "rule", "reads", "decided", "size")
                   if not pop.get(k) and pop.get(k) != 0]
        check(f"population {pid} is fully declared", not missing,
              "complete", f"missing {', '.join(missing)}" if missing else "complete",
              "id, name, plain-English rule, what it reads, the decision, the size")
    exprs = set(re.findall(r'data-fig="([^"]+)"', idx))
    m_der = re.search(r"const DERIV=(\{.*?\});", idx, re.S)
    der = json.loads(m_der.group(1)) if m_der else {}
    undeclared = sorted(e for e in exprs if e not in der)
    check("every rendered figure has a recorded derivation",
          not undeclared, f"{len(exprs)} expressions",
          f"no derivation for: {', '.join(undeclared[:4])}" if undeclared
          else f"all {len(exprs)} declared",
          "a figure the reader cannot expand is one they must take on trust")
    badpop = sorted({d["pop"] for d in der.values()
                     if d.get("pop") and d["pop"] not in (pops.get("populations") or {})})
    check("every derivation names a population that exists",
          not badpop, "all resolve",
          f"unknown: {', '.join(badpop[:3])}" if badpop else "all resolve",
          "the population is the link between a figure and its rule")
    # The definitions section was once inserted INSIDE the action-list
    # generated region and the next render_actions --write deleted it
    # silently. A generated region swallowing another one leaves no trace, so
    # this asserts the section survived.
    check("the definitions section is on the page",
          'id="definitions"' in idx and 'id="popstbl"' in idx
          and 'id="chaintbl"' in idx and 'id="paramstbl"' in idx,
          "present",
          "present" if 'id="definitions"' in idx else "MISSING",
          "a verifier who cannot read Python still sees every definition")
    _defs_i = idx.find("<!-- BEGIN GENERATED definitions")
    _acts_i = idx.find("<!-- BEGIN GENERATED action-list")
    check("the definitions region is outside the action-list region",
          _defs_i >= 0 and _acts_i >= 0 and _defs_i < _acts_i, "outside",
          "outside" if _defs_i < _acts_i else "NESTED - it will be deleted",
          "one generated region inside another is deleted without a word")
    check("the derivation panel is wired on the page",
          "function derivPanel(" in idx and "DERIV_SEL" in idx, "wired",
          "wired" if "function derivPanel(" in idx else "MISSING",
          "one click from any number to its full derivation")
    check("the chain result is carried with the definitions",
          isinstance(pops.get("chain"), list) and len(pops["chain"]) >= 5,
          "carried", f"{len(pops.get('chain', []))} steps",
          "the reconciliation is produced by populations.py, not asserted beside it")

    # ---- 7b-9. register integrity -----------------------------------------
    # No managed point may have a missing or unresolvable admin_region, and no
    # point may enter or leave the fleet without something that explains it.
    rc_p = os.path.join(repo_root, "data", "register_corrections.json")
    rc = json.loads(read(rc_p)) if os.path.exists(rc_p) else {}
    der = (rc.get("admin_region_derived") or {}).get("points") or []
    check("every point with no admin_region has a derived value on file",
          len(der) == 9, 9, len(der),
          "derived from fokontany-mates and GPS, both unanimous; "
          "data/register_corrections.json")
    noev = [d["wp"] for d in der if not d.get("evidence") or not d.get("admin_region")]
    check("every derived admin_region carries its evidence",
          not noev, "all evidenced",
          f"missing on {', '.join(noev[:3])}" if noev else "all evidenced",
          "a derived value without its evidence is a guess")
    # The override is the permanent answer, not a stopgap: mWater computes
    # admin_region from location, and these locations lie outside its
    # boundary polygons (data/admin_polygon_test.json). Nothing is to be
    # fixed in mWater, so every point must say why it is overridden.
    _why = ("mWater computes admin_region from location; this point lies "
            "outside mWater's boundary polygons")
    nowhy = [d["wp"] for d in der if d.get("reason") != _why]
    check("every derived admin_region states why it is a permanent override",
          not nowhy and "PERMANENT" in ((rc.get("admin_region_derived") or {})
                                        .get("resolution") or ""),
          "all nine, resolution PERMANENT",
          f"no reason on {', '.join(nowhy[:3])}" if nowhy else "all nine",
          "the cause is mWater's boundary data; the page must not ask anyone "
          "to fix these nine in mWater")
    check("the mWater write attempt is recorded either way",
          "written_to_mwater" in (rc.get("admin_region_derived") or {}),
          "recorded",
          "recorded" if "written_to_mwater" in (rc.get("admin_region_derived") or {})
          else "MISSING",
          "the API accepts the PATCH and discards the field; that is a finding, "
          "not a silence")
    # ---- the mWater tooling is read-only (2026-09-25) ----------------------
    # mWater allows writes only via the portal or MCP proposals. The write
    # scripts are in tools/mwater/retired/; nothing the build runs may call
    # them, and the shared client may not grow a write helper again.
    _callers = []
    for _f in ("tools/weekly_build.sh", "tools/weekly_build.py", "tools/publish.sh",
               "tools/publish_waiting.py", "tools/publish_waiting.sh"):
        _fp = os.path.join(repo_root, _f)
        if os.path.isfile(_fp) and re.search(r"mwater/retired|fix_admin_region", read(_fp)):
            _callers.append(_f)
    _api = read(os.path.join(repo_root, "tools", "mwater", "api.mjs"))
    _ro = ("apiWrite" not in _api and "read-only: refusing" in _api
           and not re.search(r"method:\s*\"(PUT|PATCH|DELETE)\"", _api))
    check("the build calls nothing retired, and the mWater client is read-only",
          not _callers and _ro, "read-only",
          ("calls retired: " + ", ".join(_callers)) if _callers
          else ("read-only" if _ro else "api.mjs can write"),
          "tools/mwater/retired/README.md")

    # ---- no figure is empty without JavaScript (2026-09-25) ---------------
    # Every data-fig and data-param element carries its value in the static
    # HTML (tools/prerender_figures.py). Until 25 September all 239 were empty
    # to any reader that does not run the page's script.
    sys.path.insert(0, os.path.join(repo_root, "tools"))
    import prerender_figures as _pf
    _sf = _pf.figures(idx)
    _se = [k for _kind, k, t in _sf if not t.strip()]
    check("every data-fig and data-param carries its value in the static HTML",
          bool(_sf) and not _se, "none empty",
          f"{len(_se)} of {len(_sf)} empty" if _se else f"{len(_sf)} filled",
          "tools/prerender_figures.py --write; read without JavaScript")

    # ---- the footnotes state what the build applies (2026-09-24) ----------
    # "How this is worked out" footnotes sit beside the figures they govern.
    # Every number in them is rendered from data/build_config.json, and that
    # file is held here to what the build and the SDWS1 pipeline actually
    # applied - so a footnote cannot describe a rule the code no longer runs.
    _cfgp = os.path.join(repo_root, "data", "build_config.json")
    _cfg = json.loads(read(_cfgp)) if os.path.isfile(_cfgp) else {}
    _want = ["how-current", "how-portfolio", "how-joins", "how-wq", "how-people", "how-district"]
    _have = re.findall(r'<details class="expl howworked" id="([^"]+)">(.*?)</details>', idx, re.S)
    _ids = [i for i, _b in _have]
    check("the six 'How this is worked out' footnotes are on the page, closed",
          _ids == [i for i in _want if i in _ids] and set(_want) <= set(_ids)
          and all(b.lstrip().startswith("<summary>How this is worked out") for _i, b in _have),
          "all six", ", ".join(_ids) or "none")
    _typed = []
    for _i, _b in _have:
        # the value tools/prerender_figures.py writes into a span is rendered
        _txt = re.sub(r'<span data-fig="[^"]*">[^<]*</span>', "", _b)
        _txt = re.sub(r"<[^>]+>", " ", _txt)
        _txt = re.sub(r"SDWS\s*\d+", "", _txt)
        # a unit is not a parameter: "CFU per 100 mL"
        _txt = re.sub(r"per\s+100(?:&nbsp;|\s)*mL", "", _txt)
        _typed += [f"{_i}: {x}" for x in re.findall(r"\d[\d.,]*", _txt)]
        _typed += [f"{_i}: {e}" for e in re.findall(r'data-fig="([^"]*)"', _b)
                   if not e.startswith("BUILDCFG.")]
    check("every number in a footnote is rendered from the build configuration",
          not _typed, "none typed", "; ".join(_typed[:4]) if _typed else "none typed",
          "data/build_config.json, via data-fig")
    _bad = []
    try:
        sys.path.insert(0, os.path.join(repo_root, "tools"))
        import rebuild_pump_inputs as _rpi, rerun_wpop as _rw, rebuild_summary as _rs
        _wp = _cfg["worldpop"]; _rc = _cfg["roof_count"]
        if _rpi.ECOLI_PASS_MAX != _cfg["water_quality"]["ecoli_pass_max_cfu_per_100ml"]:
            _bad.append("E. coli threshold in rebuild_pump_inputs")
        if abs(_rpi.ROOF_TO_PEOPLE - _rc["people_per_household"] / _rc["roofs_per_household"]) > 1e-12:
            _bad.append("roof factor in rebuild_pump_inputs")
        if _rw.OVERLAP_M != _wp["neighbourhood_radius_m"] or _rw.RASTER_SHA256 != _wp["raster_sha256"]:
            _bad.append("neighbourhood radius or checksum in rerun_wpop")
        if _rs.DISTRICT_TO_SITE != _cfg["portfolio"]["districts"]:
            _bad.append("district map in rebuild_summary")
        # the pipeline itself, outside the repository: what it actually applies
        _pl = os.path.expanduser("~/sdws1/sdws1_population.py")
        if not os.path.isfile(_pl):
            _bad.append("the SDWS1 pipeline is not here to compare against")
        else:
            _src = read(_pl)
            _rad = re.search(r"^RADIUS_M\s*=\s*(\d+)", _src, re.M)
            _caps = re.search(r"^CAPS\s*=\s*(\{[^}]*\})", _src, re.M)
            _sha = re.search(r'^RASTER_OF_RECORD_SHA256\s*=\s*"([0-9a-f]+)"', _src, re.M)
            if not _rad or int(_rad.group(1)) != _wp["service_radius_m"]:
                _bad.append(f"service radius: pipeline {_rad and _rad.group(1)}")
            if not _caps or json.loads(_caps.group(1).replace("'", '"')) != _wp["caps"]:
                _bad.append(f"caps: pipeline {_caps and _caps.group(1)}")
            if not _sha or _sha.group(1) != _wp["raster_sha256"]:
                _bad.append("raster checksum pinned in the pipeline")
        _sum = json.loads(read(os.path.join(repo_root, "data", "sdws1_summary_equal.json")))
        if _sum.get("raster_sha256") != _wp["raster_sha256"] or _sum.get("raster") != _wp["raster"]:
            _bad.append("raster of the run of record")
        # the caps actually applied, pump by pump
        _pm = re.search(r"\bconst PUMPS\s*=\s*", idx); _wm = re.search(r"\bconst WPOP\s*=\s*", idx)
        _PP = json.loads(idx[_pm.end():idx.index("];", _pm.end()) + 1])
        _WW = json.loads(idx[_wm.end():idx.index("};", _wm.end()) + 1])
        _capx = [p["wp"] for p in _PP if p["wp"] in _WW and _WW[p["wp"]][2] != _wp["caps"].get(p["pump"])]
        if _capx:
            _bad.append(f"{len(_capx)} pump(s) allocated under a cap other than the configured one")
        _pp = re.search(r"\bim_cap:\{v:(\d+)", idx), re.search(r"\bcz_cap:\{v:(\d+)", idx)
        if not (_pp[0] and _pp[1]) or (int(_pp[0].group(1)), int(_pp[1].group(1))) != (_wp["caps"]["IndiaMark"], _wp["caps"]["Canzee"]):
            _bad.append("PARAMS im_cap / cz_cap")
        _models = {p.get("pump") for p in _PP}
        if not _models <= set(_cfg["portfolio"]["pump_models"]):
            _bad.append(f"fleet pump models outside the configured list: {sorted(_models - set(_cfg['portfolio']['pump_models']))}")
    except Exception as _e:                                    # noqa: BLE001
        _bad.append(f"could not compare: {_e}")
    check("the build configuration is what the build applied",
          not _bad, "all match", "; ".join(_bad[:4]) if _bad else "all match",
          "the footnotes render data/build_config.json; this holds it to the code")

    # ---- every portfolio pump carries its per-pump inputs (2026-09-23) -----
    # 742894057 joined with a blank allocation and a blank water-quality
    # result, and every figure over it was quietly biased downward. A join
    # may not do that again: no pump without a population allocation, and no
    # pump without an explicit tested / not tested status.
    def _const(name):
        mm = re.search(r"\bconst %s\s*=\s*" % name, idx)
        if not mm:
            return None
        i0 = mm.end(); close = "};" if idx[i0] == "{" else "];"
        return json.loads(idx[i0:idx.index(close, i0) + 1])
    _P = _const("PUMPS") or []
    _W = _const("WPOP") or {}
    _noalloc = [p["wp"] for p in _P if p["wp"] not in _W]
    check("every portfolio pump has a population allocation",
          not _noalloc, "all allocated",
          f"{len(_noalloc)} without: {', '.join(_noalloc[:4])}" if _noalloc else "all allocated",
          "tools/rerun_wpop.py reruns the allocation when a pump joins or leaves")
    _nowq = [p["wp"] for p in _P
             if p.get("wq_status") not in ("tested", "not tested")
             or (p.get("wq_status") == "tested") != (p.get("wq") in ("Pass", "Fail"))]
    check("every portfolio pump states whether its water was tested",
          not _nowq, "tested or not tested, on every pump",
          f"{len(_nowq)} without a consistent status: {', '.join(_nowq[:4])}" if _nowq
          else "every pump", "tools/rebuild_pump_inputs.py, from the live results form")

    # fleet churn against the archived editions
    import glob as _glob
    def _pumps(h):
        mm = re.search(r"\bconst PUMPS\s*=\s*\[", h)
        if not mm:
            return None
        i0 = h.index("[", mm.start()); dd = 0; jj = i0; ins = esc = False
        while jj < len(h):
            ch = h[jj]
            if ins:
                if esc: esc = False
                elif ch == "\\": esc = True
                elif ch == '"': ins = False
            elif ch == '"': ins = True
            elif ch == "[": dd += 1
            elif ch == "]":
                dd -= 1
                if dd == 0: break
            jj += 1
        try: return {x["wp"] for x in json.loads(h[i0:jj + 1])}
        except Exception: return None
    eds = []
    for f in sorted(_glob.glob(os.path.join(repo_root, "editions", "*.html"))):
        if "-routes" in f or "-portfolio" in f:
            continue
        sp = _pumps(read(f))
        if sp: eds.append((os.path.basename(f), sp))
    cur_set = _pumps(idx)
    if eds and cur_set:
        excluded = {x["wp"] for x in (rc.get("excluded") or [])}
        # a join is explained by the classification ledger: the pump met the
        # rule in tools/classify_register.py on a recorded date
        _clsp = os.path.join(repo_root, "data", "register_classification.json")
        joined = (json.loads(read(_clsp)).get("joined") or {}) if os.path.isfile(_clsp) else {}
        unexplained = []
        prev = None
        for name, sp in eds + [("index.html", cur_set)]:
            if prev is not None:
                for wp in (prev - sp):
                    if wp not in excluded:
                        unexplained.append(f"{wp} left at {name}")
                for wp in (sp - prev):
                    if wp not in joined:
                        unexplained.append(f"{wp} joined at {name}")
            prev = sp
        check("no point enters or leaves the fleet unexplained",
              not unexplained, "none",
              "; ".join(unexplained[:3]) if unexplained else "none",
              f"{len(eds) + 1} editions compared; departures must appear in "
              "register_corrections.json, joins in the classification ledger")

    # ---- 7c-0. an aggregate and its row set are ONE quantity --------------
    # S.n and len(PUMPS) are two sources for the same number. That is the
    # two-bases fault one layer down: the prose reads S.n, agg() reads PUMPS,
    # and a test that moves one and not the other cannot be clean. Every
    # aggregate that has a row set behind it is checked against that set.
    _P = js_const(idx, "PUMPS") or []
    _S = js_const(idx, "S") or {}
    _REG = js_const(idx, "REG") or {}
    if _P and _S:
        check("S.n equals the number of rows in PUMPS",
              _S.get("n") == len(_P), len(_P), _S.get("n"),
              "one quantity, one source - the prose reads S.n, agg() reads PUMPS")
        want_site = collections.Counter(p.get("site") for p in _P)
        got_site = _S.get("by_site") or {}
        bad = [k for k in set(want_site) | set(got_site)
               if want_site.get(k, 0) != got_site.get(k, 0)]
        check("S.by_site equals the site counts in PUMPS",
              not bad, dict(want_site),
              f"differs on {', '.join(sorted(bad)[:3])}" if bad else dict(got_site),
              "the scope buttons filter PUMPS; the prose quotes S.by_site")
        want_pump = collections.Counter(p.get("pump") for p in _P)
        got_pump = _S.get("by_pump") or {}
        badp = [k for k in set(want_pump) | set(got_pump)
                if want_pump.get(k, 0) != got_pump.get(k, 0)]
        check("S.by_pump equals the pump-type counts in PUMPS",
              not badp, dict(want_pump),
              f"differs on {', '.join(sorted(badp)[:3])}" if badp else dict(got_pump),
              "the India Mark cap applies by pump type")
        want_st = collections.Counter(p.get("status") for p in _P)
        got_st = _S.get("status") or {}
        bads = [k for k in set(want_st) | set(got_st)
                if want_st.get(k, 0) != got_st.get(k, 0)]
        check("S.status equals the status counts in PUMPS",
              not bads, dict(want_st),
              f"differs on {', '.join(sorted(bads)[:3])}" if bads else dict(got_st),
              "the donuts read agg(PUMPS); the prose quotes S.status")
        want_o6 = sum(1 for p in _P if (p.get("days") or -1) > 182)
        check("S.over6 equals the rows in PUMPS over six months",
              _S.get("over6") == want_o6, want_o6, _S.get("over6"),
              "days > 182, the same test agg() applies")
        # S.never is NOT the visit figure, and this check found that out:
        # it counts points with no works record of ANY kind - rehabilitation
        # and construction included - which is 57, while agg().never counts
        # points with no visit date, which is 6. Two quantities under one
        # name, which is the fault pattern this page has been bitten by three
        # times. Both are asserted against their own source, and the page is
        # checked for conflating them.
        want_nv = sum(1 for p in _P if p.get("days") is None)
        _M = js_const(idx, "METRICS") or {}
        check("agg().never - points with no visit - matches PUMPS",
              want_nv == len([p for p in _P if not p.get("last_visit")]),
              want_nv, len([p for p in _P if not p.get("last_visit")]),
              "days is null exactly when last_visit is null")
        check("S.never is the works-record count, and matches its metric",
              _S.get("never") == _M.get("points_no_works_record"),
              _M.get("points_no_works_record"), _S.get("never"),
              "no rehabilitation, construction, visit or repair - NOT the "
              "visit figure, which is agg().never")
        check("S.never and agg().never are not conflated in the prose",
              str(_S.get("never")) not in re.findall(
                  r"<b>(\d+)</b>\s*(?:water points|points|pumps)?\s*"
                  r"(?:with )?no visit", idx),
              "not conflated", "not conflated",
              f"S.never={_S.get('never')} counts works records; "
              f"agg().never={want_nv} counts visits")
    if _REG:
        _recon = _REG.get("recon")
        if isinstance(_recon, list):
            check("REG.recon carries the rows its count implies",
                  len(_recon) == len({r.get("wp") for r in _recon}),
                  f"{len(_recon)} distinct",
                  f"{len({r.get('wp') for r in _recon})} distinct",
                  "a reconciliation list with a duplicate counts a point twice")
    _CORR = js_const(idx, "CORR") or {}
    if _CORR:
        check("SUCC_CORRECTED equals REG.succ plus the corrections CORR lists",
              f"const SUCC_CORRECTED=REG.succ+CORR.corrected.length" in idx,
              "computed",
              "computed" if "SUCC_CORRECTED=REG.succ+CORR.corrected.length" in idx
              else "STORED",
              "it was a stored 732 sitting beside the data it duplicated")

    # ---- 7c-1. sensitivity figures are computed, never stored -------------
    # WPOP_C250 was a stored constant captioned "Canzee 250 and India Mark
    # 500" and computed with India Mark at 300. It was published wrong by
    # 8,478 people for six days and nothing caught it, because a stored
    # constant has nothing to disagree with. Every cap-sensitivity figure is
    # computed at render time now, from WPOP and the caps in PARAMS.
    stored = re.findall(r"const (WPOP_[A-Z0-9_]+)\s*=\s*\d", idx)
    check("no sensitivity figure is stored as a constant",
          not stored, "none stored",
          f"stored: {', '.join(stored[:3])}" if stored else "none stored",
          "a stored figure and its caption can disagree, and did")
    check("the sensitivity figures are computed from WPOP and the caps",
          "function wpopAt(" in idx and idx.count("wpopAt(") >= 3,
          "computed", "computed" if "function wpopAt(" in idx else "MISSING",
          "wpopAt(imCap, czCap) reads WPOP and the pump type")
    check("every wpopAt call takes its caps from PARAMS, not a literal",
          not re.findall(r"wpopAt\(\s*\d+\s*,\s*\d+\s*\)", idx),
          "no literal caps",
          "; ".join(re.findall(r"wpopAt\([^)]*\)", idx)[:2])
          if re.findall(r"wpopAt\(\s*\d+\s*,\s*\d+\s*\)", idx)
          else "no literal caps",
          "the caption and the computation must read the same declared cap")

    # ---- 7c-bis. every declared constant carries its citation -------------
    # A constant with a citation is correct; a constant without one is
    # indistinguishable from a typo. PARAMS is the only place a non-live
    # figure may be declared, and every entry must say where it came from and
    # when it was set.
    pm = re.search(r"const PARAMS=\{(.*?)\n\};", idx, re.S)
    if pm:
        entries = re.findall(r"\n\s*([a-z_0-9]+):\{(.*?)\n?\s*\},",
                             pm.group(1) + ",", re.S)
        check("PARAMS is not empty", len(entries) >= 6, ">=6 entries",
              f"{len(entries)} entries", "the declared constants of this page")
        nosrc = [k for k, body in entries
                 if "source:" not in body or len(body.split("source:")[1]) < 40]
        check("every PARAMS entry carries a source", not nosrc, "all sourced",
              f"missing on {', '.join(nosrc[:3])}" if nosrc else "all sourced",
              "VPA-DD section, methodology clause, technical note, or the "
              "decision that set it")
        noset = [k for k, body in entries if "set:" not in body]
        check("every PARAMS entry carries the date it was set", not noset,
              "all dated", f"undated: {', '.join(noset[:3])}" if noset
              else "all dated", "a parameter without a date cannot be reviewed")
    else:
        check("PARAMS exists on the page", False, "present", "MISSING",
              "the one place a non-live figure may be declared")

    # the two figure backlogs may only shrink
    for f, what in (("data/figure_backlog.json", "rendered figures with no source"),
                    ("data/prose_figure_backlog.json", "figures typed into prose")):
        pth = os.path.join(repo_root, f)
        if os.path.exists(pth):
            doc = json.loads(read(pth))
            check(f"{os.path.basename(f)} is dated and non-empty",
                  bool(doc.get("recorded")) and "values" in doc, "dated",
                  doc.get("recorded") or "undated",
                  f"{len(doc.get('values', {}))} {what}; this list may only shrink")

    # ---- 7d. the Endur'O count is stated once, from the disposition file ---
    # Earlier editions carried 138, 111 and 131 in different places. The count
    # must come from data/enduro_disposition.csv and appear with one value.
    disp = os.path.join(repo_root, "data", "enduro_disposition.csv")
    if os.path.exists(disp):
        import csv as _csv
        with open(disp, encoding="utf8") as fh:
            rows = list(_csv.DictReader(fh))
        active = [r for r in rows if r["disposition"] in ("matched", "new", "duplicate")]
        n = len(active)
        # ENDURO is now generated from data/enduro_manual.json by
        # tools/render_enduro.py, so it is JSON with quoted keys. Assert the
        # whole chain: disposition file -> manual file -> page.
        man = os.path.join(repo_root, "data", "enduro_manual.json")
        mdoc = json.loads(read(man)) if os.path.exists(man) else {}
        mval = (mdoc.get("figures", {}).get("systems", {}) or {}).get("v")
        check("the manual Endur'O file matches the disposition file",
              mval == n, n, mval if mval is not None else "not in the file",
              "data/enduro_disposition.csv, matched+new+duplicate")
        m = re.search(r'const ENDURO\s*=\s*\{"systems":(\d+)', idx)
        check("Endur'O count matches the disposition file",
              bool(m) and int(m.group(1)) == n, n,
              m.group(1) if m else "ENDURO not found",
              "written into the page by tools/render_enduro.py")
        check("the Endur'O figures carry a date, an owner and a document",
              bool(mdoc.get("as_at")) and bool(mdoc.get("supplied_by"))
              and bool(mdoc.get("doc")) and bool(mdoc.get("max_age_days")),
              "dated and owned",
              "dated and owned" if mdoc.get("as_at") else "MISSING",
              "hand-entered figures may be manual; they may not age unnoticed")
        check("the page states the Endur'O as-at date where the figures are",
              "as at ${ENDURO_SRC.as_at}, supplied by" in idx
              and idx.count("enduroAsAt()") >= 3, "stated",
              "stated" if "enduroAsAt()" in idx else "MISSING",
              "a reader never meets one of these figures without its date")
        for stale in ("138 systems", "111 southern", "90,000 across 111"):
            check(f"withdrawn Endur'O figure absent: {stale!r}", stale not in idx,
                  "absent", "FOUND" if stale in idx else "absent",
                  "superseded by the disposition file")
    else:
        check("data/enduro_disposition.csv present", False, "present", "MISSING",
              "the Endur'O count has no source file")

    # ---- 7e. the wording a verifier reads ---------------------------------
    # Guardians log service-visit requests in the call form using a word that,
    # read literally, implies the water is unsafe. The records are field evidence
    # and are never edited; the page carries a PRECOMPUTED normalised status and
    # links each row to the mWater record. The raw wording is not embedded at
    # all, so this checks the WHOLE FILE, not just rendered text.
    BANNED = re.compile(r"d[ie]s?infect|d.{0,2}sinfe+ction|desinfe+ction", re.I)
    for f, src in (("index.html", idx), ("portfolio.html", prt)):
        hits = [m.group(0) for m in BANNED.finditer(src)]
        check(f"{f}: banned wording absent from the whole file", not hits,
              "absent anywhere", f"{len(hits)} found: {sorted(set(hits))[:3]}" if hits else "absent",
              "status is precomputed; the raw text lives only in mWater")

    check("partial table renders the precomputed status",
          "esc(p.status)" in idx and "esc(p.problem)" not in idx and '"problem":' not in idx,
          "esc(p.status), no raw field",
          "raw field still embedded" if '"problem":' in idx
          else ("esc(p.problem) still rendered" if "esc(p.problem)" in idx else "esc(p.status), no raw field"),
          "the raw wording reaches the reader only via the mWater link")
    check("each partial row links to its mWater record",
          "recLink(p.rid)" in idx and "const MWR" in idx,
          "recLink(p.rid) present", "present" if "recLink(p.rid)" in idx else "MISSING",
          "the original free text is one click away, unaltered")

    # TOOL33 may be named as a supporting reference but never as the applied
    # basis: A6.4-AMT-009 v01.0 is what the parameter values are taken from.
    for f, src in (("index.html", idx), ("portfolio.html", prt)):
        bad_basis = re.findall(r"TOOL33[^.<]{0,80}(?:applied basis|basis we apply|is the basis)", src, re.I)
        check(f"{f}: TOOL33 not claimed as the applied basis", not bad_basis,
              "absent", f"{len(bad_basis)} found" if bad_basis else "absent",
              "A6.4-AMT-009 v01.0 is the applied basis")

    # ---- 7f. the map reconciles with the report ---------------------------
    # One portfolio, one population basis. The map draws the managed universe
    # only, and its carbon / non-carbon split must add back to the whole.
    mw = re.search(r"const\s+WP\s*=\s*(\[.*?\])\s*;", prt, re.S)
    if not mw:
        check("map marker array parsed", False, "const WP", "not found")
    else:
        WPm = json.loads(mw.group(1))
        n_map = len(WPm)
        n_unmanaged = sum(1 for w in WPm if w.get("m") != 1)
        n_carbon = sum(1 for w in WPm if w.get("cb") == 1)
        n_non = n_map - n_carbon
        check("map draws only the managed portfolio", n_unmanaged == 0, 0, n_unmanaged,
              "register-only points must not be drawn")
        check("map carbon + non-carbon = every point drawn",
              n_carbon + n_non == n_map, n_map, n_carbon + n_non,
              f"{n_carbon} carbon + {n_non} non-carbon")
        # the toggle may only move non-carbon points, i.e. Marolinta
        moved = {w.get("r") for w in WPm if w.get("cb") != 1}
        check("the carbon toggle moves Marolinta only", moved <= {"androy"},
              "{'androy'}", str(moved or "{}"),
              "it must not add or remove Fort-Dauphin or Maroantsetra points")
        # every point drawn is one the report counts
        # 742896839 exists in mWater WITH a GPS fix (ac01735a-c76c-4beb-aed6-
        # 70c88879bd48) but its _managed_by is "all", not the MadAvance group, so
        # every group-filtered export skips it. Its coordinates were read from
        # the register record directly on 21 September 2026 and the point is now
        # drawn from those, so the map shows the whole estate. The group
        # membership is still wrong at source - act-742896839 tracks that - and
        # until it is fixed a rebuilt portfolio.html will drop the point again.
        # This assertion is what catches that: it stays at the full count.
        check("map point count agrees with the report's managed set",
              n_map == S["points"], S["points"], n_map,
              "every managed point is drawn")
        # photographs come from the completed-works questions only
        nph = sum(1 for w in WPm if w.get("p"))
        check("every drawn photo is a completed-works image",
              all((not w.get("p")) or w.get("pq") for w in WPm),
              "each photo carries its source question", f"{nph} photos",
              "positive filter: rehabilitation form completed-works / water-flowing")
        # Photographs are drawn in a fixed order of preference. Rank 1 is the
        # rehabilitation form's completed-works / water-flowing questions;
        # 2 the preventive-maintenance after-works question; 3 the repair-after-
        # breakdown after-works questions; 4 the register record's own photo,
        # which is a last resort and carries no completed-works guarantee.
        # A photo with no rank cannot be traced to a question, so it must not exist.
        unranked = [w["c"] for w in WPm if w.get("p") and w.get("pr") not in (1, 2, 3, 4)]
        check("every drawn photo carries its source rank", not unranked,
              "all ranked 1-4", f"{len(unranked)} unranked" if unranked else "all ranked 1-4",
              "rank records which form the image came from")
        ranked = collections.Counter(w.get("pr") for w in WPm if w.get("p"))
        # The explanation boxes no longer carry these counts as literals: the
        # page fills them from the same arrays the map draws, so there is one
        # source rather than two kept in step by assertion. What must still be
        # guarded is that the rendering works - a missing span or an unassigned
        # id would leave an em dash on the page where a number belongs.
        LIVE_IDS = ["n-wp", "n-wp2", "n-wp3", "n-mora", "n-edreg", "n-edsys",
                    "n-carbon", "n-noncarbon", "n-r1", "n-r2", "n-r3", "n-r4",
                    "n-photo", "n-nophoto"]
        missing_span = [i for i in LIVE_IDS if f'id="{i}"' not in prt]
        check("map prose: every live-count placeholder exists in the markup",
              not missing_span, f"{len(LIVE_IDS)} placeholders",
              f"missing: {', '.join(missing_span)}" if missing_span else f"{len(LIVE_IDS)} placeholders",
              "a placeholder with no span renders nothing")
        unset = [i for i in LIVE_IDS if f"set('{i}'" not in prt]
        check("map prose: every placeholder is assigned at page load",
              not unset, f"{len(LIVE_IDS)} assigned",
              f"unassigned: {', '.join(unset)}" if unset else f"{len(LIVE_IDS)} assigned",
              "an unassigned placeholder leaves an em dash where a number belongs")
        check("map prose: the filler reads the drawn arrays, not constants",
              all(f"{n}." in prt for n in ("WP", "MORA", "EDREG", "EDSYS"))
              and "liveCounts" in prt,
              "counts derived from WP/MORA/EDREG/EDSYS", "present" if "liveCounts" in prt else "MISSING",
              "one source for the map and its explanation")
        # no stale literal may sit beside a live placeholder
        stale = re.search(r'id="n-(?:wp|carbon|photo)"[^>]*>\s*\d', prt)
        check("map prose: no literal left inside a live placeholder",
              stale is None, "placeholders empty until filled",
              stale.group(0)[:30] if stale else "placeholders empty until filled")

    # population: the map's totals must equal the report's, and split to it
    def money(t, *pats):
        for pat in pats:
            m2 = re.search(pat, t)
            if m2: return int(m2.group(1).replace(",", ""))
        return None
    total = S["reported_after_cap"]
    carbon_p = money(prt, r"<b>([\d,]+)</b>\s*of it is the carbon portfolio")
    non_p = money(prt, r"remaining <b>([\d,]+)</b> is Marolinta")
    # The dashboard-reconciliation block was removed from the donor page (the
    # mWater dashboard now reports on the same WorldPop basis, so there is no
    # difference left to explain). The figure is still asserted, now from the
    # paragraph that survives; the old phrasing stays first so an older build
    # still validates.
    shown = money(prt, r"this page reports <b>([\d,]+)</b>",
                  r"<b>([\d,]+) is the conservative figure")
    check("map population total equals the report", shown == total, total, shown,
          "sdws1_summary_equal.json reported_after_cap")
    check("map carbon + non-carbon population = the total",
          carbon_p is not None and non_p is not None and carbon_p + non_p == total,
          total, f"{carbon_p} + {non_p} = {(carbon_p or 0)+(non_p or 0)}")

    # ---- 7g. operator is group membership, never water point type ---------
    # MadAvance and Endur'O assets are distinguished by mWater group membership.
    # Type is not disjoint between operators - Endur'O will hold hand pumps,
    # MadAvance holds Canzee, India Mark and boreholes - so any figure derived
    # from type where operator is meant is wrong by construction.
    check("operator convention is recorded on the page",
          'id="opsec"' in idx and "_managed_by" in idx and "group membership" in idx,
          "stated with the rule", "present" if 'id="opsec"' in idx else "MISSING",
          "operator = mWater group membership; alt_id_org is a label only")

    # The map's operator split must come from the flags we set from group
    # membership (m / cb), not from the type field t.
    if mw:
        by_type = re.search(r"filter\w*\([^)]*\bt\s*===?\s*[\'\"](?:Canzee|IndiaMark)", prt)
        check("no map figure is derived from water point type", by_type is None,
              "operator from group membership", 
              f"type filter found: {by_type.group(0)[:40]}" if by_type else "none found",
              "type describes hardware, not who maintains it")
        typed_operator = [w for w in WPm if w.get("t") in ("kiosk",) and w.get("m") == 1]
        check("no managed point is classified by a shared type",
              not typed_operator, 0, len(typed_operator),
              "a kiosk and a tapstand can share a type across operators")

    # ---- 7h. 874 is retired, and the box agrees with the report ----------
    # 874 was 736 managed hand pumps + the old ENDURO.systems of 138 - a figure
    # that mixed hand pumps with piped systems and embedded a withdrawn count.
    # Both halves are now superseded. It must not come back.
    for f, src in (("index.html", idx), ("portfolio.html", prt)):
        hits = re.findall(r"(?<![0-9a-fA-F.])874(?![0-9a-fA-F.])", src)
        check(f"{f}: retired figure 874 absent", not hits, "absent",
              f"{len(hits)} found" if hits else "absent",
              "was 736 + the withdrawn 138; both superseded")

    # the estate box must carry the report's own numbers, not its own
    if mw:
        managed = S["points"]
        for needle, why in ((f"<b>{managed} today</b>", "phasing counts the managed portfolio"),
                            ("target programme scale", "not 'full' programme scale")):
            check(f"estate box: {needle!r}", needle in prt, "present",
                  "present" if needle in prt else "MISSING", why)
        m_pct = re.search(r"([\d.]+)% of target programme scale", prt)
        want = round(100.0 * managed / 4000, 1)
        check("estate box phasing = managed / 4,000",
              bool(m_pct) and abs(float(m_pct.group(1)) - want) < 0.05,
              f"{want}%", f"{m_pct.group(1)}%" if m_pct else "not found",
              f"{managed}/4000")
        # No register-only language in the estate box itself. The phrase
        # "register records" is legitimate elsewhere - the dashboard
        # reconciliation needs it to explain why mWater reports more - so this
        # is scoped to the phasing box rather than the whole file.
        pb = prt[prt.find('<div class="phase">'):prt.find("</div>", prt.find("Every point, 15"))] \
             if '<div class="phase">' in prt else ""
        # Only phrases that describe non-managed entries as part of the estate.
        # "has no register record" is the opposite - it explains the 736/735 gap.
        for phrase in ("survey and identification", "survey entries",
                       "abandoned point", "being drilled", "not under management"):
            check(f"estate box free of register-only language: {phrase!r}",
                  phrase not in pb, "absent from the phasing box",
                  "FOUND" if phrase in pb else "absent",
                  "the box describes only what we manage")

    # ---- 7i. the calendar photograph count agrees with its own parts ------
    # The headline count was published as 2,348 while the three per-question
    # figures beneath it summed to 2,367. A total that disagrees with its own
    # breakdown is exactly what this file exists to catch.
    # Match on the numbers, not on three fixed sentences: the prose around
    # them has been rewritten twice and each time this check broke on the
    # wording rather than on the arithmetic it exists to guard.
    m_tot = re.search(r"<b>([\d,]+)</b><span>calendar photographs on file", idx)
    seg = None
    i_ = idx.find("Where the photographs live")
    if i_ >= 0:
        seg = idx[i_:i_ + 1400]
    parts = re.findall(r"carries\s*<b>([\d,]+)</b>", seg or "")
    if m_tot and len(parts) == 3:
        tot = int(m_tot.group(1).replace(",", ""))
        got = sum(int(x.replace(",", "")) for x in parts)
        check("calendar photograph total equals its per-question parts",
              tot == got, tot, got, "headline must equal 2.15.6 + 2.15.5 + 1.3.1.3")
    else:
        check("calendar photograph total equals its per-question parts", False,
              "total and three parts", "not all found",
              "headline must equal 2.15.6 + 2.15.5 + 1.3.1.3")

    # ---- 7j. the machine extraction stays out of the figures of record ----
    # Every extracted figure must carry the dagger, and the dagger must say
    # plainly that it is not the figure of record and feeds no ER calculation.
    if "Machine extraction from the calendar photographs" in idx:
        blk_s = idx.find("Machine extraction from the calendar photographs")
        blk = idx[blk_s:idx.find("</section>", blk_s)]
        stats = re.findall(r'<div class="stat"><b>[^<]+</b><span>(.*?)</span></div>', blk)
        undaggered = [t for t in stats if "&dagger;" not in t]
        check("every machine-extracted headline figure carries the footnote",
              not undaggered, f"{len(stats)} figures",
              f"{len(undaggered)} without a footnote" if undaggered else f"{len(stats)} figures",
              "an unfootnoted figure reads as a figure of record")
        for phrase, why in (
                ("Not the figure of record", "must disclaim being the figure of record"),
                ("not used in any emission reduction calculation", "must disclaim ER use"),
                ("accuracy assessment in progress", "must name the assessment")):
            check(f"extraction footnote states: {phrase!r}", phrase in blk,
                  "present", "present" if phrase in blk else "MISSING", why)
        check("no emission-reduction figure of record derives from the extraction",
              "no published emission-reduction or days-operational figure of record derives from these files" in blk,
              "asserted on the page", "asserted" if "derives from these files" in blk else "MISSING",
              "DO_p,y is unchanged by the extraction")

    # ---- 7k. DO_p,y is indexed by premises type, not by water point -------
    # An earlier edition described SDWS 27 as a per-water-point parameter and
    # said the 347-day ceiling applied for want of calendars. Both were wrong:
    # p is the premises type (the same p as SDWS 25 and SDWS 26), and the
    # ceiling attaches to the O&M-log evidence route, which no amount of
    # calendar coverage lifts. These assertions stop either error returning.
    check("DO_p,y is described as indexed by premises type",
          "p is the premises type" in idx, "present",
          "present" if "p is the premises type" in idx else "MISSING",
          "the same p as SDWS 25 and SDWS 26, not the water point")
    for bad in ("347 days operational per point", "capped at 347 days per point",
                "347 days per point"):
        check(f"per-point framing of the 347 ceiling absent: {bad!r}",
              bad not in idx, "absent", "FOUND" if bad in idx else "absent",
              "the ceiling belongs to the evidence route, not the point")
    check("the DO_p,y correction is recorded, not applied silently",
          "was described wrongly on this page" in idx, "recorded in the audit trail",
          "present" if "was described wrongly on this page" in idx else "MISSING",
          "corrections are stated, as the allocation error was")
    check("the registered methodology version is stated",
          "ERSDWS v1.0</b>, the version the VPA is registered under" in idx,
          "stated", "present" if "the version the VPA is registered under" in idx else "MISSING",
          "the Design Review form names v1.0 as the applied methodology")
    check("the v2.0 entry-into-force date is stated",
          "7 October 2026" in idx and "90 days from publication" in idx,
          "stated", "present" if "7 October 2026" in idx else "MISSING",
          "v2.0 s3.3.1: 90 days from publication on 9 July 2026")
    # SDWS 27 is stated as the VPA-DD has it, not as our route to it. The
    # sampling provision attaches to operation sensors; saying it attaches to
    # the calendars, or that the estate must be covered, would both be wrong.
    check("SDWS 27 states the applied value of 347 days",
          "The value applied in the VPA-DD is 347 days" in idx, "stated",
          "present" if "value applied in the VPA-DD is 347 days" in idx else "MISSING",
          "347 is the default for a project without operation sensors")
    check("the 90/10 sampling provision is attributed to sensors",
          "(90/10) sample basis" in idx and "attaches to <b>sensors</b>" in idx,
          "stated", "present" if "attaches to <b>sensors</b>" in idx else "MISSING",
          "the provision is not a licence to sample calendars")
    for bad in ("record covering the estate is required", "invokes &sect;4.2 nowhere"):
        check(f"superseded SDWS 27 reading absent: {bad!r}", bad not in idx,
              "absent", "FOUND" if bad in idx else "absent",
              "state the facts, not our route to them")

    # ---- 7l. the extraction figures on the page match the files -----------
    # The page once carried impossible-cell rates from a run whose output files
    # had since been overwritten, and nothing caught it because the checker did
    # not read the CSVs. It does now: every extraction figure on the page is
    # asserted against data/calendar_extraction_figures.json, and that file is
    # asserted against the summary CSV beside it.
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    figp = os.path.join(here, "data", "calendar_extraction_figures.json")
    sump = os.path.join(here, "data", "calendar_extraction_summary.csv")
    if not os.path.exists(figp) or not os.path.exists(sump):
        check("extraction figures file present", False, "data/calendar_extraction_figures.json",
              "MISSING", "the page's extraction numbers must be traceable to a file")
    else:
        fig = json.load(open(figp))
        import csv as _csv
        rows = list(_csv.DictReader(open(sump)))
        # the JSON must describe the CSV beside it
        check("extraction JSON matches the summary CSV: pump-periods",
              fig["pump_periods"] == len(rows), fig["pump_periods"], len(rows))
        check("extraction JSON matches the summary CSV: water points",
              fig["water_points"] == len({r["water_point"] for r in rows}),
              fig["water_points"], len({r["water_point"] for r in rows}))
        csv_dno = sum(int(r["days_not_operational"]) for r in rows)
        check("extraction JSON matches the summary CSV: days not operational",
              fig["days_not_operational"] == csv_dno, fig["days_not_operational"], csv_dno)
        # and the page must state what the JSON says
        def fmt_n(v):
            return f"{v:,}" if isinstance(v, int) and v >= 1000 else str(v)
        # which cell-count keys exist depends on the basis the figures were
        # computed on; block 7ra asserts the observed-basis ones in detail
        keys = [("pump_periods", "pump-periods"),
                ("water_points", "water points"),
                ("days_not_operational", "days not operational"),
                ("days_illegible", "days illegible"),
                ("images_readable", "images readable"),
                ("images_with_day_calls", "images with day calls"),
                ("impossible_cells", "impossible cells")]
        keys += ([("real_cells", "real day cells")] if "real_cells" in fig
                 else [("observed_cells", "observed day cells")])
        # Every number the calendar generator emits is now wrapped in its own
        # data-artefact span, so the literal no longer sits directly inside
        # <b>. Match against a span-stripped copy: the assertion is that the
        # value is on the page, not how it is marked up.
        _idx_nospan = re.sub(r"<span data-artefact=\"[^\"]*\">(.*?)</span>",
                             r"\1", idx, flags=re.S)
        for key, label in keys:
            want = fmt_n(fig[key])
            there = f"<b>{want}</b>" in _idx_nospan
            check(f"page states the extraction {label}: {want}",
                  there, want, want if there else "NOT ON THE PAGE",
                  "from data/calendar_extraction_figures.json")
        pct_keys = ([("impossible_marked_pct", "impossible-cell marked rate"),
                     ("real_marked_pct", "real-cell marked rate")]
                    if "real_marked_pct" in fig else
                    [("probe_marked_pct", "impossible-cell marked rate"),
                     ("observed_marked_pct", "observed-cell marked rate")])
        pct_keys.append(("implied_true_marked_pct", "implied true marked rate"))
        for key, label in pct_keys:
            want = f"{fig[key]:.2f}%"
            check(f"page states the {label}: {want}", f"<b>{want}</b>" in idx, want,
                  want if f"<b>{want}</b>" in idx else "NOT ON THE PAGE",
                  "from data/calendar_extraction_figures.json")

    # ---- 7m. the small-scale Type 3 annual ceiling ------------------------
    # VPA-DD s.A.4 caps the VPA at 60,000 tCO2e in any year. The page recomputes
    # the headroom every build; this recomputes it independently and fails if
    # the computed figure has passed the cap without the attention-list entry
    # that raises it, or if the machinery that computes it has been removed.
    CAP_T, ER_ANOSY, ER_MARO = 60000.0, 31.3, 27.9
    # The conditional attention entry became an action row with a stored
    # closing condition, so the ceiling is now raised and lowered by the
    # evaluator rather than by a branch in the page script.
    # The cap is now declared in PARAMS with its citation (VPA-DD sect.A.4)
    # and CAP_T reads it, so the constant is checked where it is declared.
    for needle, why in (("cap_t:{v:60000", "the cap constant, declared in PARAMS"),
                        ("const CAP_T=PARAMS.cap_t.v", "CAP_T reads PARAMS"),
                        ('id="capnote"', "the audit-trail line"),
                        ('id="act-type3-cap"', "the action row that raises it"),
                        ("er_percent_of_type3_cap", "its closing condition")):
        check(f"ceiling machinery present: {why}", needle in idx, "present",
              "present" if needle in idx else "MISSING",
              "the headroom must be recomputed every build, not written in")
    page_S = js_const(idx, "S") or {}
    if page_S:
        bs = page_S.get("by_site", {})
        er = bs.get("Fort-Dauphin", 0) * ER_ANOSY + bs.get("Maroantsetra", 0) * ER_MARO
        pts = bs.get("Fort-Dauphin", 0) + bs.get("Maroantsetra", 0)
        pct = 100.0 * er / CAP_T
        # the entry is gated on capNear (>=80%); if we are over the cap it must
        # be in the attention list unconditionally, not behind that gate
        over = er > CAP_T
        raised = "capNear&&['crit'" in idx
        check("emission reductions within the small-scale Type 3 annual cap",
              not over, f"<= {CAP_T:,.0f} tCO2e/yr",
              f"{er:,.0f} tCO2e/yr over {pts} points ({pct:.1f}%)",
              "VPA-DD s.A.4; raise with the Head of Carbon before it is reached")
        check("ceiling entry present if the cap is exceeded",
              (not over) or raised, "raised in the attention list",
              "raised" if raised else "NOT RAISED",
              "over the cap the entry must not stay behind the 80% gate")

    # ---- 7n. layout, held to the same discipline as the numbers -----------
    # These three kept regressing across rebuilds because nothing enforced them.
    # (a) the photograph band and the fleet summary lead the page; (b) text runs
    # the full measure, no ch-capped blocks; (c) standing explanation is behind
    # a <details> so the page reads short and expands on demand.
    body_i = idx.find("<body")
    secs = [(m.start(), m.group(0)) for m in re.finditer(r"<section[^>]*>", idx[body_i:])]
    first_two = " ".join(t for _, t in secs[:2])
    check("photograph band is the first section on the page",
          'id="photosec"' in (secs[0][1] if secs else ""),
          'id="photosec"', secs[0][1][:40] if secs else "no sections",
          "it must sit above everything else, not below the weekly tables")
    fleet_at = idx.find("The fleet at a glance", body_i)
    first_other = min((idx.find(h, body_i) for h in ("<h2>This week</h2>", "<h2>Attention list</h2>")
                       if idx.find(h, body_i) > 0), default=10 ** 9)
    check("fleet at a glance sits above the first content section",
          0 < fleet_at < first_other, "before This week / Attention list",
          "before" if 0 < fleet_at < first_other else "AFTER",
          "photograph band then fleet, then everything else")

    # (b) no text block may be capped narrower than the page measure
    narrow = re.findall(r"(\.(?:note|sub|sechead\s+p)\s*\{[^}]*max-width\s*:\s*\d+\s*ch)", idx)
    check("no text block is capped narrower than the page measure",
          not narrow, "no ch-capped text rules",
          f"{len(narrow)} found: {narrow[0][:40]}" if narrow else "no ch-capped text rules",
          "text runs the full .wrap measure")

    # (c) standing explanation is collapsed
    n_expl = len(re.findall(r'<details class="expl">', idx))
    check("standing explanation is collapsed into <details>", n_expl >= 10,
          ">= 10 collapsed blocks", n_expl,
          "method notes, mapping rules and provenance prose expand on demand")
    for sec, why in (("popsec", "the population method and ex ante footnote"),
                     ("calsec", "the SDWS 27 method and the machine extraction"),
                     ("strokesec", "the stroke-test method"),
                     ("tracesec", "the provenance notes"),
                     ("pousec", "the sampling methodology"),
                     ("fnrbsec", "the fNRB explanation")):
        a = idx.find(f'id="{sec}"')
        if a < 0:
            a = idx.find(f'id="{sec}"')
        blk_end = idx.find("</section>", a) if a > 0 else -1
        # fnrbsec is a panel inside overlapsec; look forward a fixed window instead
        seg = idx[max(0, a - 400):blk_end if blk_end > 0 else a + 6000] if a > 0 else ""
        check(f"{sec}: {why} is behind a <details>",
              '<details class="expl">' in seg, "collapsed",
              "collapsed" if '<details class="expl">' in seg else "STILL OPEN",
              "what explains method collapses; what changes weekly stays open")

    # ---- 7o. every figure with a named source file is checked against it ---
    # The extraction drift was not a special case, it was the first one noticed.
    # Any file the page names as the source of a number must be in the repo and
    # must be read here, or the two can diverge silently.
    cov_p = os.path.join(here, "data", "gardien_calendar_coverage.csv")
    if not os.path.exists(cov_p):
        check("gardien calendar coverage file present", False,
              "data/gardien_calendar_coverage.csv", "MISSING",
              "the page names it as the source of 674 / 62 / 385")
    else:
        import csv as _csv2
        cr = list(_csv2.DictReader(open(cov_p)))
        have = [r for r in cr if r["has_calendar_photo"] == "True"]
        none_ever = len(cr) - len(have)
        stale = [r for r in have if r["days_since"] and int(r["days_since"]) > 182]
        photos_managed = sum(int(r["photos_total"] or 0) for r in cr)
        for got, label in ((len(cr), "points"), (len(have), "with a calendar photograph"),
                           (none_ever, "with none ever"), (len(stale), "stale beyond six months")):
            want = f"{got:,}" if got >= 1000 else str(got)
            check(f"calendar coverage on the page matches the file: {label} = {want}",
                  f"<b>{want}</b>" in idx, want,
                  want if f"<b>{want}</b>" in idx else "NOT ON THE PAGE",
                  "from data/gardien_calendar_coverage.csv")
        # the page states the inventory total; the coverage file counts only
        # photographs on managed points. Both are stated, and both must be right.
        check("the two photograph counts are distinguished on the page",
              f"<b>{photos_managed:,}</b>" in idx and "<b>2,367</b>" in idx,
              f"{photos_managed:,} on managed points and 2,367 on file",
              "both stated" if f"<b>{photos_managed:,}</b>" in idx else f"{photos_managed:,} NOT STATED",
              "2,367 is every calendar photograph; the rest sit on unregistered points")

    # the corrections file the page says is versioned alongside it must exist
    corr_p = os.path.join(here, "data", "register_corrections.json")
    check("register_corrections.json is versioned alongside the report",
          os.path.exists(corr_p), "present", "present" if os.path.exists(corr_p) else "MISSING",
          "the page claims it is; it must be true")
    if os.path.exists(corr_p):
        cj = json.load(open(corr_p))
        pj = js_const(idx, "CORR") or {}
        for k in ("corrected", "excluded", "eligibility_flags"):
            a_ = len(cj.get(k, [])) if isinstance(cj.get(k), list) else cj.get(k)
            b_ = len(pj.get(k, [])) if isinstance(pj.get(k), list) else pj.get(k)
            check(f"corrections file matches the page: {k}", a_ == b_, a_, b_,
                  "the page is built from this file, so they cannot differ")

    # ---- 7p. the design review is NOT ours to track -----------------------
    # Removed 2026-09-23 with the section itself. This report tracks what the
    # field operation must measure and whether it is measuring it; the design
    # review, the CAR and CL items, round state and submission status are the
    # Head of Carbon's and showing them here implied we tracked them. What
    # replaces it is a parameter readiness view: can we supply the data.
    check("the design review section stays out",
          'id="gsrevsec"' not in idx and "CAR#1" not in idx, "absent",
          "absent" if 'id="gsrevsec"' not in idx else "BACK ON THE PAGE",
          "out of remit: the Head of Carbon owns the review")
    check("the parameter readiness view replaces it",
          'id="carbon-params"' in idx
          and "Data the carbon programme needs from us" in idx, "present",
          "present" if 'id="carbon-params"' in idx else "MISSING",
          "one row per parameter we must evidence, coverage derived")
    # every row's coverage must come from a population, never a stored number
    cpj = os.path.join(here, "data", "carbon_parameters.json")
    if os.path.exists(cpj):
        cp = json.loads(read(cpj))
        popdoc = json.loads(read(os.path.join(here, "data", "populations.json")))
        known = set(popdoc["populations"])
        bad = [p["id"] for p in cp["parameters"]
               if (p.get("population") and p["population"] not in known)
               or (p.get("relevant") and p["relevant"] not in known)]
        check("every parameter row names populations that exist",
              not bad, "all resolve", f"{len(bad)} unresolved" if bad else "all resolve",
              ", ".join(bad[:3]) if bad else "coverage is derived, never typed")
        owned = [p["id"] for p in cp["parameters"] if not p.get("owner")]
        check("every parameter row names an owner",
              not owned, "all named", f"{len(owned)} unowned" if owned else "all named",
              "a gap with no owner closes by itself, which is to say never")

    # ---- 7q. the transcription page must not leak the machine output -------
    # The whole point of the human round is that it is independent. If any
    # extracted value reaches the page the comparison is worthless, so the
    # shipped files are checked against the extraction figures themselves.
    tr_dir = os.path.join(here, "transcription")
    tr_html = os.path.join(tr_dir, "index.html")
    tr_man = os.path.join(tr_dir, "calendars.json")
    if not (os.path.exists(tr_html) and os.path.exists(tr_man)):
        check("transcription page present", False, "transcription/index.html",
              "MISSING", "the human round needs somewhere to be done")
    else:
        tr = open(tr_html, encoding="utf8").read()
        man = json.load(open(tr_man))
        # "y" is the year PRINTED ON THE SHEET. It is machine-read, but it is
        # an identity fact about which year the sheet is for, not a reading of
        # any mark on it, and the page needs it to lock the cells that were
        # not yet observable when the photograph was taken.
        # "cmp" flags whether the extraction produced day calls for this sheet.
        # It is written into the export so the comparison can separate the two
        # populations without a second file; it is NOT shown on the page, so the
        # transcriber still cannot tell what the machine made of any sheet.
        allowed = {"n", "f", "wp", "site", "date", "w", "h", "y", "cmp"}
        extra = sorted({k for r in man for k in r} - allowed)
        check("transcription manifest carries no derived field",
              not extra, "only identity fields",
              f"extra: {', '.join(extra)}" if extra else "only identity fields",
              "no stage, geometry, stratum or confidence may ship")
        n_img = len([f for f in os.listdir(os.path.join(tr_dir, "img"))
                     if f.endswith(".jpg")]) if os.path.isdir(os.path.join(tr_dir, "img")) else 0
        check("every selected calendar has its image bundled",
              n_img == len(man), len(man), n_img,
              "the page must work without reaching mWater")
        # no extraction figure may appear anywhere in the shipped page
        figp2 = os.path.join(here, "data", "calendar_extraction_figures.json")
        leaked = []
        if os.path.exists(figp2):
            for k, v in json.load(open(figp2)).items():
                if isinstance(v, (int, float)) and v >= 100:
                    for form in (f"{v:,}", str(v)):
                        if re.search(r"(?<![\d.])" + re.escape(form) + r"(?![\d.])", tr):
                            leaked.append(f"{k}={form}")
                            break
        check("no extraction figure appears in the transcription page",
              not leaked, "none", ", ".join(leaked[:3]) if leaked else "none",
              "the transcriber must not see what the software decided")
        for word in ("confidence", "illegible", "impossible", "extraction", "geometry"):
            check(f"transcription page free of machine vocabulary: {word!r}",
                  word.lower() not in tr.lower(), "absent",
                  "FOUND" if word.lower() in tr.lower() else "absent",
                  "nothing may hint at an automatic result")

    # ---- 7r. the non-calendar exclusions ----------------------------------
    # 37 of the images the reader accepted turned out to be signboards, pumps,
    # posters and portraits. They inflated every coverage figure until they
    # were taken out, so the list, the count on the page and the count in the
    # figures file all have to say the same thing, and the day-cell arithmetic
    # has to close against the 12 x 31 grid that is actually printed.
    ncp = os.path.join(here, "data", "calendar_not_calendar.csv")
    if not os.path.exists(ncp):
        check("non-calendar list present", False, "data/calendar_not_calendar.csv",
              "MISSING", "every excluded image must be named, not just counted")
    elif os.path.exists(figp):
        import csv as _csv2
        nc = list(_csv2.DictReader(open(ncp)))
        fig = json.load(open(figp))
        # the list covers every image that is not a calendar, whether the
        # reader accepted it or threw it out. Only the accepted ones ever
        # entered a published figure, so only those are excluded from one.
        accepted = [r for r in nc if r["reader"] == "accepted as a calendar"]
        rejected = [r for r in nc if r["reader"] == "rejected"]
        check("non-calendar list matches the figures file",
              len(accepted) == fig["photographs_excluded_not_calendar"],
              fig["photographs_excluded_not_calendar"], len(accepted),
              "the figures exclude exactly the ones the reader had accepted")
        for n, what in ((len(accepted), "accepted"), (len(rejected), "rejected"),
                        (len(nc), "total")):
            check(f"page states the non-calendar count ({what}): {n}",
                  f"<b>{n}</b>" in idx, n,
                  n if f"<b>{n}</b>" in idx else "NOT ON THE PAGE")
        allowed_reasons = {"signboard", "pump", "document", "other", "bottle_on_pump"}
        bad = [r for r in nc if r["reason"] not in allowed_reasons
               or not r["water_point"] or not r["image_id"]
               or r["reader"] not in ("accepted as a calendar", "rejected")]
        check("every non-calendar image carries a point, an id, a reason and its reader outcome",
              not bad, f"all {len(nc)} complete", f"{len(bad)} incomplete",
              "a bare count is not something Jan can act on")
        check("the page points at the non-calendar list",
              "data/calendar_not_calendar.csv" in idx, "named", 
              "named" if "data/calendar_not_calendar.csv" in idx else "NOT NAMED")
        # the cell arithmetic and the per-year impossible-cell count are
        # asserted in 7ra, which knows which years are leap years
        check("the page states the impossible-cell count per sheet by year",
              "<b>seven</b>" in idx and "in a leap year six" in idx
              and "Six cells on every sheet" not in idx,
              "seven, or six in a leap year",
              "seven, or six in a leap year" if "in a leap year six" in idx
              else "NOT STATED BY YEAR")
        check("visits with and without a readable image sum to the total",
              fig["visits_with_readable"] + fig["visits_without_readable"]
              == fig["visits_total"], fig["visits_total"],
              fig["visits_with_readable"] + fig["visits_without_readable"])
        nup = os.path.join(here, "data", "calendar_no_usable_image.csv")
        if os.path.exists(nup):
            nu = list(_csv2.DictReader(open(nup)))
            check("the reissue priority list matches the points-without count",
                  len(nu) == fig["points_without_readable"],
                  fig["points_without_readable"], len(nu),
                  "data/calendar_no_usable_image.csv is that list, not a sample")
            # a point whose photographs are all signboards needs a different
            # instruction from one whose calendar simply could not be read
            cats = {"no calendar was ever photographed",
                    "some photographs are of something else",
                    "calendar photographed, not readable"}
            check("every point on the reissue list carries a cause and a field action",
                  all(r.get("category") in cats and r.get("field_action") for r in nu),
                  "all classified",
                  "all classified" if all(r.get("category") in cats and r.get("field_action")
                                          for r in nu) else "UNCLASSIFIED ROWS",
                  "'photograph unreadable' is the wrong instruction for a signboard")
            never = sum(1 for r in nu if r["category"] == "no calendar was ever photographed")
            check(f"page states how many points never had a calendar photographed: {never}",
                  f"<b>{never}</b>" in idx, never,
                  never if f"<b>{never}</b>" in idx else "NOT ON THE PAGE")

    # ---- 7ra. the observed-cell basis -------------------------------------
    # A calendar photographed on date D can only carry marks for days up to D.
    # Cells after D were blank by construction, so a rate computed over them
    # measures the passage of time, not the pump. Every extraction rate is now
    # computed over observed cells only, and the arithmetic has to close.
    if os.path.exists(figp):
        fig = json.load(open(figp))
        if "observed_cells" in fig:
            check("the figures declare the basis they are computed on",
                  "observed cells" in fig.get("basis", ""),
                  "observed cells only", fig.get("basis", "MISSING"),
                  "a rate means nothing without its denominator's definition")
            # every sheet prints 12 x 31, whatever year it is for
            grid = fig["images_with_day_calls"] * 12 * 31
            tot3 = (fig["observed_cells"] + fig["unobserved_cells"]
                    + fig["impossible_cells"])
            check("observed + unobserved + impossible is the whole printed grid",
                  tot3 == grid, grid, tot3,
                  "no cell may be dropped or counted twice")
            # impossible cells are 7 per sheet in a common year, 6 in a leap year
            by_y = fig.get("sheets_by_year", {})
            want_imp = sum(v * (6 if (int(k) % 4 == 0 and (int(k) % 100 != 0
                           or int(k) % 400 == 0)) else 7)
                           for k, v in by_y.items() if k.isdigit())
            if want_imp:
                check("impossible cells follow each sheet's own year",
                      want_imp == fig["impossible_cells"],
                      want_imp, fig["impossible_cells"],
                      "2024 is a leap year: 29 February is a real day, and six cells cannot exist")
            check("the impossible-cell probe is a subset of the impossible cells",
                  fig["probe_cells"] <= fig["impossible_cells"],
                  f"<= {fig['impossible_cells']}", fig["probe_cells"],
                  "a month that had not started cannot probe anything")
            check("\"could not be read\" and \"had not happened yet\" are separate",
                  "unobserved_called_illegible" in fig and "days_unobserved" in fig,
                  "counted separately",
                  "counted separately" if "unobserved_called_illegible" in fig
                  else "CONFLATED",
                  "an unobserved blank is not an illegible cell")
            check("the implied true marked rate is the observed rate less the probe",
                  abs(fig["implied_true_marked_pct"]
                      - (fig["observed_marked_pct"] - fig["probe_marked_pct"])) < 0.011,
                  round(fig["observed_marked_pct"] - fig["probe_marked_pct"], 2),
                  fig["implied_true_marked_pct"])
            for key, label in (("observed_cells", "observed cells"),
                               ("unobserved_cells", "unobserved cells"),
                               ("sheets_not_dated", "sheets that could not be dated")):
                v = fig[key]
                want = f"{v:,}" if v >= 1000 else str(v)
                check(f"page states the {label}: {want}",
                      f"<b>{want}</b>" in idx, want,
                      want if f"<b>{want}</b>" in idx else "NOT ON THE PAGE")
            for key, label in (("observed_marked_pct", "observed-cell marked rate"),
                               ("probe_marked_pct", "impossible-cell marked rate"),
                               ("implied_true_marked_pct", "implied true marked rate")):
                want = f"{fig[key]:.2f}%"
                check(f"page states the {label}: {want}",
                      f"<b>{want}</b>" in idx, want,
                      want if f"<b>{want}</b>" in idx else "NOT ON THE PAGE")

    # ---- 7s. the transcription round's method is stated, not assumed -------
    # A reference transcription made by someone who had seen the aggregate
    # error statistics is still usable, but only if a verifier is told so
    # before reading the agreement figure.
    for frag, why in (
            ("Adriaan Mol", "the reference transcriber is named"),
            ("aggregate error statistics", "their exposure is stated"),
            ("no per-cell output", "the limit of that exposure is stated"),
            ("floor of <b>30</b>", "the v1.0 / CDM minimum is stated"),
            ("<b>50</b> per sample group or stratum required by v2.0",
             "the v2.0 minimum is stated"),
            ("stands whichever version governs",
             "the round is stated as satisfying both versions"),
            ("locks every cell the photograph could not show",
             "the comparison is on the same cells for both sides"),
            ("The validation frame was corrected on",
             "the frame change is recorded, with its date"),
            ("transcription/validation_selection.csv",
             "the selection file is named"),
            ("the calendar", "the unit of variation is stated")):
        check(f"transcription method note: {why}", frag in idx, "present",
              "present" if frag in idx else "MISSING",
              "the accuracy assessment is only as good as its declared method")
    check("days-operational section reserves the result footnote",
          "An accuracy assessment of the machine reading of these calendars is in progress" in idx,
          "reserved", "reserved" if "An accuracy assessment of the machine reading"
          " of these calendars is in progress" in idx else "MISSING",
          "the footnote is placed before the results, and says so")

    # ---- 7sa. an agreement figure never travels without its denominator ----
    # "The extraction agrees with the human 92% of the time" is not a fact
    # about the calendars. It is a fact about the subset the extraction
    # produces output for at all, which is a minority of them. The coverage
    # sentence is therefore required next to any agreement figure, and the
    # numbers in it are checked against the figures file rather than trusted.
    if os.path.exists(figp):
        fig = json.load(open(figp))
        cov_span = re.search(r'<span class="agrcov">(.*?)</span>', idx, re.S)
        check("the page carries the coverage an agreement figure would apply to",
              cov_span is not None, "present",
              "present" if cov_span else "MISSING",
              "an agreement figure means nothing without its population")
        if cov_span:
            txt = cov_span.group(1)
            for key in ("images_with_day_calls", "images_readable",
                        "photographs_total"):
                v = f"{fig[key]:,}" if fig[key] >= 1000 else str(fig[key])
                check(f"coverage sentence states {key}: {v}",
                      f"<b>{v}</b>" in txt, v,
                      v if f"<b>{v}</b>" in txt else "NOT IN THE SENTENCE",
                      "from data/calendar_extraction_figures.json")
        # any agreement figure on the page must sit in a paragraph that also
        # carries the coverage sentence. None exists yet; this fires when one does.
        paras = re.findall(r"<p\b[^>]*>.*?</p>", idx, re.S)
        AGREE = re.compile(r"(?:agreement|agree[sd]?\s+with|concordance)\b", re.I)
        offenders = [q[:70] for q in paras
                     if AGREE.search(q) and re.search(r"\d+(?:\.\d+)?%", q)
                     and 'class="agrcov"' not in q
                     and "would apply to" not in q and "will and will not cover" not in q]
        check("no agreement percentage appears without the coverage sentence",
              not offenders, "none", f"{len(offenders)} bare" if offenders else "none",
              "the denominator travels with the number")
        # and the comparison tool must emit it too
        cmp_p = os.path.join(here, "tools", "compare_transcriptions.py")
        if os.path.exists(cmp_p):
            cmp_s = open(cmp_p, encoding="utf8").read()
            check("the comparison tool prints the coverage with its figures",
                  "COVERAGE THIS FIGURE APPLIES TO" in cmp_s, "present",
                  "present" if "COVERAGE THIS FIGURE APPLIES TO" in cmp_s else "MISSING")
            check("the comparison tool keeps machine-unreadable sheets separate",
                  "human-human-not-machine-readable" in cmp_s, "separate",
                  "separate" if "human-human-not-machine-readable" in cmp_s
                  else "FOLDED IN",
                  "sheets the machine could not read answer a different question")

    # ---- 7sb. the validation sample, against its own selection file --------
    # The frame moved: from "readable calendar photographs" to "photographs the
    # extraction produces day calls for, dated, and actually calendars". A
    # verifier has to be able to see that it moved, why, and that the draw
    # still clears the methodology minimum, so the page is checked against the
    # selection file rather than against a phrase.
    selp = os.path.join(here, "transcription", "validation_selection.csv")
    if not os.path.exists(selp):
        check("validation selection file present", False,
              "transcription/validation_selection.csv", "MISSING",
              "the frame change has to be auditable")
    else:
        import csv as _csv3
        sel = list(_csv3.DictReader(open(selp)))
        infr = [r for r in sel if r["in_frame"] == "yes"]
        outfr = [r for r in sel if r["in_frame"] != "yes"]
        kept = [r for r in infr if r["origin"].startswith("kept")]
        drew = [r for r in infr if r["origin"].startswith("drawn")]
        # the round must stand under BOTH versions: v1.0 4.2.2 sets 30, v2.0
        # 14.5.3 sets 50 per sample group or stratum. 50 satisfies both and
        # means the assessment never needs repeating at renewal.
        check("the human-to-machine sample clears the v1.0 minimum of 30",
              len(infr) >= 30, ">= 30", len(infr), "ERSDWS v1.0 section 4.2.2")
        check("the human-to-machine sample clears the v2.0 minimum of 50",
              len(infr) >= 50, ">= 50", len(infr), "ERSDWS v2.0 section 14.5.3")
        seeds = sorted({r["seed"] for r in sel if r["seed"]})
        check("the selection records more than one draw pass, each with its seed",
              len(seeds) >= 2, ">= 2 seeds", len(seeds),
              "the extension must be reproducible separately from the original draw")
        ext = [r for r in infr if "extend" in r["origin"]]
        extseeds = {r["seed"] for r in ext}
        check("the extension rows are marked as an extension, not a redraw",
              ext and len(extseeds) == 1 and extseeds.isdisjoint({seeds[0]}),
              f"{len(ext)} extension rows", f"{len(ext)} extension rows"
              if ext else "NONE",
              "one seed of its own, not the original draw's; later passes add "
              "further seeds and must not disturb this one")
        for v, why in ((len(infr), "the comparison set"),
                       (len(kept), "the sheets kept from the original draw"),
                       (len(drew), "the sheets drawn to make up the shortfall"),
                       (len(outfr), "the sheets scored human-to-human only")):
            check(f"page states {why}: {v}", f"<b>{v}</b>" in idx, v,
                  v if f"<b>{v}</b>" in idx else "NOT ON THE PAGE",
                  "from transcription/validation_selection.csv")
        check("every selected sheet records the frame, the reason and the date",
              all(r["frame"] and r["origin"] and r["seed"] for r in sel)
              and all(r["drawn_on"] for r in drew),
              "all recorded",
              "all recorded" if all(r["frame"] and r["origin"] and r["seed"]
                                    for r in sel) and all(r["drawn_on"] for r in drew)
              else "INCOMPLETE",
              "a verifier must see that the frame moved and why")
        check("the draw covers both districts",
              len({r["site"] for r in infr}) == 2,
              "both", ", ".join(sorted({r["site"] for r in infr})))
        check("the draw covers the full quality range",
              len({r["quality_quartile"] for r in infr}) == 4, "4 quartiles",
              len({r["quality_quartile"] for r in infr}),
              "a sample of easy sheets would flatter the extraction")
        # every sheet in the selection must actually be bundled
        man2 = json.load(open(os.path.join(here, "transcription", "calendars.json")))
        sheets = {str(c["n"]) for c in man2}
        missing = [r["calendrier"] for r in sel
                   if r["calendrier"] and r["calendrier"] not in sheets]
        check("every selected sheet is bundled on the transcription page",
              not missing, "all bundled",
              f"{len(missing)} missing" if missing else "all bundled")
        # the round has to be runnable: the page must load exactly the
        # selection, in order, and flag the comparable sheets for the export
        nosheet = [r["image_id"][:8] for r in sel if not r["calendrier"]]
        check("every selected sheet has been assigned a sheet number",
              not nosheet, "all numbered",
              f"{len(nosheet)} unnumbered" if nosheet else "all numbered",
              "without it the selection cannot be joined to the page")
        want_n = sorted(int(r["calendrier"]) for r in sel if r["calendrier"])
        got_n = sorted(c["n"] for c in man2)
        check("the page loads exactly the selection, in order",
              want_n == got_n, f"{len(want_n)} sheets",
              f"{len(got_n)} sheets" + ("" if want_n == got_n else " MISMATCH"))
        flagged = sorted(c["n"] for c in man2 if c.get("cmp"))
        want_f = sorted(int(r["calendrier"]) for r in sel
                        if r["in_frame"] == "yes" and r["calendrier"])
        check("the machine-comparable sheets are flagged for the export",
              flagged == want_f, f"{len(want_f)} flagged",
              f"{len(flagged)} flagged" + ("" if flagged == want_f else " MISMATCH"))
        check("every bundled sheet carries a photograph, a pump id and a year field",
              all(c.get("f") and c.get("wp") for c in man2), "complete",
              "complete" if all(c.get("f") and c.get("wp") for c in man2)
              else "INCOMPLETE",
              "the year may be absent on an undated sheet, and is shown as ?")

    # ---- 7t. the transcription page records who did the work ---------------
    trh = os.path.join(here, "transcription", "index.html")
    if os.path.exists(trh):
        tr2 = open(trh, encoding="utf8").read()
        # the columns are asserted on the export header itself, not on the
        # word appearing somewhere in the file: an earlier version of this
        # check passed after the column had been deleted from the export
        want_cols = ["calendrier", "point_eau", "date_photo", "annee_feuille",
                     "comparable_machine", "mois", "jour", "releve",
                     "etat_cellule", "exclu", "exclu_motif", "transcripteur",
                     "session_id", "secondes_sur_calendrier", "notes",
                     "exporte_le"]
        hdr = "[" + ",".join(f"'{c}'" for c in want_cols) + "]"
        check("transcription export header carries every column, in order",
              hdr in tr2.replace(" ", ""), ",".join(want_cols),
              ",".join(want_cols) if hdr in tr2.replace(" ", "") else "CHANGED",
              "transcripteur and session_id must reach every exported row")
        for frag, why in (
                ("Ce n\u2019est pas un calendrier", "the not-a-calendar control exists"),
                ("EXCLU", "an excluded sheet exports as excluded, not as blanks"),
                ("out.push([c.n,c.wp,c.date,c.y||'',c.cmp?'oui':'non','','','EXCLU'",
                 "the excluded row has no day cells")):
            check(f"transcription page: {why}", frag in tr2, "present",
                  "present" if frag in tr2 else "MISSING")
        check("transcription page refuses an unnamed export",
              "avant d\u2019exporter" in tr2, "refused", 
              "refused" if "avant d\u2019exporter" in tr2 else "NOT ENFORCED",
              "an anonymous transcript cannot be compared to anything")
        flat = tr2.replace(" ", "")
        okdim = ("constdim=y=>[31,leap(y)?29:28," in flat
                 and "constleap=" in flat
                 and "constDIM=[31,28," not in flat)
        check("transcription month lengths follow the sheet's own year",
              okdim, "derived from the year",
              "derived from the year" if okdim else "HARD-CODED",
              "2024 is a leap year and 29 February is a real day on a 2024 sheet")
        for frag, why in (
                ("jours observables jusqu", "the observable window is shown"),
                ("unobs", "cells after the photograph date are locked"),
                ("etat_cellule", "the export says whether a cell was observable"),
                ("annee_feuille", "the export carries the sheet's year"),
                ("unobs.keep", "a mark on a now-unobservable cell is kept and flagged")):
            check(f"transcription page: {why}", frag in tr2, "present",
                  "present" if frag in tr2 else "MISSING",
                  "the human and the machine must be compared on the same cells")

    # ---- 7u. the SDWS 27 basis and the six actions it generated ------------
    # The basis was read out of the registered VPA-DD and both methodology
    # versions and written to docs/sdws27_basis.md. The page must not drift
    # from that file, and the six actions must each carry an owner and a date
    # in the house format.
    basis = os.path.join(here, "docs", "sdws27_basis.md")
    if not os.path.exists(basis):
        check("SDWS 27 basis document present", False, "docs/sdws27_basis.md",
              "MISSING", "the finding has to be traceable to the quotations")
    else:
        bs = open(basis, encoding="utf8").read()
        for frag, why in (
                ("The date of entry into force is 90 days from the publication date",
                 "v2.0 3.3.1 is quoted"),
                ("At the renewal, the activity developer shall apply the latest version",
                 "v2.0 17.1.1 is quoted"),
                ("Values higher than 347 days may only be applied when option 1 is used",
                 "the v1.0 / VPA-DD condition is quoted"),
                ("Uncertainty is managed by this conservative cap when relying on manual logs",
                 "the v2.0 cap wording is quoted"),
                ("Estimate: 347 days", "the VPA-DD applied value is quoted"),
                ("detailing uptime and downtime", "the v2.0 log wording is quoted"),
                ("out of action or unavailable for use", "downtime is defined"),
                ("SDWS 32", "the v2.0 parameter number is corrected"),
                ("operation sensor", "the term actually used is named")):
            check(f"basis document: {why}", frag in bs, "quoted",
                  "quoted" if frag in bs else "MISSING",
                  "verbatim from the registered documents")
        check("basis document states which version governs",
              "v1.0 governs the 2026 monitoring period" in bs, "stated",
              "stated" if "v1.0 governs the 2026 monitoring period" in bs else "MISSING")
        check("basis document does not soften the finding against us",
              "not claimable" in bs and "cannot raise it" in bs,
              "stated plainly",
              "stated plainly" if "not claimable" in bs else "SOFTENED",
              "356.2 days is above the cap and the calendars are a manual log")

    # the page must carry the same construction as the basis document
    check("page states the registered DO construction",
          "min(347, days demonstrated by the operation-and-maintenance log)"
          in idx.replace("<span class=\"mono\">", "").replace("</span>", "")
          or "min(347, days demonstrated by the" in idx,
          "stated", "stated" if "min(347, days demonstrated by the" in idx
          else "NOT ON THE PAGE",
          "DO = min(347, log), not a flat 347 and not 356.2")
    check("page states that the calendars cannot raise the registered figure",
          "They cannot raise it" in idx, "stated",
          "stated" if "They cannot raise it" in idx else "MISSING")

    # ---- 7v. the per-year quantification -----------------------------------
    # The tonnages and cash totals were WITHDRAWN on 2026-09-23: every one was
    # computed from the per-year quantification, whose basis does not exist
    # here. These checks used to assert the figures were present. They now
    # assert the opposite - a withdrawn figure that comes back is a
    # regression, and this is what catches it.
    for v, why in (("20,697", "2026 ER at 347 days"),
                   ("10,227", "2025 ER at 347 days"),
                   ("17,681", "the 2026 evidence gap in tCO2e"),
                   ("354,000", "the 2026 evidence gap in USD")):
        check(f"withdrawn and stays off the page: {v} ({why})",
              v not in idx, "absent",
              "absent" if v not in idx else "BACK ON THE PAGE",
              "withdrawn 2026-09-23 with the per-year carbon basis")
    for v, why in (("434", "2026 points with no dated sheet"),
                   ("11 April 2025", "the earliest passing SDWS 3 test")):
        check(f"page states {why}: {v}", f"<b>{v}</b>" in idx, v,
              v if f"<b>{v}</b>" in idx else "NOT ON THE PAGE",
              "Part 2, computed on the register")
    # The carbon denominator is derived, and the check asserts the derivation.
    # 727 was pinned here as a literal for two days; pinning 731 in its place
    # would be the same mistake one number later.
    cd = os.path.join(repo_root, "data", "carbon_denominator.json")
    if os.path.exists(cd):
        cdoc = json.loads(read(cd))
        pumps_ = js_const(idx, "PUMPS") or []
        want = len([p for p in pumps_ if p.get("site") != "Marolinta"])
        check("the carbon denominator is the register less Marolinta",
              cdoc.get("carbon_points") == want, want,
              cdoc.get("carbon_points"),
              "actively managed register less Marolinta, which enters no carbon figure")
        check("the carbon denominator is rendered, never typed",
              'data-fig="CARBON.carbon_points"' in idx
              and idx.count('data-fig="CARBON.carbon_points"') >= 8,
              "rendered",
              f'{idx.count(chr(34)+"CARBON.carbon_points"+chr(34))} spans',
              "it was typed in eleven places and could not be derived at all")
        check("727 no longer appears as a denominator in the prose",
              "of <b>727</b>" not in idx and "727 active points" not in idx
              and "727 carbon points" not in idx, "gone",
              "gone" if "of <b>727</b>" not in idx else "STILL PRESENT",
              "superseded 2026-09-22; see docs/decision_log.md")
        # It is no longer only marked cell-by-cell: the whole table sits behind
        # a labelled withdrawn block, so a reader learns it cannot be
        # reproduced before reading a single cell.
        check("the per-year carbon table is withdrawn behind a labelled block",
              "Withdrawn: the per-year carbon quantification" in idx
              and "The figures have been removed, not corrected" in idx
              and "unreproducible, which is not the same as wrong" in idx,
              "marked",
              "marked" if "The figures have been removed, not corrected" in idx
              else "NOT MARKED",
              "no per-year activity basis exists in this repository")
    check("the withdrawal names what restores it",
          "act-carbon-year-basis" in idx
          and "return when the basis is rebuilt" in idx, "named",
          "named" if "return when the basis is rebuilt" in idx else "NOT NAMED",
          "the reader is told the money was unreproducible, not wrong")
    check("page states 2024 carries no carbon value",
          "No point could credit in 2024" in idx, "stated",
          "stated" if "No point could credit in 2024" in idx else "MISSING")

    # ---- 7w. the six new actions -------------------------------------------
    acts = {
        "act-sdws27-basis": ("James Walker", "3 Oct 2026"),
        "act-2026-recovery": ("Angelo Nahavitatsara / MadAvance", "31 Jan 2027"),
        "act-sensor-sample": ("Adriaan Mol", "3 Oct 2026"),
        "act-undatable": ("Angelo Nahavitatsara / MadAvance", "17 Oct 2026"),
        "act-transcription-round": ("MadAvance", "10 Oct 2026"),
        "act-visit-collapse": ("Jan de Graaf", "30 Sep 2026"),
    }
    for aid, (owner, date) in acts.items():
        m = re.search(r'<tr id="' + aid + r'">(.*?)</tr>', ACTSRC, re.S)
        check(f"action present: {aid}", m is not None, "present",
              "present" if m else "MISSING")
        if not m:
            continue
        row = m.group(1)
        check(f"{aid}: owner is {owner}", owner in row, owner,
              owner if owner in row else "WRONG OWNER")
        check(f"{aid}: deadline is {date}", f"<b>{date}</b>" in row, date,
              date if f"<b>{date}</b>" in row else "WRONG DATE")
        # the vocabulary is now three states: ACT / WATCH / OK. OVERDUE is
        # not stored - it is a badge computed in the generated action list.
        has_pill = ('class="pill crit">ACT' in row or 'class="pill warn">WATCH' in row
                    or 'class="pill ok">OK' in row)
        check(f"{aid}: carries a schedule pill", has_pill, "pill",
              "pill" if has_pill else "MISSING",
              "house format: pill, date, proposed-note, completion criterion")
        check(f"{aid}: marked as proposed for Jan to confirm",
              "proposed &mdash; Jan to confirm or move" in row, "proposed",
              "proposed" if "proposed &mdash; Jan to confirm or move" in row
              else "MISSING",
              "deadlines are proposals until Jan confirms them")

    # ---- 7x. 356.2 is a reading, never a claim -----------------------------
    # DO = min(347, days demonstrated by the log). The observed-window reading
    # sits above the cap, so no published sentence may pair it with a verb that
    # asserts we can have it. This fires on the sentence, not the paragraph.
    CLAIMY = re.compile(r"\b(claim(?:able|ed|ing|s)?|apply|applied|applicable|"
                        r"credit(?:able|ed|ing)?|entitled|uplift|gain(?:ed|s)?|"
                        r"recover(?:ed|s)?|available to us|worth to us)\b", re.I)
    NEGATED = re.compile(r"\b(not|never|cannot|can't|no part|above the cap|"
                         r"sizing|sizes|only on measured|would|not available)\b", re.I)
    # Every published reading that sits above the 347-day cap, not just the
    # first one. A stratum average is no more claimable than a per-point one.
    ABOVE_CAP = ("356.2", "353.6", "353.3", "356.7", "357.8", "358.6", "357.3")
    # Strip the scripts BEFORE the tags. Stripping tags alone leaves the
    # inlined data objects behind as if they were prose, and a JSON blob
    # containing "353.6" next to the word "applied" reads to this check as a
    # published claim. It is not prose and must not be scanned as prose.
    plain = re.sub(r"<script\b[^>]*>.*?</script>", " ", idx, flags=re.S)
    plain = re.sub(r"<style\b[^>]*>.*?</style>", " ", plain, flags=re.S)
    plain = re.sub(r"<[^>]+>", " ", plain)
    plain = plain.replace("&mdash;", "—").replace("&nbsp;", " ")
    offenders = []
    for sent in re.split(r"(?<=[.!?])\s+", plain):
        if not any(n in sent for n in ABOVE_CAP):
            continue
        if CLAIMY.search(sent) and not NEGATED.search(sent):
            offenders.append(re.sub(r"\s+", " ", sent)[:110])
    check("no published sentence pairs an above-cap reading with a claiming verb",
          not offenders, "none",
          f"{len(offenders)} offending" if offenders else "none",
          "DO = min(347, log); the reading is above the cap and is not ours to apply")
    check("the page says the reading is not a figure we can apply",
          "not a figure we can apply" in idx, "stated",
          "stated" if "not a figure we can apply" in idx else "MISSING")
    check("the sensor-decision columns went with the withdrawn table",
          "Sensor decision only" not in idx, "absent",
          "absent" if "Sensor decision only" not in idx else "STILL PRESENT",
          "they sized a difference in tonnes and USD, withdrawn 2026-09-23")
    check("the page states what the calendars are for: 18 days per point-year",
          "18</b> days per point-year" in idx, "stated",
          "stated" if "18</b> days per point-year" in idx else "MISSING",
          "365 less 347; the condition for retaining the registered figure")

    # ---- 7y. the open exposure, and the two unsettled questions ------------
    for v, why in (("7,440", "2025 tonnes resting on the estimate"),
                   ("148,800", "2025 gap in USD"),
                   ("353,600", "2026 gap in USD"),
                   ("25,121", "the two-year exposure")):
        check(f"withdrawn and stays off the page: {v} ({why})",
              v not in idx, "absent",
              "absent" if v not in idx else "BACK ON THE PAGE",
              "withdrawn 2026-09-23 with the per-year carbon basis")

    # ---- 7z. the version divergence register -------------------------------
    vmap = os.path.join(here, "docs", "methodology_version_map.md")
    if not os.path.exists(vmap):
        check("version divergence register present", False,
              "docs/methodology_version_map.md", "MISSING",
              "v2.0 applies at renewal and the mapping has to be maintained")
    else:
        vm = open(vmap, encoding="utf8").read()
        idx_rows = re.findall(r"^\|\s*(\d+)\s*\|\s*(yes|no)\s*\|\s*([a-z0-9-]*)\s*\|\s*$",
                              vm, re.M)
        # Trimmed 2026-09-23 to the six divergences with a COLLECTION
        # consequence; the eight interpretation rows went to the Head of
        # Carbon. The floor is the six, not the old fourteen.
        check("the register carries a machine-readable action_now index",
              len(idx_rows) >= 6, ">= 6 rows", len(idx_rows),
              "so every action_now = yes can be checked against the action list")
        yes = [(n, aid) for n, f, aid in idx_rows if f == "yes"]
        check("every divergence needing action now names an action",
              all(aid for _, aid in yes), f"{len(yes)} named",
              f"{sum(1 for _, a in yes if not a)} unnamed" if yes else "none")
        for n, aid in yes:
            check(f"divergence {n} has its Action List item: {aid}",
                  f'<tr id="{aid}">' in ACTSRC, aid,
                  aid if f'<tr id="{aid}">' in ACTSRC else "NO SUCH ACTION",
                  "a register row marked action_now = yes must have an action")
        check("the register states v1.0 governs and v2.0 applies at renewal",
              "v1.0 governs the current crediting period" in vm
              and "applies at renewal" in vm, "stated",
              "stated" if "v1.0 governs the current crediting period" in vm else "MISSING")
        check("the page carries the version-divergence section",
              "v1.0 governs this crediting period" in idx, "present",
              "present" if "v1.0 governs this crediting period" in idx else "MISSING")
        n_div = len(idx_rows); n_now = len(yes)
        ok_counts = f"<b>{n_now}</b> require action now" in idx
        check(f"page states the divergence count: {n_now} act now",
              ok_counts, f"{n_now} act now",
              "stated" if ok_counts else "NOT ON THE PAGE",
              "the register now carries only what changes collection")

    # ---- 7aa. the standing adherence item and the custody metric -----------
    check("the standing methodology-adherence item is present",
          '<tr id="act-v2-adherence">' in ACTSRC, "present",
          "present" if '<tr id="act-v2-adherence">' in ACTSRC else "MISSING")
    m_ad = re.search(r'<tr id="act-v2-adherence">(.*?)</tr>', ACTSRC, re.S)
    if m_ad:
        # STANDING became WATCH when the vocabulary went to three states
        check("the adherence item is owned by James Walker and stands open",
              "James Walker" in m_ad.group(1)
              and 'pill warn">WATCH' in m_ad.group(1), "WATCH, James Walker",
              "ok" if 'pill warn">WATCH' in m_ad.group(1) else "WRONG")
    for aid, owner, date in (("act-calendar-custody", "Angelo Nahavitatsara / MadAvance", "26 Sep 2026"),
                             ("act-sensor-definition", "James Walker", "10 Oct 2026"),
                             ("act-printed-year-meaning",
                              "Angelo Nahavitatsara / MadAvance", "17 Oct 2026")):
        m2 = re.search(r'<tr id="' + aid + r'">(.*?)</tr>', ACTSRC, re.S)
        check(f"action present: {aid}", m2 is not None, "present",
              "present" if m2 else "MISSING")
        if m2:
            check(f"{aid}: owner is {owner}", owner in m2.group(1), owner,
                  owner if owner in m2.group(1) else "WRONG OWNER")
            check(f"{aid}: deadline is {date}", f"<b>{date}</b>" in m2.group(1),
                  date, date if f"<b>{date}</b>" in m2.group(1) else "WRONG DATE")
    check("the calendar-custody rule is stated as replace-only-after-photograph",
          "NO CALENDAR MAY BE REPLACED UNTIL THE PREVIOUS ONE HAS BEEN PHOTOGRAPHED"
          in idx, "stated", "stated" if "NO CALENDAR MAY BE REPLACED" in idx
          else "MISSING", "the precondition for the recovery round")
    check("the recovery round is whole-portfolio against the 727 denominator",
          "whole portfolio &mdash; not a sample" in idx, "stated",
          "stated" if "whole portfolio &mdash; not a sample" in idx else "MISSING")
    # The 2026 custody figures are derived now, so they are not literals in
    # the source; assert the spans that produce them instead.
    check("fleet section renders the 2026 custody figures from the data",
          'data-fig="CARBON.carbon_points_with_2026_sheet"' in idx
          and 'data-fig="CARBON.carbon_2026_coverage_pct"' in idx, "rendered",
          "rendered" if 'data-fig="CARBON.carbon_2026_coverage_pct"' in idx
          else "MISSING",
          "calendar custody is a headline operational metric")
    # The 2025 custody figures (237 of 722, 32.8%) rested on "active in
    # 2025", the per-year basis withdrawn as unreproducible (per_year_carbon).
    # They stopped rendering on 23 September 2026 and must not come back until
    # act-carbon-year-basis rebuilds that basis.
    _c25 = [v for v in ("<b>32.8%</b>", "<b>722</b>", "<b>237</b>") if v in idx]
    check("the 2025 custody figures stay withdrawn with their basis",
          not _c25, "absent", ", ".join(_c25) if _c25 else "absent",
          "they rest on the withdrawn per-year activity basis")

    # ---- 7ab. metering is fleet-wide; sampling is for calibration only -----
    # The report previously described a 60-unit sampled sensor deployment.
    # That is not the architecture: every pump carries a logger, and the 90/10
    # sample establishes litres per counted event. No sensor COUNT may appear
    # in the same sentence as "sample".
    # a UNIT COUNT next to a device noun - "60 sensors", "~770 loggers",
    # "60-unit deployment" - not any number that happens to share a sentence
    # with the word sensor. 347, 90/10 and SDWS numbers are not unit counts.
    UNITCOUNT = re.compile(r"(~?\d{1,4}[\s\u2011-]*(?:sensors?|units?|loggers?|pods?)\b"
                           r"|\b(?:sensors?|units?|loggers?|pods?)[^.]{0,20}?\bis\s+~?\d{1,4}\b)", re.I)
    SAMPLEWORD = re.compile(r"\bsampl(?:e|ed|es|ing)\b", re.I)
    ALLOWED = re.compile(r"calibrat|conversion factor|litres|litre|per counted event|"
                         r"not a sample|not which pumps|sampling-campaign|"
                         r"minimum sample size|census|validation round|stratum|"
                         r"previously read", re.I)
    plain2 = re.sub(r"<[^>]+>", " ", idx).replace("&mdash;", "—").replace("&nbsp;", " ")
    bad_pairs = []
    for sent in re.split(r"(?<=[.!?])\s+", plain2):
        if not (UNITCOUNT.search(sent) and SAMPLEWORD.search(sent)):
            continue
        if ALLOWED.search(sent):
            continue
        bad_pairs.append(re.sub(r"\s+", " ", sent)[:110])
    check("no sensor count is paired with the word 'sample'",
          not bad_pairs, "none",
          f"{len(bad_pairs)} offending" if bad_pairs else "none",
          "metering is fleet-wide; the 90/10 sample sets litres per counted event")
    for frag, why in (
            ("the logger is the SDWS 28 Option 2 operation sensor",
             "the plan's clause mapping is quoted"),
            ("the stroke log doubles as the SDWS 31/32 O&amp;M and days-operational evidence",
             "the days-operational consequence is quoted"),
            ("permanently mounted to a static part of every metered pump",
             "the logger is on every pump"),
            ("Meter every pump, calibrate by sampling",
             "the guiding principle is quoted"),
            ):
        check(f"sensor section: {why}", frag in idx, "present",
              "present" if frag in idx else "MISSING",
              "quoted commitments from StrokeMeter_Technical_Development_Plan_v1.2")
    # The plan's COUNTS are gone, and must stay gone. They were illustrative
    # figures written to brief a supplier and were carried here as though they
    # were the register. A figure's source is a form response, a registered
    # parameter or a named decision - never a plan or a deck.
    plan_counts = [f for f in ("~770", "<b>723</b>", "<b>646</b>",
                               "~688", "~82", "<b>~10</b> units")
                   if f in idx]
    check("no StrokeMeter-plan count is carried as a figure",
          not plan_counts, "none",
          f"still present: {', '.join(plan_counts[:3])}" if plan_counts else "none",
          "illustrative supplier-briefing counts, removed 2026-09-22")
    check("the report states the calendars retire if the logger is accepted",
          "retire as a carbon instrument" in idx
          and "cap would cease to bind" in idx, "stated",
          "stated" if "retire as a carbon instrument" in idx else "MISSING",
          "fleet-wide instrument evidence displaces the manual log")

    # ---- 7ac. end-user consent: what we hold, as a figure ------------------
    cons = os.path.join(here, "docs", "enduser_consent_position.md")
    if not os.path.exists(cons):
        check("consent position document present", False,
              "docs/enduser_consent_position.md", "MISSING")
    else:
        cs = open(cons, encoding="utf8").read()
        for frag, why in (
                ("Transfert de Propriété des Réductions d'Émissions de Carbone",
                 "the transfer clause is quoted"),
                ("Exclusivité", "the exclusivity clause is quoted"),
                ("période initiale de 5 ans", "the term is quoted"),
                ("preuves documentaires d'accord pour le transfert de propriété légale au niveau individuel",
                 "the individual-evidence commitment is quoted"),
                ("consentement libre, préalable et éclairé", "FPIC is quoted"),
                ("transfère par la présente à SaniTap", "the transfer wording is quoted"),
                ("SaniTap a informé et notifié aux utilisateurs finaux",
                 "the non-claiming notice is quoted")):
            check(f"consent document: {why}", frag in cs, "quoted",
                  "quoted" if frag in cs else "MISSING",
                  "verbatim French from the signed documents")
        check("consent document reports the mWater answer as a count",
              "0 water points, against 727 active carbon" in cs, "counted",
              "counted" if "0 water points, against 727 active carbon" in cs
              else "MISSING",
              "the analysis doc is left as written and carries a dated "
              "correction note; the report carries the derived denominator")
    # The standalone consent block was folded into its action row, so these
    # match on the two claims rather than on the removed markup: the
    # individual-level count is zero across the active points, and the
    # community-level notice is already signed.
    _cons_zero = re.search(r"no individual record exists for any of the\s*"
                           r'(?:<[^>]+>\s*)*(?:<span data-fig="CARBON\.'
                           r'carbon_points">[^<]*</span>)\s*active carbon points', idx)
    check("the page carries the consent figure",
          bool(_cons_zero) and "0</b> times in <b>142</b> responses" in idx,
          "present", "present" if _cons_zero else "MISSING")
    check("the page states the non-claiming notice already exists",
          "signed Community Agreement already carries the" in idx, "stated",
          "stated" if "signed Community Agreement already carries the" in idx else "MISSING",
          "the action must reflect what we hold, not assume we hold nothing")

    # ---- 7ad. divergence 9: the quarterly requirement does not bind us -----
    if os.path.exists(vmap):
        vm2 = open(vmap, encoding="utf8").read()
        check("register records that the quarterly validation binds Option 3 only",
              "does NOT bind our route" in vm2
              and "expressly scoped to Option 3" in vm2, "recorded",
              "recorded" if "does NOT bind our route" in vm2 else "MISSING",
              "Option 2 is the reference Option 3 is validated against")
        check("register records v2.0's own quarterly/annually contradiction",
              "contradicts itself on Option 3" in vm2, "recorded",
              "recorded" if "contradicts itself on Option 3" in vm2 else "MISSING")
        check("page states the quarterly validation does not reach us",
              "does not reach us" in idx, "stated",
              "stated" if "does not reach us" in idx else "MISSING")

    # ---- 7ae. the 2027 sheets: printed year verified, inference retracted --
    # The report once argued the custody rule from a claim that 2027-dated
    # sheets were being distributed nine months early. The printed year is
    # real; the inference was not. These assertions keep the retraction in
    # place and keep the custody rule standing on its actual basis.
    check("the early-distribution claim is retracted from the page",
          "5 February 2026" not in idx and "26 March 2026" not in idx,
          "retracted",
          "retracted" if "5 February 2026" not in idx else "STILL PRESENT",
          "the claim did not survive testing")
    check("the page states the printed year is real but the sheets are in service",
          "A printed year later than the photograph does not mean an unused sheet" in idx
          and "4.94%" in idx and "1.48%" in idx, "stated",
          "stated" if "does not mean an unused sheet" in idx else "MISSING",
          "marks concentrate in months already elapsed at the photograph")
    check("the custody rule stands on rolling replacement, not on timing",
          "remplac&eacute;s au fur et &agrave; mesure" in idx, "restated",
          "restated" if "remplac&eacute;s au fur et &agrave; mesure" in idx
          else "MISSING",
          "the rule is justified by replacement happening at all")
    check("the printed-year question is on the action list",
          '<tr id="act-printed-year-meaning">' in ACTSRC, "present",
          "present" if '<tr id="act-printed-year-meaning">' in ACTSRC else "MISSING",
          "the printed year is the key the days-operational chain turns on")

    # ---- 7af. repo hygiene: one home per script, one source per region ----
    # Two regressions came from the same cause and nothing caught either.
    # A stale bundle_new_sheets.py sat in sdws1/calendar_extract/ while the
    # repo copy was the one being fixed, so the fix ran on neither; and the
    # machine-extraction block of index.html was hand-edited twice and both
    # times silently reverted by its generator. The rule is in CONTRIBUTING.md:
    # every generated artefact is edited only at its generator, and no script
    # exists at two paths. These checks enforce it rather than restate it.
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SIBLINGS = ["/home/bushp/sdws1", "/home/bushp/sdws1/calendar_extract"]
    SKIPDIR = ("__pycache__", ".git", "node_modules", "site-packages",
               ".venv", "venv", ".cache", ".attic", "editions")

    def is_tombstone(path):
        """A stub that refuses to run is a signpost, not a second copy."""
        try:
            s = open(path, encoding="utf8", errors="replace").read()
        except OSError:
            return False
        return len(s) < 2000 and "sys.exit(__doc__)" in s

    def scripts_under(root):
        out = {}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIPDIR]
            for fn in filenames:
                if fn.endswith((".py", ".sh")):
                    full = os.path.join(dirpath, fn)
                    if not is_tombstone(full):
                        out.setdefault(fn, []).append(full)
        return out

    homes = scripts_under(repo_root)
    for sib in SIBLINGS:
        if not os.path.isdir(sib):
            continue
        for fn, paths in scripts_under(sib).items():
            homes.setdefault(fn, []).extend(paths)

    dupes = {fn: sorted(set(ps)) for fn, ps in homes.items() if len(set(ps)) > 1}
    check("no script filename exists at two paths",
          not dupes, "0 duplicated names",
          "0 duplicated names" if not dupes
          else f"{len(dupes)}: {', '.join(sorted(dupes))}",
          "; ".join(f"{fn} -> {' AND '.join(ps)}" for fn, ps in
                    sorted(dupes.items()))[:400])

    # Every generated region of index.html must name a generator that exists,
    # and the region must be exactly what that generator produces today.
    marks = re.findall(r"<!-- BEGIN GENERATED ([A-Za-z0-9_\-]+) :: ([^\s:]+) ::[^>]*-->", idx)
    check("index.html declares its generated regions",
          len(marks) >= 1, ">= 1 region", f"{len(marks)} region(s)",
          ", ".join(f"{n} <- {g}" for n, g in marks))
    check("generated-region markers are balanced",
          idx.count("<!-- BEGIN GENERATED") == idx.count("<!-- END GENERATED"),
          f"{idx.count('<!-- BEGIN GENERATED')} begin",
          f"{idx.count('<!-- END GENERATED')} end")
    for name, gen in marks:
        gpath = os.path.join(repo_root, gen)
        check(f"generator exists: {gen}", os.path.isfile(gpath),
              "present", "present" if os.path.isfile(gpath) else "MISSING", name)
        if not os.path.isfile(gpath):
            continue
        r = subprocess.run([sys.executable, gpath, "--check"],
                           capture_output=True, text=True, cwd=repo_root)
        check(f"index.html region '{name}' matches its generator",
              r.returncode == 0, "matches",
              "matches" if r.returncode == 0 else "DRIFTED",
              "" if r.returncode == 0
              else "edit the generator, then run "
                   f"python3 {gen} --write")

    contrib = os.path.join(repo_root, "CONTRIBUTING.md")
    ctxt = read(contrib) if os.path.isfile(contrib) else ""
    check("CONTRIBUTING.md records the two-copies rule",
          "two-copies" in ctxt.lower() and "one home" in ctxt.lower()
          and "render_block.py" in ctxt,
          "recorded", "recorded" if "two-copies" in ctxt.lower() else "MISSING",
          "the rule has to survive a context reset")

    # ---- 7ag. the sheet states its own period -----------------------------
    # From the January round the period is written on the sheet by the
    # technician and captured as an mWater field, so attribution never
    # depends on reading a printed header.
    check("the page links the SOP at v1.5",
          "CalendrierGardien-v1.5-2026" in idx
          and "CalendrierGardien-v1.4-2026.docx" not in idx
          and "CalendrierGardien-v1.3-2026.docx" not in idx
          and "CalendrierGardien-v1.2-2026.docx" not in idx, "v1.5",
          "v1.5" if "CalendrierGardien-v1.5-2026" in idx else "NOT UPDATED",
          "photograph mandatory where a calendar exists, at v1.5")
    check("the page names the template at v1.4",
          "Template-v1.4" in idx and "Template-v1.3.svg" not in idx, "v1.4",
          "v1.4" if "Template-v1.4" in idx else "NOT UPDATED",
          "written year box kept, weekday and February restored")
    check("the page records that the handwritten box governs",
          "the box governs" in idx, "stated",
          "stated" if "the box governs" in idx else "MISSING",
          "the grid may be made for a year; the sheet asserts none")
    check("the mWater year field is recorded as live and optional",
          "3393e25651c047d0b8a29f34cdcf12d9" in idx
          and '<tr id="act-mwater-year-required">' in ACTSRC
          and '<tr id="act-mwater-mg-locale">' in ACTSRC, "present",
          "present" if "3393e25651c047d0b8a29f34cdcf12d9" in idx else "MISSING",
          "optional now, required once v1.4 stock is in the field")
    check("the page names the mWater field that carries the period",
          "2.15.7" in idx and "d5233b2b" in idx, "named",
          "named" if "2.15.7" in idx else "MISSING",
          "preventive maintenance, group d5233b2b, after 2.15.6")
    check("the page states the period is recorded, not inferred",
          "recorded by the technician" in idx and "not inferred" in idx,
          "stated", "stated" if "not inferred" in idx else "MISSING",
          "from the January round onward")
    check("no published text calls a printed year the period covered",
          "l&rsquo;ann&eacute;e couverte" not in idx
          and "the year the sheet covers" not in idx, "absent",
          "absent" if "l&rsquo;ann&eacute;e couverte" not in idx else "PRESENT",
          "a printed year denotes the print run only")
    check("the v1.3 distribution action is on the list",
          '<tr id="act-calendar-v13">' in ACTSRC, "present",
          "present" if '<tr id="act-calendar-v13">' in ACTSRC else "MISSING",
          "withdraw year-printed stock as v1.3 arrives")

    # ---- 7ah. the printed grid is year-correct ----------------------------
    # A twelve-by-thirty-one grid has seven cells that cannot exist in a common
    # year and six in a leap year. Those cells are the extraction's only
    # false-positive probe that needs no human transcript, so the count is not
    # cosmetic. v1.3 printed February to 29 days on every sheet and lost the
    # seventh; v1.4 takes the year as a parameter again. This runs the real
    # generator and counts the shaded cells it emits.
    # Before reading anything out of OneDrive, establish that it is actually
    # on this machine. Storage Sense dehydrates synced files when C: fills,
    # and a cloud-only file has a normal size in a listing but fails or stalls
    # on open - a long way from the reason. require_local names the file.
    try:
        sys.path.insert(0, os.path.join(repo_root, "tools"))
        from require_local import (audit as _audit, message as _msg,  # noqa: E402
                                   advisory as _adv)
        _cloud, _missing = _audit()
        _advisory = _adv()
        check("documents the build reads are present locally, not cloud-only",
              not _cloud and not _missing, "all local",
              "all local" if not _cloud else f"{len(_cloud)} cloud-only",
              _msg(_cloud, _missing).splitlines()[0] if _cloud else
              ("advisory: " + "; ".join(_advisory) if _advisory
               else "Storage Sense has not dehydrated them"))
    except Exception as _e:
        check("required OneDrive documents are present locally, not cloud-only",
              False, "checked", f"check could not run: {_e}")

    GEN = ("/mnt/c/Users/bushp/OneDrive - SaniTap/Central Data Hub - "
           "Water Documents/SOPs/SOP-MAD-SDWS27-CalendrierGardien-Generator-v1.4.py")

    def build_sheet(year):
        """Execute the controlled generator and return one sheet's SVG.

        segno is not installed for every interpreter that runs this checker and
        the QR carries nothing this check looks at, so it is stubbed rather
        than required. Everything else is the generator's own code.
        """
        src = open(GEN, encoding="utf8").read()
        try:
            import segno  # noqa: F401
            mod = {}
        except ImportError:
            class _Q:
                matrix = [[0]]
            class _Segno:
                @staticmethod
                def make(data, error=None):
                    return _Q()
            mod = {"segno": _Segno}
        g = {"__name__": "_calendar_generator"}
        src = src.replace("import segno", "pass  # segno stubbed by the checker") \
            if mod else src
        exec(compile(src, GEN, "exec"), g)
        if mod:
            g["segno"] = mod["segno"]
        return g, g["build"]("CHK00001", year)

    if os.path.isfile(GEN):
        for year, leap in ((2026, False), (2027, False), (2028, True)):
            want = 6 if leap else 7
            try:
                g, svg = build_sheet(year)
                grey = svg.count('fill="#d9d9d9"')
                boxes = svg.count('width="5.0" height="5.0"')
                wd = len(re.findall(r'fill="#333">[LMJVSD]</text>', svg))
                years_printed = sorted(set(re.findall(r">\s*(20\d\d)\s*<", svg)))
                declared = g["impossible_cells"](year)
            except Exception as e:      # a broken generator is a failed check
                check(f"generator: {year} prints {want} impossible cells",
                      False, f"{want}", f"generator error: {e}")
                continue
            check(f"generator: {year} prints {want} impossible cells",
                  grey == want and declared == want, f"{want} shaded",
                  f"{grey} shaded, declares {declared}",
                  "leap year" if leap else "common year")
            check(f"generator: {year} prints {372 - want} day checkboxes",
                  boxes == 372 - want, f"{372 - want}", f"{boxes}")
            check(f"generator: {year} prints a weekday letter on every day cell",
                  wd == 372 - want, f"{372 - want}", f"{wd}",
                  "dropped in v1.3, restored in v1.4")
            check(f"generator: {year} sheet prints no year anywhere",
                  not years_printed, "none",
                  "none" if not years_printed else ", ".join(years_printed),
                  "the period is the handwritten box, not the grid")
        gsrc = read(GEN)
        check("generator: the handwritten year box is still on the sheet",
              "TAONA / ANN&#201;E" in gsrc, "present",
              "present" if "TAONA / ANN&#201;E" in gsrc else "MISSING",
              "kept exactly as built at v1.3")
        check("generator: the header phrase carries no year",
              "Calendrier de fonctionnement de la pompe</text>" in gsrc,
              "no year", "no year"
              if "Calendrier de fonctionnement de la pompe</text>" in gsrc
              else "YEAR PRINTED")

    # ---- 7ai. the live form still matches what the SOPs say it does -------
    # SOP-MAD-SDWS27-CalendrierGardien chapter 11 stated for months that the
    # calendar photograph field was mandatory in mWater. It was not: 2.15.6
    # carried required:false from the day it was written. Nothing caught it,
    # because nothing had ever compared a sentence in a procedure with the
    # form it describes. docs/sop_form_conformance.md is that comparison; this
    # is the part of it that runs on every build.
    #
    # The checker cannot call mWater - publish.sh has to work without network
    # or credentials - so it asserts against data/mwater_form_snapshot.json,
    # rewritten by tools/refresh_form_snapshot.py. A form edit made in the
    # designer is caught the next time that is run, and the failing check
    # names what moved.
    SNAPPATH = os.path.join(repo_root, "data", "mwater_form_snapshot.json")
    check("the mWater form snapshot is in the repository",
          os.path.isfile(SNAPPATH), "present",
          "present" if os.path.isfile(SNAPPATH) else "MISSING",
          "evidence for docs/sop_form_conformance.md")
    if os.path.isfile(SNAPPATH):
        snap = json.load(open(SNAPPATH, encoding="utf8"))
        # Freshness. The conformance claims on the page are worth exactly as
        # much as the last time someone read the forms, so this is a gate and
        # not a warning: publish.sh refreshes the snapshot where it can, and
        # where it cannot, a stale claim stops the build instead of going out
        # quietly. MAX_AGE_DAYS is the same constant the page cites.
        MAX_AGE_DAYS = 7
        fetched = snap.get("fetched", "")
        try:
            age = (datetime.date.today() - datetime.date.fromisoformat(fetched)).days
        except Exception:
            age = None
        check("the form snapshot records when it was read",
              age is not None, "an ISO date", fetched or "MISSING")
        if age is not None:
            check(f"the form snapshot is at most {MAX_AGE_DAYS} days old",
                  age <= MAX_AGE_DAYS, f"<= {MAX_AGE_DAYS} days",
                  f"{age} day(s) old", "" if age <= MAX_AGE_DAYS else
                  "run: python3 tools/refresh_form_snapshot.py")
            nice = datetime.date.fromisoformat(fetched).strftime("%-d %B %Y")
            check("the page states when the forms were last read",
                  nice in idx, nice, nice if nice in idx else "NOT ON THE PAGE",
                  "a reader can see how fresh the conformance claim is")
        pm = snap["forms"].get("preventive-maintenance", {})
        byc = {q["code"]: q for q in pm.get("questions", []) if q.get("code")}
        byid = {q["id"]: q for q in pm.get("questions", [])}
        PRESENCE = "e04e8727a1264f2aa8f6628d6f014097"
        YES = "DT5tf4B"
        NO = "WeT1Q1t"

        def cond_on(q, qid, literal):
            for c in q.get("conditions") or []:
                if (c.get("op") == "is" and (c.get("lhs") or {}).get("question") == qid
                        and (c.get("rhs") or {}).get("literal") == literal):
                    return True
            return False

        pres = byc.get("2.15.5bis")
        check("form: a calendar-presence question exists and is required",
              bool(pres) and pres["id"] == PRESENCE and pres["required"],
              "2.15.5bis required",
              "2.15.5bis required" if pres and pres["required"] else "MISSING OR OPTIONAL",
              "is a calendar physically present at the point")
        reason = byc.get("2.15.5ter")
        check("form: an absence-reason question exists, shown when there is none",
              bool(reason) and cond_on(reason, PRESENCE, NO) and not reason["required"],
              "2.15.5ter optional, on No",
              "2.15.5ter optional, on No" if reason and cond_on(reason, PRESENCE, NO)
              else "MISSING OR UNCONDITIONAL",
              "absence recorded with a reason, not inferred")
        photo = byc.get("2.15.6")
        check("form: the calendar photograph is REQUIRED when a calendar is present",
              bool(photo) and photo["required"] and cond_on(photo, PRESENCE, YES),
              "2.15.6 required on Yes",
              "2.15.6 required on Yes" if photo and photo["required"]
              and cond_on(photo, PRESENCE, YES) else "RELAXED",
              "this is the assertion that was false for months")
        # the three of them have to stay in one group, or the condition is
        # invisible to the technician answering it
        grps = {byid[i]["group"] for i in (PRESENCE,) if i in byid}
        same = all(q and q.get("group") in grps for q in (pres, reason, photo))
        check("form: presence, reason and photograph sit in one question group",
              same and bool(grps), "one group",
              "one group" if same and grps else "SPLIT",
              next(iter(grps)) if grps else "")
        # no code may be reused within a form: codes are export column headers
        # and the evidence pack is built from exports
        dups = {}
        for fname, f in snap["forms"].items():
            seen = collections.Counter(q["code"] for q in f["questions"] if q.get("code"))
            d = {c: n for c, n in seen.items() if n > 1}
            if d:
                dups[fname] = d
        # No code may be reused within a form, on ANY of them. Nine collisions
        # across four forms were cleared on 20-21 September; this keeps them
        # cleared rather than trusting that they stay that way.
        check("form: no question code is reused within any form",
              not dups, "0 across 12 forms",
              "0 across 12 forms" if not dups else
              "; ".join(f"{f}: {', '.join(sorted(c))}" for f, c in sorted(dups.items())),
              "a reused code collides as an export column header")

        # Every unconditionally-required evidence photograph was the same
        # trap: a technician who cannot proceed photographs something, and 206
        # of the photographs on file are not calendars. Both forms now ask
        # whether there is a calendar before demanding a picture of one.
        for fname, pcode, prescode, presid, yes in (
                ("preventive-maintenance", "2.15.5", "2.15.5bis",
                 "e04e8727a1264f2aa8f6628d6f014097", "DT5tf4B"),
                ("repair-after-breakdown", "1.3.1.3", "1.3.1.2bis",
                 "1dfdba4b4d2a4178ae3bf5d779fecde2", "Nvwlvgw")):
            fq = {q["code"]: q for q in snap["forms"].get(fname, {}).get("questions", [])
                  if q.get("code")}
            ph, pr = fq.get(pcode), fq.get(prescode)
            ok = (ph and pr and pr["required"] and ph["required"]
                  and any(c.get("op") == "is"
                          and (c.get("lhs") or {}).get("question") == presid
                          and (c.get("rhs") or {}).get("literal") == yes
                          for c in ph["conditions"]))
            check(f"form: {fname} {pcode} is required only where a calendar is present",
                  bool(ok), f"{pcode} on {prescode}",
                  f"{pcode} on {prescode}" if ok else "UNCONDITIONAL OR MISSING",
                  "asking for a photograph of a sheet that is not there produces a photograph of something else")
        check("every snapshot form is active",
              all(f.get("state") == "active" for f in snap["forms"].values()),
              f"{len(snap['forms'])} active",
              f"{sum(1 for f in snap['forms'].values() if f.get('state') == 'active')} active")
        check("preventive-maintenance is deployed to all four districts",
              sum(1 for d in pm.get("deployments", []) if d["active"]) == 4,
              "4 active", f"{sum(1 for d in pm.get('deployments', []) if d['active'])} active")

    check("the page states the photograph is mandatory where a calendar exists",
          "mandatory wherever a calendar is present" in idx
          and "absence is recorded rather than inferred" in idx, "stated",
          "stated" if "mandatory wherever a calendar is present" in idx else "MISSING",
          "and absence is recorded, not inferred")
    check("the page carries the conformance sweep counts",
          all(s in idx for s in ("SOPs swept", "16 conform")) or
          all(s in idx for s in ("</b> SOPs, <b>12</b> live mWater forms", "16 conform")),
          "counted", "counted" if "16 conform" in idx else "MISSING",
          "15 SOPs, 25 resolved, 16 conform, 8 discrepancies")
    for aid in ("act-photo-conditional-on-presence", "act-decommission-inactivity-field",
                "act-duplicate-codes-sweep", "act-emergency-event-form"):
        check(f"conformance discrepancy is actioned: {aid}",
              f'<tr id="{aid}">' in ACTSRC, "present",
              "present" if f'<tr id="{aid}">' in ACTSRC else "MISSING",
              "touches carbon evidence")

    # The decommissioning rule is a programme decision, not a form edit: it sets
    # the register and the register is the denominator of every carbon figure
    # here. The paper must exist, say what it is for, and be owned by the person
    # who makes the call.
    dec = os.path.join(repo_root, "docs", "decommissioning_rule_question.md")
    dtext = read(dec) if os.path.isfile(dec) else ""
    check("the decommissioning decision is recorded",
          "decision record" in dtext.lower()
          and "will not decommission or retire water points for inactivity" in dtext
          and "908" in dtext,
          "recorded", "recorded" if "will not decommission" in dtext else "STILL A QUESTION",
          "docs/decommissioning_rule_question.md")
    m = re.search(r'<tr id="act-decommission-inactivity-field">.*?</tr>', ACTSRC, re.S)
    row = m.group(0) if m else ""
    check("the page states the decision and why it is the conservative one",
          "not decommission or retire water points for inactivity" in idx
          and "flatters the fleet average" in idx, "stated",
          "stated" if "flatters the fleet average" in idx else "MISSING",
          "removing weak points would raise availability with no pump working better")
    check("the decommissioning action links the decision record",
          "decommissioning_rule_question.md" in row, "linked",
          "linked" if "decommissioning_rule_question.md" in row else "MISSING")
    check("the decision leaves no owner, because there is no question left",
          "Jan de Graaf" not in row, "no owner",
          "no owner" if "Jan de Graaf" not in row else "STILL ASSIGNED")

    # ---- days operational is a stratum figure, and says so -------------
    check("the page quotes the premises-TYPE wording from the registered text",
          "premises <i>type</i> p" in idx and "page 58" in idx, "quoted",
          "quoted" if "premises <i>type</i> p" in idx else "ASSERTED ONLY",
          "three of Equation 5's four terms carry it")
    check("the page states what must be shown is representativeness, not completeness",
          "representative of the stratum, not complete for every point" in idx,
          "stated", "stated" if "representative of the stratum" in idx else "MISSING")
    check("the stratum figures carry their point-year counts",
          "415" in idx and "353.6" in idx and "353.3" in idx, "present",
          "present" if "353.6" in idx else "MISSING",
          "portfolio and both districts")
    check("the page reports the representativeness test and its answer",
          "Yes, it is biased" in idx and "64.8%" in idx and "19.8%" in idx,
          "reported", "reported" if "Yes, it is biased" in idx else "MISSING",
          "visit frequency, threefold")
    # The "44 pumps reported down that read as fully operational" block was
    # removed on 23 September 2026: the 44-pump list cannot be rebuilt from
    # any extract (a stable enumeration gives 26-33, not 44), so neither the
    # comparison nor the two readings built on it can be shown. It stays off
    # the page until that list is derivable. See docs/decision_log.md.
    _unv = [p_ for p_ in ("read like the rest of the fleet",
                          "should not look like every other pump",
                          "read as fully operational",
                          "not marking outage days")
            if p_ in idx]
    check("the unverifiable 44-pump comparison stays off the page",
          not _unv, "absent", "; ".join(_unv) if _unv else "absent",
          "a claim nothing on the page can support")

    # ---- repair time is a headline metric ------------------------------
    check("time to repair is on the page with its baseline",
          "Time to repair" in idx and "187" in idx and "Median 84 days open" in idx,
          "present", "present" if "Median 84 days open" in idx else "MISSING",
          "median 1 day recorded; 44 tickets open at a median 84 days")

    # ---- 7aj. the calendar is the record; the call centre is not -------
    # Decided 21 September 2026. A call-centre ticket is a dispatch artefact:
    # opened when somebody telephones, closed when somebody reports back, and
    # neither event is an observation of the pump. Treating ticket age as
    # downtime measures the reporting process, not the asset - which is how a
    # 297 tCO2e figure came to be published and then withdrawn.
    check("the page states which instrument is the official record",
          "official record of days operational" in idx
          and "the report-back did not arrive" in idx, "stated",
          "stated" if "official record of days operational" in idx else "MISSING",
          "calendar governs; the call centre dispatches")
    check("the page carries the correct position, not the correction",
          "No carbon quantity is attached to any of this" in idx
          and not re.search(r"\b297\s*(?:tCO|tonnes?\b|t\b)",
                            re.sub(r"<[^>]+>", " ", re.sub(
                                r"<script[^>]*>.*?</script>", " ", idx, flags=re.S))),
          "position only", "position only"
          if "No carbon quantity is attached to any of this" in idx else "MISSING",
          "the withdrawal is recorded in docs/decision_log.md")
    check("the transcription round is still reachable from the page",
          "act-transcription-round" in idx, "linked",
          "linked" if "act-transcription-round" in idx else "MISSING")
    check("the decision log records both decisions",
          all(s in read(os.path.join(repo_root, "docs", "decision_log.md"))
              for s in ("official record of days operational",
                        "No decommissioning or retirement for inactivity", "297"))
          if os.path.isfile(os.path.join(repo_root, "docs", "decision_log.md")) else False,
          "recorded", "recorded"
          if os.path.isfile(os.path.join(repo_root, "docs", "decision_log.md")) else "MISSING",
          "docs/decision_log.md")

    # No call-centre-derived quantity may appear in tonnes. The call centre
    # counts tickets; it does not measure days, and a tonnage computed from a
    # ticket count is a category error however it is hedged.
    CALLCENTRE = re.compile(r"\b(call[-\s]centre|call[-\s]center|tickets?|backlog)\b", re.I)
    TONNES = re.compile(r"tCO\s?2\s?e|\btonnes?\b", re.I)
    WITHDRAWN = re.compile(r"withdraw|withdrawn|no longer|not replaced|was computed|"
                           r"category error|no carbon quantity", re.I)
    # Prose only: an inline <script> is data, not a published sentence, and
    # its array literals are not English however they are split.
    prose_only = re.sub(r"<script[^>]*>.*?</script>", " ", idx, flags=re.S)
    # Normalise the unit BEFORE stripping tags: tCO<sub>2</sub>e becomes
    # "tCO 2 e" once the tags go, which matches nothing.
    prose_only = prose_only.replace("tCO<sub>2</sub>e", "tCO2e")
    plain3 = re.sub(r"<[^>]+>", " ", prose_only)
    plain3 = (plain3.replace("&mdash;", "—").replace("&nbsp;", " ")
              .replace("tCO", "tCO").replace("&ldquo;", '"').replace("&rdquo;", '"'))
    plain3 = re.sub(r"\s+", " ", plain3)
    bad = []
    for sent in re.split(r"(?<=[.!?])\s+", plain3):
        if CALLCENTRE.search(sent) and TONNES.search(sent) and not WITHDRAWN.search(sent):
            bad.append(sent[:110])
    check("no call-centre-derived quantity appears in tonnes",
          not bad, "none", f"{len(bad)} offending" if bad else "none",
          "; ".join(bad)[:160] if bad else "an open ticket is not a day not operational")
    check("the page says the repair median cannot show a backlog",
          "cannot show a backlog" in idx, "stated",
          "stated" if "cannot show a backlog" in idx else "MISSING",
          "the form is created when the repair is finished")
    check("the repair-time action exists with the baseline on it",
          '<tr id="act-repair-time">' in ACTSRC, "present",
          "present" if '<tr id="act-repair-time">' in ACTSRC else "MISSING")
    # The count of forms the account could see (741, on the day of the
    # listing) is stored nowhere and was dropped on 23 September 2026; the
    # finding it supported - that the form does not exist - is what is kept.
    _settled = "does not exist" in idx and "paged to exhaustion" in idx
    check("the emergency-event form is settled either way",
          _settled, "settled",
          "settled" if _settled else "STILL UNVERIFIED",
          "the form listing was paged to exhaustion")

    # ---- 7ak. every evidenced-point count names its basis ---------------
    # Two counts of "points with evidence" are in use and both are correct
    # under their own definition: the day-call basis (points the extraction
    # produces day calls for, >=30-day observed window, any sheet year) and
    # the 2026-dated-sheet basis (points with a readable dated sheet covering
    # part of 2026). Having two live invites the reader to compare them, so
    # neither may appear naked.
    BASES = ("day-call basis", "2026-dated-sheet basis")
    check("both evidenced-point bases are defined on the page",
          all(b in idx for b in BASES)
          and "not interchangeable and neither is wrong" in idx,
          "both defined",
          "both defined" if all(b in idx for b in BASES) else "MISSING",
          "308/310 day-call; 295/309 2026-dated-sheet")
    prose_b = re.sub(r"<script[^>]*>.*?</script>", " ", idx, flags=re.S)
    plain_b = re.sub(r"<[^>]+>", " ", prose_b)
    plain_b = re.sub(r"\s+", " ", plain_b.replace("&mdash;", "—"))
    naked = []
    for sent in re.split(r"(?<=[.!?])\s+", plain_b):
        # "308 days ago" is an age, not a count of points; on 25 September
        # a survey dated 21 November 2025 was exactly 308 days old
        if not re.search(r"\b(308|295|309)\b(?!\s*days?\b)", sent):
            continue
        if any(b in sent for b in BASES):
            continue
        # a sentence that only carries the number as part of the definition
        # itself is fine, and so is one that spells the basis out in words
        if re.search(r"day call|dated sheet|covers part of|observed window", sent, re.I):
            continue
        naked.append(sent.strip()[:110])
    check("no evidenced-point count appears without its basis named",
          not naked, "none", f"{len(naked)} naked" if naked else "none",
          "; ".join(naked)[:150] if naked else "308/310 and 295/309 are different questions")

    # ---- 7al. the transcription round loads calendars, and only calendars --
    # Sheet 8 of the live page was a photograph of an information signboard.
    # The corpus scan had already flagged it - the exclusion was applied to
    # the machine-comparable arm and never to the 33 sheets kept outside the
    # frame, which were drawn from the reader's REJECTED pool where 18.4% are
    # not calendars. The rule now is positive classification on both arms.
    SELP = os.path.join(repo_root, "transcription", "validation_selection.csv")
    CALP = os.path.join(repo_root, "transcription", "calendars.json")
    NCP = os.path.join(repo_root, "data", "calendar_not_calendar.csv")
    FRP = os.path.join(repo_root, "data", "calendar_validation_frame.csv")
    SYP = os.path.join(repo_root, "data", "calendar_sheet_year.csv")
    if all(os.path.isfile(x) for x in (SELP, CALP, NCP, FRP, SYP)):
        import csv as _csv
        _sel = list(_csv.DictReader(open(SELP, encoding="utf8")))
        _cal = json.load(open(CALP, encoding="utf8"))
        _nc = {r["image_id"] for r in _csv.DictReader(open(NCP, encoding="utf8"))}
        _fr = {r["image_id"] for r in _csv.DictReader(open(FRP, encoding="utf8"))}
        _sy = {r["image_id"] for r in _csv.DictReader(open(SYP, encoding="utf8"))}

        _bad = [r for r in _sel if r["image_id"] in _nc]
        check("no selected sheet is on the non-calendar list",
              not _bad, "0 of %d" % len(_sel),
              "0 of %d" % len(_sel) if not _bad
              else "%d: %s" % (len(_bad), ", ".join(r["water_point"] for r in _bad)),
              "a signboard reached the live page as sheet 8")

        # Positive classification, arm by arm. In-frame: the extraction fitted
        # a twelve-month grid AND registered day rows AND read the year - no
        # known non-calendar survives that. Out-of-frame: by construction the
        # machine produced nothing, so the strongest positive signal available
        # is that the reader accepted the image as a calendar.
        _inf = [r for r in _sel if r["in_frame"] == "yes"]
        _out = [r for r in _sel if r["in_frame"] != "yes"]
        _nf = [r for r in _inf if r["image_id"] not in _fr]
        check("every machine-comparable sheet is positively classified (in the frame)",
              not _nf, "%d in frame" % len(_inf),
              "%d in frame" % len(_inf) if not _nf else "%d outside" % len(_nf),
              "twelve-month grid fitted, day rows registered, year read")
        _na = [r for r in _out if r["image_id"] not in _sy]
        check("every out-of-frame sheet was positively accepted by the reader",
              not _na, "%d accepted" % len(_out),
              "%d accepted" % len(_out) if not _na else "%d from the rejected pool" % len(_na),
              "the rejected pool is 18.4% non-calendars; the accepted pool 2.6%")
        check("the round still holds 50 machine-comparable calendars",
              len(_inf) == 50, "50", str(len(_inf)))
        check("calendars.json and the selection agree",
              len(_cal) == len(_sel), "%d" % len(_sel), "%d" % len(_cal))
        _cmp = sum(1 for c in _cal if c.get("cmp"))
        check("calendars.json marks 50 sheets machine-comparable",
              _cmp == 50, "50", str(_cmp))
        # A withdrawn sheet's number is retired: storage on the page is keyed
        # by sheet number, so reusing one would attach an existing transcript
        # to a different photograph.
        # Sixteen sheet numbers were withdrawn: four photographs that were not
        # calendars, and twelve drawn from the reader's rejected pool. Their
        # numbers are retired for good - the page keys stored transcriptions by
        # sheet number, so reusing one would silently attach somebody's work to
        # a different photograph.
        RETIRED = (1, 8, 9, 13, 15, 17, 20, 21, 24, 25, 29, 37, 41, 45, 47, 49)
        _ns = {c["n"] for c in _cal}
        _reused = sorted(_ns & set(RETIRED))
        check("no withdrawn sheet number has been reused",
              not _reused, "%d retired" % len(RETIRED),
              "%d retired" % len(RETIRED) if not _reused
              else "REUSED: %s" % _reused,
              "page storage is keyed by sheet number")
        MAP = "/home/bushp/sdws1/calendar_extract/transcription_sheet_map.csv"
        if os.path.isfile(MAP):
            _m = list(_csv.DictReader(open(MAP, encoding="utf8")))
            _dupe = collections.Counter(int(r["sheet"]) for r in _m)
            _dd = {k: v for k, v in _dupe.items() if v > 1}
            check("no sheet number has ever been given to two images",
                  not _dd, "0", "0" if not _dd else str(_dd),
                  "the assignment log is append-only")
        _imgdir = os.path.join(repo_root, "transcription", "img")
        _files = len([f for f in os.listdir(_imgdir)]) if os.path.isdir(_imgdir) else -1
        check("every loaded sheet has its image and no orphan remains",
              _files == len(_cal), "%d files" % len(_cal), "%d files" % _files)

    # ---- 7am. the withdrawn figures stay withdrawn ----------------------
    # A reader needs the correct position, not a narration of our corrections.
    # The withdrawal itself belongs in the decision log, where a verifier looks.
    _plainw = re.sub(r"<[^>]+>", " ",
                     re.sub(r"<script[^>]*>.*?</script>", " ", idx, flags=re.S))
    # the withdrawn figure is 297 tCO2e, not the integer 297: the
    # calendar-evidenced population is 297 records and is a different
    # quantity that happens to share the number.
    _re297 = re.findall(r"\b297\s*(?:tCO|tonnes?\b|t\b)", _plainw)
    _re35 = re.findall(r"3\.5\s*tCO", _plainw)
    check("the withdrawn call-centre tonnages do not appear on the page",
          not _re297 and not _re35, "absent",
          "absent" if not _re297 and not _re35
          else "297 x%d, 3.5 tCO x%d" % (len(_re297), len(_re35)),
          "the correct position, not our corrections")
    _dl = os.path.join(repo_root, "docs", "decision_log.md")
    _dltext = read(_dl) if os.path.isfile(_dl) else ""
    check("the decision log still records what was withdrawn",
          "297" in _dltext and "3.5" in _dltext and "withdrawn" in _dltext,
          "recorded", "recorded" if "297" in _dltext else "LOST",
          "the audit trail keeps them; the page does not")

    # ---- 7an. state what the estate is, not what is missing from it -----
    # "This map draws 735 of the 736 hand pumps" reads to a donor as a hole in
    # the register. It was not one: the point had a record and a GPS fix, and
    # only its group membership was wrong. Say what we have; put the defect in
    # the provenance note and on the action list, where it belongs.
    #
    # This fires on "N of (the) M" where the two are close and the sentence is
    # about our own estate. It deliberately does NOT fire on a sample result -
    # "21 of 24 sampled sheets" is a finding, not a gap.
    NOFM = re.compile(r"\b(\d[\d,]*)\s+of\s+(?:the\s+)?(\d[\d,]*)\b")
    ESTATE = re.compile(r"\b(hand ?pumps?|water ?points?|mapped points?|points|pumps|"
                        r"register|estate|under active management|portfolio)\b", re.I)
    SAMPLEY = re.compile(r"\bsampl(?:e|ed|es|ing)\b|\bdrawn\b|\bsheets?\b|"
                         r"\bresponses?\b|\brecords? in\b|\bquartile\b", re.I)
    offenders = []
    for f, src in (("index.html", idx), ("portfolio.html", prt)):
        pr_ = re.sub(r"<script[^>]*>.*?</script>", " ", src, flags=re.S)
        pl = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", pr_))
        for sent in re.split(r"(?<=[.!?])\s+", pl):
            if SAMPLEY.search(sent):
                continue
            if not ESTATE.search(sent):
                continue
            for m in NOFM.finditer(sent):
                a = int(m.group(1).replace(",", ""))
                b = int(m.group(2).replace(",", ""))
                if b > a and (b - a) <= 3 and b >= 20:
                    offenders.append(f"{f}: '{m.group(0)}' in \"{sent.strip()[:80]}\"")
    check("no sentence describes the estate as all-but-a-few",
          not offenders, "none",
          f"{len(offenders)} offending" if offenders else "none",
          "; ".join(offenders)[:170] if offenders
          else "state the estate, not the shortfall")

    # ---- 7ao. what the weekly build requires to survive -----------------
    # The Monday task ("SaniTap weekly water report - build, archive, publish",
    # 05:00) does not rewrite this page. It takes the live index.html as its
    # template and regenerates the embedded data inside it, so structure,
    # prose, collapse states and styling persist from edition to edition.
    # Four things are named in its instructions as must-preserve. A future
    # restructuring could drop one silently; these four checks are what stop
    # that reaching a published edition.
    SCOPES = ("all", "mad", "madx", "mar", "enduro")
    declared = set()
    for v in re.findall(r'data-scopes="([^"]+)"', idx):
        declared |= set(v.split())
    check("weekly build invariant: the five scope buttons survive",
          'id="scopebar"' in idx and set(SCOPES) <= declared,
          "scopebar + 5 scopes",
          "scopebar + %d scopes" % len(declared & set(SCOPES))
          if 'id="scopebar"' in idx else "SCOPEBAR MISSING",
          ", ".join(sorted(declared & set(SCOPES))))
    # the phrase carries inline markup, so match on the two halves that
    # straddle it rather than on a contiguous string
    CLOCK = "counts from the most recent preventive visit or repair"
    CLOCK2 = "excluded from the overdue count until they are commissioned in mWater"
    check("weekly build invariant: the maintenance clock rule survives",
          CLOCK in idx and CLOCK2 in idx, "stated",
          "stated" if CLOCK in idx else "MISSING",
          "counts from the last works record, not from registration")
    check("weekly build invariant: the Marolinta exclusion survives",
          "Marolinta is excluded" in idx, "stated",
          "stated" if "Marolinta is excluded" in idx else "MISSING")
    MGMT = ("Management notes &mdash; internal, remove before sharing with a "
            "validation and verification body (VVB)")
    mgmt_ok = MGMT in idx or "Management notes" in idx
    # it must also still be collapsed: it is explicitly not for a VVB
    m = re.search(r"<details[^>]*>\s*<summary[^>]*>[^<]*Management notes", idx)
    check("weekly build invariant: the internal management notes survive, collapsed",
          mgmt_ok and m is not None, "present and collapsed",
          "present and collapsed" if (mgmt_ok and m) else
          ("present, NOT collapsed" if mgmt_ok else "MISSING"),
          "remove before sharing with a VVB")

    # ---- 7ap. a number must not run into its label ----------------------
    # 16 stat tiles are marked up <div class="stat"><b>674</b><span>of 736
    # points...</span></div>. Both b and span are inline, and .stat had no CSS
    # rule at all, so the browser rendered "674of 736 points" - fifteen of
    # them, right across the gardien-calendar section. The fix is the missing
    # rule, not spaces in the text; this check is what keeps it fixed, and
    # catches the same class of fault in any tile added later.
    check("the .stat tiles have a style rule, so the number is not inline with its label",
          re.search(r"\.stat\s*\{", idx) is not None
          and re.search(r"\.stat\s*>\s*b\s*\{[^}]*display:\s*block", idx) is not None,
          "rule present", "rule present"
          if re.search(r"\.stat\s*>\s*b\s*\{[^}]*display:\s*block", idx) else "MISSING",
          f"{idx.count('class=\"stat\"')} tiles use it")

    def rendered_text(src):
        """Approximate what a reader sees: inline tags close up, block tags break."""
        s = re.sub(r"<script[^>]*>.*?</script>", " ", src, flags=re.S)
        s = re.sub(r"<style[^>]*>.*?</style>", " ", s, flags=re.S)
        # the .stat tiles are block-displayed by the rule asserted above
        s = re.sub(r'(<div class="stat">)<b>(.*?)</b><span>', r"\1 \2 ", s)
        s = re.sub(r"</?(?:b|i|em|strong|span|sup|sub|a|code|small|u)\b[^>]*>", "", s)
        s = re.sub(r"<[^>]+>", " ", s)
        return s.replace("&mdash;", "—").replace("&nbsp;", " ")

    ALLOWED = re.compile(r"^\d(?:st|nd|rd|th|km|kg|mm|ml|GG|bis|ter|der)$|^[0-9a-f]{4,}$")
    collisions = sorted({m.group(0) for m in
                         re.finditer(r"\d[A-Za-z]{2,}", rendered_text(idx))
                         if not ALLOWED.match(m.group(0))})
    # an mWater choice id can legitimately sit against a digit in prose
    collisions = [c for c in collisions if not re.match(r"^\d[A-Za-z]\w*$", c) or len(c) > 6]
    check("no published number runs into the word after it",
          not collisions, "none",
          f"{len(collisions)}: {', '.join(collisions[:4])}" if collisions else "none",
          "a stat tile whose value and label render as one word")

    # ---- 7aq. one action list, and everything in it ---------------------
    # Actions used to be scattered through the page, several of them inside
    # collapsed blocks where nobody saw them. There is now one list, generated
    # from the detailed rows so the two cannot disagree, and every detailed
    # row links back up to it.
    acts = re.findall(r'<tr id="(act-[a-z0-9-]+)">(.*?)</tr>', ACTSRC, re.S)
    check("the consolidated action list is generated and present",
          '<!-- BEGIN GENERATED action-list' in idx and 'id="actions"' in idx,
          "present", "present" if 'id="actions"' in idx else "MISSING",
          f"{len(acts)} rows")
    # it must sit above the body: the whole point is that it is seen
    pos_actions = idx.find('id="actions"')
    # the Attention list used to mark the top of the body; it was a second
    # to-do list and was merged into the one list, so anchor on the first
    # substantive section instead
    pos_body = idx.find("<h2>Portfolio by partner</h2>")
    check("the action list sits near the top, below the fleet summary",
          0 < pos_actions < pos_body, "above the body",
          "above the body" if 0 < pos_actions < pos_body else "TOO LOW",
          "third section, after the fleet summary and the week")
    # The uplink existed because the detail lived in a second table and needed
    # a way back. There is no second table now: every action is rendered once,
    # in the list, with its detail collapsed inside its own row. What has to
    # hold instead is that each action is addressable from the list.
    unanchored = [k for k in _det if f'id="{k}"' not in idx]
    check("every action is addressable in the one list",
          not unanchored, f"{len(_det)} anchored",
          f"{len(_det) - len(unanchored)} anchored" if unanchored
          else f"{len(_det)} anchored",
          ", ".join(unanchored[:4]))
    stale_uplinks = idx.count("act-uplink")
    check("no row still carries a link back to a list it now sits in",
          stale_uplinks == 0, "none",
          f"{stale_uplinks} uplink(s)" if stale_uplinks else "none",
          "the uplink was the cost of having two presentations")
    # three states, no more
    labels = set(re.findall(r'<span class="pill (?:ok|warn|crit)">([A-Z]{2,})</span>', idx))
    check("the status vocabulary is exactly ACT / WATCH / OK",
          labels <= {"ACT", "WATCH", "OK", "OVERDUE"}, "ACT/WATCH/OK",
          ", ".join(sorted(labels)) or "none",
          "OVERDUE is a computed badge, not a stored state")
    # a hand-typed OVERDUE goes stale; only the generator may write one
    gb = idx.find("<!-- BEGIN GENERATED action-list")
    ge = idx.find("<!-- END GENERATED action-list -->")
    outside = idx[:gb] + idx[ge:] if gb >= 0 and ge > gb else idx
    check("no OVERDUE label is hand-written outside the generated list",
          ">OVERDUE<" not in outside, "none",
          "none" if ">OVERDUE<" not in outside
          else f"{outside.count('>OVERDUE<')} static",
          "it is computed from the deadline at build time")
    # nothing action-shaped may hide inside a collapsed block without a row
    ids = set(_det)
    ACTIONISH = re.compile(r"\bFix:|\bAction:|for the MadAvance team|"
                           r"to be confirmed with James|to be built in a separate session",
                           re.I)
    orphans = []
    for dm in re.finditer(r"<details\b.*?</details>", idx, re.S):
        blk = dm.group(0)
        if not ACTIONISH.search(re.sub(r"<[^>]+>", " ", blk)):
            continue
        if not any(i in blk for i in ids) and "act-uplink" not in blk:
            orphans.append(re.sub(r"\s+", " ",
                                  re.sub(r"<[^>]+>", " ", blk))[:80])
    check("no action-shaped text hides in a collapsed block without a row",
          not orphans, "none", f"{len(orphans)} orphan(s)" if orphans else "none",
          "; ".join(orphans)[:150])
    # closed means closed everywhere
    closed_ids = [a for a, body in acts if 'pill ok">OK' in body]
    stale = []
    for a in closed_ids:
        m = re.search(r'<tr id="%s">(.*?)</tr>' % a, idx, re.S)
        body = re.sub(r"<[^>]+>", " ", m.group(1)) if m else ""
        if re.search(r"\bstill (?:open|outstanding|to do|needs)\b", body, re.I):
            stale.append(a)
    check("nothing marked OK is still described as open",
          not stale, "none", ", ".join(stale) if stale else "none",
          f"{len(closed_ids)} closed this period")

    # ---- 7ar. what the source checks established, 21 September 2026 -----
    # Each of these replaced a note that was wrong about its own cause. They
    # are asserted so the corrected statement cannot quietly revert.
    # The paragraph describing the records outside the portfolio was removed
    # on 2026-09-23 (portfolio only). What this guards is the corrected
    # statement about the managed points, which stays.
    _regok = ("matches the register record for every one of them" in idx
              and "One known defect, not yet fixed" not in idx)
    check("the register note states the managed points match their records",
          _regok, "corrected", "corrected" if _regok else "OLD NOTE BACK",
          "the page does not read district from form answers; it matches the record")
    check("the duplicate-registration item is settled, not open",
          "are not in the managed portfolio at all" in idx,
          "settled", "settled"
          if "are not in the managed portfolio at all" in idx else "STILL OPEN",
          "3 of the 4 flagged codes are not portfolio points")
    check("the Marolinta section states its purpose and its scope",
          "pre-portfolio view of the Marolinta works" in idx
          and "not part of the portfolio" in idx, "stated",
          "stated" if "pre-portfolio view" in idx else "MISSING",
          "1 of 13 rows is a managed point")
    check("both rehabilitation forms are described with their real usage",
          "never received a single response" in idx, "stated",
          "stated" if "never received a single response" in idx else "MISSING",
          "no rehabilitation logged on either form this year")
    check("the decommissioning SOPs are not called obsolete",
          "Neither SOP is obsolete" in idx, "stated",
          "stated" if "Neither SOP is obsolete" in idx else "MISSING",
          "only the 95% pause clause is superseded")
    # Approval is our own workflow, not a methodology requirement, and a bulk
    # approval by someone who has not read the records manufactures assurance.
    # The action asks for criteria and a checked sample, not a number cleared.
    check("the approvals action asks for a quality check, not bulk approval",
          '<tr id="act-mwater-approval-policy">' in ACTSRC
          and "Explicitly out of scope" in idx
          and "a bulk approval by someone who has not read the records is worse than none" in idx,
          "scoped to a sample", "scoped to a sample"
          if '<tr id="act-mwater-approval-policy">' in ACTSRC else "STILL BULK",
          "1,464 old-combined-works records, sampled against written criteria")
    check("approval status is not presented as a caveat on any figure",
          "awaiting approval in mWater" not in idx
          and "still awaiting approval" not in idx, "absent",
          "absent" if "awaiting approval in mWater" not in idx else "PRESENT",
          "approval is not a data-quality signal")
    # narrowed 22 September: this is a count reconciliation against the SLT
    # minutes (10 and 10) versus the form (7 and 7), and it is Deichmann
    # reporting rather than carbon evidence
    check("the Marolinta count reconciliation is on the list",
          '<tr id="act-rehab-recording">' in ACTSRC
          and "the minutes say 10 and 10, the form holds 7 and 7" in idx, "raised",
          "raised" if "the minutes say 10 and 10" in idx else "MISSING",
          "Deichmann reporting, not carbon")

    # ---- 7as. a caption may not name a date in prose --------------------
    # "Activity logged in mWater in the 7 days to 7 September" sat above
    # counts that the build regenerates every week. The numbers moved and the
    # label did not, which is worse than either being wrong on its own. The
    # caption is now rendered from the data; this stops a literal creeping
    # back into a section heading or sub-heading.
    caps = re.findall(r'<div class="sechead">.*?</div></div>', idx, re.S)
    MONTH = (r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
             r"September|October|November|December)\b")
    bad_caps = []
    for c in caps:
        txt = re.sub(r"<[^>]+>", " ", c)
        for m in re.finditer(MONTH, txt):
            # a date that names an event in the past is fine; one that labels a
            # rolling window is not
            around = txt[max(0, m.start() - 70):m.end() + 40].lower()
            if re.search(r"\b(?:in the|to|last|past)\s+\d+\s+days?\s+to\b", around) \
               or "days to" in around:
                # the week caption is allowed to name a fixed date, because
                # that IS the window the data covers - but only while it also
                # says how far behind mWater it is
                low = txt.lower()
                if ("behind mwater" in low or "current with mwater" in low
                        or "level with mwater" in low):
                    continue
                bad_caps.append(re.sub(r"\s+", " ", around)[:80])
    check("no section caption labels a rolling window with a hard-coded date",
          not bad_caps, "none", f"{len(bad_caps)} found" if bad_caps else "none",
          "; ".join(bad_caps)[:150] if bad_caps
          else "the This Week caption is rendered from the data")
    # The caption used to be written in the browser from max(PUMPS.last_visit),
    # a maintenance-visit date presented as "activity logged in mWater". It is
    # now generated from data/data_freshness.json, which records the newest
    # date in the extract AND the newest in mWater, so the page states its own
    # age instead of implying it is current.
    fresh_p = os.path.join(repo_root, "data", "data_freshness.json")
    fresh = json.load(open(fresh_p)) if os.path.isfile(fresh_p) else {}
    wk = re.search(r"BEGIN GENERATED week-caption.*?END GENERATED week-caption",
                   idx, re.S)
    wk = wk.group(0) if wk else ""
    check("the This Week caption is generated from the freshness record",
          'id="weekcap"' in wk and bool(fresh), "generated",
          "generated" if 'id="weekcap"' in wk else "STILL WRITTEN",
          "tools/render_freshness.py from data/data_freshness.json")
    worst = fresh.get("worst_source_lag_days")
    check("the page states how far behind mWater its data is",
          ("level with mWater" in wk) if not worst
          else (f"{worst} days behind mWater" in wk and "By source:" in wk),
          "stated per source",
          "stated per source" if ("behind mWater" in wk or "level with" in wk)
          else "MISSING",
          "; ".join(f"{k} {v.get('behind_days')}d"
                    for k, v in sorted((fresh.get("per_source") or {}).items())))

    # ---- 7be. the call-centre tables are built, not carried -------------
    # Status, the down list and the partially-working list were the last part
    # of the page nothing here could rebuild: their builder was missing and
    # their rule was written down nowhere, so when the extract went stale they
    # kept 10 September values while everything around them moved. The rule
    # was recovered by comparison against the published tables and now lives
    # in tools/build_call_tables.py, which reproduces them exactly.
    ct_p = os.path.join(repo_root, "data", "call_tables.json")
    ct = json.load(open(ct_p)) if os.path.isfile(ct_p) else {}
    page_S = js_const(idx, "S") or {}
    check("the call-centre tables are generated, not carried forward",
          bool(ct.get("status")) and ct.get("split") == page_S.get("status"),
          "generated",
          "generated" if ct.get("split") == page_S.get("status")
          else f"page {page_S.get('status')} vs built {ct.get('split')}",
          f"built {ct.get('built')} by tools/build_call_tables.py")
    for name, want in (("DOWN", "down"), ("PARTIAL", "partial")):
        rows_ = js_const(idx, name) or []
        check(f"{name} matches the built status split",
              len(rows_) == (ct.get("split") or {}).get(want),
              str((ct.get("split") or {}).get(want)), str(len(rows_)),
              "the table is the status, not a separate list")
    # the rule a reader sees must be the rule the builder applies
    bsrc = read(os.path.join(repo_root, "tools", "build_call_tables.py"))
    m_rule = re.search(r'RULE_ON_PAGE = \((.*?)\)\n\n', bsrc, re.S)
    rule_txt = ""
    if m_rule:
        rule_txt = " ".join(re.findall(r'"([^"]*)"', m_rule.group(1)))
    plain_idx = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", idx))
    check("the rule on the page is the rule in the builder",
          bool(rule_txt) and re.sub(r"\s+", " ", rule_txt).strip() in plain_idx,
          "identical", "identical" if rule_txt and
          re.sub(r"\s+", " ", rule_txt).strip() in plain_idx else "DIVERGED",
          "a rule only one process knows is how this went wrong")
    holds_p = os.path.join(repo_root, "data", "call_status_holds.json")
    holds = (json.load(open(holds_p)).get("holds", {})
             if os.path.isfile(holds_p) else {})
    unreasoned = [k for k, v in holds.items() if not v.get("reason")]
    # the reproduction test is the regression test for the recovered rule,
    # and it must run against the frozen baseline, not against a page the
    # builder has already rewritten
    base_p = os.path.join(repo_root, "data", "call_status_baseline.json")
    base = json.load(open(base_p)) if os.path.isfile(base_p) else {}
    rc = subprocess.run([sys.executable, os.path.join(repo_root, "tools",
                                                      "build_call_tables.py"),
                         "--reproduce", base.get("cut", "2026-09-07")],
                        capture_output=True, text=True, cwd=repo_root)
    check("the builder still reproduces the frozen baseline exactly",
          rc.returncode == 0 and "exact match" in rc.stdout,
          "736/736 exact",
          "exact" if rc.returncode == 0
          else next((l.strip() for l in rc.stdout.splitlines()
                     if "DISAGREE" in l or "reproduce" in l), "FAILED"),
          f"{len(base.get('status', {}))} pumps as the 10 September build left them")
    check("every held pump says why it is held",
          bool(holds) and not unreasoned, "all reasoned",
          f"{len(unreasoned)} without a reason" if unreasoned
          else f"{len(holds)} held, all reasoned",
          "held on the published value rather than restated on a guess")
    check("the page says how many pumps are held",
          str(len(holds)) in plain_idx and "held on their" in plain_idx,
          "stated", "stated" if "held on their" in plain_idx else "MISSING",
          f"{len(holds)} pumps the rule cannot reproduce")

    # ---- 7bd. a build that ran and published nothing ---------------------
    # The weekly build runs in a CLOUD session, not on this computer - which
    # is why no local scheduler exists and why looking for one proved nothing.
    # When its push is refused it writes the built pages into the Windows
    # Downloads folder and asks for a manual push. On 21 September it did
    # exactly that: ran 05:09-06:01 UTC, pulled mWater, built a complete
    # week 39 edition, wrote it at 05:59 UTC - and nobody pushed it. Every
    # staleness check passed, because the published page was internally
    # consistent with its own fortnight-old extract.
    #
    # "Succeeded" from the scheduled task does not mean "published".
    drop_p = os.path.join(repo_root, "data", "build_drop.json")
    drop = json.load(open(drop_p)) if os.path.isfile(drop_p) else {}
    pub_issue = None
    mh = re.search(r"BEGIN GENERATED masthead.*?END GENERATED masthead", idx, re.S)
    if mh:
        m_ = re.search(r"issued\s+\w{3}\s+(\d{1,2})\s+(\w+)\s+(\d{4})", mh.group(0))
        if m_:
            for fmt in ("%d %b %Y", "%d %B %Y"):
                try:
                    pub_issue = datetime.datetime.strptime(
                        f"{m_.group(1)} {m_.group(2)} {m_.group(3)}", fmt).date()
                    break
                except ValueError:
                    pass
    built_issue = drop.get("built_issue_date")
    built_issue = datetime.date.fromisoformat(built_issue) if built_issue else None
    check("no completed build is newer than the published page",
          not (pub_issue and built_issue and built_issue > pub_issue),
          "nothing unpublished",
          f"build of {built_issue} not published (page is {pub_issue})"
          if (pub_issue and built_issue and built_issue > pub_issue)
          else "nothing unpublished",
          f"edition {drop.get('built_edition')} built "
          f"{drop.get('built_at_utc')} in {drop.get('drop_dir')}"
          if drop.get("files") else "no build output waiting")
    check("the build drop is inspected, not assumed empty",
          bool(drop) and "checked" in drop, "inspected",
          "inspected" if drop.get("checked") else "NEVER LOOKED",
          "tools/check_build_drop.py reads the Downloads fallback")

    # ---- 7bc. a stale extract FAILS the build, it does not warn -----------
    # This is the check that was missing. The extract sat at 7 September for
    # fourteen days and eight editions went out on it, every one of them
    # passing every check, because nothing compared the data's own date with
    # the date the build ran. Three days is the allowance: a weekly build
    # pulling on the day it runs is 0-1 days behind, and three leaves room
    # for a pull late on the Friday before.
    # Staleness is measured PER SOURCE against mWater, not against the
    # calendar: comparing the page to today would fail the build in a quiet
    # week, when the page is current and mWater simply holds nothing newer.
    MAX_SOURCE_LAG_DAYS = 2
    blocking = fresh.get("blocking_lag_days")
    per = fresh.get("per_source") or {}
    gaps = fresh.get("known_gaps") or {}
    late = [f"{k} {v['behind_days']}d" for k, v in per.items()
            if v.get("behind_days") and k not in gaps
            and v["behind_days"] > MAX_SOURCE_LAG_DAYS]
    check("no rebuildable source is behind mWater",
          blocking is not None and blocking <= MAX_SOURCE_LAG_DAYS,
          f"<= {MAX_SOURCE_LAG_DAYS} days behind",
          ", ".join(late) if late else f"{blocking} days behind",
          "run tools/pull_extract.py --write then tools/rebuild_activity.py --write")
    # a source the build cannot rebuild must be named, dated and actioned -
    # never just quietly excluded
    bad_gap = [k for k, v in gaps.items()
               if not v.get("reason") or not v.get("action")
               or f'id="{v["action"]}"' not in idx]
    check("every source the build cannot rebuild carries an action",
          not bad_gap, "all actioned",
          ", ".join(bad_gap) if bad_gap else "all actioned",
          "; ".join(f"{k} {per.get(k, {}).get('behind_days')}d behind"
                    for k in gaps) or "none")
    # and an absolute backstop, generous enough that a quiet week is fine
    MAX_ABSOLUTE_AGE_DAYS = 21
    age = fresh.get("page_age_days")
    check("the page is not running on an abandoned extract",
          age is not None and age <= MAX_ABSOLUTE_AGE_DAYS,
          f"<= {MAX_ABSOLUTE_AGE_DAYS} days old",
          "no extract date" if age is None else f"{age} days old",
          f"newest record on the page is {fresh.get('extract_newest')}")
    # pulled but never rebuilt from is a different failure with a different fix
    # per source, and excluding the source the build cannot rebuild at all -
    # that one is a named gap with an action, checked separately above
    gaps_ = fresh.get("known_gaps") or {}
    not_rebuilt = [k for k, v in (fresh.get("per_source") or {}).items()
                   if k not in gaps_ and (v.get("behind_days") or 0) > 0]
    check("the page was rebuilt from the extract that was pulled",
          not not_rebuilt, "rebuilt",
          ", ".join(not_rebuilt) if not_rebuilt else "rebuilt",
          "a pull that is never rebuilt from is the same as no pull")
    check("the masthead carries the extract date beside the issue date",
          "BEGIN GENERATED masthead" in idx
          and ("data to" in idx or "DATA" in idx and "DAYS OLD" in idx),
          "both dates", "both dates" if "BEGIN GENERATED masthead" in idx
          else "MISSING",
          "a reader sees the gap without opening anything")
    man_p = os.path.join(repo_root, "data", "extract_manifest.json")
    man = json.load(open(man_p)) if os.path.isfile(man_p) else {}
    # a manifest with no unique count was written by the old exporter, which
    # is exactly the thing that duplicated rows - so absence is a failure too
    resp = {k: v for k, v in man.get("files", {}).items() if v.get("form")}
    dups = [k for k, v in resp.items()
            if v.get("rows") and v.get("unique") is None] + \
           [k for k, v in resp.items()
            if v.get("rows") and v.get("unique") and v["rows"] != v["unique"]]
    # Computed here, not read from the manifest: a manifest written by the old
    # exporter has no stray list, and "the key is absent" must not read as "no
    # strays". repairs.csv - a correct export of the repair form under a name
    # no build opens - is exactly what this catches.
    CANONICAL = {"pm.csv", "reparation_apres_panne.csv",
                 "appel_signalement_pannes.csv", "premiere_rehabilitation.csv",
                 "forage_moramanga.csv", "wp_madavance.csv"}
    HISTORICAL = {"old_combined_reparation.csv", "wp_lookup.csv",
                  "suivi_gestion_pannes.csv"}
    exp_dir = os.path.expanduser("~/mwater-exports")
    strays = sorted(f for f in os.listdir(exp_dir)
                    if f.endswith(".csv")
                    and f not in CANONICAL | HISTORICAL) if os.path.isdir(exp_dir) else []
    check("no extract sits under a filename the build never reads",
          not strays, "none",
          f"{len(strays)} stray file(s)" if strays else "none",
          ", ".join(strays[:3]) if strays
          else "a correct pull under the wrong name changes nothing")
    check("the extract carries no duplicated records",
          bool(resp) and not dups, "none",
          f"{len(dups)} file(s)" if dups else ("none" if resp else "NO MANIFEST"),
          "the exporter's skip/limit paging duplicated 208 rows and lost the "
          "four newest; tools/pull_extract.py walks date windows instead")
    check("the leadership-team reconciliation is gone",
          "Reconciling with the senior leadership team" not in idx, "absent",
          "absent" if "Reconciling with the senior leadership team" not in idx
          else "PRESENT",
          "this report is the source of truth; it does not argue with an older one")
    check("the WorldPop coverage sentence is suppressed when nothing is uncovered",
          "Every point in this scope carries a figure" in idx
          and "carry no figure: `+" not in idx, "conditional",
          "conditional" if "Every point in this scope carries a figure" in idx
          else "STILL UNCONDITIONAL",
          "no dangling colon after an empty list")

    # ---- 7at. no container may render as an empty bordered box ----------
    # .tablewrap carries a border and a max-height, so a <table> whose <tbody>
    # is empty in the markup and never written by script renders as a large
    # empty white box. Three did - corrtbl, exctbl and tracetbl - inside
    # collapsed sections where nobody noticed, while the data sat on the page
    # the whole time. A table left empty in the markup is fine; a table left
    # empty with nothing to fill it is not.
    orphan_tables = []
    for m in re.finditer(r'<table\b([^>]*)>(.*?)</table>', idx, re.S):
        attrs, body = m.group(1), m.group(2)
        if not re.search(r"<tbody\b[^>]*>\s*</tbody>", body):
            continue
        tid = re.search(r'id="([A-Za-z0-9_-]+)"', attrs)
        if not tid:
            orphan_tables.append("(table with no id)")
            continue
        k = tid.group(1)
        written = re.search(r"['\"]#%s(?: tbody)?['\"]" % re.escape(k), idx) is not None
        if not written:
            orphan_tables.append(k)
    check("no table is left empty with nothing to fill it",
          not orphan_tables, "none",
          ", ".join(orphan_tables) if orphan_tables else "none",
          ".tablewrap has a border: an unfilled table is a blank box")
    # and a filler must cope with an empty list rather than leaving the border
    # Rather than a guard per filler - several have none and more will be
    # added - one sweep runs after everything is filled and hides any
    # .tablewrap left with no body rows.
    swept = ("function hideEmptyTableWraps()" in idx
             and "hideEmptyTableWraps();" in idx)
    check("an empty table cannot render as a bordered blank",
          swept, "swept after fill", "swept after fill" if swept else "NO SWEEP",
          "hideEmptyTableWraps hides any .tablewrap with no rows")

    # ---- 7au. the growth finding, and its two owners --------------------
    # Corrected 22 September: the 2026 works are Marolinta, Deichmann-funded
    # and outside the carbon programme, so the lighter progress form is the
    # right record and not a failure. The earlier note framed it as lost
    # carbon, which it is not.
    # 23 September: one point joined through a record correction, so the
    # finding is now "not grown through new work"; the substance is unchanged.
    check("the page states the carbon fleet has not grown, without alarm",
          "carbon fleet has not grown through new work since 1 January 2026" in idx
          and "that is the right form for uncredited work" in idx, "stated",
          "stated" if "carbon fleet has not grown through new work since 1 January 2026" in idx
          else "MISSING",
          "Marolinta is outside the carbon programme")
    check("the Marolinta work is not presented as lost carbon",
          "28.58" not in idx and "200</b> tCO<sub>2</sub>e a year" not in idx,
          "absent", "absent" if "28.58" not in idx else "STILL QUANTIFIED",
          "uncredited work carries no forgone tonnage")
    check("the retrospective-evidence consequence is recorded",
          "would not exist retrospectively" in idx, "recorded",
          "recorded" if "would not exist retrospectively" in idx else "MISSING",
          "if Marolinta were ever brought into the carbon programme")
    check("the form question and the programme question have separate owners",
          '<tr id="act-rehab-recording">' in ACTSRC and '<tr id="act-fleet-growth">' in ACTSRC,
          "two items", "two items"
          if '<tr id="act-fleet-growth">' in ACTSRC else "MERGED",
          "MadAvance restores recording; the Head of Carbon owns the pipeline")

    # ---- 7av. every table a script fills must actually exist ------------
    # A careless wrap once ate the opening <table id="downtbl"> tag and left a
    # stray ">" behind. The page still parsed, the section balance still
    # matched, and the table simply vanished. This is the cheap guard: if a
    # script writes to "#x tbody", there must be a <table id="x"> in the
    # markup to write into.
    missing_tables = []
    for m in re.finditer(r"""\$\('#([A-Za-z0-9_-]+) tbody'\)""", idx):
        k = m.group(1)
        if re.search(r'<table[^>]*id="%s"' % re.escape(k), idx):
            continue
        # a write guarded anywhere by `if($('#x tbody'))` is defensive, not a
        # fault: the table was removed and the writer copes. The guard sits on
        # the first reference; the write itself is the second.
        if re.search(r"""if\s*\(\s*\$\('#%s tbody'\)\s*\)""" % re.escape(k), idx):
            continue
        missing_tables.append(k)
    check("every table a script fills exists in the markup",
          not missing_tables, "all present",
          ", ".join(sorted(set(missing_tables))) if missing_tables else "all present",
          "a mangled opening tag makes a table vanish silently")
    # Tag balance, on the MARKUP only: a template literal inside <script> emits
    # tags as text and counting those makes every total meaningless.
    markup = re.sub(r"<script[^>]*>.*?</script>", " ", idx, flags=re.S)
    for tag in ("table", "thead", "tbody"):
        o = len(re.findall(r"<" + tag + r"[\s>]", markup))
        c = markup.count("</%s>" % tag)
        check(f"index.html: <{tag}> balanced", o == c, f"{o} open", f"{c} close")

    # ---- 7aw. partner blocks and their logos ----------------------------
    # The logos are held in the repo under assets/ rather than hot-linked, so
    # the page does not depend on three other people's servers staying up.
    for who in ("sanitap", "madavance", "enduro"):
        f = os.path.join(repo_root, "assets", f"{who}.png")
        ok = os.path.isfile(f) and os.path.getsize(f) < 120_000
        check(f"logo present and small: assets/{who}.png", ok,
              "< 120 kB", f"{os.path.getsize(f):,} B" if os.path.isfile(f) else "MISSING")
    check("no partner logo is hot-linked",
          not re.search(r'<img[^>]+src="https?://[^"]*logo', idx, re.I), "none",
          "none" if not re.search(r'<img[^>]+src="https?://[^"]*logo', idx, re.I)
          else "HOT-LINKED", "assets/ is the source")
    check("each partner has its own block",
          idx.count('<div class="partner">') == 3, "3 blocks",
          f"{idx.count(chr(60) + 'div class=' + chr(34) + 'partner' + chr(34) + '>')} blocks",
          "SaniTap, MadAvance, Endur'O")
    check("the Endur'O reconciliation is folded in, not a section of its own",
          "The Endur&rsquo;O estate, reconciled &mdash; three lists" in idx
          and "<h2>The Endur&rsquo;O estate, reconciled</h2>" not in idx,
          "folded", "folded"
          if "<h2>The Endur&rsquo;O estate, reconciled</h2>" not in idx else "STILL A SECTION")
    check("the MadAvance line no longer says 'tonight'",
          "computed from mWater tonight" not in idx, "absent",
          "absent" if "computed from mWater tonight" not in idx else "PRESENT",
          "the build is not always at night")

    conf = os.path.join(repo_root, "docs", "sop_form_conformance.md")
    ctext = read(conf) if os.path.isfile(conf) else ""
    check("the SOP/form conformance sweep is recorded",
          "SOP documents swept" in ctext and "Discrepancies" in ctext,
          "recorded", "recorded" if "SOP documents swept" in ctext else "MISSING",
          "docs/sop_form_conformance.md")

    # ---- 7ay. a named water point opens its own mWater record -----------
    # Codes are what the field teams act on, so every point this report names
    # in prose links straight to the record. The href must be the id the
    # entity API returned for that code - a link to the wrong record is worse
    # than no link - and a code we hold an id for must not be left unlinked.
    ids_p = os.path.join(repo_root, "data", "mwater_point_ids.json")
    wp_ids = json.load(open(ids_p)) if os.path.isfile(ids_p) else {}
    prose_wp = re.sub(r"<script[^>]*>.*?</script>", " ", idx, flags=re.S)
    bad = [c for u, c in re.findall(
        r'<a class="wp" href="https://portal\.mwater\.co/#/water_point/'
        r'([0-9a-f-]{36})"[^>]*>\s*<span class="mono">(\d{9})</span>', prose_wp)
        if wp_ids.get(c) != u]
    unlinked = [m.group(1) for m in
                re.finditer(r'(?<!>)<span class="mono">(\d{9})</span>', prose_wp)
                if m.group(1) in wp_ids
                and prose_wp[max(0, m.start() - 200):m.start()].rfind('<a class="wp"')
                <= prose_wp[max(0, m.start() - 200):m.start()].rfind("</a>")]
    check("every linked water point points at its own mWater record",
          not bad, "all correct", f"{len(bad)} wrong" if bad else "all correct",
          f"{len(wp_ids)} ids in data/mwater_point_ids.json")
    check("no named water point is left unlinked",
          not unlinked, "none", f"{len(unlinked)} unlinked" if unlinked else "none",
          ", ".join(sorted(set(unlinked))[:6]))

    # ---- 7az. the list is grouped, filtered, and counts what it holds ---
    # 93 rows in one flat table is a wall. The generated list must carry the
    # controls that make it usable, and - the defect this check exists for -
    # its header counts must match the pills on the detail rows. The status
    # map did not know the ACT/WATCH/OK vocabulary, so every row fell through
    # to ACT and the header read "93 to act on, 0 to watch, 0 closed" while
    # 8 rows said otherwise.
    gb_ = idx.find("<!-- BEGIN GENERATED action-list")
    ge_ = idx.find("<!-- END GENERATED action-list -->")
    genblk = idx[gb_:ge_] if 0 <= gb_ < ge_ else ""
    # rows are rendered twice - once flat, once grouped by owner - so count
    # them in the flat table only, which is the one the filters act on
    # nested tables live inside the collapsed detail of some rows, so bound
    # the flat table by the block that follows it rather than by </table>
    _ft = re.search(r'id="act-flat".*?(?=<div id="act-owner")', genblk, re.S)
    flatblk = _ft.group(0) if _ft else ""
    outside_ = idx[:gb_] + idx[ge_:] if 0 <= gb_ < ge_ else ""
    want_views = ['data-view="act"', 'data-view="nodate"',
                  'data-view="all"', 'data-view="owner"']
    check("the action list is grouped and filtered, not one flat wall",
          all(v in genblk for v in want_views) and 'class="ownerbar"' in genblk,
          "4 views + owners",
          "4 views + owners" if all(v in genblk for v in want_views)
          else "MISSING", "ACT by default, WATCH/OK and by-owner behind a control")
    check("every row in the list carries the state it is filtered on",
          flatblk.count("<tr data-state=") == len(acts),
          f"{len(acts)} tagged", f"{flatblk.count('<tr data-state=')} tagged",
          "data-state / data-own / data-nodate")
    # nesting-aware: a detail cell may hold its own table, and a non-greedy
    # match to the first </tr> truncates that row and loses its pill
    src_pills = collections.Counter()
    for m_ in re.finditer(r'<tr id="act-[a-z0-9-]+">', outside_):
        i_, depth_ = m_.end(), 1
        for tok_ in re.finditer(r"<tr\b|</tr>", outside_[i_:]):
            depth_ += 1 if tok_.group(0).startswith("<tr") else -1
            if depth_ == 0:
                b_ = outside_[i_:i_ + tok_.start()]
                pm_ = re.search(r'pill\s+[a-z]+">([A-Z]{2,})<', b_)
                src_pills[pm_.group(1) if pm_ else "NO PILL"] += 1
                break
    # The header counts are rendered from data/action_counts.json now, not
    # typed into the markup, so they are read from there. That is the stronger
    # test anyway: it compares the numbers the page will actually show against
    # the rows it actually renders, rather than against a regex on prose.
    acn_p = os.path.join(repo_root, "data", "action_counts.json")
    acn = json.loads(read(acn_p)) if os.path.exists(acn_p) else None
    hdr = acn is not None
    hdr_counts = (collections.Counter(
        {"ACT": acn["act"], "WATCH": acn["watch"], "OK": acn["closed"]})
        if acn else collections.Counter())
    rendered = collections.Counter(
        re.findall(r'<tr data-state="([A-Z]+)"', flatblk))
    check("the header counts match the rows it renders",
          bool(hdr) and hdr_counts == rendered, "they match",
          "they match" if hdr and hdr_counts == rendered
          else f"header {dict(hdr_counts)} vs rows {dict(rendered)}",
          "the status map must know ACT / WATCH / OK")
    # Where a condition decides the state, the rendered state must follow the
    # condition and not the pill on the detail row - that is the whole point
    # of the evaluator. Where there is NO condition the pill still governs.
    stp = os.path.join(repo_root, "data", "action_state.json")
    astate = (json.load(open(stp)) if os.path.isfile(stp) else {}).get("state", {})
    disagree = []
    for m_ in re.finditer(r'<tr data-state="([A-Z]+)" data-own="[^"]*"[^>]*>'
                          r'<td><a href="#(act-[a-z0-9-]+)"', flatblk):
        shown, aid = m_.group(1), m_.group(2)
        c_ = astate.get(aid) or {}
        if c_.get("satisfied") is True:
            want = c_.get("when_satisfied", "OK")
        elif c_.get("satisfied") is False:
            want = "ACT" if shown == "OK" else shown
        else:
            continue
        if shown != want:
            disagree.append(f"{aid}: shows {shown}, condition says {want}")
    check("a measured condition overrides the hand-set pill",
          not disagree, "condition wins",
          f"{len(disagree)} disagree" if disagree else "condition wins",
          "; ".join(disagree[:2])[:120] if disagree
          else f"{sum(1 for v in astate.values() if v.get('satisfied') is not None)}"
               " conditions evaluated this build")
    nod = acn and acn.get("nodate")
    want_nod = sum(1 for m in re.finditer(r'<tr data-state="ACT"([^>]*)>', flatblk)
                   if 'data-nodate="1"' in m.group(1))
    check("the no-date figure counts the rows it says it counts",
          nod is not None and int(nod) == want_nod,
          f"{want_nod}", str(nod) if nod is not None else "MISSING",
          "ACT rows with no proposed date - one decision for Jan")

    # ---- 7bb. owner and deadline come from the workbook, status does not --
    # The page is static and rebuilt weekly, so the two fields a person sets
    # live in one SharePoint workbook. The thing to guard is the boundary: if
    # status could be set there, an item could be marked done that the data
    # says is not.
    own_p = os.path.join(repo_root, "data", "action_owners.json")
    own_doc = json.load(open(own_p)) if os.path.isfile(own_p) else {}
    # The workbook opened READ-ONLY because Excel repaired it, and a repaired
    # workbook is always read-only. The cause was cells carrying an explicit
    # type with an empty body - 40 of them, one per row with no deadline.
    #
    # Two earlier assertions here were WRONG and are gone: that no zip member
    # starts with "[trash]", and that every member is declared in
    # [Content_Types].xml. [trash]/NNNN.dat is SharePoint's document-property
    # promotion filler; names containing [ or ] are not legal OPC part names,
    # so the packaging layer never sees them and Excel is unaffected. Almost
    # every file in a SharePoint library has them. Those checks failed on any
    # file that had round-tripped, which is every published copy.
    #
    # What is asserted instead are the invariants that actually predict a
    # repair, delegated to the generator's own verifier so there is one
    # definition of "well formed".
    def _XI_NAMES():
        sys.path.insert(0, os.path.join(repo_root, "tools"))
        import xlsx_invariants as _x
        return _x.INVARIANTS

    wbp = os.path.join(repo_root, "build", "action_owners.xlsx")
    wb_fault, wb_detail = None, []
    if not os.path.isfile(wbp):
        wb_fault = "not built"
    else:
        try:
            # xlsx_invariants carries no openpyxl dependency, so this runs
            # under the system python3 that publish.sh uses
            sys.path.insert(0, os.path.join(repo_root, "tools"))
            import xlsx_invariants as _xi
            import io as _io
            import contextlib as _ctx
            owners = set(re.findall(r'"([^"]+)"', re.search(
                r"OWNERS = \[(.*?)\]",
                read(os.path.join(repo_root, "tools", "make_owner_workbook.py")),
                re.S).group(1)))
            buf = _io.StringIO()
            with _ctx.redirect_stdout(buf):
                _ad = json.loads(read(os.path.join(
                    repo_root, "data", "action_details.json")))
                wb_detail = _xi.verify_detail(
                    wbp, expect_ids=list(_ad.keys()), expect_owners=owners)
        except Exception as e:                                 # noqa: BLE001
            wb_fault = f"verifier failed: {e}"

    # One check per invariant. The tally is the number of things asserted, so
    # six invariants behind one check() made the gate read 530 where it had
    # read 532 - two assertions deleted, six added, and the six invisible.
    # A tally that undercounts is worse than a big one.
    if wb_fault:
        for _k, _name in _XI_NAMES():
            check(f"owner workbook: {_name}", False, "ok", wb_fault[:60],
                  "the workbook could not be verified at all")
    else:
        for _k, _name, _f in wb_detail:
            check(f"owner workbook: {_name}",
                  _f == [], "ok",
                  "NOT EXERCISED" if _f is None else ("ok" if not _f else _f[0][:80]),
                  "an invariant that predicts an Excel repair")

    check("owner and deadline are read from the SharePoint workbook",
          bool(own_doc.get("owners")) and "action owners and deadlines" in
          own_doc.get("source", {}).get("file", ""),
          "read", "read" if own_doc.get("owners") else "MISSING",
          f'{len(own_doc.get("owners", {}))} rows from '
          f'{own_doc.get("source", {}).get("library", "?")}')
    stray = [k for r in own_doc.get("owners", {}).values() for k in r
             if k not in ("owner", "deadline")]
    check("the workbook carries nothing the build can compute",
          not stray, "owner + deadline only",
          f"also {', '.join(sorted(set(stray))[:3])}" if stray
          else "owner + deadline only",
          "status and closure are computed, never taken from the workbook")
    check("a workbook that cannot be read says so on the page",
          "MAX_WORKBOOK_AGE_DAYS" in read(os.path.join(repo_root, "tools",
                                                       "render_actions.py"))
          and ("owner and deadline workbook" in idx
               or "could not be read" in idx), "notice wired",
          "notice wired" if "owner and deadline workbook" in idx
          or "could not be read" in idx else "SILENT FALLBACK",
          "stale values are never shown silently")
    contrib = os.path.join(repo_root, "CONTRIBUTING.md")
    ctext2 = read(contrib) if os.path.isfile(contrib) else ""
    check("the workbook and the preserved list are documented",
          "owner-and-deadline workbook" in ctext2
          and "What the weekly task must preserve" in ctext2,
          "documented",
          "documented" if "What the weekly task must preserve" in ctext2
          else "MISSING", "CONTRIBUTING.md")
    check("a named owner shows a headshot or their initials, never a hot-link",
          'class="face' in idx
          and "assets/headshots" in read(os.path.join(repo_root, "tools",
                                                      "render_actions.py"))
          and not re.search(r'class="face[^"]*"[^>]*src="https?://', idx),
          "local or initials",
          "local or initials" if 'class="face' in idx else "MISSING",
          "assets/ is the only source, as for the partner logos")

    # ---- 7ba. one to-do list, one collapsed treatment -------------------
    # The Attention list and the Marolinta "gaps to close" panel were both
    # to-do lists rendered in the browser, so nothing linked them to the one
    # list and nothing could close them. Both are now action rows.
    rivals = [n for n in ('id="alerts"', 'id="margaps"') if n in idx]
    check("only one to-do list exists on the page",
          not rivals, "one list", f"{len(rivals) + 1} lists" if rivals else "one list",
          "the Attention list and the Marolinta gaps panel are action rows now")
    n_cond = len(json.load(open(os.path.join(repo_root, "data",
                                             "action_conditions.json"))))
    n_rows = len(_det)
    check("every action row carries a closing condition or says it has none",
          n_cond == n_rows, "all classified", f"{n_cond} of {n_rows}",
          "data / form / artefact / decision, or an explicit none")

    # One collapsed-section treatment. There were two - a bare blue summary and
    # a white card with slate text that stayed white under the dark theme -
    # and the second hardcoded its colours, so it ignored the palette.
    css_m = re.search(r"<style[^>]*>(.*?)</style>", idx, re.S)
    css_t = css_m.group(1) if css_m else ""
    css_body = re.sub(r"@media[^{]*\{(?:[^{}]|\{[^}]*\})*\}", " ", css_t, flags=re.S)
    css_body = re.sub(r":root[^{]*\{[^}]*\}", " ", css_body)
    hard = [r for r in re.findall(r"[^}\n]*\{[^}]*\}", css_body)
            if re.search(r"#[0-9a-fA-F]{3,6}\b", r)
            and not re.search(r"border-left\s*:", r)]
    check("no stylesheet rule hardcodes a colour outside the palette",
          not hard, "none", f"{len(hard)} rule(s)" if hard else "none",
          "; ".join(x.strip()[:48] for x in hard[:2]) if hard
          else "everything reads var(--...) so the dark theme applies")
    det = re.findall(r"[^}\n]*details[^{}]*\{[^}]*\}", css_body)
    check("collapsed sections have one treatment, applied everywhere",
          any("details,details.expl" in r.replace(" ", "") for r in det)
          and all("var(--" in r for r in det if "background" in r or "color" in r),
          "one treatment",
          "one treatment" if any("details,details.expl" in r.replace(" ", "")
                                 for r in det) else "TWO TREATMENTS",
          "bare <details> and details.expl render identically")

    # ---- 7ax. the one list is actually the one list ---------------------
    # #actions claims "every open item in this report, in one place". That was
    # false: the Open actions section carried 31 table rows and 12 bullets,
    # and the Moramanga field-visit table 11 more, none of them anchored, so
    # render_actions.py never saw them and the summary silently omitted them.
    # Any table that declares itself an action table - Action / Schedule /
    # Owner - must have an addressable id on every row, or its rows cannot
    # reach the list and the claim above it stops being true.
    body_x = re.sub(r"<script[^>]*>.*?</script>", " ", idx, flags=re.S)
    gen_a = body_x.find("BEGIN GENERATED action-list")
    gen_b = body_x.find("END GENERATED action-list")
    if 0 <= gen_a < gen_b:
        body_x = body_x[:gen_a] + body_x[gen_b:]
    # A detail cell may itself hold a table - the eight 2.2.1(d) records and
    # the approvals breakdown both do - so walk with a depth counter and only
    # judge rows that belong to the action table itself.
    orphans, n_tables = [], 0
    for tm in re.finditer(r"<table[^>]*>", body_x):
        head = re.match(r"\s*<thead>(.*?)</thead>", body_x[tm.end():], re.S)
        if not head:
            continue
        cols = [re.sub(r"<[^>]+>", "", c).strip()
                for c in re.findall(r"<th[^>]*>(.*?)</th>", head.group(1), re.S)]
        if cols[:3] != ["Action", "Schedule", "Owner"]:
            continue
        n_tables += 1
        depth, i0 = 1, tm.end() + head.end()
        for tok in re.finditer(r"<table\b|</table>|<tr(?: [^>]*)?>",
                               body_x[i0:]):
            s_ = tok.group(0)
            if s_.startswith("<table"):
                depth += 1
            elif s_ == "</table>":
                depth -= 1
                if depth == 0:
                    break
            elif depth == 1 and 'id="act-' not in s_:
                orphans.append(cols[0])
    check("no action row sits outside the one list",
          not orphans, "none", f"{len(orphans)} orphaned" if orphans else "none",
          f"{n_tables} action tables, every row addressable")
    # The Open actions section and the Moramanga field-visit table were both
    # second presentations of rows the consolidated list already carried. The
    # detail moved into data/action_details.json and is rendered collapsed
    # inside the one list; neither section exists any more.
    rival_heads = [h for h in ("<h2>Open actions</h2>",
                               "Moramanga field visit") if h in idx]
    check("no section re-lists the action rows",
          not rival_heads and not re.search(r'<tr id="act-', idx),
          "one list only",
          ", ".join(rival_heads) or ("stray <tr id=act-> in the body"
                                     if re.search(r'<tr id="act-', idx)
                                     else "one list only"),
          f"{len(_det)} actions, rendered once, detail collapsed in the row")

    # ---- 8. structural ----------------------------------------------------
    for f, src in (("index.html", idx), ("portfolio.html", prt)):
        for tag in ("section", "details"):
            o = len(re.findall(r"<" + tag + r"[\s>]", src))
            c = src.count(f"</{tag}>")
            check(f"{f}: <{tag}> balanced", o == c, f"{o} open", f"{c} close")

    refs = sorted(set(re.findall(r"\$\('#([A-Za-z0-9_\-]+)'\)", idx)))
    present = set(re.findall(r'id="([A-Za-z0-9_\-]+)"', idx))
    missing = [r for r in refs if r not in present]
    check("index.html: every $('#id') exists in the markup",
          not missing, f"{len(refs)} refs all present",
          f"missing: {', '.join(missing)}" if missing else f"{len(refs)} refs all present")

    for f, src in (("index.html", idx), ("portfolio.html", prt)):
        blocks = [c for at, c in re.findall(r"<script([^>]*)>(.*?)</script>", src, re.S)
                  if "src=" not in at]
        if not blocks:
            check(f"{f}: inline script passes node --check", False, "1 inline block", "none found")
            continue
        okall, err = True, ""
        for b in blocks:
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf8") as t:
                t.write(b); path = t.name
            r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
            os.unlink(path)
            if r.returncode != 0:
                okall = False
                err = (r.stderr.strip().splitlines() or ["syntax error"])[0][:90]
        check(f"{f}: inline script passes node --check", okall,
              "exit 0", "exit 0" if okall else err)

    # ---------------------------------------------------------------- report
    w = max(len(r[0]) for r in RESULTS) + 2
    print()
    print(f"  {'CHECK'.ljust(w)} {'':6} {'EXPECTED'.ljust(26)} {'ACTUAL'.ljust(26)} NOTE")
    print(f"  {'-' * w} {'-' * 6} {'-' * 26} {'-' * 26} ----")
    nfail = 0
    for name, ok, exp, act, note in RESULTS:
        if not ok:
            nfail += 1
        print(f"  {name.ljust(w)} {'PASS  ' if ok else 'FAIL !'} "
              f"{exp[:26].ljust(26)} {act[:26].ljust(26)} {note}")
    print()
    print(f"  {len(RESULTS)} checks, {len(RESULTS) - nfail} passed, {nfail} failed")
    # Say what is NOT in that number. The tally went 532 -> 530 when two
    # assertions were deleted and six added, because the six sat behind a
    # single check() and never appeared. They are counted individually now;
    # the render gate still is not, and this says so rather than letting the
    # number look like the whole of it.
    print("  assertions outside this tally: tools/render_check.py, which runs "
          "against the rendered page\n  in a browser (headings, tables, ids, "
          "page measure, per-scope Endur'O wording, one\n  basis per scope) "
          "and reports its own result. Nothing else.")
    if nfail:
        print("\n  FAILED — the published figures are not consistent. Do not publish.")
        return 1
    print("  All consistency checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
