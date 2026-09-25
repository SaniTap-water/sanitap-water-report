# -*- coding: utf-8 -*-
"""The SDWS 26 section: what the November 2025 round measured, and its limits.

The headline is the seasonal average - the mean of the dry-season and
rainy-season served shares - by James Walker's ruling of 23 September 2026.
The both-seasons and either-season readings appear only in the derivation
panel under each average (tools/render_derivations.py), never as figures.

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


def avg(p):
    """The SDWS 26 served share: the average of the dry-season and rainy-season
    shares (James Walker, 23 September 2026), computed on the page."""
    return (f"((100*{p}.served_dry/{p}.answered_both"
            f"+100*{p}.served_rain/{p}.answered_both)/2).toFixed(1)")


def block():
    src = open(PAGE, encoding="utf8").read()
    m = re.search(r"^const SDWS26\s*=\s*", src, re.M)
    S = json.loads(src[m.end():src.index("};", m.end()) + 1])

    def pct(p, k):
        return fig(f"(100*{p}.{k}/{p}.answered_both).toFixed(1)")

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
            f'<td class="num">{fig(p + ".served_dry")}<br>'
            f'<span class="muted">{pct(p, "served_dry")}%</span></td>'
            f'<td class="num">{fig(p + ".served_rain")}<br>'
            f'<span class="muted">{pct(p, "served_rain")}%</span></td>'
            f'<td class="num"><b>{fig(avg(p))}%</b></td>'
            f'<td class="num">{fig(p + ".water_points")}</td>'
            f'<td>{cl}</td>'
            f'<td class="num">{fig(p + ".hh_size_mean")}</td></tr>')

    total = ('<tr><td><b>Both scenarios</b></td>'
             f'<td class="num">{fig("SDWS26.answered_both")}</td>'
             f'<td class="num">{fig("SDWS26.served_dry")}<br>'
             f'<span class="muted">{pct("SDWS26", "served_dry")}%</span></td>'
             f'<td class="num">{fig("SDWS26.served_rain")}<br>'
             f'<span class="muted">{pct("SDWS26", "served_rain")}%</span></td>'
             f'<td class="num"><b>{fig(avg("SDWS26"))}%</b></td>'
             f'<td class="num">&mdash;</td><td>&mdash;</td><td class="num">&mdash;</td></tr>')

    return f"""{BEGIN}
<section data-scopes="all mad madx mar" id="sdws26">
  <div class="sechead"><div><h2>SDWS 26 &mdash; premises served, from the November 2025 round</h2>
  <p>The annual monitoring survey asks how often a household draws drinking water from the project
  water point, once for the dry season and once for the rainy season. A premises counts as served
  in a season when it reports use <b>at least every two days</b>, and <b>the served share is the
  average of the dry-season and rainy-season shares</b>. <span class="muted">Every figure below
  expands to its population, rule, form and arithmetic.</span></p></div>
  <span class="count">{fig(avg("SDWS26"))}% served</span></div>

  <div class="tablewrap" style="max-height:none"><table class="ind" id="sdws26tbl">
  <thead><tr><th>Scenario</th><th class="num">Answered both seasons</th>
  <th class="num">Served, dry season<br><span class="muted" style="font-weight:400">WS1.18</span></th>
  <th class="num">Served, rainy season<br><span class="muted" style="font-weight:400">WS1.39</span></th>
  <th class="num">Served share<br><span class="muted" style="font-weight:400">average of the two seasons</span></th>
  <th class="num">Water points</th><th>Clusters vs B.7.3</th>
  <th class="num">Mean household size</th></tr></thead>
  <tbody>{''.join(rows)}{total}</tbody></table></div>

  <p class="note"><b>The headline is the seasonal average: {fig(avg("SDWS26"))}% across both
  scenarios</b>, {fig(avg("SDWS26.scenarios['Fort-Dauphin']"))}% in Fort-Dauphin and
  {fig(avg("SDWS26.scenarios['Maroantsetra']"))}% in Maroantsetra. <span class="muted">The
  both-scenarios figure pools the responses of the two scenarios. Open any average for its working,
  which also shows the both-seasons and either-season readings as a sensitivity.</span></p>

  <p class="note" id="sdws26-rule"><b>The seasonal rule.</b> The served share is the average of two
  shares: the premises served in the dry season (WS1.18) and the premises served in the rainy season
  (WS1.39), each over the premises that answered both questions. It is <b>not</b> the share served in
  both seasons. <b>The served set</b> is <i>Every day</i>, <i>More than 1 time per day</i> and
  <i>Every 2 days</i>, matched by choice id (<span class="mono">J1qZUqA</span>,
  <span class="mono">6wqmK16</span>, <span class="mono">h4uZZBz</span>), never by position: the
  declared scale is not monotonic, because &ldquo;more than once a day&rdquo; sits second.
  <span class="muted">Source for both: James Walker, Carbon Lead, email &ldquo;Re: Water program
  dashboard &amp; actions&rdquo;, 23 September 2026 &mdash; <i>&ldquo;Let&rsquo;s average it to
  prevent unnecessarily losing credits&rdquo;</i> on the seasonal rule, and <i>&ldquo;Correct&rdquo;</i>
  on the served set. Recorded in <span class="mono">docs/decision_log.md</span>.</span></p>

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
