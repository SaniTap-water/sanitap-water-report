# -*- coding: utf-8 -*-
"""The "Calls and what followed" table under the activity tiles.

One row per managed pump a call-centre contact reported not working (down, or
partially working for a reason other than a routine service request) in the
last window_days, from its first such call in the window: the next submitted
repair or preventive visit after the call in mWater, days elapsed, and a flag
for a call with no repair after 7 days. Renders data/call_followup.json
(CALLF on the page), written by tools/call_followup.py.

    python3 tools/render_call_followup.py --write
    python3 tools/render_call_followup.py --check
"""
import difflib, html, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prerender_figures import same as _same  # noqa: E402
import table_notes  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
DATA = os.path.join(REPO, "data", "call_followup.json")
BEGIN = ("<!-- BEGIN GENERATED call-followup :: tools/render_call_followup.py "
         ":: do not edit between these markers -->")
END = "<!-- END GENERATED call-followup -->"
MWR = "https://portal.mwater.co/#/responses/"
W = "CALLF.windows.window"
WK = "CALLF.windows.week"


def fig(e):
    return f'<span data-fig="{e}"></span>'


def link(rid, text):
    return f'<a href="{MWR}{html.escape(rid)}" target="_blank" rel="noopener">{text}</a>' if rid else text


def block(d):
    w = d["windows"]["window"]
    rows = []
    for i, r in enumerate(w["calls"]):
        b = f"{W}.calls[{i}]"
        n = r["next"]
        nxt = ("&mdash; nothing yet" if not n else
               link(n["rid"], f'{html.escape(n["kind"])} <span data-fig="{b}.next.date"></span>') +
               f' <span class="muted">(+<span data-fig="{b}.next.days"></span> d)</span>')
        rep = ("&mdash;" if not r["next_repair"] else
               link(r["next_repair"]["rid"], f'<span data-fig="{b}.next_repair.date"></span>') +
               f' <span class="muted">(+<span data-fig="{b}.next_repair.days"></span> d)</span>')
        pill = {"no repair after 7 days": '<span class="pill crit">none in time</span>',
                "repaired within 7 days": '<span class="pill ok">in time</span>',
                "not yet due": '<span class="pill na">not yet due</span>'}[r["flag"]]
        rows.append(f'<tr><td><span class="mono">{html.escape(r["wp"])}</span></td><td>{html.escape(r["site"])}</td>'
                    f'<td>{link(r["call_rid"], f"""<span data-fig="{b}.call_date"></span>""")}'
                    + (f' <span class="muted">({fig(b + ".calls_in_window")} calls)</span>' if r["calls_in_window"] > 1 else "")
                    + f'</td><td>{"down" if r["status"] == "down" else "partially working"}</td>'
                    f'<td>{nxt}</td><td>{rep}</td><td>{pill}</td></tr>')
    body = "\n".join(rows) or '<tr><td colspan="7" class="muted">No call reported a managed pump not working in this window.</td></tr>'
    return f"""
<div class="panel" id="callfollow" style="margin-top:12px">
  <div class="eyebrow">Calls and what followed</div>
  <p class="note" style="margin-top:6px">The pumps behind the tile &ldquo;Pumps a call reported not working&rdquo;: in the {fig(W + '.days')} days to {fig(W + '.to')}, <b>{fig(W + '.pumps_called')}</b> managed pumps were reported down or partially working, by their first such call. <b>{fig(W + '.repaired_7d')}</b> had a repair record within {fig('CALLF.followup_days')} days, <b>{fig(W + '.no_repair_7d')}</b> had none after {fig('CALLF.followup_days')} days, and {fig(W + '.not_yet_due')} calls are not yet {fig('CALLF.followup_days')} days old. Preventive visits submitted in the same window: {fig(W + '.pm_records')} on {fig(W + '.pumps_visited')} pumps, <b>{fig(W + '.overlap_n')}</b> of them pumps that were also called about. <span class="muted">Last {fig(WK + '.days')} days: {fig(WK + '.pumps_called')} pumps called, {fig(WK + '.pm_records')} preventive visits, {fig(WK + '.overlap_n')} in both.</span></p>
  <div class="tablewrap"><table data-table="callfollow" class="ind"><thead><tr><th>Pump</th><th>District</th><th>Call</th><th>Reported</th><th>Next record in mWater</th><th>Next repair</th><th>Repaired in time</th></tr></thead><tbody>
{body}
</tbody></table></div>
{table_notes.render("callfollow")}
</div>
"""


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    want = block(json.load(open(DATA, encoding="utf8")))
    idx = open(PAGE, encoding="utf8").read()
    if BEGIN not in idx or END not in idx:
        sys.exit("index.html has no call-followup markers")
    a, z = idx.index(BEGIN) + len(BEGIN), idx.index(END)
    if mode == "--write":
        open(PAGE, "w", encoding="utf8").write(idx[:a] + want + idx[z:])
        print("index.html: call-followup " + ("unchanged" if _same(idx[a:z], want) else "rewritten"))
        return 0
    if _same(idx[a:z], want):
        print("index.html call-followup matches its generator")
        return 0
    print("\n".join(list(difflib.unified_diff(idx[a:z].splitlines(), want.splitlines(), "index.html",
                                              "render_call_followup.py", lineterm="", n=0))[:20]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
