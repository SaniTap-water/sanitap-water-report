# -*- coding: utf-8 -*-
"""Layout acceptance test for the built page (Adriaan Mol, 30 Sep 2026).

Loads the page in Chromium (Playwright; preinstalled, never `playwright
install`) at 1522 px and 506 px with every <details> open, lets the table
sizer run, and fails on:

  1. an inline pixel width on any table (style="width:...px"; a min-width
     set through --tmin is not a width);
  2. at 1522 px, a .num column wider than 25% of its table while a text
     column in the same table is under 160 px;
  3. action-list column shares more than 2 points off 50/12/6/8/24;
  4. any empty <h2>, including one that renders no text as the page loads
     (a heading inside a collapsed <details> is empty to a reader);
  5. the withdrawn wording of the old section title anywhere on the page;
  6. any stat tile whose computed background, border colour or radius
     differs from the partner cards';
  7. at 1522 px, any section content box narrower than 90% of the content
     column (tables inside .tablescroll/.tablewrap excepted).

    python3 tools/check_layout.py                     # the built index.html
    python3 tools/check_layout.py --url https://...   # the live page
    python3 tools/check_layout.py --shots docs/qa/2026-09-30 --tag after

Exits non-zero on any failure; publish.sh runs it as part of the gate.
"""
import argparse, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDE, NARROW = 1522, 506
ACT_SHARES = [50, 12, 6, 8, 24]
SHOTS = {  # name -> selector of the element to capture
    "chaintbl": "#chaintbl",
    "action-list": "#act-flat",
    "this-week": "section:has(#week)",
    "partner-cards": "section:has(.partner)",
    "marolinta": "section:has(> .sechead h2)",   # resolved in JS below
    "sdws18": "#pousec",
}

JS_PREP = """async () => {
  document.querySelectorAll('details').forEach(d => d.open = true);
  window.dispatchEvent(new Event('resize'));
  await new Promise(r => setTimeout(r, 900));
  if (typeof layoutTables === 'function') layoutTables();
  await new Promise(r => setTimeout(r, 300));
}"""

