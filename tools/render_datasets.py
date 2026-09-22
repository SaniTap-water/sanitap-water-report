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
import json, os, sys

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
}


def block():
    out = [BEGIN,
           "// Inlined datasets. Every figure quoted in the prose above must be",
           "// reachable from one of these, or from the register objects, or be",
           "// declared in PARAMS - see tools/figure_census.py."]
    for name, path in SETS.items():
        doc = json.load(open(os.path.join(REPO, *path), encoding="utf8"))
        if name == "METRICS":            # values only; the prose quotes those
            doc = {k: v.get("value") for k, v in doc.get("metrics", {}).items()}
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
    if page[i:j].strip() == new.strip():
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
