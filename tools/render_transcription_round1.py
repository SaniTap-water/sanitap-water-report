# -*- coding: utf-8 -*-
"""The "Transcription check, round 1" block in the calendar section.

Three readers on the same calendars and days: Adriaan Mol (28 Sep 2026),
Dieu Donné Razafimahatratra of MadAvance MERV (1 Oct 2026, cleaned) and the
machine reader. Every figure is a data-fig span on TRC1, which is
data/transcription_round1.json, written by tools/transcription_round1.py.
The evidence (raw export, cleaned data, adjustments, disagreements, summary)
is in data/transcriptions/ and linked from the block. This block reports the
check; it changes no action's status.

    python3 tools/render_transcription_round1.py --write
    python3 tools/render_transcription_round1.py --check
"""
import difflib, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prerender_figures import same as _same  # noqa: E402
import table_notes  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
BEGIN = ("<!-- BEGIN GENERATED transcription-round1 :: tools/render_transcription_round1.py "
         ":: do not edit between these markers -->")
END = "<!-- END GENERATED transcription-round1 -->"
GH = "https://github.com/SaniTap-water/sanitap-water-report/blob/main/data/transcriptions/"


def fig(expr):
    return f'<span data-fig="{expr}"></span>'


def pct(expr):
    return fig(f"({expr}*100).toFixed(1)") + "%"


def ev(name, label):
    return f'<a href="{GH}{name}" target="_blank" rel="noopener">{label}</a>'


PAIRS = [(0, "Adriaan Mol &times; Dieu Donn&eacute;"),
         (1, "Adriaan Mol &times; machine"),
         (2, "Dieu Donn&eacute; &times; machine")]
SENS = [("adriaan", "Adriaan Mol"), ("dieu_donne", "Dieu Donn&eacute;"),
        ("both_humans_agree", "cells where both humans agree")]


