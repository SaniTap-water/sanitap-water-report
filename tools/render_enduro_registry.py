# -*- coding: utf-8 -*-
"""The Endur'O "Registered in mWater" block and the samples-under-each-tap
table (3 Oct 2026).

Renders data/enduro_registry.json (ENDUROREG on the page), written by
tools/rebuild_enduro_registry.py, into two generated regions:

  enduro-registry  in the Endur'O partner card: the registered water systems
                   and water points per scheme (type, GPS, photo), the
                   hand-entered headline beside them with the difference, and
                   the SMARTAP check on the Amboasary gara smart taps;
  piped-wq-taps    in the piped water-quality panel: each registered tap that
                   Cathy sampled, by tap code or within the matching distance,
                   with its samples and its system's results, and the sampling
                   points that match no registered tap.

Coordinates are not printed here; the map draws the taps (portfolio.html).

    python3 tools/render_enduro_registry.py --write
    python3 tools/render_enduro_registry.py --check
"""
import difflib, html, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prerender_figures import same as _same  # noqa: E402
import table_notes  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
DATA = os.path.join(REPO, "data", "enduro_registry.json")
# the portal has no route to an individual water point (tools/check_links.py),
# so codes are shown, not linked
R = "ENDUROREG"


def marks(name):
    return (f"<!-- BEGIN GENERATED {name} :: tools/render_enduro_registry.py "
            f":: do not edit between these markers -->", f"<!-- END GENERATED {name} -->")


def fig(e):
    return f'<span data-fig="{e}"></span>'


def esc(s):
    return html.escape(s or "", quote=False)


def yn(b):
    return "yes" if b else '<span class="muted">no</span>'


def types_text(d):
    return ", ".join(f"{esc(k)}&nbsp;&times;&nbsp;{v}" for k, v in d.items()) or "&mdash;"