JS_CHECK = r"""(args) => {
  const [wide, shares] = args, out = [];
  const vis = el => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
  // 1. inline pixel width on a table
  for (const t of document.querySelectorAll('table')) {
    const s = t.getAttribute('style') || '';
    if (/(^|;)\s*width\s*:\s*[\d.]+px/i.test(s))
      out.push(['inline-width', (t.id || t.className || 'table') + ': ' + s]);
  }
  // 2. .num column over 25% while a text column is under 160 px
  if (wide) for (const t of document.querySelectorAll('table')) {
    if (!vis(t)) continue;
    const tw = t.getBoundingClientRect().width; if (!tw) continue;
    let n = 0; for (const r of t.rows) { let k = 0; for (const c of r.cells) k += c.colSpan || 1; n = Math.max(n, k); }
    const row = [...t.rows].find(r => r.cells.length === n && [...r.cells].every(c => (c.colSpan || 1) === 1) && r.getBoundingClientRect().height > 0);
    if (!row) continue;
    const w = [...row.cells].map(c => c.getBoundingClientRect().width);
    const isNum = i => { let a = 0, b = 0; for (const r of t.rows) { const c = r.cells[i]; if (!c || (c.colSpan || 1) > 1 || r.cells.length !== n) continue;
        if (c.tagName === 'TH') { if (c.classList.contains('num')) return true; continue; } b++; if (c.classList.contains('num')) a++; } return b > 0 && a / b > 0.6; };
    const num = w.map((_, i) => isNum(i));
    const bigNum = w.some((v, i) => num[i] && v > 0.25 * tw + 1);
    const thin = w.map((v, i) => [v, i]).filter(([v, i]) => !num[i] && v < 159.5);
    if (bigNum && thin.length)
      out.push(['num-vs-text', `${t.id || t.className || 'table'}: widths ${w.map(Math.round).join('/')} of ${Math.round(tw)}`]);
  }
  // 3. action-list shares
  const at = document.querySelector('#act-flat table.acttbl');
  if (at && vis(at)) {
    const tw = at.getBoundingClientRect().width;
    const row = [...at.rows].find(r => r.cells.length === 5 && r.getBoundingClientRect().height > 0);
    if (row) {
      const got = [...row.cells].map(c => 100 * c.getBoundingClientRect().width / tw);
      got.forEach((g, i) => { if (Math.abs(g - shares[i]) > 2)
        out.push(['action-shares', `column ${i + 1}: ${g.toFixed(1)}% (want ${shares[i]}%)`]); });
    }
  } else out.push(['action-shares', 'action list not found or not visible']);
  // 4. empty h2
  document.querySelectorAll('h2').forEach((h, i) => { if (!h.textContent.trim())
    out.push(['empty-h2', `h2 #${i} after "${(h.closest('section')?.previousElementSibling?.querySelector('h2')?.textContent || '').trim().slice(0, 60)}"`]); });
  // 5. withdrawn wording
  const withdrawn = ['figure is', 'over'].join(' ');   // built, so this file is not itself a leftover
  if (document.documentElement.outerHTML.includes(withdrawn)) out.push(['figure-is-over', 'present']);
  // 6. stat tiles against the partner cards
  const pc = document.querySelector('.partner');
  if (!pc) out.push(['tiles', 'no partner card to compare with']);
  else {
    const ref = getComputedStyle(pc), key = s => [s.backgroundColor, s.borderTopColor, s.borderTopLeftRadius].join(' | ');
    const want = key(ref);
    for (const el of document.querySelectorAll('.tile, .wk > div, .actstats > .stat, .stats > .stat')) {
      if (!vis(el)) continue;
      const k = key(getComputedStyle(el));
      if (k !== want) out.push(['tiles', `${el.closest('section')?.querySelector('h2')?.textContent.trim().slice(0, 40) || '?'}: ${k} (partner ${want})`]);
    }
    for (const g of document.querySelectorAll('.tiles, .wk, .actstats, .stats')) {
      const b = getComputedStyle(g).backgroundColor;
      if (vis(g) && b !== 'rgba(0, 0, 0, 0)' && b !== ref.backgroundColor)
        out.push(['tiles', `grid ${g.id || g.className}: background ${b}`]);
    }
  }
  // 7. section content narrower than the content column
  if (wide) {
    const col = document.querySelector('.wrap');
    const cs = getComputedStyle(col), cw = col.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    for (const sec of document.querySelectorAll('.wrap section')) {
      if (!vis(sec)) continue;
      for (const ch of sec.querySelectorAll(':scope > *, :scope > details > *:not(summary)')) {
        if (!vis(ch) || ch.tagName === 'SUMMARY' || ch.tagName === 'SCRIPT' || ch.tagName === 'STYLE') continue;
        const d = getComputedStyle(ch).display; if (d.startsWith('inline') || d === 'contents') continue;
        if (ch.matches('.tablescroll, .tablewrap') || ch.closest('.tablescroll, .tablewrap')) continue;
        if (ch.matches('table') && ch.parentElement.matches('.tablescroll, .tablewrap')) continue;
        const w = ch.getBoundingClientRect().width;
        // a box inside an open <details> is measured against the details' own content box
        const host = ch.parentElement.tagName === 'DETAILS' ? ch.parentElement : null;
        const ref = host ? host.clientWidth - parseFloat(getComputedStyle(host).paddingLeft) - parseFloat(getComputedStyle(host).paddingRight) : cw;
        if (w < 0.9 * ref - 1)
          out.push(['narrow', `${(sec.querySelector('h2')?.textContent || sec.id || '?').trim().slice(0, 50)} > ${ch.tagName.toLowerCase()}${ch.id ? '#' + ch.id : ''}${ch.className ? '.' + String(ch.className).split(' ')[0] : ''}: ${Math.round(w)} of ${Math.round(ref)} px`]);
      }
    }
    // a grid with fewer visible items than column tracks leaves its content
    // narrower than the column (Marolinta sat in a one-child .grid2)
    for (const g of document.querySelectorAll('.wrap section .grid2, .wrap section .partners, .wrap section .tiles, .wrap section .actstats, .wrap section .stats, .wrap section .wk')) {
      if (!vis(g)) continue;
      const tracks = getComputedStyle(g).gridTemplateColumns.split(' ').filter(v => parseFloat(v) > 0).length;  // auto-fit collapses empty tracks to 0px
      const items = [...g.children].filter(vis).length;
      if (getComputedStyle(g).display === 'grid' && items > 0 && items < tracks)
        out.push(['narrow', `${(g.closest('section').querySelector('h2,h3')?.textContent || '?').trim().slice(0, 50)} > .${String(g.className).split(' ')[0]}: ${items} item(s) in ${tracks} columns`]);
    }
  }
  return out;
}"""

