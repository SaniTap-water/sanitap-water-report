# -*- coding: utf-8 -*-
"""Layout acceptance test for the built page (Adriaan Mol, 30 Sep 2026).

Loads the page in Chromium (Playwright; preinstalled, never `playwright
install`) in the light AND the dark scheme at three laptop sizes - 1280x800,
1440x900, 1920x1080 (laptops only, 30 Sep 2026; the narrow-screen CSS stays,
untested) - with every <details> open, lets the table sizer run, and fails on:

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
  7. any section content box narrower than 90% of the content column
     (tables inside .tablescroll/.tablewrap excepted), or a grid with an
     empty column track;
  8. a tinted surface (tiles, partner cards, table headers, a collapsed
     panel's summary bar) under 1.25:1 against the page background, or tiles
     that are not all the same colour;
  9. visible text under 4.5:1 against its composited background (3:1 for
     text 24 px and larger), pills and other translucent fills composited;
 10. a partner card whose logo is not left of its text, or taller than
     220 px (Endur'O excepted when its text needs more).

    python3 tools/check_layout.py                     # the built index.html
    python3 tools/check_layout.py --url https://...   # the live page
    python3 tools/check_layout.py --shots docs/qa/2026-09-30 --tag after

Exits non-zero on any failure; publish.sh runs it as part of the gate.
"""
import argparse, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAPTOPS = ((1280, 800), (1440, 900), (1920, 1080))
SCHEMES = ("light", "dark")
SHOT_WIDTH = 1440
ACT_SHARES = [50, 12, 6, 8, 24]
SHOTS = ["this-week", "fleet-at-a-glance", "partner-cards", "marolinta", "action-list",
         "chaintbl", "sdws18"]

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
    for (const el of document.querySelectorAll('.tile, .wk > div, .actstats > .stat, .stats > .stat, .donut')) {
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

JS_TINT = r"""() => {
  const out = [], rgb = c => { const v = (c.match(/-?[\d.]+(e-?\d+)?/g) || []).map(Number); return /^color\(srgb/.test(c) ? v.map((x, i) => i < 3 ? x * 255 : x) : v; };
  const lum = c => { const [r, g, b] = rgb(c).slice(0, 3).map(v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); });
    return .2126 * r + .7152 * g + .0722 * b; };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + .05) / (y + .05); };
  const page = getComputedStyle(document.body).backgroundColor;
  const vis = el => el.getClientRects().length > 0;
  const groups = {
    tiles: [...document.querySelectorAll('.tile, .wk > div, .actstats > .stat, .stats > .stat, .donut')],
    'partner cards': [...document.querySelectorAll('.partner')],
    'table headers': [...document.querySelectorAll('thead th')],
    'panel summaries': [...document.querySelectorAll('details.expl > summary, details.panel > summary')] };
  const seen = new Set();
  for (const [g, els] of Object.entries(groups)) {
    for (const el of els) { if (!vis(el)) continue;
      const bg = getComputedStyle(el).backgroundColor; if (g === 'tiles') seen.add(bg);
      const r = ratio(page, bg);
      if (r < 1.25) { out.push(`${g}: ${bg} on page ${page} is ${r.toFixed(2)}:1 (< 1.25)`); break; } } }
  if (seen.size > 1) out.push(`tiles are not identical: ${[...seen].join(' / ')}`);
  return out;
}"""

JS_CONTRAST = r"""() => {
  // rgb()/rgba() give 0-255 channels; color-mix() results come back as
  // color(srgb r g b / a) with 0-1 channels
  const parse = c => { const m = c.match(/-?[\d.]+(e-?\d+)?/g); if (!m) return [0, 0, 0, 0]; const v = m.map(Number);
    const k = /^color\(srgb/.test(c) ? 255 : 1; return [v[0] * k, v[1] * k, v[2] * k, v.length > 3 ? v[3] : 1]; };
  const over = (top, under) => { const a = top[3]; return [0, 1, 2].map(i => top[i] * a + under[i] * (1 - a)).concat(1); };
  const lum = c => { const [r, g, b] = c.slice(0, 3).map(v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * r + .7152 * g + .0722 * b; };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + .05) / (y + .05); };
  const cache = new Map();
  const bgOf = el => {                      // the composited background behind el
    if (!el || el === document.documentElement) return [255, 255, 255, 1];
    if (cache.has(el)) return cache.get(el);
    const under = bgOf(el.parentElement);
    const c = parse(getComputedStyle(el).backgroundColor);
    const out = c[3] > 0 ? over(c, under) : under;
    cache.set(el, out); return out;
  };
  const fails = new Map();
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    if (!n.nodeValue.trim()) continue;
    const el = n.parentElement; if (!el || el.closest('script,style,noscript,[hidden],.tip')) continue;
    if (!el.getClientRects().length) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || +cs.opacity === 0) continue;
    const inSvg = el.closest('svg');
    const fg0 = parse(inSvg ? cs.fill : cs.color); if (fg0[3] === 0) continue;
    const bg = bgOf(inSvg ? inSvg.parentElement : el);
    const fg = fg0[3] < 1 ? over(fg0, bg) : fg0;
    const px = parseFloat(cs.fontSize), need = px >= 24 ? 3 : 4.5;
    const r = ratio(fg, bg);
    if (r < need - 0.005) {
      const key = `${cs.color}|${bg.slice(0, 3).map(Math.round).join(',')}`;
      const cur = fails.get(key) || { n: 0, r, fg: cs.color, bg: `rgb(${bg.slice(0, 3).map(Math.round).join(', ')})`, eg: [] };
      cur.n++; if (cur.eg.length < 3) cur.eg.push(`${el.tagName.toLowerCase()}${el.className && typeof el.className === 'string' ? '.' + el.className.split(' ').filter(Boolean).join('.') : ''} "${n.nodeValue.trim().slice(0, 24)}"`);
      fails.set(key, cur);
    }
  }
  return [...fails.values()].sort((a, b) => b.n - a.n)
    .map(f => ({ n: f.n, what: `${f.n} text node(s) ${f.fg} on ${f.bg} = ${f.r.toFixed(2)}:1, e.g. ${f.eg.join('; ')}` }));
}"""

JS_PARTNER = r"""() => {
  const out = [];
  for (const c of document.querySelectorAll('.partner')) {
    const img = c.querySelector('img'), txt = c.querySelector('.pname');
    if (!img || !txt) { out.push('a partner card without a logo or a name'); continue; }
    const name = txt.textContent.trim(), ri = img.getBoundingClientRect(), rt = txt.getBoundingClientRect();
    const body = c.querySelector('.pbody')?.getBoundingClientRect();
    if (!(ri.right <= rt.left + 1 && (!body || ri.right <= body.left + 1)))
      out.push(`${name}: logo is not left of the text (logo ${Math.round(ri.left)}-${Math.round(ri.right)}, text from ${Math.round(rt.left)})`);
    const h = c.getBoundingClientRect().height;
    if (h > 220.5 && !/endur/i.test(name)) out.push(`${name}: card is ${Math.round(h)} px tall (> 220)`);
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
    'fleet-at-a-glance': () => [...document.querySelectorAll('h2')].find(h => h.textContent.trim() === 'The fleet at a glance')?.closest('section, div.sechead')?.parentElement?.closest('section') || [...document.querySelectorAll('h2')].find(h => h.textContent.trim() === 'The fleet at a glance')?.closest('section') || document.getElementById('tiles'),
    'details-collapsed': () => document.getElementById('weekhow'),
    'details-open': () => document.getElementById('weekhow'),
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


def shoot(pg, shots, tag, scheme, name):
    if not pg.evaluate(JS_SHOT_TARGET, name):
        print(f"  screenshot {name}: element not found")
        return
    path = os.path.join(shots, f"{tag + '-' if tag else ''}{scheme}-{name}.png")
    pg.locator(f'[data-shot="{name}"]').screenshot(path=path)
    print(f"  screenshot {path}")


def run(url, shots=None, tag=None):
    from playwright.sync_api import sync_playwright
    fails = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for scheme in SCHEMES:
            for width, height in LAPTOPS:
                where = f"{scheme} {width}"
                pg = b.new_page(viewport={"width": width, "height": height}, color_scheme=scheme)
                pg.goto(url, wait_until="load")
                pg.wait_for_timeout(1200)
                # 4b. as loaded, before anything is opened: an <h2> a reader or a
                # screen reader meets with no rendered text (e.g. inside a
                # collapsed <details>) is an empty heading too
                for what in pg.evaluate(JS_EMPTY_H2_AS_LOADED):
                    fails.append((where, "empty-h2", what))
                snap = shots and width == SHOT_WIDTH
                if snap:
                    os.makedirs(shots, exist_ok=True)
                    shoot(pg, shots, tag, scheme, "details-collapsed")
                pg.evaluate(JS_PREP)
                for kind, what in pg.evaluate(JS_CHECK, [True, ACT_SHARES]):
                    fails.append((where, kind, what))
                for what in pg.evaluate(JS_TINT):
                    fails.append((where, "tint", what))
                for f in pg.evaluate(JS_CONTRAST):
                    fails.append((where, "contrast", f["what"]))
                for what in pg.evaluate(JS_PARTNER):
                    fails.append((where, "partner-cards", what))
                if snap:
                    for name in SHOTS + ["details-open"]:
                        shoot(pg, shots, tag, scheme, name)
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
    kinds = ["inline-width", "num-vs-text", "action-shares", "empty-h2", "figure-is-over", "tiles", "narrow",
             "tint", "contrast", "partner-cards"]
    print(f"check_layout: {a.url}")
    for k in kinds:
        got = [f for f in fails if f[1] == k]
        print(f"  {'FAIL' if got else 'ok  '} {k:15s} {len(got)}")
        for w, _, what in got[:12]:
            print(f"         [{w}] {what}")
        if len(got) > 12:
            print(f"         ... and {len(got) - 12} more")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