def registry(d):
    rows = []
    for i, s in enumerate(d["schemes"]):
        b = f"{R}.schemes[{i}]"
        rows.append(
            f'<tr><td>{esc(s["name"]) or "<span class=muted>no name</span>"}'
            + (' <span class="muted">(decommissioned)</span>' if s["status"] == "decommissioned" else "")
            + f'</td><td><span class="mono">{esc(s["code"])}</span></td>'
            f'<td>{esc(s["type"]) or "&mdash;"}</td><td>{yn(s["gps"])}</td><td>{yn(s["photo"])}</td>'
            f'<td class="num">{fig(b + ".points")}</td><td>{types_text(s["point_types"])}</td>'
            f'<td class="num">{fig(b + ".points_gps")}</td><td class="num">{fig(b + ".points_photo")}</td></tr>')
    ns = d["no_system"]
    rows.append(
        f'<tr><td><i>No water system set</i></td><td>&mdash;</td><td>&mdash;</td><td>&mdash;</td><td>&mdash;</td>'
        f'<td class="num">{fig(R + ".no_system.points")}</td><td>{types_text(ns["point_types"])}</td>'
        f'<td class="num">{fig(R + ".no_system.points_gps")}</td><td class="num">{fig(R + ".no_system.points_photo")}</td></tr>')
    rows.append(
        f'<tr class="tot"><td><b>All registered</b></td><td></td><td></td>'
        f'<td class="num">{fig(R + ".counts.systems_gps")}</td><td class="num">{fig(R + ".counts.systems_photo")}</td>'
        f'<td class="num"><b>{fig(R + ".counts.points")}</b></td><td>{types_text(d["counts"]["point_types"])}</td>'
        f'<td class="num">{fig(R + ".counts.points_gps")}</td><td class="num">{fig(R + ".counts.points_photo")}</td></tr>')
    smart = []
    for i, r in enumerate(d["smartap"]["rows"]):
        smart.append(
            f'<tr><td>{esc(r["name"])}</td><td><span class="mono">{esc(r["code"])}</span></td><td>{esc(r["type"]) or "&mdash;"}</td>'
            f'<td>{"<span class=mono>" + esc(r["system"]) + "</span>" if r["system"] else "<span class=muted>none set</span>"}</td>'
            f'<td>{"<span class=mono>" + esc(r["device"]) + "</span>" if r["device"] else "<span class=muted>not in the description</span>"}</td>'
            f'<td>{yn(r["gps"])}</td><td>{yn(r["photo"])}</td></tr>')
    sm = d["smartap"]
    smart_body = "\n".join(smart) or '<tr><td colspan="7" class="muted">No SMARTAP record is readable in the Endur&rsquo;O group.</td></tr>'
    C = R + ".compare"
    return f"""
<div class="panel" id="enduro-registered" style="margin-top:12px" data-scopes="all enduro">
  <div class="eyebrow">Registered in mWater &mdash; Endur&rsquo;O&rsquo;s own records, live</div>
  <p style="margin:8px 0 0"><b>The headline stays hand-entered until it is reconciled.</b> The Endur&rsquo;O figures in the tiles &mdash; {fig('ENDURO.systems')} piped systems under management and {fig('ENDURO.people')} people &mdash; are hand-entered from <span class="mono">data/enduro_manual.json</span>. What follows is read live from Endur&rsquo;O&rsquo;s mWater group (<span class="mono">{esc(d["group"]["name"])}</span>) at every build and does not replace them.</p>
  <p class="note" style="margin:10px 0 0"><b>Registered today: {fig(R + '.counts.systems')} water systems and {fig(R + '.counts.points')} water points.</b> {fig(R + '.counts.points_gps')} of the points carry GPS and {fig(R + '.counts.points_photo')} a photograph; {fig(R + '.counts.points_no_system')} have no water system set. <span class="muted">Pulled {fig(R + '.pulled')}.</span></p>
  <div class="tablewrap"><table data-table="enduro-reg-compare" class="ind"><thead><tr><th>Count</th><th class="num">Hand-entered</th><th class="num">Registered in mWater</th><th class="num">Difference</th><th>Hand-entered source</th></tr></thead><tbody>
<tr><td>Piped systems under management (headline) against registered water systems</td><td class="num">{fig(C + '.systems_manual')}</td><td class="num">{fig(C + '.systems_registered')}</td><td class="num">{fig(C + '.systems_diff')}</td><td>reconciled site list, as at {fig(C + '.headline_as_at')}</td></tr>
<tr><td>Water systems in the register snapshot</td><td class="num">{fig(C + '.regsys_manual')}</td><td class="num">{fig(C + '.systems_registered')}</td><td class="num">{fig(C + '.regsys_diff')}</td><td>register snapshot, as at {fig(C + '.manual_as_at')}</td></tr>
<tr><td>Water points in the register snapshot</td><td class="num">{fig(C + '.points_manual')}</td><td class="num">{fig(C + '.points_registered')}</td><td class="num">{fig(C + '.points_diff')}</td><td>register snapshot, as at {fig(C + '.manual_as_at')}</td></tr>
</tbody></table></div>
{table_notes.render("enduro-reg-compare")}
  <details class="expl" id="enduro-reg-schemes" style="margin-top:10px"><summary>Water systems and water points per scheme ({fig(R + '.counts.systems')} systems)</summary>
  <div class="tablewrap"><table data-table="enduro-reg-schemes" class="ind"><thead><tr><th>Scheme</th><th>Code</th><th>Type</th><th>GPS</th><th>Photo</th><th class="num">Water points</th><th>Point types</th><th class="num">With GPS</th><th class="num">With photo</th></tr></thead><tbody>
{chr(10).join(rows)}
</tbody></table></div>
{table_notes.render("enduro-reg-schemes")}
  </details>
  <details class="expl" id="enduro-smartap" style="margin-top:10px"><summary>The Amboasary gara smart taps: {fig(R + '.smartap.found')} registered, {fig(R + '.smartap.linked')} linked to the system</summary>
  <p class="note" style="margin-top:0">Each smart tap is registered as a water point, named SMARTAP and a number, linked to the water system <span class="mono">1108783583</span> ({esc(sm["system_name"]) or "Amboasary gara"}), with the meter&rsquo;s deviceID in its description. {fig(R + '.smartap.kiosk')} are typed kiosk, {fig(R + '.smartap.with_device')} carry a deviceID, {fig(R + '.smartap.with_photo')} have a photograph.</p>
  <div class="tablewrap"><table data-table="enduro-smartap" class="ind"><thead><tr><th>Name</th><th>Code</th><th>Type</th><th>Water system</th><th>deviceID</th><th>GPS</th><th>Photo</th></tr></thead><tbody>
{smart_body}
</tbody></table></div>
{table_notes.render("enduro-smartap")}
  </details>
</div>
"""


