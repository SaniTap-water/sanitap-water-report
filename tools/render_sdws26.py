# -*- coding: utf-8 -*-
"""The SDWS 26 section: what the November 2025 round measured, and its limits.

Every figure here is a span over SDWS26 or a population, so the section moves
when the round does and cannot be edited into agreement with itself. The limits
are rendered from the same data as the result, which is the point: a reader who
sees the proportion sees the cluster shortfall beside it without scrolling.

    python3 tools/render_sdws26.py --write | --check
"""
import json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
BEGIN = ("<!-- BEGIN GENERATED sdws26 :: tools/render_sdws26.py :: "
         "do not edit between these markers -->")
END = "<!-- END GENERATED sdws26 -->"
MW = "https://portal.mwater.co/#/forms/"


def esc(x):
    return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def nice(d):
    import datetime
    x = datetime.date.fromisoformat(str(d)[:10])
    return f"{x.day} {x.strftime('%B')} {x.year}"


def fig(expr):
    return f'<span data-fig="{expr}"></span>'


def block():
    src = open(PAGE, encoding="utf8").read()
    m = re.search(r"^const SDWS26\s*=\s*", src, re.M)
    S = json.loads(src[m.end():src.index("};", m.end()) + 1])

    rows = []
    for scen in sorted(S["scenarios"]):
        p = f"SDWS26.scenarios['{scen}']"
        short = S["scenarios"][scen]["clusters_short_by"]
        cl = (f'{fig(p + ".clusters")} of {fig("SDWS26.min_clusters")}'
              + (f' <span class="pill crit">short by {fig(p + ".clusters_short_by")}</span>'
                 if short else ' <span class="pill ok">met</span>'))
        rows.append(
            f'<tr><td><b>{esc(scen)}</b></td>'
            f'<td class="num">{fig(p + ".answered_both")}</td>'
            f'<td class="num"><b>{fig(p + ".served_both_seasons")}</b><br>'
            f'<span class="muted">{fig("(100*" + p + ".served_both_seasons/" + p + ".answered_both).toFixed(1)")}%</span></td>'
            f'<td class="num">{fig(p + ".served_either_season")}<br>'
            f'<span class="muted">{fig("(100*" + p + ".served_either_season/" + p + ".answered_both).toFixed(1)")}%</span></td>'
            f'<td class="num">{fig(p + ".water_points")}</td>'
            f'<td>{cl}</td>'
            f'<td class="num">{fig(p + ".hh_size_mean")}</td></tr>')

    total = ('<tr><td><b>Both scenarios</b></td>'
             f'<td class="num">{fig("SDWS26.answered_both")}</td>'
             f'<td class="num"><b>{fig("SDWS26.served_both_seasons")}</b><br>'
             f'<span class="muted">{fig("(100*SDWS26.served_both_seasons/SDWS26.answered_both).toFixed(1)")}%</span></td>'
             f'<td class="num">{fig("SDWS26.served_either_season")}<br>'
             f'<span class="muted">{fig("(100*SDWS26.served_either_season/SDWS26.answered_both).toFixed(1)")}%</span></td>'
             f'<td class="num">&mdash;</td><td>&mdash;</td><td class="num">&mdash;</td></tr>')

    return f"""{BEGIN}
<section data-scopes="all mad madx mar" id="sdws26">
  <div class="sechead"><div><h2>SDWS 26 &mdash; premises served, from the November 2025 round</h2>
  <p>The annual monitoring survey asks how often a household draws drinking water from the project
  water point, once for the dry season and once for the rainy season. A premises counts as served
  when it reports use <b>at least every two days</b>. <span class="muted">Matched by choice id, not
  by position: the declared scale is not monotonic &mdash; &ldquo;more than once a day&rdquo; sits
  second, after &ldquo;every day&rdquo;. Every figure below expands to its population, rule,
  form and arithmetic.</span></p></div>
  <span class="count">{fig("(100*SDWS26.served_both_seasons/SDWS26.answered_both).toFixed(1)")}% served</span></div>

  <div class="tablewrap" style="max-height:none"><table class="ind" id="sdws26tbl">
  <thead><tr><th>Scenario</th><th class="num">Answered both seasons</th>
  <th class="num">Served, both seasons<br><span class="muted" style="font-weight:400">conservative</span></th>
  <th class="num">Served, either season<br><span class="muted" style="font-weight:400">permissive</span></th>
  <th class="num">Water points</th><th>Clusters vs B.7.3</th>
  <th class="num">Mean household size</th></tr></thead>
  <tbody>{''.join(rows)}{total}</tbody></table></div>

  <p class="note"><b>The seasonal rule does not move the parameter.</b> The two candidate readings
  &mdash; served in both seasons, or served in either &mdash; differ by
  <b>{fig("SDWS26.rule_difference")}</b> record out of <b>{fig("SDWS26.answered_both")}</b>.
  The conservative reading is shown as the headline and the permissive one beside it, so the choice
  is visible rather than buried. <span class="muted">The scale mapping is the same on both: the
  served set is the three choice ids that mean every day, more than once a day, and every two days.</span></p>

  <div class="panel" style="margin-top:16px"><div class="eyebrow">What this round does not evidence</div>
  <ul class="note">
    <li><b>It evidences the 2025 monitoring period, not 2026.</b> Every response was submitted
    between <b>{esc(nice(S["round_from"]))}</b> and <b>{esc(nice(S["round_to"]))}</b>. A 2026
    figure needs its own round; this one cannot be carried forward.</li>
    <li><b>Maroantsetra reached {fig("SDWS26.scenarios['Maroantsetra'].clusters")} clusters against
    the VPA-DD B.7.3 minimum of {fig("SDWS26.min_clusters")}</b>, short by
    {fig("SDWS26.scenarios['Maroantsetra'].clusters_short_by")}. Fort-Dauphin reached
    {fig("SDWS26.scenarios['Fort-Dauphin'].clusters")} and met it. The shortfall is stated rather
    than rounded away, because a verifier will count the communes.</li>
    <li><b>No response carries an approval.</b> All
    {fig("SDWS26.responses_total")} sit unapproved in mWater
    &mdash; <a href="#act-sdws26-approve-2025">act-sdws26-approve-2025</a>.</li>
    <li><b>{fig("SDWS26.excluded_part_entries")} responses are excluded from the denominator</b>
    as abandoned part-entries: they answered neither usage question, and between 2 and 21 of the
    form's 92 questions. Counting a part-entry as a non-response understates the proportion;
    counting it as served overstates it. The exclusion is a stated rule, not a silent filter.</li>
  </ul></div>

  <p class="note" style="margin-bottom:0"><b>SDWS 25, in passing.</b> Mean household size in this
  round is <b>{fig("SDWS26.scenarios['Fort-Dauphin'].hh_size_mean")}</b> in Fort-Dauphin and
  <b>{fig("SDWS26.scenarios['Maroantsetra'].hh_size_mean")}</b> in Maroantsetra, which still round
  to the registered 4.5 and 3.7. <span class="muted">Derived from the same round, question WS1.12;
  the registered values are unchanged and nothing here restates them.</span>
  <a href="{MW}{S['form']}" target="_blank" rel="noopener">The survey form</a>.</p>
</section>
{END}"""


def apply(write):
    page = open(PAGE, encoding="utf8").read()
    new = block()
    if BEGIN not in page:
        sys.exit("render_sdws26: markers not present; place them first")
    i, j = page.index(BEGIN), page.index(END) + len(END)
    if page[i:j].strip() == new.strip():
        print("index.html sdws26 matches its generator")
        return 0
    if not write:
        print("index.html sdws26 DIFFERS from its generator")
        return 1
    open(PAGE, "w", encoding="utf8").write(page[:i] + new + page[j:])
    print("index.html: sdws26 rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(apply("--write" in sys.argv))
