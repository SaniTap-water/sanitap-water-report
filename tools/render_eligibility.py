# -*- coding: utf-8 -*-
"""The "Pre-project eligibility" section (3 Oct 2026).

Renders data/eligibility.json (ELIG on the page), written by
tools/rebuild_eligibility.py: hand pumps under methodology 2.2.1(d) (the
three-month out-of-order control, its photographs, the works date, the
record) and piped systems under SDWS 12 (pre-project results and whether any
fails the health-based rule), each row linked to its mWater record so a
verifier can open it. Scope-aware: hand-pump counts sum ELIG's districts over
SITES, rows carry data-scopes by district, and the piped part shows only where
the scope covers Endur'O.

    python3 tools/render_eligibility.py --write
    python3 tools/render_eligibility.py --check
"""
import difflib, html, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prerender_figures import same as _same  # noqa: E402
import table_notes  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
DATA = os.path.join(REPO, "data", "eligibility.json")
BEGIN = ("<!-- BEGIN GENERATED eligibility :: tools/render_eligibility.py "
         ":: do not edit between these markers -->")
END = "<!-- END GENERATED eligibility -->"
RESP = "https://portal.mwater.co/#/responses/"
FORM = "https://portal.mwater.co/#/forms/"
SITE_SCOPES = {"Maroantsetra": "all mad madx", "Fort-Dauphin": "all mad madx", "Marolinta": "all mad mar"}
STATUS_PILL = {"yes_photo": "ok", "yes_no_photo": "ok", "no": "crit", "blank": "warn",
               "no_record": "warn", "borehole_form": "na"}
SCRIPT = """<script>
// Eligibility figures follow the scope: each sums ELIG's districts over SITES.
function eligSites(){ return (typeof SITES!=='undefined' && SITES) ? SITES : Object.keys(ELIG.hp.by_site); }
function elig(k){ return eligSites().reduce((a,s)=>a+(((ELIG.hp.by_site[s]||{})[k])||0),0); }
</script>"""


def fig(e):
    return f'<span data-fig="{e}"></span>'


def esc(s):
    return html.escape(s or "", quote=False)


def ids(text):
    """Escape, and mark water point and system codes as identifiers."""
    return re.sub(r"(?<![\w.])(\d{9,10})(?![\w.])", r'<span class="mono">\1</span>', esc(text))


def rlink(rid, text="record"):
    return (f'<a href="{RESP}{esc(rid)}" target="_blank" rel="noopener">{text}</a>'
            if rid else '<span class="muted">none</span>')


