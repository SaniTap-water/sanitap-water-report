# -*- coding: utf-8 -*-
"""The provenance of the provenance: every definition, readable on the page.

populations.py and PARAMS are the two files that decide what every figure on
this page means. A verifier who cannot read Python should still be able to see
each definition, its rule in plain English, what it reads, the decision that
set it and its date. This renders both, plus the reconciliation chain and any
step of it that does not hold.

    python3 tools/render_definitions.py --write
    python3 tools/render_definitions.py --check
"""
import json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
BEGIN = ("<!-- BEGIN GENERATED definitions :: tools/render_definitions.py :: "
         "do not edit between these markers -->")
END = "<!-- END GENERATED definitions -->"
MW = "https://portal.mwater.co/#/forms/"


def esc(x):
    return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))



def retire(text, retired):
    """Mark each retired value quoted in a decision as history, not current.

    A decision records what changed - "the stored ttr_n of 606 reproduces from
    no rule" - so it has to quote the value it retired. Rendered bare, that
    value reads as a figure the page stands behind; marked, it renders struck
    through and labelled, and the census classes it as a retired quotation.
    """
    import re as _re
    for val, on, was in retired or []:
        text = _re.sub(r"(?<![\d.,])" + _re.escape(val) + r"(?![\d])",
                       f'<span class="retired" data-retired="{on}" '
                       f'data-was="{esc(was)}">{val}</span>', text, count=1)
    return text

def block():
    pops = json.load(open(os.path.join(REPO, "data", "populations.json"),
                          encoding="utf8"))
    P = pops["populations"]
    rows = []
    for pid, p in sorted(P.items(), key=lambda kv: -kv[1]["size"]):
        if p.get("internal"):            # the whole mWater group: build-only
            continue
        reads = "<br>".join(
            (f'<a href="{MW}{r[1]}" target="_blank" rel="noopener">{esc(r[0])}</a>'
             if len(r) > 1 and r[1] else esc(r[0]))
            + (f'<br><span class="muted mono">{esc(r[2])}</span>'
               if len(r) > 2 and r[2] else "")
            for r in (p.get("reads") or [])) or "<span class='muted'>—</span>"
        derives = (" &rarr; ".join(esc(d) for d in p.get("derives_from") or [])
                   or "<span class='muted'>—</span>")
        rows.append(
            f'<tr><td><b>{esc(p["name"])}</b><br>'
            f'<span class="mono muted" style="font-size:.78em">{esc(pid)}</span></td>'
            f"""<td class="num"><b><span data-fig="POPS.populations['{pid}'].size"></span></b></td>"""
            f'<td>{esc(p["rule"])}</td>'
            f'<td>{reads}</td>'
            f'<td>{retire(esc(p.get("decided")), p.get("retired"))}'
            + (f'<br><span class="muted">{esc(p.get("decided_on"))}</span>'
               if p.get("decided_on") and p["decided_on"] != "—" else "")
            + f'</td><td>{derives}</td></tr>')

    chain = "".join(
        f'<tr><td>{esc(c["step"])}</td>'
        f'<td class="num"><span data-fig="POPS.chain[{k}].detail"></span></td>'
        f'<td><span class="verdict {"vok" if c["holds"] else "vbad"}">'
        f'{"holds" if c["holds"] else "does not hold"}</span></td></tr>'
        for k, c in enumerate(pops.get("chain", [])) if not c.get("internal"))

    gaps = "".join(
        f'<li><b>{esc(g["step"])}</b> &mdash; '
        f'<span data-fig="POPS.gaps[{k}].what"></span>'
        + (f' <span class="muted">({esc(g["known"])})</span>' if g.get("known") else "")
        + "</li>" for k, g in enumerate(pops.get("gaps", [])))

    return f"""{BEGIN}
<section data-scopes="all mad madx mar enduro" id="definitions">
  <div class="sechead"><div><h2>What every figure is over</h2>
  <p>Figures used to move because no file said what a population <i>is</i>. These are the
  definitions the whole page is built on, each one a set of records rather than a stored count, so
  a figure cannot drift from the thing it counts. Every number on this page expands to name one of
  these. Written by <span class="mono">tools/populations.py</span>; nothing here is typed.</p>
  </div></div>
  <div class="tablewrap" style="max-height:none"><table class="ind" id="popstbl">
  <thead><tr><th>Population</th><th class="num">Records</th><th>The rule</th>
  <th>What it reads</th><th>The decision that set it</th><th>Derives from</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table></div>

  <div class="sechead" style="margin-top:22px"><div><h3>Does the chain reconcile?</h3>
  <p>Each step is a set relation that either holds or does not. A step that does not hold is
  reported here rather than closed by adjusting a definition.</p></div></div>
  <div class="tablewrap" style="max-height:none"><table class="ind" id="chaintbl">
  <thead><tr><th>Step</th><th class="num">Counts</th><th>Verdict</th></tr></thead>
  <tbody>{chain}</tbody></table></div>
  {'<div class="panel" style="margin-top:14px"><div class="eyebrow">Where it does not reconcile</div><ul class="note">' + gaps + '</ul></div>' if gaps else ''}

  <details class="expl" style="margin-top:18px"><summary>Declared parameters &mdash; the values
  that are chosen, not measured</summary>
  <div class="panel" style="margin-top:12px">
  <p class="note" style="margin-top:0">These do not move with the data and must not. Each carries
  the citation that makes it a parameter rather than a typo, and the date it was set. Rendered
  from <span class="mono">PARAMS</span> on this page.</p>
  <div class="tablewrap" style="max-height:none"><table class="ind" id="paramstbl">
  <thead><tr><th>Parameter</th><th class="num">Value</th><th>Citation</th><th>Set</th></tr></thead>
  <tbody></tbody></table></div></div></details>
</section>
{END}"""


def apply(write):
    page = open(PAGE, encoding="utf8").read()
    new = block()
    if BEGIN in page:
        i, j = page.index(BEGIN), page.index(END) + len(END)
    else:
        # Anchor OUTSIDE the action-list generated region. Anchoring on the
        # <section id="actions"> tag put this block inside that region, and
        # the next render_actions --write deleted it without a word.
        anchor = "<!-- BEGIN GENERATED action-list"
        if anchor not in page:
            anchor = '<section data-scopes="all mad madx mar enduro" id="actions">'
        if anchor not in page:
            sys.exit("render_definitions: no anchor")
        i = j = page.index(anchor)
        new = new + "\n"
    if page[i:j].strip() == new.strip():
        print("index.html definitions match their generator")
        return 0
    if not write:
        print("index.html definitions DIFFER from their generator")
        return 1
    open(PAGE, "w", encoding="utf8").write(page[:i] + new + page[j:])
    print("index.html definitions section rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(apply("--write" in sys.argv))