def taps(d):
    rows = []
    for i, t in enumerate(d["tap_samples"]):
        b = f"{R}.tap_samples[{i}]"
        sr = d["results_by_system"].get(t["system"] or "")
        rows.append(
            f'<tr><td><span class="mono">{esc(t["code"])}</span></td>'
            f'<td>{esc(t["name"]) or "&mdash;"}</td><td>{"<span class=mono>" + esc(t["system"]) + "</span>" if t["system"] else "&mdash;"}</td>'
            f'<td class="num">{fig(b + ".samples")}</td><td>{fig(b + ".first")}</td><td>{fig(b + ".last")}</td>'
            f'<td>{esc(", ".join(t["points"])) or "&mdash;"}</td><td>{esc(t["method"])}</td>'
            + (f'<td class="num">{fig(R + ".results_by_system['" + t["system"] + "'].tests")}</td>' if sr
               else '<td class="num">&mdash;</td>') + '</tr>')
    body = "\n".join(rows) or '<tr><td colspan="9" class="muted">No sampling point matches a registered tap.</td></tr>'
    un = []
    for i, sp in enumerate(d["sampling"]["points"]):
        if sp["tap"]:
            continue
        b = f"{R}.sampling.points[{i}]"
        un.append(
            f'<tr><td>{esc(sp["id"])}</td><td class="num">{fig(b + ".samples")}</td><td>{fig(b + ".first")}</td>'
            f'<td>{fig(b + ".last")}</td><td>{esc(", ".join(sp["types"])) or "&mdash;"}</td>'
            f'<td>{"<span class=mono>" + esc(sp["nearest_tap"]) + "</span> " + esc(sp["nearest_name"] or "") if sp["nearest_tap"] else "&mdash;"}</td>'
            f'<td class="num">{fig(b + ".nearest_m") if sp["nearest_m"] is not None else "&mdash;"}</td></tr>')
    unbody = "\n".join(un) or '<tr><td colspan="7" class="muted">Every sampling point matches a registered tap.</td></tr>'
    S = R + ".sampling"
    return f"""
<details class="expl" id="piped-wq-taps" style="margin-top:10px" data-scopes="all enduro"><summary>Samples under each registered tap: {fig(S + '.matched')} of {fig(S + '.points.length')} sampling points on a registered tap</summary>
<p class="note" style="margin-top:0"><b>The match.</b> A sample whose tap code or deviceID names a registered Endur&rsquo;O water point goes to that tap ({fig(S + '.by_code')} so far). The others are grouped into sampling points &mdash; samples within {fig(S + '.cluster_m')}&nbsp;m of one another &mdash; and each point goes to the nearest registered tap within {fig(S + '.match_m')}&nbsp;m. Several points landing on one tap are shown once, under that tap. <span class="muted">{fig(S + '.samples')} final samples, {fig(S + '.with_gps')} with GPS.</span></p>
<p class="note"><b>Results are per system, not per tap.</b> Until the result form&rsquo;s tap question (1.2b) is filled, a result names only its water system, so each tap shows its own samples beside its system&rsquo;s results, never results of its own.</p>
<div class="tablewrap"><table data-table="piped-wq-taps" class="ind"><thead><tr><th>Tap</th><th>Name</th><th>Water system</th><th class="num">Samples</th><th>First</th><th>Last</th><th>Sampling points</th><th>Matched by</th><th class="num">System results</th></tr></thead><tbody>
{body}
</tbody></table></div>
{table_notes.render("piped-wq-taps")}
<p class="note"><b>Sampling points with no registered tap within {fig(S + '.match_m')}&nbsp;m: {fig(S + '.unmatched.length')}.</b> They stay on the map as sampling points.</p>
<div class="tablewrap"><table data-table="piped-wq-unmatched" class="ind"><thead><tr><th>Sampling point</th><th class="num">Samples</th><th>First</th><th>Last</th><th>Recorded type</th><th>Nearest registered tap</th><th class="num">Distance (m)</th></tr></thead><tbody>
{unbody}
</tbody></table></div>
{table_notes.render("piped-wq-unmatched")}
</details>
"""


REGIONS = {"enduro-registry": registry, "piped-wq-taps": taps}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    d = json.load(open(DATA, encoding="utf8"))
    idx = open(PAGE, encoding="utf8").read()
    bad = 0
    for name, fn in REGIONS.items():
        b, e = marks(name)
        if b not in idx or e not in idx:
            sys.exit(f"index.html has no {name} markers")
        a, z = idx.index(b) + len(b), idx.index(e)
        want = fn(d)
        if mode == "--write":
            print(f"index.html: {name} " + ("unchanged" if _same(idx[a:z], want) else "rewritten"))
            idx = idx[:a] + want + idx[z:]
        elif not _same(idx[a:z], want):
            bad = 1
            print("\n".join(list(difflib.unified_diff(idx[a:z].splitlines(), want.splitlines(),
                                                      "index.html", name, lineterm="", n=0))[:20]))
    if mode == "--write":
        open(PAGE, "w", encoding="utf8").write(idx)
        return 0
    if not bad:
        print("index.html enduro-registry and piped-wq-taps match their generator")
    return bad


if __name__ == "__main__":
    sys.exit(main())
