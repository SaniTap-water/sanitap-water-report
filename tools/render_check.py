# -*- coding: utf-8 -*-
"""Assert what the page actually RENDERS, not what its markup says.

WHY THIS EXISTS
---------------
While wrapping a table in a scroll container, the opening <table id="downtbl">
tag was eaten and a stray ">" left behind. The page still parsed. Every
section balanced. Every markup check passed. The table simply was not on the
page any more, and nothing noticed until somebody read it.

Markup checks cannot see that class of fault, because the markup was still
well-formed - it just described a different page. This loads index.html in
headless Chromium, lets the scripts run, and asserts against the rendered DOM.

    python3 tools/render_check.py --manifest   # record what is there now
    python3 tools/render_check.py              # fail if any of it has gone

The manifest (data/render_manifest.json) is generated from the current page,
so it records the page as it stands and fails when something disappears. It is
deliberately not hand-written: a hand-written list drifts, and the point is to
catch what nobody thought to list.

Chromium comes from the Playwright cache already on this machine; the browser
path is discovered rather than assumed, so this runs without a download.
"""
import glob, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
MANIFEST = os.path.join(REPO, "data", "render_manifest.json")
HEIGHT_TOLERANCE = 0.10          # the page may shrink by a tenth, not more


def chromium_path():
    for pat in ("chromium-*/chrome-linux/chrome",
                "chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"):
        hits = sorted(glob.glob(os.path.join(
            os.environ.get("PLAYWRIGHT_BROWSERS_PATH",
                           os.path.expanduser("~/.cache/ms-playwright")), pat)))
        if hits:
            return hits[-1]
    return None


PROBE = r"""() => {
  const vis = el => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return !el.hidden && s.display !== 'none' && s.visibility !== 'hidden'
           && (r.width > 0 || r.height > 0);
  };
  // headings that are on the page and visible
  const headings = [...document.querySelectorAll('h2')]
      .filter(vis).map(h => h.textContent.trim().replace(/\s+/g, ' '));
  // tables: filled, or hidden on purpose
  const tables = {};
  document.querySelectorAll('table[id]').forEach(tb => {
    const rows = tb.querySelectorAll('tbody tr').length;
    const wrap = tb.closest('.tablewrap');
    const hidden = (wrap && wrap.hidden) || !vis(tb);
    tables[tb.id] = { rows, hidden };
  });
  // ids the scripts look up, and whether they resolve
  const src = [...document.querySelectorAll('script:not([src])')]
      .map(s => s.textContent).join('\n');
  const ids = new Set();
  for (const m of src.matchAll(/\$\('#([A-Za-z0-9_-]+)'\)/g)) ids.add(m[1]);
  for (const m of src.matchAll(/getElementById\('([A-Za-z0-9_-]+)'\)/g)) ids.add(m[1]);
  const missing = [...ids].filter(i => !document.getElementById(i));
  // scope buttons
  const buttons = [...document.querySelectorAll('#scopebar [data-scope], #scopebar button')]
      .map(b => b.dataset.scope || b.textContent.trim());
  // Every section must share the page measure. Six of them once rendered at
  // the full window width because a misplaced </div> closed .wrap early: the
  // markup token counts balanced, so only a rendered page could show it.
  const wrap = document.querySelector('.wrap');
  const cs = wrap ? getComputedStyle(wrap) : null;
  const measure = wrap
    ? Math.round(wrap.getBoundingClientRect().width
                 - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight))
    : 0;
  const off = [...document.querySelectorAll('section')]
      .map(s => ({ t: (s.querySelector('h2') || {textContent:'(none)'})
                        .textContent.slice(0, 44),
                   w: Math.round(s.getBoundingClientRect().width) }))
      .filter(x => Math.abs(x.w - measure) > 2);
  return {
    headings, tables, missing_ids: missing, buttons,
    height: document.body.scrollHeight,
    measure, off_measure: off,
    sections: document.querySelectorAll('section').length,
  };
}"""


def probe(page_path):
    from playwright.sync_api import sync_playwright
    exe = chromium_path()
    if not exe:
        sys.exit("render_check: no chromium in the Playwright cache")
    errors = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=exe)
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto("file://" + page_path, wait_until="load")
        pg.wait_for_timeout(1200)
        out = pg.evaluate(PROBE)
        # Portfolio by partner, per scope. "not in scope" was ambiguous: it
        # read as a gap in the data rather than as a filter, and nobody could
        # say from the page whether Endur'O was being excluded or was simply
        # missing. Each button now pins what the Endur'O column must render.
        out["partner"] = {}
        for s in ("all", "mad", "madx", "mar", "enduro"):
            try:
                pg.click(f'#scopebar button[data-s="{s}"]')
                pg.wait_for_timeout(250)
                out["partner"][s] = pg.evaluate(
                    """() => {const r=document.querySelectorAll('#ptable tbody tr');
                       if(!r.length) return null;
                       const c=r[0].querySelectorAll('td');
                       return {end:c[2].textContent.trim().replace(/\\s+/g,' '),
                               tot:c[3].textContent.trim()};}""")
            except Exception:                                  # noqa: BLE001
                out["partner"][s] = None
        pg.click('#scopebar button[data-s="all"]')
        pg.wait_for_timeout(250)
        # scope behaviour: each button must change what is visible
        scopes = {}
        for s in out["buttons"]:
            try:
                pg.click(f'#scopebar [data-scope="{s}"]', timeout=1500)
                pg.wait_for_timeout(250)
                scopes[s] = pg.evaluate(
                    "() => [...document.querySelectorAll('section')]"
                    ".filter(x => !x.hidden && getComputedStyle(x).display !== 'none').length")
            except Exception:
                scopes[s] = None
        out["scope_visible_sections"] = scopes
        b.close()
    out["page_errors"] = errors
    return out


