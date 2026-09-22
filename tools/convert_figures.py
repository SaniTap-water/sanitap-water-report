# -*- coding: utf-8 -*-
"""Replace typed live figures in the body prose with data-fig spans.

The body prose is static HTML: it cannot interpolate, so 290 live figures were
typed into it. This replaces them, from an explicit per-value specification -
NOT by matching values blindly, because the same number means different things
in different sentences. 723 is REG.succ in eighteen places and the 17 July 2026
maintenance census in two others; interpolating both would make the census
figure move with the register, which is worse than typing it.

So each value carries an expression, and optionally SKIP patterns: an
occurrence whose surrounding text matches a SKIP is left alone and reported,
for a human to place in PARAMS as a cited constant instead.

    python3 tools/convert_figures.py --dry     # what it would change
    python3 tools/convert_figures.py --write
"""
import os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")

# value -> (expression, [skip regexes applied to +-90 chars of context])
# value -> (expression, [skip regexes applied to +-90 chars of context])
#
# Only values whose every occurrence has been READ are here. A value is not
# added because it matches a number in the data: 90 matched thirty times and
# every one was "90/10 sampling" or a p90 percentile; 84 matched seven times
# and every one was a URL fragment or a generated evidence string. Blind
# matching would have written those into the page as live figures.
SPEC = {
    736:  ("S.n", []),
    731:  ("PUMPS.filter(p=>p.site!=='Marolinta').length", []),
    127:  ("S.by_site['Fort-Dauphin']", []),
    604:  ("S.by_site['Maroantsetra']", []),
    452:  ("S.over6", []),
    390:  ("S.sched['overdue']", []),
    606:  ("TTR.ttr_n", []),
    627:  ("WPOPMETA.points_with_a_barrier", []),
    122:  ("WPOPMETA.points_cut_over_10pct", []),
    723:  ("REG.succ", [r"census", r"17 July", r"646 Canzee", r"India Mark III",
                        r"stated"]),
    908:  ("REG.register_total", []),
    773:  ("REG.total_first_rehab", []),
    770:  ("REG.final_records", []),
    751:  ("REG.dashboard", []),
    738:  ("REG.dashboard_fdmar", []),
    732:  ("SUCC_CORRECTED", []),
    867:  ("S.n+ENDURO.systems", []),
    131:  ("ENDURO.systems", [r"withdrawn"]),
    181:  ("ENDURO.reg.points", []),
    135238: ("S.benef_total", []),
    32351522: ("WPOPMETA.raster_national_sum", []),
}

NOT_PROSE = [
    re.compile(r"<script\b[^>]*>.*?</script>", re.S),      # code
    re.compile(r"<style\b[^>]*>.*?</style>", re.S),        # css
    re.compile(r'<span class="mono">[^<]*</span>'),        # identifiers
    re.compile(r"<[a-zA-Z][^>]*>"),                        # every tag: URLs,
                                                           # hrefs, attributes
    re.compile(r"<!--\s*BEGIN GENERATED.*?END GENERATED[^>]*-->", re.S),
]


def regions(html):
    """Byte ranges that are NOT body prose."""
    bad = []
    for rx in NOT_PROSE:
        bad += [(m.start(), m.end()) for m in rx.finditer(html)]
    return sorted(bad)


def protected(pos, bad):
    for a, b in bad:
        if a <= pos < b:
            return True
        if a > pos:
            break
    return False


def convert(write):
    html = open(PAGE, encoding="utf8").read()
    bad = regions(html)
    changed, skipped = [], []
    # longest values first, so 736 is not eaten while matching 36
    for val in sorted(SPEC, key=lambda v: -v):
        expr, skips = SPEC[val]
        pat = re.compile(r"(?<![\d.,>])" + f"{val:,}".replace(",", r"[, ]?")
                         + r"(?![\d.,<])")
        out, last, n = [], 0, 0
        for m in pat.finditer(html):
            if protected(m.start(), bad):
                continue
            ctx = html[max(0, m.start() - 90):m.end() + 90]
            hit = next((s for s in skips if re.search(s, ctx, re.I)), None)
            if hit:
                skipped.append((val, hit, re.sub(r"\s+", " ", ctx)[:110]))
                continue
            out.append(html[last:m.start()])
            out.append(f'<span data-fig="{expr}"></span>')
            last = m.end()
            n += 1
        if n:
            out.append(html[last:])
            html = "".join(out)
            bad = regions(html)
            changed.append((val, expr, n))
    print(f"  {sum(c[2] for c in changed)} literal(s) replaced, "
          f"{len(changed)} distinct value(s)")
    for v, e, n in sorted(changed, key=lambda c: -c[2]):
        print(f"    {v:>9,}  x{n:<3} -> {e}")
    if skipped:
        print(f"\n  {len(skipped)} left alone - the sentence means something "
              "other than the live figure.")
        print("  These belong in PARAMS as cited constants, not in prose:")
        for v, why, ctx in skipped:
            print(f"    {v:>9,}  (matched skip /{why}/)")
            print(f"               {ctx}")
    if write:
        open(PAGE, "w", encoding="utf8").write(html)
        print("\n  index.html written")
    else:
        print("\n  dry run - nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(convert("--write" in sys.argv))
