# -*- coding: utf-8 -*-
"""The collapsed pairing detail in the piped water-quality panel.

Each piped result is paired with its sampling record by the 72-hour rule
(tools/rebuild_piped_wq.py, Adriaan Mol, 28 September 2026). What does not
pair is listed here with its response codes, so Cathy can pair it by hand: a
result with no sample, a sample with no result after 7 days, a sample taken
outside the standposts-only protocol, and a date that disagrees with its
sample. Results filed before the protocol went live are listed apart as
baseline, not paired. The build never fails on these; publish.sh prints the
same list as a gate readout.

    python3 tools/render_piped_pairing.py --write
    python3 tools/render_piped_pairing.py --check
"""
import difflib, html, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prerender_figures import same as _same  # noqa: E402
import table_notes  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
DATA = os.path.join(REPO, "data", "piped_wq.json")
BEGIN = ("<!-- BEGIN GENERATED piped-wq-pairing :: tools/render_piped_pairing.py "
         ":: do not edit between these markers -->")
END = "<!-- END GENERATED piped-wq-pairing -->"
F = "PIPEDWQ.pairing"


def fig(expr):
    return f'<span data-fig="{expr}"></span>'


def codes(xs):
    return ", ".join(f'<span class="mono">{html.escape(x)}</span>' for x in xs) or "&mdash;"


def mono(x):
    return f'<span class="mono">{html.escape(x)}</span>' if x else "&mdash;"


def block(p):
    rows = []
    for x in p["flags"]["result_without_sample"]:
        near = (f'<span class="muted">near: </span>{codes(x["candidates"])}'
                if x["candidates"] else "&mdash;")
        rows.append((f"result with no sample: {html.escape(x['why'])}", mono(x["point"]),
                     html.escape(x["submitted"]), codes([x["result"]]), near))
    for x in p["flags"]["sample_without_result"]:
        rows.append((f"sample with no result after {p['after_days']} days"
                     + (" (pre-completion test)" if x.get("pre_completion") else ""),
                     mono(x["point"]), x["day"], "&mdash;", codes([x["sample"]])))
    for x in p["flags"]["outside_protocol"]:
        where = (f'system {mono(x["system"])}' if not x.get("point") and x.get("system")
                 else mono(x.get("point")))
        rows.append((f"outside protocol &ndash; sample at a public standpost: "
                     f"{html.escape(x['why'])}", where, x["day"] or "&mdash;", "&mdash;",
                     codes([x["sample"]])))
    for x in p["flags"].get("earlier_project_record") or []:
        rows.append((f"{html.escape(x['why'])} (paired and counted)"
                     + (f": Endur&rsquo;O point {mono(x['endur_o_point'])}" if x.get("endur_o_point") else ""),
                     mono(x["point"]), x["day"] or "&mdash;", "&mdash;", codes([x["sample"]])))
    for x in p["flags"]["date_mismatch"]:
        rows.append((f"date mismatch (paired): result says {x['result_day']}, "
                     f"sample taken {x['sample_day']}", mono(x["point"]), x["sample_day"],
                     codes([x["result"]]), codes([x["sample"]])))
    body = "\n".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td><td>{d}</td><td>{e}</td></tr>"
                     for a, b, c, d, e in rows)
    table = ("" if not rows else
             '<div class="tablewrap"><table data-table="piped-pairing" class="ind"><thead><tr>'
             "<th>Flag</th><th>Water point</th><th>Day</th><th>Result (response code)</th>"
             f"<th>Sample (response code)</th></tr></thead><tbody>\n{body}\n</tbody></table></div>\n"
             + table_notes.render("piped-pairing") + "\n")
    base = p["baseline"]["result_list"]
    baseline = ("" if not base else
                f'<p class="note"><b>Baseline, not paired.</b> <span data-fig="{F}.baseline.results">'
                "</span> results were submitted before the tap-level sampling protocol went live "
                f'(<span data-fig="{F}.protocol_live_day"></span>), with <span data-fig="'
                f'{F}.baseline.samples"></span> samples from the same period. They are pre-project '
                "baseline: not paired, not flagged, not counted above. Results: "
                + ", ".join(f'{codes([x["result"]])} <span class="muted">({x["submitted"]})</span>'
                            for x in base) + ".</p>\n")
    return f"""
<details class="expl" id="piped-wq-pairing" style="margin-top:10px"><summary>Results paired with their samples: {fig(F + '.paired')} of {fig(F + '.results')}; {fig(F + '.flagged_total')} flagged for pairing by hand</summary>
<p class="note" style="margin-top:0"><b>The rule.</b> Piped water quality is sampled only at public standposts and kiosks: what comes out of the tap. No source, tank or household samples. A result on the piped result form pairs with the most recent <i>unpaired</i> record on the <a href="https://portal.mwater.co/#/forms/{p['sampling_form']}" target="_blank" rel="noopener">piped sampling form</a> at the same water point (sampling <span class="mono">1.1b</span>), taken within the {fig(F + '.window_hours')}&nbsp;hours before the result was submitted. Each sample pairs once. A pair takes its GPS, sample type and photo from the sampling record. The sampling date on the result (<span class="mono">1.2.2</span>) is a cross-check only: more than {fig(F + '.date_mismatch_days')} day from the sample keeps the pair and adds a date-mismatch note. The code and GPS copied onto the result (<span class="mono">1.2.1</span>, <span class="mono">1.2.3</span>) are not read. A sample with no water point, or at a household, is outside protocol and is flagged, never paired. A sample at an earlier-project record (another organisation&rsquo;s old kiosk) pairs through the Moramanga crosswalk and counts, flagged to use the Endur&rsquo;O point next time. <span class="muted">Decision: Adriaan Mol, 28 Sep 2026.</span></p>
<p class="note"><b>Now.</b> {fig(F + '.paired')} of the {fig(F + '.results')} results since the protocol went live are paired ({fig(F + '.paired_with_gps')} with GPS, {fig(F + '.paired_with_photo')} with a photo, {fig(F + '.date_mismatch')} with a date mismatch), from {fig(F + '.samples')} sampling records. {fig(F + '.outside_protocol')} samples are outside protocol, {fig(F + '.flagged.sample_without_result')} have no result after {fig(F + '.after_days')} days and {fig(F + '.samples_pending')} are within that window. <b>Pre-completion tests</b> &mdash; samples on a system whose upgrade or new build is under way: {fig(F + '.pre_completion.samples')}, of which {fig(F + '.pre_completion.paired')} paired. They are shown here and enter no carbon or portfolio figure. <span class="muted">Coordinates are not shown on this page; the pairs with their GPS stay with the extracts. Flags never stop the build: each one is Cathy&rsquo;s to pair by hand.</span></p>
{table}{baseline}</details>
"""


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    p = json.load(open(DATA, encoding="utf8"))["pairing"]
    want = block(p)
    idx = open(PAGE, encoding="utf8").read()
    if BEGIN not in idx or END not in idx:
        sys.exit("index.html has no piped-wq-pairing markers")
    a = idx.index(BEGIN) + len(BEGIN)
    z = idx.index(END)
    if mode == "--write":
        open(PAGE, "w", encoding="utf8").write(idx[:a] + want + idx[z:])
        print("index.html: piped-wq-pairing "
              + ("unchanged" if _same(idx[a:z], want) else "rewritten"))
        return 0
    if _same(idx[a:z], want):
        print("index.html piped-wq-pairing matches its generator")
        return 0
    print("\n".join(list(difflib.unified_diff(
        idx[a:z].splitlines(), want.splitlines(), "index.html",
        "render_piped_pairing.py", lineterm="", n=0))[:20]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