def block():
    t = "TRC1"
    rows = "\n".join(
        f"<tr><td>{name}</td><td class=\"num\">{pct(f'{t}.pairs[{i}].agreement')}</td>"
        f"<td class=\"num\">{fig(f'{t}.pairs[{i}].kappa')}</td>"
        f"<td class=\"num\">{fig(f'{t}.pairs[{i}].cells_scored')}</td>"
        f"<td class=\"num\">{fig(f'{t}.calendar_pairs[{i}].both_marked')}</td>"
        f"<td class=\"num\">{fig(f'{t}.calendar_pairs[{i}].a_only')}</td>"
        f"<td class=\"num\">{fig(f'{t}.calendar_pairs[{i}].b_only')}</td></tr>"
        for i, name in PAIRS)
    srows = "\n".join(
        f"<tr><td>{name}</td><td class=\"num\">{pct(f'{t}.machine_vs.{k}.sensitivity')}</td>"
        f"<td class=\"num\">{pct(f'{t}.machine_vs.{k}.specificity')}</td>"
        f"<td class=\"num\">{fig(f'{t}.machine_vs.{k}.tp')}</td>"
        f"<td class=\"num\">{fig(f'{t}.machine_vs.{k}.fn')}</td>"
        f"<td class=\"num\">{fig(f'{t}.machine_vs.{k}.fp')}</td></tr>"
        for k, name in SENS)
    return f"""
<div class="panel" id="transcription-round1" style="margin:14px 0">
  <div class="eyebrow">Transcription check, round <span class="mono">1</span></div>
  <p class="note" style="margin-top:6px">Three readers of the same calendars and days: Adriaan Mol (<span class="mono">28 Sep 2026</span>), Dieu Donn&eacute; Razafimahatratra of MadAvance MERV (<span class="mono">1 Oct 2026</span>) and the machine reader. Dieu Donn&eacute;&rsquo;s export is kept as exported and cleaned in the ingest script, every step a row of the adjustments file: {fig(t + '.cleaning.void_after_photo')} marks after the photo date void; calendar <span class="mono">43</span>&rsquo;s {fig(t + '.cleaning.margin_note_x')} X from the gardien&rsquo;s margin notes kept out of the grid figures; {fig(t + '.cleaning.x_to_question.length')} X the transcriber&rsquo;s own note calls a doubtful sign counted as ?; {fig(t + '.cleaning.held_out.length')} sheets dated a year ahead held out until MadAvance confirms which side was marked; calendar <span class="mono">3</span> excluded. Cleaned: {fig(t + '.clean_totals.x')} X and {fig(t + '.clean_totals.question')} ? on {fig(t + '.clean_totals.calendars_marked')} of {fig(t + '.clean_totals.calendars')} calendars. One observed window for every reader (sheet year and photo date). X against blank is scored; ? is shown, never scored right or wrong.</p>
  <p class="note">Both humans confirmed {fig(t + '.calendars_both_humans')} calendars; the machine reads {fig(t + '.calendars_three_way')} of them, the set below.</p>
  <div class="tablewrap"><table data-table="trc1-agreement" class="ind"><thead><tr><th>Pair</th><th class="num">Agreement, X or blank (days)</th><th class="num">Cohen&rsquo;s &kappa;</th><th class="num">Days scored</th><th class="num">Calendars marked by both</th><th class="num">by the first only</th><th class="num">by the second only</th></tr></thead><tbody>
{rows}
</tbody></table></div>
{table_notes.render("trc1-agreement")}
  <div class="tablewrap"><table data-table="trc1-machine" class="ind"><thead><tr><th>Machine reader against</th><th class="num">Sensitivity</th><th class="num">Specificity</th><th class="num">X found</th><th class="num">X missed</th><th class="num">X the reference reads blank</th></tr></thead><tbody>
{srows}
</tbody></table></div>
{table_notes.render("trc1-machine")}
  <p class="note"><b>The two humans disagree on {fig(t + '.human_disagreements')} days</b> on {fig(t + '.human_disagreement_calendars')} calendars: {fig(t + ".human_disagreements_by_type['X contre vide']")} where one reads X and the other blank, {fig(t + ".human_disagreements_by_type['? contre vide']")} where Dieu Donn&eacute; reads ? and Adriaan blank. These are to be settled by eye before the machine is scored. {fig(t + '.cleaning.year_questions.length')} of the void marks would fall on or before the photo date with the sheet year one earlier, so the year of those sheets is worth a look; it is not shown to be wrong.</p>
  <p class="note" style="margin-bottom:0"><b>Evidence:</b> {ev('round1_resume.md', 'summary')}, {ev('round1_ajustements.csv', 'adjustments')}, {ev('round1_desaccords_humains.csv', 'human disagreements')}, {ev('round1_calendriers.csv', 'per calendar')}, {ev('round1_matrices.csv', 'confusion matrices')}, {ev('releves_calendriers_dieu-donne_serie1_2026-10-01.csv', 'raw export')} (<span class="mono">data/transcriptions/</span>, <span class="mono">tools/transcription_round1.py</span>). The validation round is <a href="#act-transcription-round">act-transcription-round</a>.</p>
</div>
"""


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    want = block()
    idx = open(PAGE, encoding="utf8").read()
    if BEGIN not in idx or END not in idx:
        sys.exit("index.html has no transcription-round1 markers")
    a = idx.index(BEGIN) + len(BEGIN)
    z = idx.index(END)
    if mode == "--write":
        open(PAGE, "w", encoding="utf8").write(idx[:a] + want + idx[z:])
        print("index.html: transcription-round1 "
              + ("unchanged" if _same(idx[a:z], want) else "rewritten"))
        return 0
    if _same(idx[a:z], want):
        print("index.html transcription-round1 matches its generator")
        return 0
    print("\n".join(list(difflib.unified_diff(
        idx[a:z].splitlines(), want.splitlines(), "index.html",
        "render_transcription_round1.py", lineterm="", n=0))[:20]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
