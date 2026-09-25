# -*- coding: utf-8 -*-
"""Write every figure's value into the static HTML, and fail if one is empty.

WHY THIS EXISTS
---------------
Every live figure in the prose is <span data-fig="S.n"></span>: an expression
the page evaluates in the browser. Until 25 September 2026 the span was EMPTY
in the HTML itself, so a reader without JavaScript - a text extractor, a
search index, a mail client previewing the page, a verifier saving it as text -
read "Outlets within  km of one another" and "  managed hand pumps". All 227
data-fig spans and all 12 data-param spans on the published page were empty.

This step loads the page in the headless browser the render check already
uses, evaluates each expression exactly as fillFigures() does, and writes the
value into the span. JavaScript still overwrites it with the live value on
load, so the two can only differ if the HTML is stale - which --check fails.

The generators write their regions with empty spans. They compare through
unfilled(), so a region that differs only in prerendered values is not drift;
a region they rewrite comes back empty and is refilled here before any gate.

    python3 tools/prerender_figures.py --write   # browser: fill every span
    python3 tools/prerender_figures.py --check   # browser: every value current
    python3 tools/prerender_figures.py --gate    # no browser: none empty
"""
import html, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
TMP = os.path.join(REPO, ".prerender.html")

# Script and style blocks are not HTML a reader sees, and a JavaScript template
# such as figSpan's `<span data-fig=...>${v}</span>` must never be touched.
_OPAQUE = re.compile(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", re.S)
# An attribute value may itself contain ">" - "p=>p.site" - so the tag is
# matched attribute by attribute rather than with [^>]*.
_ATTRS = r'(?:[^>"]|"[^"]*")*'
FIGURE = re.compile(r'(<(\w+)\b(' + _ATTRS + r'\bdata-(fig|param)="([^"]*)"' + _ATTRS + r')>)'
                    r'([^<]*)(</\2>)')


def _segments(src):
    """(is_html, text) pieces of the page, in order."""
    pos = 0
    for m in _OPAQUE.finditer(src):
        yield True, src[pos:m.start()]
        yield False, m.group(0)
        pos = m.end()
    yield True, src[pos:]


def _sub(src, fn):
    return "".join(FIGURE.sub(fn, t) if ok else t for ok, t in _segments(src))


def figures(src):
    """[(kind, key, static text)] for every figure element a non-JS reader gets."""
    out = []
    for ok, t in _segments(src):
        if ok:
            out += [(m.group(4), html.unescape(m.group(5)), html.unescape(m.group(6)))
                    for m in FIGURE.finditer(t)]
    return out


def unfilled(src):
    """The page with every figure element's prerendered value removed."""
    return _sub(src, lambda m: m.group(1) + m.group(7))


def same(a, b):
    """Two generated regions are the same if they differ only in prerendered values."""
    return unfilled(a).strip() == unfilled(b).strip()


EVAL = r"""([figs, params]) => {
  const out = {fig: {}, param: {}};
  for (const e of figs) {                 // exactly what fillFigures() does
    let v;
    try { v = (new Function('return (' + e + ')'))(); } catch (x) { v = undefined; }
    out.fig[e] = (v === undefined || v === null || (typeof v === 'number' && !isFinite(v)))
      ? null : (typeof v === 'number' ? fmt(v) : String(v));
  }
  for (const k of params) {
    const P = PARAMS[k];
    out.param[k] = P ? (typeof P.v === 'number' ? fmt(P.v) : String(P.v)) : null;
  }
  return out;
}"""


def evaluate(src):
    """Every static expression's value, from the page's own data, in a browser."""
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import render_check as R
    from playwright.sync_api import sync_playwright
    exe = R.chromium_path()
    if not exe:
        sys.exit("prerender_figures: no chromium in the Playwright cache")
    figs = figures(src)
    fx = sorted({k for kind, k, _t in figs if kind == "fig"})
    px = sorted({k for kind, k, _t in figs if kind == "param"})
    # evaluated on the page with its values removed, so nothing stale feeds it
    open(TMP, "w", encoding="utf8").write(unfilled(src))
    errors = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=exe)
            pg = b.new_page(viewport={"width": 1280, "height": 900})
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto("file://" + TMP, wait_until="load", timeout=90000)
            pg.wait_for_timeout(1200)
            got = pg.evaluate(EVAL, [fx, px])
            b.close()
    finally:
        if os.path.exists(TMP):
            os.remove(TMP)
    if errors:
        sys.exit("prerender_figures: the page raised a script error: " + errors[0][:200])
    return got


def gate(src):
    """No browser needed: every figure element carries a value in the HTML."""
    figs = figures(src)
    empty = [(kind, k) for kind, k, t in figs if not t.strip()]
    print(f"figure elements in the static HTML: {len(figs)} "
          f"({sum(1 for f in figs if f[0] == 'fig')} data-fig, "
          f"{sum(1 for f in figs if f[0] == 'param')} data-param); "
          f"empty without JavaScript: {len(empty)}")
    for kind, k in empty[:10]:
        print(f"  EMPTY data-{kind}: {k[:100]}")
    return 0 if not empty else 1


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--gate"
    src = open(PAGE, encoding="utf8").read()
    if mode == "--gate":
        return gate(src)
    got = evaluate(src)
    bad = [f"data-{k}: {x[:90]}" for k in ("fig", "param") for x, v in got[k].items() if v is None]
    if bad:
        print("these figures cannot be computed, so they would render as '?':")
        for b_ in bad[:10]:
            print("  " + b_)
        return 1
    if mode == "--write":
        new = _sub(src, lambda m: m.group(1) + html.escape(got[m.group(4)][html.unescape(m.group(5))],
                                                             quote=False) + m.group(7))
        n = len(figures(new))
        if new != src:
            open(PAGE, "w", encoding="utf8").write(new)
        print(f"prerendered {n} figure element(s) into the static HTML"
              + ("" if new != src else " (already current)"))
        return gate(new)
    # --check: every static value is the value the page computes now
    stale = [(kind, k, t, got[kind][k]) for kind, k, t in figures(src)
             if t != got[kind][k]]
    print(f"static values checked against the page's own computation: "
          f"{len(figures(src))}; stale or empty: {len(stale)}")
    for kind, k, t, v in stale[:10]:
        print(f"  data-{kind} {k[:70]}: static {t!r}, computed {v!r}")
    return 0 if not stale else 1


if __name__ == "__main__":
    sys.exit(main())
