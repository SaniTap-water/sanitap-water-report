# -*- coding: utf-8 -*-
"""For each unsourced figure, find the artefact field that produces that value.

The residue cannot be closed by a bounded closure over the artefact fields -
that was tried and reverted, because a closure accepts any arithmetic that
happens to land on the number, including a typo's. This does the opposite: it
looks for an artefact field whose value is EXACTLY the figure, and reports the
figure as unmatched when there is none. A mistyped figure matches nothing.

    python3 tools/match_residue.py             # the table
    python3 tools/match_residue.py --unmatched # only what resists
"""
import json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
BACKLOG = os.path.join(REPO, "data", "figure_backlog.json")


def leaves(obj, path=""):
    """(path, value) for every scalar in a nested structure."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from leaves(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from leaves(v, f"{path}[{i}]")
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield path, obj


def artefact_values():
    """Every scalar every artefact produces, by where it came from."""
    import embedded_fields as EF
    out = {}

    def add(src, path, v):
        out.setdefault(round(float(v), 6), []).append(f"{src}:{path}")

    for name, _line, val in EF.objects():
        for p, v in leaves(val, name):
            add("page", p, v)
    # Backlog files record line numbers and counts ABOUT figures; they do not
    # produce figures. Including them matched 1,169 to a line number, which is
    # exactly the false positive this tool exists to avoid.
    SKIP = {"figure_backlog.json", "prose_figure_backlog.json",
            "unsourced_figures.json", "mwater_form_snapshot.json",
            "render_manifest.json", "extract_manifest.json"}
    data = os.path.join(REPO, "data")
    for f in sorted(os.listdir(data)):
        if not f.endswith(".json") or f in SKIP:
            continue
        try:
            d = json.load(open(os.path.join(data, f), encoding="utf8"))
        except Exception:
            continue
        for p, v in leaves(d, ""):
            add(f"data/{f}", p, v)
    return out


def main():
    only_un = "--unmatched" in sys.argv
    back = json.load(open(BACKLOG, encoding="utf8"))["values"]
    av = artefact_values()
    matched, unmatched = [], []
    for fig, meta in back.items():
        try:
            n = float(str(fig).replace(",", ""))
        except ValueError:
            unmatched.append((fig, meta, "not numeric"))
            continue
        hits = av.get(round(n, 6)) or []
        # a figure is only "produced" by an artefact if some field equals it
        if hits:
            matched.append((fig, meta, hits))
        else:
            unmatched.append((fig, meta, "no artefact field carries this value"))

    if not only_un:
        print(f'{"FIGURE":>13}  {"N":>3}  PRODUCED BY')
        for fig, meta, hits in sorted(matched, key=lambda x: -x[1]["n"]):
            src = ", ".join(sorted(set(hits))[:3])
            more = f" (+{len(set(hits)) - 3})" if len(set(hits)) > 3 else ""
            print(f"{fig:>13}  x{meta['n']:<3} {src}{more}")
    print(f"\n{len(matched)} of {len(back)} figures are produced by an artefact field")
    print(f"{len(unmatched)} resist matching:")
    for fig, meta, why in sorted(unmatched, key=lambda x: -x[1]["n"]):
        print(f"  {fig:>13}  x{meta['n']:<3} {meta['section'][:34]:36} {why}")
        print(f"                     {meta['sentence'][:96]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
