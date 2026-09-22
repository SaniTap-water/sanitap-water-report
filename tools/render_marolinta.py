# -*- coding: utf-8 -*-
"""Render the Marolinta works table, with district and commune filled in.

The table used to be built in the browser from REG.marolinta and showed a red
"no district" pill on 11 of 13 rows. Those rows are survey and prospection
entries: they carry no admin_div names, but they do carry admin_region, and
every located point sharing that region resolves to one place. So the district
and the commune are recoverable from the register and are shown; the fokontany
is not, and where it is missing the row says why in one line instead of
showing an empty pill.

    python3 tools/render_marolinta.py --write | --check
"""
import difflib, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEGIN = ("<!-- BEGIN GENERATED marolinta-table :: tools/render_marolinta.py "
         ":: do not edit between these markers -->")
END = "<!-- END GENERATED marolinta-table -->"


def wp_link(code, ids):
    """Link a water point to a RECORD that references it.

    The portal has no route to an individual entity: #/water_point/<uuid> and
    every variant of it land on "Page not found", and the app's own route
    table has no entity route at all. A response does resolve, and is the
    better target anyway - it opens the document that says something about the
    point. data/mwater_point_responses.json maps codes to response ids.
    """
    import json as _json
    p = os.path.join(REPO, "data", "mwater_point_responses.json")
    m = _json.load(open(p, encoding="utf8")) if os.path.isfile(p) else {}
    d = m.get(code) or {}
    for kind, what in (("works", "first-rehabilitation record"),
                       ("borehole", "borehole-progress record"),
                       ("repair", "repair record"),
                       ("pm", "maintenance visit"),
                       ("call", "call-centre record")):
        rid = d.get(kind)
        if rid:
            return (f'<a class="wp" href="https://portal.mwater.co/#/responses/'
                    f'{rid}" target="_blank" rel="noopener" title="Open the '
                    f'{what} for water point {code} in mWater">'
                    f'<span class="mono">{code}</span></a>')
    return f'<span class="mono">{code}</span>'


def _ids():
    p = os.path.join(REPO, "data", "mwater_point_ids.json")
    return json.load(open(p)) if os.path.isfile(p) else {}


def headline():
    """What the Marolinta works actually are, before the record detail.

    The scope button is now on the same basis as this section - the work -
    so this text no longer contrasts the two counts. It states the register
    relationship, which is the thing worth knowing: the register holds five
    Marolinta points and shares exactly one of them with the work.
    """
    w = json.load(open(os.path.join(REPO, "data", "marolinta_works.json")))
    m, mo = w["marolinta"], w["moramanga"]
    reh = m["by_type_final"].get("Réhabilitation", 0)
    new = m["by_type_final"].get("Nouvelle construction", 0)
    sh = m["shortfall"]
    ben = json.load(open(os.path.join(REPO, "data", "marolinta_benef.json")))
    return (
      '<div class="actstats" style="margin-bottom:14px">\n'
      f'  <div class="stat"><b>{m["points_final"]}</b><span>water points touched by '
      'the borehole-progress form, <b>all records final</b> &mdash; no drafts'
      '</span></div>\n'
      f'  <div class="stat"><b>{new} + {reh}</b><span>new constructions and '
      'rehabilitations recorded</span></div>\n'
      f'  <div class="stat"><b>{sh["Nouvelle construction"] + sh["Réhabilitation"]}</b>'
      '<span>works reported to date with <b>no record at all</b> &mdash; '
      f'{sh["Nouvelle construction"]} new, {sh["Réhabilitation"]} rehabilitations'
      '</span></div>\n'
      f'  <div class="stat"><b>{ben["total"]:,}</b><span><b>people served &mdash; a '
      'field count.</b> Recorded by the team on each record. <b>Not a WorldPop '
      'allocation</b>, and not comparable with the WorldPop figures elsewhere on '
      'this page</span></div>\n'
      '</div>\n'
      '<p class="note"><b>These count the work, not the register.</b> The '
      'maintained register holds <b>5</b> Marolinta points &mdash; the five '
      'boreholes that appear in the 736 reconciliation as <i>actively managed but '
      'never first-rehabilitated</i> &mdash; and <b>only one of those five</b> '
      f'appears on this form at all. The work is <b>{m["points_final"]}</b> points, '
      'and the Marolinta scope button reports it on that basis.</p>\n'
      '<p class="note"><b>Against what Jan reported: 10 new boreholes and 10 '
      f'rehabilitations to date.</b> The form holds <b>{new}</b> new constructions and '
      f'<b>{reh}</b> rehabilitations, all final. So <b>{sh["Nouvelle construction"]} new '
      f'boreholes and {sh["Réhabilitation"]} rehabilitations have no record at all</b> '
      '&mdash; not a draft, not an incomplete form, nothing. '
      '<span class="muted">An earlier note here assumed all 18 responses on this form '
      'were Marolinta. They are not: the form is deployed twice, and Marolinta has no '
      'drafts at all.</span></p>\n'
      '<p class="note"><b>The other deployment is Moramanga, and it is a different '
      f'picture.</b> It carries <b>{mo["responses"]}</b> records, every one a '
      '<i>Nouvelle construction</i> and <b>not one a rehabilitation</b>: '
      f'<b>{mo["final"]}</b> final &mdash; ' + wp_link("928155136", _ids()) + ', '
      f'submitted 23 June 2026 &mdash; and <b>{mo["draft"]} still drafts</b>, never '
      'submitted. All five were entered by AMEDE MADAVANCE and all five leave the '
      'functional status blank. <b>A draft is not a delivered borehole:</b> it is '
      'invisible to every count and carries no status. '
      '<span class="muted">These belong to the Moramanga work, owned by Jan and the '
      'Endur&rsquo;O team rather than by Angelo &mdash; '
      '<a href="#act-mor-submit-drafts">submit the four drafts</a>.</span></p>\n'
      '<p class="note"><b>Two different bases, which must not be added or compared.'
      f'</b> The <b>{ben["total"]:,}</b> above is a <b>field count</b>: the sum of the '
      f'beneficiaries the team recorded on each of the <b>{ben["n"]}</b> records, '
      f'{ben["lo"]}&ndash;{ben["hi"]} per point. Every other people-served figure on '
      'this page &mdash; the <b>126,780</b> for MadAvance among them &mdash; is a '
      '<b>WorldPop allocation</b> over 1&nbsp;km service areas, overlaps split, '
      'capacity ceiling applied. <b>The model is deliberately not run over these '
      'points.</b> Marolinta sits outside the carbon programme, the field count is the '
      f'honest number for it, and the {ben["n"]} points lie within about a kilometre of '
      'each other &mdash; so summing per-point service areas without the model&rsquo;s '
      'overlap split would double-count badly. <span class="muted">All '
      f'{ben["n"]} carry a usable coordinate; none was excluded for want of one.</span>'
      '</p>\n'
      '<p class="note"><b>No Marolinta point carries a preventive visit, a repair or a '
      'water-quality result.</b> Not one of the ' + str(m["points_final"]) + ' has any '
      'maintenance or testing record of any kind, so none can enter the carbon file '
      'however the works are recorded. <b>Marolinta is Deichmann-funded and outside the '
      'carbon programme</b>: it appears in no emission-reduction figure on this page, '
      'and the scope button exists to show the work, not to credit it.</p>\n')


