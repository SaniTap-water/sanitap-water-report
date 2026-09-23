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
import glob, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
MANIFEST = os.path.join(REPO, "data", "render_manifest.json")
# headline tiles at desktop width: the tallest content may exceed the
# shortest by at most this much before the row reads as ragged
TILE_TOLERANCE_PX = 6
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


BASIS_PROBE = r"""() => {
  const vis = el => {
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    return !el.closest('[hidden]') && st.display !== 'none'
           && st.visibility !== 'hidden' && (r.width > 0 || r.height > 0);
  };
  // Figures the page itself declares as measuring the same quantity.
  const q = {};
  document.querySelectorAll('[data-q]').forEach(el => {
    if (!vis(el)) return;
    const v = el.querySelector('.v');
    const val = (v ? v.textContent : el.textContent).trim();
    const lab = el.querySelector('.l');
    (q[el.dataset.q] = q[el.dataset.q] || []).push({
      v: val, l: lab ? lab.textContent.trim().replace(/\s+/g, ' ').slice(0, 70)
                     : (el.closest('tr') ? el.closest('tr').children[0].textContent.trim() : '')
    });
  });
  const note = document.getElementById('scopenote');
  return {
    q,
    headline: (document.querySelector('#tiles [data-q="points"] .v') || {}).textContent || null,
    note_bold: note ? [...note.querySelectorAll('b')].map(b => b.textContent.trim()) : [],
    note: note ? note.textContent.replace(/\s+/g, ' ').trim().slice(0, 160) : null,
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
        # 60s, not the 30s default: the page is 1.4 MB and grows every
        # week, and a gate that flakes on a slow load teaches people to
        # re-run it until it passes.
        pg.goto("file://" + page_path, wait_until="load", timeout=60000)
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
        # ONE BASIS PER SCOPE.
        # Three times now the page has carried two numbers for the same thing
        # in one view: 867 against 908, Marolinta 5 against 13, 3,130 against
        # 126,780. Every time the markup was fine and every time a reader
        # found it before a check did. So the page declares, with data-q,
        # which figures measure the same quantity, and this asserts two
        # things per scope button: the headline count is the count the
        # caption states, and no quantity is reported twice with different
        # values.
        out["basis"] = {}
        for s in ("all", "mad", "madx", "mar", "enduro"):
            try:
                pg.click(f'#scopebar button[data-s="{s}"]')
                pg.wait_for_timeout(300)
                out["basis"][s] = pg.evaluate(BASIS_PROBE)
            except Exception as e:                             # noqa: BLE001
                out["basis"][s] = {"error": str(e)}
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

        # THE PORTFOLIO ONLY (decided 2026-09-23). The count of the whole
        # MadAvance mWater group must not appear in any text the page can
        # show, on any scope, including collapsed blocks. Script and style
        # are not text; data objects in scripts are not rendered.
        grp = None
        try:
            grp = json.load(open(os.path.join(REPO, "data",
                                              "register_classification.json")))["group_records"]
        except Exception:                                      # noqa: BLE001
            pass
        out["group_count"] = grp
        out["group_count_seen"] = []
        if grp:
            pat = r"(?<![\d.,])" + re.escape(f"{grp:,}") + r"(?![\d,])"
            for s in ("all", "mad", "madx", "mar", "enduro"):
                pg.click(f'#scopebar button[data-s="{s}"]')
                pg.wait_for_timeout(250)
                txt = pg.evaluate("""() => { const c = document.body.cloneNode(true);
                    c.querySelectorAll('script,style,template').forEach(x => x.remove());
                    return c.textContent; }""")
                for m in re.finditer(pat, txt):
                    out["group_count_seen"].append(
                        f"{s}: ...{' '.join(txt[max(0, m.start()-60):m.end()+40].split())}...")
            pg.click('#scopebar button[data-s="all"]')
            pg.wait_for_timeout(250)

        # THE HEADLINE ROW IS ONE FRAME. A tile taller than its neighbours
        # stretches every tile in the row and leaves empty space.
        out["tile_heights"] = pg.evaluate("""() => {
            const g = document.querySelector('#tiles'); if (!g) return [];
            const was = g.style.alignItems; g.style.alignItems = 'start';
            const r = [...g.querySelectorAll(':scope > .tile')].map(t => ({
                h: Math.round(t.getBoundingClientRect().height),
                v: Math.round(t.querySelector('.v').getBoundingClientRect().height),
                l: t.textContent.trim().replace(/\\s+/g, ' ').slice(0, 40)}));
            g.style.alignItems = was; return r; }""")

        # THE PAGE NEVER SCROLLS SIDEWAYS ON A PHONE. A wide table scrolls
        # inside its own container; the page does not.
        mp = b.new_page(viewport={"width": 390, "height": 800})
        mp.goto("file://" + page_path, wait_until="load", timeout=60000)
        mp.wait_for_timeout(1200)
        out["mobile"] = mp.evaluate("""() => ({sw: document.documentElement.scrollWidth,
            vw: innerWidth,
            wide: [...document.querySelectorAll('body *')]
              .filter(e => e.getBoundingClientRect().right > innerWidth + 1
                        && !e.closest('.tablewrap'))
              .slice(0, 4).map(e => e.tagName + (e.id ? '#' + e.id : ''))})""")
        mp.close()
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
    # one basis per scope - see BASIS_PROBE
    for s, b in (got.get("basis") or {}).items():
        if not b or b.get("error"):
            fails.append(f"scope {s}: basis probe failed ({(b or {}).get('error')})")
            continue
        head = (b.get("headline") or "").strip()
        if not head:
            fails.append(f"scope {s}: no headline 'water points in scope' figure")
        elif head not in b.get("note_bold", []):
            fails.append(
                f"scope {s}: the headline reads {head} but the caption does not "
                f"state it; the caption's own figures are "
                f"{[x for x in b.get('note_bold', []) if any(c.isdigit() for c in x)]}")
        for qty, items in (b.get("q") or {}).items():
            vals = sorted({i["v"] for i in items})
            if len(vals) > 1:
                where = "; ".join(f"{i['v']} ({i['l']})" for i in items)
                fails.append(f"scope {s}: two bases for '{qty}' in one view - {where}")

    if got.get("off_measure"):
        for x in got["off_measure"]:
            fails.append(f"section is off the page measure "
                         f"({x['w']}px against {got['measure']}px): {x['t']}")
    if want["height"]:
        drop = (want["height"] - got["height"]) / want["height"]
        if drop > HEIGHT_TOLERANCE:
            fails.append(f"page height fell {drop:.0%} "
                         f"({want['height']} -> {got['height']}px)")

    for x in got.get("group_count_seen") or []:
        fails.append(f"the whole mWater group count ({got['group_count']}) is "
                     f"rendered; the page covers the managed portfolio only: {x}")
    tiles = sorted(got.get("tile_heights") or [], key=lambda t: -t["h"])
    if len(tiles) > 1 and tiles[0]["h"] - tiles[1]["h"] > TILE_TOLERANCE_PX:
        fails.append(f"one headline tile sets the row height: {tiles[0]['l']!r} is "
                     f"{tiles[0]['h']}px against {tiles[1]['h']}px for the next tallest "
                     f"(limit {TILE_TOLERANCE_PX}px)")
    vs = [t["v"] for t in tiles]
    if vs and max(vs) - min(vs) > TILE_TOLERANCE_PX:
        fails.append(f"headline tile numbers are not one line of one size: "
                     f"heights {min(vs)}-{max(vs)}px")
    mob = got.get("mobile") or {}
    if mob and mob["sw"] > mob["vw"] + 1:
        fails.append(f"the page scrolls sideways at phone width ({mob['sw']}px "
                     f"against {mob['vw']}px): {', '.join(mob['wide']) or 'unknown'}")

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
