# -*- coding: utf-8 -*-
"""Keep the portfolio map page in step with the report.

portfolio.html was built once by hand: a 736-point marker list and a dozen
figures typed into its text - points and people per site, the carbon
subtotal, the people-served total, the "736 today" phasing box, the layer
labels. Nothing rewrote any of it. When 742894057 joined the portfolio on 23
September the report moved to 737 and the map stayed at 736, and the
map-versus-report checks failed the build. This rewrites them from the
report's own data - PUMPS for the points, WPOP for the people served - on
every build.

Each figure is found by an anchored pattern that must match exactly once, so
a wording change in portfolio.html fails loudly here rather than leaving a
number behind.

The marker list (WP) keeps every existing entry for a pump still in the
portfolio, drops pumps that left, and adds pumps that joined. A joining pump
gets no photograph: photographs are chosen by a ranked selection that is not
part of the build, so it is drawn without one rather than with a guess.

    python3 tools/render_portfolio.py --write
    python3 tools/render_portfolio.py --check
"""
import csv, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(REPO, "index.html")
PORT = os.path.join(REPO, "portfolio.html")
TARGET = 4000                      # the target programme scale the page states
REGION = {"Maroantsetra": "maro", "Fort-Dauphin": "anosy", "Marolinta": "androy"}


def const(src, name, sep=r"\s*=\s*"):
    m = re.search(r"\bconst %s%s" % (name, sep), src)
    i = m.end()
    close = "};" if src[i] == "{" else "];"
    j = src.index(close, i) + 1
    return i, j, json.loads(src[i:j])


def fmt(n):
    return f"{n:,}"


def build():
    idx = open(INDEX, encoding="utf8").read()
    pumps = const(idx, "PUMPS")[2]
    wpop = const(idx, "WPOP")[2]
    pts = {s: [p for p in pumps if p["site"] == s] for s in REGION}
    ppl = {s: sum((wpop.get(p["wp"]) or [0, 0])[1] for p in v) for s, v in pts.items()}
    n = {s: len(v) for s, v in pts.items()}
    carbon_n = n["Maroantsetra"] + n["Fort-Dauphin"]
    carbon_p = ppl["Maroantsetra"] + ppl["Fort-Dauphin"]
    total_n, total_p = len(pumps), sum(ppl.values())

    src = open(PORT, encoding="utf8").read()
    subs = [
        (r'(<tr><td>Maroantsetra</td><td class="num">)[\d,]+(</td><td class="num">)[\d,]+',
         rf'\g<1>{fmt(n["Maroantsetra"])}\g<2>{fmt(ppl["Maroantsetra"])}'),
        (r'(<tr><td>Anosy \(Fort-Dauphin\)</td><td class="num">)[\d,]+(</td><td class="num">)[\d,]+',
         rf'\g<1>{fmt(n["Fort-Dauphin"])}\g<2>{fmt(ppl["Fort-Dauphin"])}'),
        (r'(<tr class="tot"><td>Carbon portfolio</td><td class="num">)[\d,]+(</td><td class="num">)[\d,]+',
         rf'\g<1>{fmt(carbon_n)}\g<2>{fmt(carbon_p)}'),
        (r'(<tr><td>Androy \(Marolinta\), separately funded</td><td class="num">)[\d,]+(</td><td class="num">)[\d,]+',
         rf'\g<1>{fmt(n["Marolinta"])}\g<2>{fmt(ppl["Marolinta"])}'),
        (r'<b>[\d,]+ today</b>', f'<b>{fmt(total_n)} today</b>'),
        (r'(<div class="bar"><i style="width:)[\d.]+(%"></i></div>\s*<span>)[\d.]+(% of target programme scale)',
         rf'\g<1>{100 * total_n / TARGET:.1f}\g<2>{100 * total_n / TARGET:.1f}\g<3>'),
        (r'(This map draws the <b>)[\d,]+(</b> hand pumps)', rf'\g<1>{fmt(total_n)}\g<2>'),
        (r'(<b>Basis\.</b> The <b>)[\d,]+(</b> hand pumps)', rf'\g<1>{fmt(total_n)}\g<2>'),
        (r'(<b>)[\d,]+( is the conservative figure and the one in the carbon file\.</b> <b>)[\d,]+'
         r'(</b> of it is the carbon portfolio; the remaining <b>)[\d,]+(</b>)',
         rf'\g<1>{fmt(total_p)}\g<2>{fmt(carbon_p)}\g<3>{fmt(ppl["Marolinta"])}\g<4>'),
        (r'(Maroantsetra &mdash; )[\d,]+( pumps)', rf'\g<1>{n["Maroantsetra"]}\g<2>'),
        (r'(Anosy \(Fort-Dauphin\) &mdash; )[\d,]+( pumps)', rf'\g<1>{n["Fort-Dauphin"]}\g<2>'),
        (r'(Androy \(Marolinta\) &mdash; )[\d,]+( pumps)', rf'\g<1>{n["Marolinta"]}\g<2>'),
    ]
    for pat, rep in subs:
        src, k = re.subn(pat, rep, src)
        if k != 1:
            sys.exit(f"render_portfolio: pattern matched {k} times, expected once: {pat[:70]}")

    # the marker list
    i, j, wp = const(src, "WP", r" = ")
    fleet = {p["wp"]: p for p in pumps}
    keep = [w for w in wp if w["c"] in fleet]
    have = {w["c"] for w in keep}
    reg = {}
    rp = os.path.expanduser("~/mwater-exports/wp_madavance.csv")
    if os.path.isfile(rp):
        reg = {r["code"]: r for r in csv.DictReader(open(rp, encoding="utf8"))}
    for code in sorted(set(fleet) - have):
        p, r = fleet[code], reg.get(code, {})
        village = " / ".join(x for x in (r.get("admin_div5"), r.get("admin_div3"),
                                         r.get("admin_div2")) if x) or p.get("commune") or ""
        keep.append({"c": code, "y": p["lat"], "x": p["lon"], "t": p["pump"], "v": village,
                     "r": REGION[p["site"]], "m": 1,
                     "cb": 0 if p["site"] == "Marolinta" else 1})
    src = src[:i] + json.dumps(keep, ensure_ascii=False, separators=(",", ":")) + src[j:]
    return src


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    new = build()
    old = open(PORT, encoding="utf8").read()
    if mode == "--write":
        open(PORT, "w", encoding="utf8").write(new)
        print("portfolio.html " + ("unchanged" if new == old else "rewritten from the report's data"))
        return 0
    print("portfolio.html " + ("matches the report" if new == old else "DIFFERS from the report"))
    return 0 if new == old else 1


if __name__ == "__main__":
    sys.exit(main())
