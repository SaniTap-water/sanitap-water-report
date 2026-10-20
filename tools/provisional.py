#!/usr/bin/env python3
"""The PROVISIONAL notice on the page (20 Oct 2026).

A REVIEW gate that fails does not stop the edition (data/gate_classes.json):
the edition is published and every such failure is listed at the top of the
page as PROVISIONAL, and on the week's approval task, until Jan or Adriaan
has looked at it. The list is data/provisional.json, written by
tools/gate_decide.py at the end of publish.sh. Every build starts with it
empty (--clear), so an item never outlives the run that found it.

    python3 tools/provisional.py --clear   # empty list, empty region (start of a build)
    python3 tools/provisional.py --write   # region from data/provisional.json
    python3 tools/provisional.py --check   # exit 1 if the region differs from the list
"""
import html, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(REPO, "index.html")
PROV = os.path.join(REPO, "data", "provisional.json")
BEGIN = "<!-- BEGIN GENERATED provisional :: tools/provisional.py :: do not edit between these markers -->"
END = "<!-- END GENERATED provisional -->"
AFTER = "<!-- END GENERATED masthead -->"
LABEL = {"render_check": "Rendered layout", "layout": "Layout acceptance test",
         "panels": "Figure panels and expanding blocks", "readability": "Table readability",
         "transcription_page": "Transcription page", "routes_page": "Route page exports",
         "migration": "Responses on a successor form", "links": "mWater links",
         "figure_census": "Figure census", "vintage_shrink": "An extract shrank",
         "status_actions": "Status cross-references", "routes_plans": "Catch-up route plans",
         "moramanga_parent": "Moramanga duplicate-parent readout"}


def load():
    return json.load(open(PROV, encoding="utf8")) if os.path.isfile(PROV) else {"items": []}


def render(doc):
    items = doc.get("items") or []
    if not items:
        return ""
    li = []
    for it in items:
        d = "; ".join(it.get("detail") or []) or it.get("message") or ""
        li.append(f'<li><b>{html.escape(LABEL.get(it["gate"], it["gate"]))}</b> '
                  f'({html.escape(it["why"])}): <span class="mono">{html.escape(d)}</span></li>')
    return ('<div class="provisional" id="provisional" role="status" style="border:1px solid var(--warn);'
            'border-radius:8px;padding:10px 14px;margin:10px 0"><p style="margin:0"><b>PROVISIONAL.</b> '
            'This edition is published, but the checks below did not pass. They are listed on this '
            "week's approval task for Jan or Adriaan, and the items they name stay provisional until "
            'one of them has reviewed it.</p><ul style="margin:6px 0 0">' + "".join(li) + "</ul></div>")


def splice(idx, block):
    if BEGIN not in idx:
        i = idx.index(AFTER) + len(AFTER)
        idx = idx[:i] + "\n" + BEGIN + END + idx[i:]
    a = idx.index(BEGIN) + len(BEGIN)
    b = idx.index(END)
    return idx[:a] + block + idx[b:]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    idx = open(IDX, encoding="utf8").read()
    if mode == "--clear":
        json.dump({"note": "cleared at the start of the build", "items": []},
                  open(PROV, "w", encoding="utf8"), indent=1)
        mode = "--write"
    want = splice(idx, render(load()))
    if mode == "--write":
        if want != idx:
            open(IDX, "w", encoding="utf8").write(want)
        print(f"provisional: {len(load().get('items') or [])} item(s) on the page")
        return 0
    if mode == "--check":
        return 0 if want == idx else 1
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main())