def block(d):
    L = d["labels"]
    hp = []
    for r in d["hp"]["rows"]:
        hp.append(
            f'<tr data-scopes="{SITE_SCOPES.get(r["site"], "all mad")}"><td><span class="mono">{esc(r["wp"])}</span></td>'
            f'<td>{esc(r["site"])}</td>'
            f'<td><span class="pill {STATUS_PILL[r["status"]]}">{esc(L[r["status"]])}</span></td>'
            f'<td>{"yes" if r["photos"] else "<span class=muted>no</span>"}</td>'
            f'<td>{esc(r["works_date"] or r["submitted"] or "")}</td>'
            f'<td>{rlink(r["response"])}</td></tr>')
    gaps = []
    for g in d["gaps"]:
        gaps.append(
            f'<tr><td><span class="mono">{esc(g["wp"])}</span></td><td>{esc(g["issue"])}</td>'
            f'<td>{"in the managed fleet" if g["in_fleet"] else "<span class=muted>outside the managed fleet</span>"}</td>'
            f'<td>{"yes" if g["photos"] else "<span class=muted>no</span>"}</td>'
            f'<td>{esc(g["works_date"] or "")}</td><td>{rlink(g["response"])}</td><td>{esc(g["action"])}</td></tr>')
    sysrows, lists = [], []
    for i, s in enumerate(d["piped"]):
        b = f"ELIG.piped[{i}]"
        pill = "ok" if s["eligible"] else ("warn" if s["status"] != "not_managed" else "na")
        sysrows.append(
            f'<tr><td>{esc(s["name"]) or "<span class=muted>no name</span>"}</td><td><span class="mono">{esc(s["code"])}</span></td>'
            f'<td>{esc(s["status"].replace("_", " "))}</td><td>{esc(s["works_complete"] or "")}</td>'
            f'<td class="num">{fig(b + ".results")}</td>'
            f'<td>{esc(s["first"] + " to " + s["last"]) if s["results"] else "&mdash;"}</td>'
            f'<td class="num">{fig(b + ".ecoli_present_pct") + "%" if s["results"] else "&mdash;"}</td>'
            f'<td><span class="pill {pill}">{esc(s["eligibility"])}</span></td>'
            f'<td>{"<a href=" + chr(34) + "#elig-res-" + esc(s["code"]) + chr(34) + ">the results</a>" if s["results"] else "&mdash;"}</td></tr>')
        if s["results"]:
            items = "".join(f'<li>{rlink(rid, esc(rid[:8]) + "&hellip;")}</li>' for rid in s["responses"])
            lists.append(
                f'<details class="expl" id="elig-res-{esc(s["code"])}" style="margin-top:8px"><summary>{esc(s["name"])}: '
                f'the {fig(b + ".results")} pre-project results in mWater</summary>'
                f'<p class="note" style="margin-top:0">On the piped result form (<a href="{FORM}{d["forms"]["piped_result"]}" '
                f'target="_blank" rel="noopener">Piped Water || Water Quality Testing_SDWS 3__Result</a>), dated '
                f'{fig(b + ".first")} to {fig(b + ".last")}; {fig(b + ".ecoli_present")} of them with <i>E. coli</i> '
                f'above {fig("ELIG.piped_rule.pass_max")} per 100&nbsp;ml. Each link opens the response.</p>'
                f'<ol class="cols" style="columns:4;font-size:.85em">{items}</ol></details>')
    exc = d["exceptions"]
    exc_items = "".join(f'<li><span class="mono">{esc(e["wp"])}</span> ({esc(e["figures"])}): {ids(e["reason"])}</li>'
                        for e in exc["hand_pumps"])
    exc_items += "".join(f'<li>{esc(e["site"])} ({esc(e["figures"])}): {ids(e["reason"])}</li>' for e in exc["sites"])
    exc_items += "".join(f'<li><span class="mono">{esc(e["code"])}</span>, {ids(e["name"])} ({esc(e["figures"])}): {ids(e["reason"])}</li>'
                         for e in exc["piped"])
    kiosk = next((e for e in exc["piped"] if e["code"] == "1125843376"), None)
    return f"""
<section data-scopes="all mad madx mar enduro" id="eligsec">
{SCRIPT}
<div class="sechead"><div><h2>Pre-project eligibility: non-functional or non-potable before the project</h2><p>Methodology 2.2.1(d) and SDWS 12: a point may count only if it was out of order, or its water was not safe, before the project. A rehabilitated hand pump must have been out of order, with no planned maintenance, for at least three months beforehand; a piped system must show water that failed the health-based rule before its works were complete. Every row links to its mWater record so a verifier can open it.</p></div></div>
<div class="panel" data-scopes="all mad madx mar">
<div class="eyebrow">Hand pumps &mdash; out of order for three months before the works (2.2.1(d))</div>
<p style="margin:8px 0 0"><b>{fig("elig('evidenced')")} of the {fig("elig('total')")} managed pumps in this scope carry the control answered Yes</b> on their first-rehabilitation record: {fig("elig('yes_photo')")} with the photographs that prove it, {fig("elig('yes_no_photo')")} without. {fig("elig('no')")} answered No, {fig("elig('blank')")} left it blank, {fig("elig('no_record')")} have no first-rehabilitation record, and {fig("elig('borehole_form')")} are Marolinta works on the borehole-progress form, which carries no such control.</p>
<div data-scopes="all mad madx">
<p class="note" style="margin:10px 0 0"><b>The gaps: the {fig("ELIG.gaps.length")} records already flagged under 2.2.1(d)</b> &mdash; {fig("ELIG.gaps_no")} answered No, {fig("ELIG.gaps_blank")} left blank; {fig("ELIG.gaps_in_fleet")} of the pumps are in the managed fleet. This is an eligibility question, not a data error: nothing here says the rehabilitation did not happen. <a href="#act-close-eight-2-2">The action that closes them</a>.</p>
<div class="tablewrap"><table data-table="elig-gaps" class="ind"><thead><tr><th>Water point</th><th>Issue</th><th>Fleet</th><th>Photographs</th><th>Works date</th><th>Record</th><th>Action</th></tr></thead><tbody>
{chr(10).join(gaps)}
</tbody></table></div>
{table_notes.render("elig-gaps")}
</div>
<details class="expl" id="elig-hp" style="margin-top:10px"><summary>Every managed pump in this scope: the control, the photographs, the works date and the record</summary>
<div class="tablewrap"><table data-table="elig-hp" class="ind"><thead><tr><th>Water point</th><th>District</th><th>Out of order three months before</th><th>Photographs</th><th>Works date</th><th>Record</th></tr></thead><tbody>
{chr(10).join(hp)}
</tbody></table></div>
{table_notes.render("elig-hp")}
</details>
</div>
<div class="panel" style="margin-top:12px" data-scopes="all enduro">
<div class="eyebrow">Piped systems &mdash; non-potable before the works (SDWS 12)</div>
<p style="margin:8px 0 0"><b>A piped system shows it was non-potable before the project when at least one pre-project result fails the health-based rule</b>, <i>E. coli</i> above {fig("ELIG.piped_rule.pass_max")} per 100&nbsp;ml. A result is pre-project if it is dated before the tap-level protocol went live ({fig("ELIG.piped_rule.protocol_live_text")}), or before the system&rsquo;s works completion where that date is recorded. <b>{fig("ELIG.piped_counts.eligible")} of the {fig("ELIG.piped_counts.systems")} systems</b> show it; {fig("ELIG.piped_counts.no_test")} have no pre-project test.</p>
<p class="note" style="margin:10px 0 0"><b>The baseline must be taken before works completion.</b> Once a system&rsquo;s works are complete, no test can show its starting situation any more, so a system with no pre-project test cannot show eligibility this way after the event.</p>
<p class="note" style="margin:10px 0 0"><b>Amboasary gara&rsquo;s results are pre-project evidence of need.</b> They record the starting situation that qualifies the system for the programme, while its upgrade is under way. They are not a failure or a risk of a managed system, and they call for no corrective action: the system joins the managed portfolio only after its works are complete and its post-works tests are done.</p>
<div class="tablewrap"><table data-table="elig-piped" class="ind"><thead><tr><th>System</th><th>Code</th><th>Status</th><th>Works complete</th><th class="num">Pre-project results</th><th>Dates</th><th class="num">With <i>E. coli</i></th><th>Eligibility</th><th>Records</th></tr></thead><tbody>
{chr(10).join(sysrows)}
</tbody></table></div>
{table_notes.render("elig-piped")}
{chr(10).join(lists)}
<p class="note" style="margin:10px 0 0"><b>The managed Antananarivo kiosk</b> (<span class="mono">1125843376</span>, water point <span class="mono">1125843383</span>). {ids(kiosk["reason"]) if kiosk else ""}</p>
</div>
<details class="expl" id="elig-exceptions" style="margin-top:12px"><summary>Listed exceptions: what may stand in the figures without eligibility evidence</summary>
<p class="note" style="margin-top:0">The build fails if a point or system is in the managed or carbon figures with neither eligibility evidence nor an entry here (<span class="mono">data/eligibility_exceptions.json</span>) or in the 2.2.1(d) gaps above.</p>
<ul class="note">{exc_items}</ul>
</details>
</section>
"""


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    want = block(json.load(open(DATA, encoding="utf8")))
    idx = open(PAGE, encoding="utf8").read()
    if BEGIN not in idx or END not in idx:
        sys.exit("index.html has no eligibility markers")
    a, z = idx.index(BEGIN) + len(BEGIN), idx.index(END)
    if mode == "--write":
        open(PAGE, "w", encoding="utf8").write(idx[:a] + want + idx[z:])
        print("index.html: eligibility " + ("unchanged" if _same(idx[a:z], want) else "rewritten"))
        return 0
    if _same(idx[a:z], want):
        print("index.html eligibility matches its generator")
        return 0
    print("\n".join(list(difflib.unified_diff(idx[a:z].splitlines(), want.splitlines(), "index.html",
                                              "render_eligibility.py", lineterm="", n=0))[:20]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
