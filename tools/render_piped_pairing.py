# -*- coding: utf-8 -*-
"""The collapsed pairing detail in the piped water-quality panel.

Each piped result is paired with its sampling record by site and sampling day
(tools/rebuild_piped_wq.py, Adriaan Mol, 28 September 2026). What does not
pair is listed here with its response codes, so Cathy can pair it by hand: a
result with no sample, a sample with no result after 7 days, and a site and
day with more than one of either. The build never fails on these; publish.sh
prints the same list as a gate readout.

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


def site(x):
    """'point 900' -> point <mono>900</mono>: an identifier, not a figure."""
    if not x:
        return "&mdash;"
    kind, _, code = x.partition(" ")
    return f'{kind} <span class="mono">{html.escape(code)}</span>'


def block(p):
    rows = []
    for x in p["flags"]["more_than_one"]:
        rows.append(("more than one on this site and day", site(x["site"]), x["day"],
                     codes(x["results"]), codes(x["samples"])))
    for x in p["flags"]["result_without_sample"]:
        near = (f'<span class="muted">none paired; near: </span>{codes(x["candidates"])}'
                if x["candidates"] else "&mdash;")
        why = "no sample on this site and day" if x.get("day") else x["why"]
        rows.append((f"result with no sample: {why}", site(x["site"]),
                     x.get("day") or x.get("result_day"), codes([x["result"]]), near))
    for x in p["flags"]["sample_without_result"]:
        why = f": {x['why']}" if x.get("why") else ""
        rows.append((f"sample with no result after {p['after_days']} days{why}",
                     site(x["site"]), x["day"] or "&mdash;", "&mdash;",
                     codes([x["sample"]])))
    for x in p["flags"]["code_mismatch"]:
        rows.append((f"typed sampling code {html.escape(x['typed'])} differs (paired anyway)",
                     site(x["site"]), x["day"], codes([x["result"]]), codes([x["sample"]])))
    body = "\n".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td><td>{d}</td><td>{e}</td></tr>"
                     for a, b, c, d, e in rows)
    table = ("" if not rows else
             '<div class="tablewrap"><table data-table="piped-pairing" class="ind"><thead><tr>'
             "<th>Flag</th><th>Site</th><th>Sampling day</th><th>Result (response code)</th>"
             f"<th>Sample (response code)</th></tr></thead><tbody>\n{body}\n</tbody></table></div>\n"
             + table_notes.render("piped-pairing") + "\n")
    return f"""
<details class="expl" id="piped-wq-pairing" style="margin-top:10px"><summary>Results paired with their samples: {fig(F + '.paired')} of {fig(F + '.results')}; {fig(F + '.flagged_total')} flagged for pairing by hand</summary>
<p class="note" style="margin-top:0"><b>The rule.</b> Each result on the piped result form is paired with its record on the <a href="https://portal.mwater.co/#/forms/{p['sampling_form']}" target="_blank" rel="noopener">piped sampling form</a> by the same water point (sampling <span class="mono">1.1b</span>) or, for a sample taken at the source or in the system, the same water system (<span class="mono">1.1</span>), <i>and</i> the same sampling day (result <span class="mono">1.2.2</span> against the day of sampling <span class="mono">1.4</span>, Madagascar time). A pair takes its GPS, sample type and photo from the sampling record. The sampling code typed on the result (<span class="mono">1.2.1</span>) is only a cross-check, and the GPS copied onto the result (<span class="mono">1.2.3</span>) is not read. <span class="muted">Decision: Adriaan Mol, 28 Sep 2026.</span></p>
<p class="note"><b>Now.</b> {fig(F + '.paired')} of the {fig(F + '.results')} results pair on their own ({fig(F + '.paired_with_gps')} with GPS, {fig(F + '.paired_with_photo')} with a photo, from {fig(F + '.samples')} sampling records). {fig(F + '.results_without_sampling_date')} results carry no sampling date: they were filed before question <span class="mono">1.2.2</span> existed, so they cannot pair on their own; the samples taken in the {fig('PIPEDWQ.pairing.after_days')} days before each one was read are listed beside it. {fig(F + '.flagged.more_than_one')} sites and days have more than one sample or result, {fig(F + '.flagged.sample_without_result')} samples have no result after {fig(F + '.after_days')} days, and {fig(F + '.samples_pending')} are within that window. <span class="muted">Coordinates are not shown on this page; the pairs with their GPS stay with the extracts. Flags never stop the build: each one is Cathy&rsquo;s to pair by hand.</span></p>
{table}</details>
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
