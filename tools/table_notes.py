# -*- coding: utf-8 -*-
"""One collapsed footnote under every data table: source, extraction, rows, columns.

A data table's cells need no footnote of their own; the table's footnote says
where every cell comes from. The text lives in data/table_notes.json, one entry
per table, and is rendered here. A table in hand-written HTML carries its
footnote in a generated region directly after it; a table that a generator
writes gets its footnote from render() in the same generator.

tools/figure_census.py --gate fails the build if any table is not declared as
data or prose, or if a data table's footnote is missing or lacks a part.

    python3 tools/table_notes.py --write
    python3 tools/table_notes.py --check
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prerender_figures import same as _same  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
DATA = os.path.join(REPO, "data", "table_notes.json")
PARTS = (("source", "Source"), ("extracted", "Extracted"),
         ("filter", "Rows"), ("columns", "Columns"))
REGION = re.compile(r"(<!-- BEGIN GENERATED tablenote-([\w-]+) :: tools/table_notes\.py :: "
                    r"do not edit between these markers -->)(.*?)(<!-- END GENERATED tablenote-\2 -->)",
                    re.S)


def notes():
    return json.load(open(DATA, encoding="utf8"))["tables"]


def render(key):
    n = notes()[key]
    rows = "".join(f'<dt>{label}</dt><dd data-note="{k}">{n[k]}</dd>' for k, label in PARTS)
    return (f'<details class="tablenote" data-for="{key}"><summary>About this table: '
            f'source, extraction, rows and columns</summary><dl>{rows}</dl></details>')


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    page = open(PAGE, encoding="utf8").read()
    N = notes()
    missing = [m.group(2) for m in REGION.finditer(page) if m.group(2) not in N]
    if missing:
        sys.exit("table_notes: no entry in data/table_notes.json for " + ", ".join(missing))
    new = REGION.sub(lambda m: m.group(1) + "\n" + render(m.group(2)) + "\n" + m.group(4), page)
    if _same(new, page):
        print("index.html table footnotes match data/table_notes.json")
        return 0
    if mode != "--write":
        print("index.html table footnotes DIFFER from data/table_notes.json")
        return 1
    open(PAGE, "w", encoding="utf8").write(new)
    print(f"index.html: {len(REGION.findall(new))} table footnote region(s) rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
