# -*- coding: utf-8 -*-
"""The "Hygiene promotion and gender" section (Adriaan Mol, 1 Oct 2026).

Renders data/hygiene.json (HYG on the page, tools/rebuild_hygiene.py) for the
managed portfolio. Every figure follows the scope buttons: the page functions
defined here sum HYG's per-district figures over the districts the scope
covers (SITES), so a provenance panel names the scope it is in.

    python3 tools/render_hygiene.py --write
    python3 tools/render_hygiene.py --check
"""
import datetime, difflib, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prerender_figures import same as _same  # noqa: E402
import table_notes  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
DATA = os.path.join(REPO, "data", "hygiene.json")
BEGIN = ("<!-- BEGIN GENERATED hygiene :: tools/render_hygiene.py "
         ":: do not edit between these markers -->")
END = "<!-- END GENERATED hygiene -->"
SCOPES_OF = {"Maroantsetra": "all mad madx", "Fort-Dauphin": "all mad madx", "Marolinta": "all mad mar"}
MON = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
       "November", "December"]

SCRIPT = """<script>
// Hygiene figures follow the scope: each sums HYG's districts over SITES.
function hygSites(){ return (typeof SITES!=='undefined' && SITES) ? SITES : HYG.sites; }
function hyg(k){ return hygSites().reduce((a,s)=>a+(((HYG.by_site[s]||{})[k])||0),0); }
function hygCarbon(k){ return hygSites().filter(s=>s!=='Marolinta').reduce((a,s)=>a+(((HYG.by_site[s]||{})[k])||0),0); }
function hygMonth(m){ return hygSites().reduce((a,s)=>a+(((HYG.months[m]||{})[s])||0),0); }
function hygYear(y,k){ return hygSites().reduce((a,s)=>a+((((HYG.years[y]||{})[s])||{})[k]||0),0); }
function hygBasicPct(y){ const n=hygYear(y,'jmp_n'); return n ? Math.round(100*hygYear(y,'jmp_basic')/n)+'%' : 'none'; }
function hygMeets(y){ return (hygYear(y,'sessions')>0 && hygYear(y,'jmp_n')>0) ? 'yes' : 'no'; }
function hygLast(s){ return (HYG.by_site[s]||{}).last || 'none recorded'; }
</script>"""


def fig(e):
    return f'<span data-fig="{e}"></span>'