def page_arg(argv):
    """--page PATH gates a candidate where it lies, before anything is copied.

    A candidate must be verified in place: copying first and checking after
    leaves the repository half-written if the check fails.
    """
    if "--page" in argv:
        i = argv.index("--page")
        if i + 1 >= len(argv):
            sys.exit("render_check: --page needs a path")
        p = os.path.abspath(argv[i + 1])
        if not os.path.isfile(p):
            sys.exit(f"render_check: no such page {p}")
        return p
    return PAGE


def main():
    argv = sys.argv[1:]
    page = page_arg(argv)
    if "--manifest" in argv:
        out = probe(page)
        json.dump(out, open(MANIFEST, "w", encoding="utf8"),
                  indent=1, sort_keys=True, ensure_ascii=False)
        print(f"render manifest written: {len(out['headings'])} headings, "
              f"{len(out['tables'])} tables, {out['sections']} sections, "
              f"height {out['height']}px")
        return 0
    if not os.path.exists(MANIFEST):
        sys.exit("render_check: no manifest; run --manifest first")
    want = json.load(open(MANIFEST, encoding="utf8"))
    got = probe(page)
    fails = []

    gone = [h for h in want["headings"] if h not in got["headings"]]
    if gone:
        fails.append(f"{len(gone)} heading(s) no longer render: " + "; ".join(gone[:4]))

    for tid, spec in want["tables"].items():
        cur = got["tables"].get(tid)
        if cur is None:
            fails.append(f"table #{tid} is no longer on the page")
        elif spec["rows"] > 0 and cur["rows"] == 0 and not cur["hidden"]:
            fails.append(f"table #{tid} lost its rows ({spec['rows']} -> 0) and is not hidden")

    if got["missing_ids"]:
        fails.append("script looks up ids that do not exist: "
                     + ", ".join(sorted(got["missing_ids"])[:6]))

    lost_buttons = [b for b in want["buttons"] if b not in got["buttons"]]
    if lost_buttons:
        fails.append("scope buttons missing: " + ", ".join(lost_buttons))
    for s, n in want.get("scope_visible_sections", {}).items():
        m = got.get("scope_visible_sections", {}).get(s)
        if n and (m is None or m == 0):
            fails.append(f"scope '{s}' now shows {m} sections (was {n})")

    # Endur'O must carry its systems under the two scopes that cover it, and
    # must say plainly that it is filtered - not absent - under the three that
    # do not.
    COVERS = {"all": True, "enduro": True, "mad": False, "madx": False,
              "mar": False}
    for s, covered in COVERS.items():
        cell = (got.get("partner") or {}).get(s)
        if cell is None:
            fails.append(f"scope {s}: the partner table rendered no rows")
            continue
        end = cell.get("end", "")
        if covered:
            if "piped systems" not in end or "not in this scope" in end:
                fails.append(f"scope {s}: Endur'O must show its piped systems, "
                             f"got {end[:60]!r}")
        else:
            if "not in this scope" not in end:
                fails.append(f"scope {s}: Endur'O must say it is filtered out, "
                             f"got {end[:60]!r}")
            elif "does not cover it" not in end:
                fails.append(f"scope {s}: the exclusion must name the scope, "
                             f"got {end[:60]!r}")
    if got.get("off_measure"):
        for x in got["off_measure"]:
            fails.append(f"section is off the page measure "
                         f"({x['w']}px against {got['measure']}px): {x['t']}")
    if want["height"]:
        drop = (want["height"] - got["height"]) / want["height"]
        if drop > HEIGHT_TOLERANCE:
            fails.append(f"page height fell {drop:.0%} "
                         f"({want['height']} -> {got['height']}px)")

    if got["page_errors"]:
        fails.append("javascript errors on load: " + "; ".join(got["page_errors"][:3]))

    if fails:
        print("RENDER CHECK FAILED")
        for f in fails:
            print("   " + f)
        print("\nIf the change was intended, re-record with:"
              "\n   python3 tools/render_check.py --manifest")
        return 1
    print(f"render ok: {len(got['headings'])} headings, {len(got['tables'])} tables, "
          f"{got['sections']} sections, measure {got['measure']}px, "
          f"height {got['height']}px "
          f"({(got['height']-want['height'])/want['height']:+.1%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