JS_EMPTY_H2_AS_LOADED = r"""() => [...document.querySelectorAll('h2')]
  .filter(h => !h.innerText.trim())
  .map(h => `as loaded: <h2> "${h.textContent.trim().slice(0, 50)}" renders no text` +
            (h.closest('details:not([open])') ? ` (inside closed <details id="${h.closest('details').id}">)` : ''))"""

JS_SHOT_TARGET = r"""(name) => {
  const pick = {
    'chaintbl': () => document.getElementById('chaintbl'),
    'action-list': () => document.getElementById('act-flat'),
    'this-week': () => document.getElementById('week')?.closest('section'),
    'partner-cards': () => document.querySelector('.partner')?.closest('section'),
    'marolinta': () => [...document.querySelectorAll('section')].find(s => /Marolinta\s*[—-]\s*what has been logged/.test(s.querySelector('h2')?.textContent || '')),
    'sdws18': () => document.getElementById('pousec') || document.getElementById('sdws18tbl')?.closest('section'),
  }[name];
  const el = pick && pick();
  if (!el) return false;
  document.querySelectorAll('[data-shot]').forEach(e => e.removeAttribute('data-shot'));
  el.setAttribute('data-shot', name);
  return true;
}"""


def run(url, shots=None, tag=None):
    from playwright.sync_api import sync_playwright
    fails = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for width in (WIDE, NARROW):
            pg = b.new_page(viewport={"width": width, "height": 1000})
            pg.goto(url, wait_until="load")
            pg.wait_for_timeout(1200)
            # 4b. as loaded, before anything is opened: an <h2> a reader or a
            # screen reader meets with no rendered text (e.g. inside a
            # collapsed <details>) is an empty heading too
            for what in pg.evaluate(JS_EMPTY_H2_AS_LOADED):
                fails.append((width, "empty-h2", what))
            pg.evaluate(JS_PREP)
            for kind, what in pg.evaluate(JS_CHECK, [width == WIDE, ACT_SHARES]):
                fails.append((width, kind, what))
            if shots and width == WIDE:
                os.makedirs(shots, exist_ok=True)
                for name in SHOTS:
                    if pg.evaluate(JS_SHOT_TARGET, name):
                        loc = pg.locator(f'[data-shot="{name}"]')
                        path = os.path.join(shots, f"{tag or 'shot'}-{name}.png")
                        loc.screenshot(path=path)
                        print(f"  screenshot {path}")
                    else:
                        print(f"  screenshot {name}: element not found")
            pg.close()
        b.close()
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="file://" + os.path.join(REPO, "index.html"))
    ap.add_argument("--shots", default=None, help="directory for screenshots")
    ap.add_argument("--tag", default=None, help="screenshot file prefix, e.g. before / after")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    fails = run(a.url, a.shots, a.tag)
    if a.json:
        print(json.dumps(fails, ensure_ascii=False, indent=1))
    kinds = ["inline-width", "num-vs-text", "action-shares", "empty-h2", "figure-is-over", "tiles", "narrow"]
    print(f"check_layout: {a.url}")
    for k in kinds:
        got = [f for f in fails if f[1] == k]
        print(f"  {'FAIL' if got else 'ok  '} {k:15s} {len(got)}")
        for w, _, what in got[:12]:
            print(f"         [{w}px] {what}")
        if len(got) > 12:
            print(f"         ... and {len(got) - 12} more")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
