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
    u = ids.get(code)
    if not u:
        return f'<span class="mono">{code}</span>'
    return (f'<a class="wp" href="https://portal.mwater.co/#/water_point/{u}" '
            f'target="_blank" rel="noopener" title="open {code} in mWater">'
            f'<span class="mono">{code}</span></a>')


def table():
    idx = open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    m = re.search(r"\bconst REG\s*=\s*", idx)
    reg = json.loads(idx[m.end():idx.index("};", m.end()) + 1])
    adm = json.load(open(os.path.join(REPO, "data", "marolinta_admin.json")))
    by = {r["code"]: r for r in adm["records"]}
    ids_p = os.path.join(REPO, "data", "mwater_point_ids.json")
    ids = json.load(open(ids_p)) if os.path.isfile(ids_p) else {}
    out = ['<div class="tablewrap"><table class="ind"><thead><tr>'
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