def table():
    idx = open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    m = re.search(r"\bconst REG\s*=\s*", idx)
    reg = json.loads(idx[m.end():idx.index("};", m.end()) + 1])
    adm = json.load(open(os.path.join(REPO, "data", "marolinta_admin.json")))
    by = {r["code"]: r for r in adm["records"]}
    ids_p = os.path.join(REPO, "data", "mwater_point_ids.json")
    ids = json.load(open(ids_p)) if os.path.isfile(ids_p) else {}
    out = [headline(), '<div class="tablewrap"><table class="ind"><thead><tr>'
           '<th>Pump</th><th class="num">Date</th><th>Intervention</th>'
           '<th>Status</th><th class="num">Beneficiaries</th>'
           '<th>District / commune</th><th>Fokontany</th></tr></thead><tbody>']
    for r in reg["marolinta"]:
        a = by.get(r["wp"], {})
        if a.get("district"):
            src = a.get("source")
            tag = ('<span class="muted" style="font-size:.82em"> from the '
                   'register&rsquo;s region</span>' if src == "admin_region" else "")
            place = f'{a["district"]} / {a["commune"]}{tag}'
        else:
            place = (f'<span class="muted">{a.get("why_empty", "not recorded")}'
                     '</span>')
        fk = a.get("fokontany")
        if fk:
            fkt = fk
        elif a.get("fokontany_from_description"):
            fkt = (f'{a["fokontany_from_description"]}<span class="muted" '
                   'style="font-size:.82em"> as written in the record '
                   'description, not a register field</span>')
        else:
            fkt = ('<span class="muted">no fokontany on the record and none '
                   'in its description</span>')
        out.append(
            f'<tr><td>{wp_link(r["wp"], ids)}</td>'
            f'<td class="num">{r.get("date") or "&mdash;"}</td>'
            f'<td>{r.get("type") or "&mdash;"}</td>'
            f'<td>{r.get("stat") or "<span class=\'muted\'>not recorded</span>"}</td>'
            f'<td class="num">{r.get("benef") or "&mdash;"}</td>'
            f'<td>{place}</td><td>{fkt}</td></tr>')
    out.append("</tbody></table></div>")
    n_reg = adm["resolved_from_register"]
    n_rgn = adm["resolved_from_region"]
    out.append(
        f'<p class="note" style="margin-top:10px"><b>District and commune are '
        f'recoverable from the register for {n_reg + n_rgn} of the '
        f'{len(reg["marolinta"])} records.</b> {n_reg} carry the administrative '
        'fields directly; ' + str(n_rgn) + ' carry only <span class="mono">'
        'admin_region</span> <span class="mono">418299</span>, and every located '
        'water point sharing that region resolves to <b>Androy / Beloha / '
        'Marolinta</b>, so the district and commune are read from there. '
        f'<b>{adm["still_missing"]} cannot be filled</b> and says so on its row. '
        '<span class="muted">Fokontany is a different matter: it varies between '
        'records and only the two registered points carry it as a field. Where a '
        'technician typed it into the description it is shown as written and '
        'marked as such. Recomputed by <span class="mono">'
        'tools/marolinta_admin.py</span>.</span></p>')
    return "\n".join(out)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    b = table()
    p = os.path.join(REPO, "index.html")
    idx = open(p, encoding="utf8").read()
    if BEGIN not in idx:
        sys.exit("index.html has no marolinta-table markers")
    a = idx.index(BEGIN) + len(BEGIN)
    z = idx.index(END)
    cur, want = idx[a:z], "\n" + b + "\n"
    if mode == "--write":
        open(p, "w", encoding="utf8").write(idx[:a] + want + idx[z:])
        print("index.html: marolinta table %s"
              % ("unchanged" if cur == want else "rewritten"))
        return 0
    if mode == "--check":
        if cur == want:
            print("index.html marolinta table matches its generator")
            return 0
        print("\n".join(list(difflib.unified_diff(
            cur.splitlines(), want.splitlines(), "index.html",
            "render_marolinta.py", lineterm="", n=1))[:20]))
        return 1
    sys.exit("usage: render_marolinta.py --write | --check")


if __name__ == "__main__":
    sys.exit(main())
