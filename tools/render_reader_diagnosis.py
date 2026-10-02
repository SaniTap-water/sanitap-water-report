# -*- coding: utf-8 -*-
"""The "Why the calendar reader misses marks" block in the calendar section.

Renders data/reader_validation.json (RVAL on the page, written by
tools/reader_validation.py): why the reader of record missed each of the
days both human readers marked X in transcription round 1, the reader as
fixed so far against the same days, and whether the publication gate
(tools/reader_gate.py) is open. The crops behind the diagnosis are in
data/reader_diagnosis/.

    python3 tools/render_reader_diagnosis.py --write
    python3 tools/render_reader_diagnosis.py --check
"""
import difflib, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prerender_figures import same as _same  # noqa: E402
import table_notes  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
DATA = os.path.join(REPO, "data", "reader_validation.json")
BEGIN = ("<!-- BEGIN GENERATED reader-diagnosis :: tools/render_reader_diagnosis.py "
         ":: do not edit between these markers -->")
END = "<!-- END GENERATED reader-diagnosis -->"
GH = "https://github.com/SaniTap-water/sanitap-water-report/tree/main/data/reader_diagnosis"

WHAT = {
    "ink below threshold": "the sampled window is on the X, but a pencil or ballpoint X covers far less of it than the threshold asks",
    "column off by a whole month": "the reader sampled the same day in the neighbouring month column",
    "column phase": "the reader&rsquo;s cell started at the printed weekday, so an X written over or beside the weekday lay outside its window",
    "row off by one": "the reader sampled the day above or below",
    "ink colour": "blue, purple or red ink, which the reader&rsquo;s mask for the printed blue shading removed or its darkness test passed over",
    "orientation": "the photograph was taken turned 90&deg; and the reader read the sheet sideways",
    "photo blurred": "the sheet is out of focus at that cell",
}


def fig(expr):
    return f'<span data-fig="{expr}"></span>'


def pct(expr):
    return fig(f"({expr}*100).toFixed(1)") + "%"


