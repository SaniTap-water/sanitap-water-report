#!/usr/bin/env python3
"""The SDWS 18 record table: every record of the 2025 household round.

One row per final response on the two deployments, from data/sdws18.json
(tools/rebuild_sdws18.py), each linked to its response in mWater, so every
figure in the section can be recounted from the records a verifier opens. The
three samples with any E. coli and the two households recorded far from their
pump are marked in the table. No coordinates and no respondent names.

check_consistency holds the table to the section: its row count equals the
tests tile (SDWS18.total.tests) and every row links to an mWater response.

    python3 tools/render_sdws18.py --write | --check
"""
import html, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from prerender_figures import same as _same  # noqa: E402

REPO = os.path.dirname(HERE)
PAGE = os.path.join(REPO, "index.html")
DATA = os.path.join(REPO, "data", "sdws18.json")
MWR = "https://portal.mwater.co/#/responses/"
BEGIN = ("<!-- BEGIN GENERATED sdws18-records :: tools/render_sdws18.py :: "
         "do not edit between these markers -->")
END = "<!-- END GENERATED sdws18-records -->"


def row(r, lt):
    e = r["ecoli"]
    flags = []
    if r["positive"]:
        flags.append('<span class="pill warn">E. coli found</span>')
    if r["gps_flag"]:
        flags.append('<span class="pill warn">GPS: <span data-fig="SDWS18.records.find(r=>r.rid===\''
                     + r["rid"] + '\').km">' + f'{r["km"]:g}' + '</span>&nbsp;km from pump</span>')
    res = ('<span class="pill ok">pass</span>' if r["pass"]
           else '<span class="pill crit">fail</span>')
    cls = ' class="flagged"' if flags else ""
    return (f'<tr{cls} data-rid="{r["rid"]}"><td>{html.escape(r["district"])}</td>'
            f'<td class="mono">{html.escape(r["water_point"] or "—")}</td>'
            f'<td class="mono">{html.escape(r["household"] or "—")}</td>'
            f'<td class="num">{html.escape(r["date"] or "—")}</td>'
            f'<td class="num">{"—" if e is None else e}</td>'
            f'<td>{res}{" " + " ".join(flags) if flags else ""}</td>'
            f'<td>{html.escape(r["comment"] or "")}</td>'
            f'<td><a href="{MWR}{r["rid"]}" target="_blank" rel="noopener" '
            f'title="Open this household water-quality record in mWater">{html.escape(r["code"] or "record")}</a></td></tr>')


def block():
    d = json.load(open(DATA, encoding="utf8"))
    lt = d["pass_rule"]["pou_lt_per_100ml"]
    head = ('<thead><tr><th>District</th><th>Water point</th><th>Household</th>'
            '<th class="num">Sampled</th><th class="num"><i>E. coli</i> per 100 ml</th>'
            '<th>Result (pass &lt; <span data-fig="SDWS18.pass_rule.pou_lt_per_100ml"></span>)</th>'
            '<th>Enumerator comment</th><th>mWater record</th></tr></thead>')
    body = "\n".join(row(r, lt) for r in d["records"])
    return ('\n<div class="tablewrap" style="margin-top:12px"><table data-table="sdws18rec" id="sdws18rec">'
            + head + "<tbody>\n" + body + "\n</tbody></table></div>\n")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    want = block()
    src = open(PAGE, encoding="utf8").read()
    if BEGIN not in src or END not in src:
        sys.exit("index.html has no sdws18-records markers")
    a, z = src.index(BEGIN) + len(BEGIN), src.index(END)
    if mode == "--write":
        open(PAGE, "w", encoding="utf8").write(src[:a] + want + src[z:])
        print("index.html: sdws18-records " + ("unchanged" if _same(src[a:z], want) else "rewritten"))
        return 0
    if _same(src[a:z], want):
        print("index.html sdws18-records matches its generator")
        return 0
    print("index.html sdws18-records DIFFERS from its generator")
    return 1


if __name__ == "__main__":
    sys.exit(main())
