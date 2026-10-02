# -*- coding: utf-8 -*-
"""The publication gate for downtime read by the calendar machine reader.

Transcription round 1 (1 Oct 2026) found the reader detected 0 of the 40 days
both human readers marked X. Every figure computed from its marks - a marked
rate, the impossible-cell error floor, a count of days not operational, an
implied uptime, the stratum days-operational averages - was withdrawn from the
page and from the data files the page inlines (Adriaan Mol, 1 Oct 2026).

They may come back only when data/reader_validation.json
(tools/reader_validation.py) shows the reader of record validated: sensitivity
of at least 0.90 and specificity of at least 0.99 against the days both human
readers mark X, on all round-1 calendars and on the held-out ones.

  validated()          -> (bool, why)
  strip(doc, name)     the doc with the machine-downtime fields removed, unless validated
  page_violations(html) machine-downtime figures found on a page

Used by tools/recompute_figures.py and tools/calendar_stratum.py (they omit
the fields) and by tools/check_consistency.py (the build fails on any).
"""
import json, os, re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALIDATION = os.path.join(REPO, "data", "reader_validation.json")

# machine-read downtime, by the data file it lives in
FIELDS = {
    "calendar_extraction_figures.json": [
        "days_not_operational", "observed_marked", "unobserved_called_marked", "observed_marked_pct",
        "probe_marked_pct", "implied_true_marked_pct", "implied_days_not_operational", "implied_uptime_days",
        "real_marked_pct", "impossible_marked_pct"],
    # per stratum (portfolio, by_site.*, by_year.*) and top level
    "calendar_stratum_figures.json": ["mean_do", "median_do", "mean_do_before_floor", "floor_pct",
                                      "mean_do_by_photos"],
}
KEYS = sorted({k for v in FIELDS.values() for k in v})

# figures withdrawn on 1 Oct 2026 and earlier statements of the same kind,
# as they would read on the page (kept narrow: each needs its unit or phrase)
WITHDRAWN_TEXT = [
    r"\b2\.41\s*%", r"\b4\.25\s*%", r"\b1\.84\s*%", r"\b8\.8\s*days", r"\b356\.2\b", r"\b98\s*%\s*of\s*days",
    r"\b97\.6\s*%", r"\b2,787\s*t", r"\b3,015\s*t", r"\b25,121\s*t", r"\b363\.9\b",
    r"supported by evidence", r"resting on the estimate", r"rarely misses a marked day",
    r"[Ii]mplied uptime\s*:\s*\d", r"days operational per point-year, on average",
]


def validated():
    try:
        v = json.load(open(VALIDATION, encoding="utf8"))
    except (OSError, ValueError):
        return False, "data/reader_validation.json missing or unreadable"
    rec = v.get("reader_of_record")
    if not v.get("gate_passed", {}).get(rec):
        r = v.get("readers", {}).get(rec, {}).get("all", {}).get("both", {})
        return False, (f"reader of record {rec} not validated: sensitivity {r.get('sensitivity')}, "
                       f"specificity {r.get('specificity')} against both-human X days")
    return True, f"reader of record {rec} validated"


def strip(doc, name):
    """Remove the machine-downtime fields from a data document, unless validated."""
    ok, why = validated()
    if ok:
        return doc
    drop = set(FIELDS[name])

    def walk(o):
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items() if k not in drop}
        return o
    out = walk(doc)
    out["machine_downtime_withheld"] = (why + "; machine-read downtime fields omitted "
                                        "(tools/reader_gate.py)")
    return out


def page_violations(html):
    """Machine-downtime figures on a page: a data-fig on a withdrawn field, a
    withdrawn field inlined in a dataset, or a withdrawn figure as text."""
    hits = []
    key_re = re.compile(r"\b(" + "|".join(map(re.escape, KEYS)) + r")\b")
    for m in re.finditer(r'data-fig="([^"]*)"', html):
        k = key_re.search(m.group(1))
        if k:
            hits.append(f"data-fig on {k.group(1)}: {m.group(1)}")
    for m in re.finditer(r'"(' + "|".join(map(re.escape, KEYS)) + r')"\s*:', html):
        hits.append(f"inlined field {m.group(1)}")
    text = re.sub(r"<script\b.*?</script>|<style\b.*?</style>|<!--.*?-->", " ", html, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;|\s+", " ", text)
    for p in WITHDRAWN_TEXT:
        for m in re.finditer(p, text):
            hits.append(f"withdrawn text '{m.group(0)}' in \"…{text[max(0, m.start() - 50):m.end() + 30]}…\"")
    return hits