def block(d):
    asof = datetime.date.fromisoformat(d["asof"])
    first = min(list(d["months"]) + ["2025-11"])
    months, y, m = [], int(first[:4]), int(first[5:7])
    while (y, m) <= (asof.year, asof.month):
        months.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    mrows = "\n".join(f'<tr><td>{MON[int(k[5:7]) - 1]} {k[:4]}</td><td class="num">{fig(f"hygMonth({json.dumps(k)})".replace(chr(34), chr(39)))}</td></tr>'
                      for k in months)
    yrows = "\n".join(
        f"<tr><td>{yy}</td><td class=\"num\">{fig(f'hygYear(\'{yy}\',\'sessions\')')}</td>"
        f"<td class=\"num\">{fig(f'hygYear(\'{yy}\',\'points\')')}</td>"
        f"<td class=\"num\">{fig(f'hygYear(\'{yy}\',\'jmp_n\')')}</td>"
        f"<td class=\"num\">{fig(f'hygBasicPct(\'{yy}\')')}</td>"
        f"<td>{fig(f'hygMeets(\'{yy}\')')}</td></tr>"
        for yy in ("2025", "2026"))
    lrows = "\n".join(
        f'<tr data-scopes="{SCOPES_OF.get(s, "all mad")}"><td>{s}</td>'
        f"<td class=\"num\">{fig(f'HYG.by_site[\'{s}\'].sessions')}</td>"
        f"<td>{fig(f'hygLast(\'{s}\')')}</td></tr>" for s in d["sites"])
    F = d["forms"]
    def form(k, what):
        x = F[k]
        return (f'<a href="https://portal.mwater.co/#/forms/{x["form_id"]}" target="_blank" rel="noopener">{x["name"]}</a> '
                f'&mdash; {what}: {fig(f"HYG.forms.{k}.responses")} submitted responses'
                + (f', {fig(f"HYG.forms.{k}.first")} to {fig(f"HYG.forms.{k}.last")}' if x["first"] else ""))
    return f"""
{SCRIPT}
<div class="sechead"><div><h2>Hygiene promotion and gender</h2><p>Sessions held at the water points we maintain, who came, and whether each year meets the hygiene-campaign obligation. Managed portfolio only; the figures follow the scope buttons.</p></div></div>
<div class="panel">
<p class="note" style="margin-top:0"><b>The obligation.</b> The registered methodology requires that &ldquo;<i>The project must conduct annual water hygiene education campaigns for the end-users</i>&rdquo; (ERSDWS v1.0, parameter <span class="mono">SDWS 20</span>, which governs this crediting period), reported each year &ldquo;<i>in a detailed &lsquo;Report of annual hygiene campaigns results&rsquo;</i>&rdquo;. The VPA-DD commits to &ldquo;<i>at least one education event each year for end-users &hellip; Evidence of the events will be including materials used and number of attendees, disaggregated by gender</i>&rdquo;. Under v2.0 the parameter is <span class="mono">SDWS 24</span>, and &ldquo;<i>The impacts of the campaign shall be assessed using the WHO/UNICEF JMP Core questions for drinking water and hygiene</i>&rdquo;. <span class="muted">A year counts as meeting it here when it has at least one recorded session on a managed point <b>and</b> a survey of managed points&rsquo; users that asks the JMP core hygiene questions (handwashing place observed, with water and soap).</span></p>
<div class="tiles" style="margin-top:8px">
  <div class="tile"><div class="v">{fig("hyg('sessions_12m')")}</div><div class="l">sessions recorded in the last {fig('HYG.window_months')} months, to {fig("HYG.asof")}</div></div>
  <div class="tile"><div class="v">{fig("hyg('points_12m')")}</div><div class="l">water points reached in the last {fig('HYG.window_months')} months, of the {fig("hyg('fleet')")} managed points in scope ({fig("hyg('fleet')?Math.round(100*hyg('points_12m')/hyg('fleet'))+'%':'—'")}); {fig("hygCarbon('points_12m')")} of the carbon fleet&rsquo;s {fig("hygCarbon('fleet')")}</div></div>
  <div class="tile"><div class="v">{fig("hyg('female')")} &middot; {fig("hyg('male')")}</div><div class="l">participants, women and girls &middot; men and boys ({fig("(hyg('female')+hyg('male'))?Math.round(100*hyg('female')/(hyg('female')+hyg('male')))+'%':'—'")} women and girls), as recorded on each session</div></div>
  <div class="tile"><div class="v">{fig("hyg('gender_sessions')")} &middot; {fig("hyg('mhm_sessions')")}</div><div class="l">sessions covering gender equality and women&rsquo;s empowerment &middot; menstrual hygiene</div></div>
</div>
<div class="tablewrap" style="margin-top:10px"><table data-table="hyg-years" class="ind"><thead><tr><th>Year</th><th class="num">Sessions</th><th class="num">Water points reached</th><th class="num">JMP survey households</th><th class="num">With basic hygiene</th><th>Meets the obligation</th></tr></thead><tbody>
{yrows}
</tbody></table></div>
{table_notes.render("hyg-years")}
<div class="grid2" style="margin-top:10px">
<div>
<div class="tablewrap"><table data-table="hyg-months" class="ind"><thead><tr><th>Month</th><th class="num">Sessions</th></tr></thead><tbody>
{mrows}
</tbody></table></div>
{table_notes.render("hyg-months")}
</div>
<div>
<div class="tablewrap"><table data-table="hyg-last" class="ind"><thead><tr><th>District</th><th class="num">Sessions on record</th><th>Last session</th></tr></thead><tbody>
{lrows}
</tbody></table></div>
{table_notes.render("hyg-last")}
</div>
</div>
<p class="note"><b>Where these come from.</b> {form("sessions", "one response per session at a water point, with topics and participants by sex")}. {form("jmp_survey", "the annual household survey that asks the JMP core hygiene questions")}. {form("cbn_gender", "the annual monitoring survey of the same households")}. <span class="muted">{fig("HYG.forms.sessions.outside_managed")} sessions were held at water points outside the managed register and are not counted. Pulled read-only from mWater with the other extracts; computed by <span class="mono">tools/rebuild_hygiene.py</span>.</span></p>
</div>
"""


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    want = block(json.load(open(DATA, encoding="utf8")))
    idx = open(PAGE, encoding="utf8").read()
    if BEGIN not in idx or END not in idx:
        sys.exit("index.html has no hygiene markers")
    a, z = idx.index(BEGIN) + len(BEGIN), idx.index(END)
    if mode == "--write":
        open(PAGE, "w", encoding="utf8").write(idx[:a] + want + idx[z:])
        print("index.html: hygiene " + ("unchanged" if _same(idx[a:z], want) else "rewritten"))
        return 0
    if _same(idx[a:z], want):
        print("index.html hygiene matches its generator")
        return 0
    print("\n".join(list(difflib.unified_diff(idx[a:z].splitlines(), want.splitlines(), "index.html",
                                              "render_hygiene.py", lineterm="", n=0))[:20]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
