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
import argparse, collections, json, os, re, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exclude_retired import RETIRED_NAME_PREFIX, KNOWN_RETIRED_CODES  # noqa: E402

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
    # 908 is the register record count and is legitimate when labelled as such.
    # It is NOT legitimate as a count of points under management.
    # 908 is the mWater register record count. It is legitimate where the page
    # says so; it is NOT legitimate as a count of points under management, in the
    # carbon portfolio, or as a people-served figure. This is a keyword test, so
    # it catches a bare "908" but cannot read a sentence - see LIMITATIONS below.
    ("908", "register record count quoted as a management figure",
     ("register", "registre", "record", "record count", "in mwater",
      "managed by madavance", "sampling frame", "register chain")),
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
        hit = RETIRED_NAME_PREFIX in src
        check(f"{f}: no {RETIRED_NAME_PREFIX!r} record present", not hit,
              "absent", "FOUND" if hit else "absent",
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
        m = re.search(r"const ENDURO\s*=\s*\{systems:(\d+)", idx)
        check("Endur'O count matches the disposition file",
              bool(m) and int(m.group(1)) == n, n, m.group(1) if m else "ENDURO not found",
              "data/enduro_disposition.csv, matched+new+duplicate")
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
        # every group-filtered export skips it and the map can draw only 735.
        # Open action "Bring water point 742896839 into the MadAvance register"
        # in index.html tracks the fix. When that lands this assertion SHOULD
        # start failing: change the -1 to 0 at the same time.
        check("map point count agrees with the report's managed set",
              n_map == S["points"] - 1, f"{S['points']} - 1 not in the MadAvance group", n_map,
              "742896839: record and GPS exist, group membership does not")
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
    m_tot = re.search(r"<b>([\d,]+)</b><span>calendar photographs on file", idx)
    parts = [re.search(p_, idx) for p_ in (
        r"carries\s*<b>([\d,]+)</b>\s*of them",
        r"carries\s*<b>([\d,]+)</b>;",
        r"carries\s*<b>([\d,]+)</b>\.")]
    if m_tot and all(parts):
        tot = int(m_tot.group(1).replace(",", ""))
        got = sum(int(x.group(1).replace(",", "")) for x in parts)
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
        for key, label in keys:
            want = fmt_n(fig[key])
            check(f"page states the extraction {label}: {want}",
                  f"<b>{want}</b>" in idx, want,
                  want if f"<b>{want}</b>" in idx else "NOT ON THE PAGE",
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
    for needle, why in (("const CAP_T=60000", "the cap constant"),
                        ('id="capnote"', "the audit-trail line"),
                        ("capNear&&['crit'", "the conditional attention entry")):
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

    # ---- 7p. the open Gold Standard review items are tracked ---------------
    # These are the gate to certification. The report went months without
    # tracking any of them; the section and the actions must both stay.
    check("the Gold Standard design review section exists",
          'id="gsrevsec"' in idx, "present",
          "present" if 'id="gsrevsec"' in idx else "MISSING",
          "round 3 sits at Request Clarification with six items open")
    for ref, why in (("&sect;4.15 CAR#1", "Section F eligibility criteria"),
                     ("&sect;4.16 CAR#4", "baseline surveys after crediting period start"),
                     ("&sect;4.16 CAR#5", "technical life of India Mk2/3 and Afridev"),
                     ("&sect;4.16 CAR#7(b)", "SDWS 3 chemical tests and parallel validation"),
                     ("&sect;4.16 CAR#8", "VVB external experts"),
                     ("&sect;4.19 CL#2", "installation database")):
        check(f"open review item tracked: {ref} ({why})", ref in idx, "tracked",
              "tracked" if ref in idx else "MISSING",
              "each open item needs a reference, an owner and a date")

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
        allowed = {"n", "f", "wp", "site", "date", "w", "h", "y"}
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
            ("minimum of <b>30</b>", "the methodology minimum is stated"),
            ("<b>46</b> can be transcribed", "the transcribable count is stated"),
            ("the machine could read <b>34</b>", "the comparable count is stated"),
            ("locks every cell the photograph could not show",
             "the comparison is on the same cells for both sides"),
            ("the calendar", "the unit of variation is stated")):
        check(f"transcription method note: {why}", frag in idx, "present",
              "present" if frag in idx else "MISSING",
              "the accuracy assessment is only as good as its declared method")
    check("days-operational section reserves the result footnote",
          "An accuracy assessment of the machine reading of these calendars is in progress" in idx,
          "reserved", "reserved" if "An accuracy assessment of the machine reading"
          " of these calendars is in progress" in idx else "MISSING",
          "the footnote is placed before the results, and says so")

    # ---- 7t. the transcription page records who did the work ---------------
    trh = os.path.join(here, "transcription", "index.html")
    if os.path.exists(trh):
        tr2 = open(trh, encoding="utf8").read()
        # the columns are asserted on the export header itself, not on the
        # word appearing somewhere in the file: an earlier version of this
        # check passed after the column had been deleted from the export
        want_cols = ["calendrier", "point_eau", "date_photo", "annee_feuille",
                     "mois", "jour", "releve", "etat_cellule", "exclu",
                     "exclu_motif", "transcripteur", "session_id",
                     "secondes_sur_calendrier", "notes", "exporte_le"]
        hdr = "[" + ",".join(f"'{c}'" for c in want_cols) + "]"
        check("transcription export header carries every column, in order",
              hdr in tr2.replace(" ", ""), ",".join(want_cols),
              ",".join(want_cols) if hdr in tr2.replace(" ", "") else "CHANGED",
              "transcripteur and session_id must reach every exported row")
        for frag, why in (
                ("Ce n\u2019est pas un calendrier", "the not-a-calendar control exists"),
                ("EXCLU", "an excluded sheet exports as excluded, not as blanks"),
                ("out.push([c.n,c.wp,c.date,c.y||'','','','EXCLU'", "the excluded row has no day cells")):
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
    if nfail:
        print("\n  FAILED — the published figures are not consistent. Do not publish.")
        return 1
    print("  All consistency checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