def block(v):
    R = "RVAL"
    causes = "\n".join(
        f'<tr><td>{c}</td><td class="num">{fig(f"{R}.diagnosis.causes['{c}']")}</td><td>{WHAT.get(c, "")}</td></tr>'
        for c in v["diagnosis"]["causes"])
    rows = []
    for rd, label in (("v2", "v2, the reader of record"), ("v3", "v3, fixed on 1 Oct 2026")):
        for sp, sl in (("all", "all calendars"), ("held out (even calendars)", "held-out calendars")):
            b = f"{R}.readers.{rd}['{sp}']"
            rows.append(f"<tr><td>{label}</td><td>{sl}</td>"
                        f"<td class=\"num\">{fig(b + '.both.tp')} of {fig(b + '.both.tp+' + b + '.both.fn')}</td>"
                        f"<td class=\"num\">{pct(b + '.both.sensitivity')}</td>"
                        f"<td class=\"num\">{pct(b + '.both.specificity')}</td>"
                        f"<td class=\"num\">{fig(b + '.both.kappa')}</td>"
                        f"<td class=\"num\">{pct(b + '.adriaan.sensitivity')}</td>"
                        f"<td class=\"num\">{pct(b + '.dieu_donne.sensitivity')}</td></tr>")
    passed = [k for k, ok in v["gate_passed"].items() if ok]
    gate = ("<b>Neither reader passes the gate</b>, so no machine-read downtime is published and the reading of "
            "every calendar photograph has not been re-run with v3."
            if not passed else
            f"<b>{', '.join(passed)} passes the gate on these days.</b> The reader of record is still "
            f"{v['reader_of_record']}; machine-read downtime returns only when the reader of record passes.")
    return f"""
<div class="panel" id="reader-diagnosis" style="margin:14px 0">
  <div class="eyebrow">Why the calendar reader misses marks, and the fix so far</div>
  <p class="note" style="margin-top:6px">For each of the {fig(R + '.diagnosis.both_x_cells')} days both human readers marked X in round <span class="mono">1</span>, and {fig(R + '.diagnosis.blank_cells')} days both read blank (a seeded draw), the reader&rsquo;s own geometry was re-run on the photograph and the cell it samples saved beside the human mark (<a href="{GH}" target="_blank" rel="noopener">crops and measures</a>, <span class="mono">tools/diagnose_reader.py</span>). Each X day was then classed by eye:</p>
  <div class="tablewrap"><table data-table="rdiag-causes" class="ind"><thead><tr><th>Why the reader missed it</th><th class="num">X days</th><th>What happened</th></tr></thead><tbody>
{causes}
</tbody></table></div>
{table_notes.render("rdiag-causes")}
  <p class="note"><b>The threshold alone rules out every X.</b> The reader calls a cell marked when ink covers {fig(R + '.diagnosis.v2_mark_threshold')} of its window and illegible from {fig(R + '.diagnosis.v2_illegible_band[0]')}; on the {fig(R + '.diagnosis.both_x_cells')} X days the most ink it measured was {fig(R + '.diagnosis.v2_max_ink_on_x')}, against up to {fig(R + '.diagnosis.v2_max_ink_on_blank')} on blank days. So even where its window sat on the X it could not call it, and the days it did call marked are not where the humans see marks. The misses fall on <span class="mono">2024</span>, <span class="mono">2025</span> and <span class="mono">2026</span> sheets alike (the <span class="mono">2027</span> sheets have no observed day and are held out), so the template is not the cause; of the {fig(R + '.diagnosis.sheets_turned_in_set')} sheets in the set that had to be turned for the transcription page, the reader&rsquo;s own orientation search read all but one.</p>
  <p class="note"><b>What v3 changes</b> (<span class="mono">tools/caltools.py</span>, <span class="mono">read_v3</span>): the grid is registered on the printed text, the month names fixing each column and the day numbers each column&rsquo;s rows, so a leaning or curled column is followed; ink is measured against the local paper with the printed rules removed, so blue, purple and pencil count; and each cell is compared with what the sheet prints there, its day number and weekday, so only what was written remains. Its threshold was chosen on the odd-numbered calendars and is reported here on the even-numbered ones too. Against the days both humans read the same way:</p>
  <div class="tablewrap"><table data-table="rdiag-metrics" class="ind"><thead><tr><th>Reader</th><th>Calendars</th><th class="num">Both-X days found</th><th class="num">Sensitivity</th><th class="num">Specificity</th><th class="num">&kappa;</th><th class="num">Sensitivity against Adriaan Mol</th><th class="num">against Dieu Donn&eacute;</th></tr></thead><tbody>
{chr(10).join(rows)}
</tbody></table></div>
{table_notes.render("rdiag-metrics")}
  <p class="note" style="margin-bottom:0">The gate needs sensitivity of at least {fig(R + '.gate.sensitivity_min*100')}% and specificity of at least {fig(R + '.gate.specificity_min*100')}% on all calendars and on the held-out ones. {gate} v3 registered {fig(R + '.registered_v3')} of the {fig(R + '.calendars')} sheets; the rest it could not register from the printed text. Every v3 design choice was made looking at round-<span class="mono">1</span> crops, so a second transcription round is the clean test.</p>
</div>
"""


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    v = json.load(open(DATA, encoding="utf8"))
    want = block(v)
    idx = open(PAGE, encoding="utf8").read()
    if BEGIN not in idx or END not in idx:
        sys.exit("index.html has no reader-diagnosis markers")
    a = idx.index(BEGIN) + len(BEGIN)
    z = idx.index(END)
    if mode == "--write":
        open(PAGE, "w", encoding="utf8").write(idx[:a] + want + idx[z:])
        print("index.html: reader-diagnosis " + ("unchanged" if _same(idx[a:z], want) else "rewritten"))
        return 0
    if _same(idx[a:z], want):
        print("index.html reader-diagnosis matches its generator")
        return 0
    print("\n".join(list(difflib.unified_diff(
        idx[a:z].splitlines(), want.splitlines(), "index.html",
        "render_reader_diagnosis.py", lineterm="", n=0))[:20]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
