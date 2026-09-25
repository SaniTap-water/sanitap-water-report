# -*- coding: utf-8 -*-
"""Inline the machine-extraction datasets so the page's figures are reachable.

WHY THIS EXISTS
---------------
The gardien-calendar section quotes seventy-eight figures - 2,367 photographs,
1,409 readable images, 4,621 days not operational - every one of which comes
from data/calendar_extraction_figures.json. But they were frozen into the
generated region as literals, so nothing on the page could reach them and the
figure gate could not tell them from numbers somebody typed.

This inlines the datasets themselves. The region regenerates from the same
file, so the prose and the object cannot diverge; and the gate can now say
that a figure in that section is one the extraction actually produced.

    python3 tools/render_datasets.py --write
    python3 tools/render_datasets.py --check
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# a region that differs only in prerendered figure values is not drift
from prerender_figures import same as _same  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
BEGIN = ("/* BEGIN GENERATED datasets :: tools/render_datasets.py :: "
         "do not edit between these markers */")
END = "/* END GENERATED datasets */"

# name in the page -> file it is inlined from
SETS = {
    "CALX": ("data", "calendar_extraction_figures.json"),
    "METRICS": ("data", "action_metrics.json"),
    "CARBON": ("data", "carbon_denominator.json"),
    "ACTN": ("data", "action_counts.json"),
    "FRESH": ("data", "data_freshness.json"),
    # every "nearest other point" distance in the corrections log, derived
    # from located_register_points by tools/check_distances.py each build
    "NEAREST": ("data", "nearest_point_distances.json"),
    # computed artefacts: the calendar stratum (tools/calendar_stratum.py) and
    # the people-served runs (tools/wpop_pipeline_figures.py), so the figures
    # the prose quotes from them are values the page can reach
    "CALS": ("data", "calendar_stratum_figures.json"),
    "WPOPX": ("data", "wpop_pipeline_figures.json"),
    # the time-to-repair table's own figures (tools/render_ttr_table.py)
    "TTRQ": ("data", "ttr_table.json"),
    # the counts the form-freshness sentence quotes, summarised from the
    # snapshot rather than inlining the whole design
    "FORMSNAP": ("data", "mwater_form_snapshot.json"),
    # the rules the build applies; the "How this is worked out" footnotes
    # render every number they state from this, never typed
    "BUILDCFG": ("data", "build_config.json"),
    # each extract's form id, pull date and row count, so every data table's
    # footnote states its own source's extraction date (25 September 2026)
    "PULLS": ("data", "extract_manifest.json"),
    # the vintage floor the week caption states (tools/check_vintage.py)
    "VINTAGE": ("data", "extract_vintage.json"),
    # how many pumps the status rule holds on their published value
    "HOLDS": ("data", "call_status_holds.json"),
    # each data-kind action's closing threshold, which the action list renders
    "ACTCOND": ("data", "action_conditions.json"),
    # the calendar photographs that are not calendars, counted from the
    # by-eye inspection file (data/calendar_not_calendar.csv)
    "NOTCAL": ("data", "calendar_not_calendar.csv"),
    # the points with no usable calendar image, by cause and field action
    "NOUSABLE": ("data", "calendar_no_usable_image.csv"),
    # the methodology-divergence register's machine-readable index: how many
    # divergences it carries and how many require action now
    "VMAP": ("docs", "methodology_version_map.md"),
}


def block():
    out = [BEGIN,
           "// Inlined datasets. Every figure quoted in the prose above must be",
           "// reachable from one of these, or from the register objects, or be",
           "// declared in PARAMS - see tools/figure_census.py."]
    for name, path in SETS.items():
        if name == "VMAP":
            rows = re.findall(r"^\|\s*(\d+)\s*\|\s*(yes|no)\s*\|\s*([a-z0-9-]*)\s*\|\s*$",
                              open(os.path.join(REPO, *path), encoding="utf8").read(), re.M)
            doc = {"divergences": len(rows), "action_now": sum(1 for _, f, _a in rows if f == "yes")}
            out.append(f"// {name}: {'/'.join(path)}")
            out.append(f"const {name}=" + json.dumps(doc, separators=(",", ":")) + ";")
            continue
        if path[-1].endswith(".csv"):
            import csv as _csv, collections as _co
            rows = list(_csv.DictReader(open(os.path.join(REPO, *path), encoding="utf8")))
            if name == "NOUSABLE":
                doc = {"total": len(rows),
                       "by_category": dict(sorted(_co.Counter(r["category"] for r in rows).items()))}
                out.append(f"// {name}: {'/'.join(path)}")
                out.append(f"const {name}=" + json.dumps(doc, separators=(",", ":"), ensure_ascii=False) + ";")
                continue
            def _summ(rs):
                return {"total": len(rs),
                        "by_reason": dict(sorted(_co.Counter(r["reason"] for r in rs).items())),
                        "by_question": dict(sorted(_co.Counter(r["question"] for r in rs).items()))}
            doc = _summ(rows)
            # the subset the calendar reader had accepted as calendars
            doc["accepted"] = _summ([r for r in rows if r["reader"] == "accepted as a calendar"])
            out.append(f"// {name}: {'/'.join(path)}")
            out.append(f"const {name}=" + json.dumps(doc, separators=(",", ":"), ensure_ascii=False) + ";")
            continue
        doc = json.load(open(os.path.join(REPO, *path), encoding="utf8"))
        if name == "METRICS":            # values only; the prose quotes those
            doc = {k: v.get("value") for k, v in doc.get("metrics", {}).items()}
        if name == "ACTCOND":            # data conditions: metric, op, target
            doc = {k: {"metric": v["metric"], "op": v["op"], "target": v["target"]}
                   for k, v in sorted(doc.items()) if v.get("kind") == "data"}
        if name == "HOLDS":              # the count and the cut, not every row
            doc = {"n": len(doc.get("holds") or []), "cut_used": doc.get("cut_used")}
        if name == "PULLS":              # per extract: form, pulled, rows
            doc = {k: {"form_id": v.get("form_id"), "pulled": str(v.get("written") or "")[:10],
                       "rows": v.get("rows"), "newest": v.get("newest_submitted")}
                   for k, v in sorted(doc.get("files", {}).items())}
        if name == "FORMSNAP":           # counts only, not the form designs
            doc = {"fetched": doc["fetched"], "forms": len(doc["forms"]),
                   "questions": sum(len(f["questions"]) for f in doc["forms"].values()),
                   "rev": {k: f.get("rev") for k, f in sorted(doc["forms"].items())}}
        out.append(f"// {name}: {'/'.join(path)}")
        out.append(f"const {name}="
                   + json.dumps(doc, separators=(",", ":"), ensure_ascii=False)
                   + ";")
    out.append(END)
    return "\n".join(out)


def apply(write):
    page = open(PAGE, encoding="utf8").read()
    new = block()
    if BEGIN in page:
        i, j = page.index(BEGIN), page.index(END) + len(END)
    else:
        anchor = "const SUCC_CORRECTED="
        if anchor not in page:
            sys.exit("render_datasets: no anchor to insert before")
        i = j = page.index(anchor)
        new = new + "\n"
    if _same(page[i:j], new):
        print("index.html datasets match their generator")
        return 0
    if not write:
        print("index.html datasets DIFFER from their generator")
        return 1
    open(PAGE, "w", encoding="utf8").write(page[:i] + new + page[j:])
    print(f"index.html datasets rewritten ({', '.join(SETS)})")
    return 0


if __name__ == "__main__":
    sys.exit(apply("--write" in sys.argv))
