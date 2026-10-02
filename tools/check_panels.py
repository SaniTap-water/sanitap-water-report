# -*- coding: utf-8 -*-
"""Every "How this figure is produced" panel opens at full width beneath its
card or card row, pushing the content below down, never overlapping or being
clipped; and every expanding <details> does the same (Adriaan Mol, 1 Oct 2026).

Loads the built page in Chromium (Playwright; preinstalled) at the three laptop
widths - 1280, 1440 and 1920 px - in the All SaniTap and Marolinta scopes
(their tiles differ). Opens every collapsed block, then opens the panels one at
a time, one figure per distinct place a panel can open (the page's own
derivAnchor), and fails when a panel:

  1. is narrower than 90% of the box it opens in (its row, or its table's
     visible width);
  2. is overlapped: a point inside it is covered by an element that is not
     the panel or inside it (sampled on a 5 x 3 grid);
  3. is clipped by an ancestor that hides overflow;
  4. leaves the next element in flow above its bottom edge (it must push the
     content below down).

Then, with every <details> open, the same overlap and clipping tests are run
on each expanded block.

Shown failing on 1 Oct 2026 against the previous placement (the "Last
recorded status" donut panel opened inside the 300-pixel card and ran over
the next one).

    python3 tools/check_panels.py
    python3 tools/check_panels.py --shots docs/qa/2026-10-01
"""
import argparse, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDTHS = ((1280, 800), (1440, 900), (1920, 1080))

JS_PREP = """async (scope) => {
  const b = document.querySelector(`#scopebar button[data-s="${scope}"]`); if (b) b.click();
  document.querySelectorAll('details').forEach(d => d.open = true);
  window.dispatchEvent(new Event('resize'));
  await new Promise(r => setTimeout(r, 700));
  if (typeof layoutTables === 'function') layoutTables();
  await new Promise(r => setTimeout(r, 200));
}"""

JS_PANELS = r"""async () => {
  const out = [], seen = new Set(), vis = el => el.getClientRects().length > 0;
  const sel = '[data-fig],[data-param],[data-manual],[data-quote],[data-artefact],[data-withdrawn],[data-retired]';
  const figs = [...document.querySelectorAll(sel)].filter(el => vis(el) && !el.closest('.deriv') && !el.closest('[hidden]'));
  const label = el => (el.dataset.fig || el.dataset.param || el.dataset.manual || el.dataset.quote || el.dataset.artefact || el.dataset.withdrawn || el.dataset.retired || '').slice(0, 70);
  const clipAnc = (n, r) => { for (let a = n.parentElement; a && a !== document.body; a = a.parentElement) {
      const cs = getComputedStyle(a);
      if (/(hidden|clip)/.test(cs.overflowX + cs.overflowY)) { const q = a.getBoundingClientRect();
        if (r.left < q.left - 1 || r.right > q.right + 1 || (/(hidden|clip)/.test(cs.overflowY) && (r.top < q.top - 1 || r.bottom > q.bottom + 1)))
          return (a.id || a.className || a.tagName).toString().slice(0, 40); }
      if (/(auto|scroll)/.test(cs.overflowX)) { const q = a.getBoundingClientRect();
        if (r.left < q.left - 1 || r.right > q.right + 1) return 'scroller ' + (a.id || a.className || a.tagName).toString().slice(0, 40); }
    } return null; };
  const covered = (box, r) => { const bad = [];
    for (const fx of [.1, .3, .5, .7, .9]) for (const fy of [.2, .5, .8]) {
      const x = r.left + r.width * fx, y = r.top + r.height * fy;
      if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
      const t = document.elementFromPoint(x, y);
      if (t && !box.contains(t) && !t.contains(box)) bad.push((t.id || t.className || t.tagName).toString().slice(0, 30));
    } return bad; };
  let n = 0;
  for (const el of figs) {
    const a = typeof derivAnchor === 'function' ? derivAnchor(el) : {after: el.closest('.tiles') || el.closest('p,td,li,h2,h3,div') || el.parentElement}, key = a.row || a.after;
    if (seen.has(key)) continue; seen.add(key);
    el.scrollIntoView({block: 'center', behavior: 'instant'});
    toggleDeriv(el); n++;
    const p = el._deriv, w = el._derivWrap || el._deriv;
    if (!p) { out.push(['no panel', label(el)]); continue; }
    p.scrollIntoView({block: 'center', behavior: 'instant'});
    await new Promise(r => requestAnimationFrame(r));
    const r = p.getBoundingClientRect();
    const host = w.tagName === 'TR' ? (w.closest('.tablescroll,.tablewrap') || w.closest('table')) : p.parentElement;
    const hr = host.getBoundingClientRect(), cs = getComputedStyle(host);
    const inner = hr.width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - parseFloat(cs.borderLeftWidth) - parseFloat(cs.borderRightWidth);
    if (r.width < 0.9 * inner - 2) out.push(['narrow', `${label(el)}: panel ${Math.round(r.width)} of ${Math.round(inner)} px`]);
    const c = clipAnc(p, r); if (c) out.push(['clipped', `${label(el)}: by ${c}`]);
    const cov = covered(p, r); if (cov.length) out.push(['overlapped', `${label(el)}: by ${[...new Set(cov)].join(', ')}`]);
    let nx = w.nextElementSibling; while (nx && !vis(nx)) nx = nx.nextElementSibling;
    if (nx && nx.getBoundingClientRect().top < r.bottom - 1 && getComputedStyle(nx).position !== 'absolute')
      out.push(['not pushed down', `${label(el)}: next element starts ${Math.round(r.bottom - nx.getBoundingClientRect().top)} px above the panel's bottom`]);
    toggleDeriv(el);
  }
  return {opened: n, fails: out};
}"""

JS_DETAILS = r"""async () => {
  const out = [];
  for (const d of document.querySelectorAll('details')) {
    if (!d.getClientRects().length || d.closest('[hidden]')) continue;
    d.scrollIntoView({block: 'start', behavior: 'instant'}); await new Promise(r => setTimeout(r, 30));
    await new Promise(r => requestAnimationFrame(r));
    let r = d.getBoundingClientRect(); if (r.height < 4) continue;
    // inside a scroll box (the readability rule keeps long tables in a 60vh
    // one) only the part in the box's window is on screen; the rest is
    // reached by scrolling the box, which is not clipping
    const sb = d.parentElement && d.parentElement.closest('.tablewrap,.tablescroll,.tbox');
    let yTop = Math.max(r.top, 0), yBot = Math.min(r.bottom, innerHeight);
    if (sb && sb.scrollHeight > sb.clientHeight + 1) { const q = sb.getBoundingClientRect(); yTop = Math.max(yTop, q.top + 1); yBot = Math.min(yBot, q.top + sb.clientHeight - 1); }
    if (yBot - yTop < 4) continue;
    for (const fx of [.05, .5, .95]) for (const fy of [.25, .75]) {
      const x = r.left + r.width * fx, y = yTop + (yBot - yTop) * fy;
      const t = document.elementFromPoint(x, y);
      if (t && !d.contains(t) && !t.contains(d)) { out.push(['details overlapped', `${(d.id || d.querySelector('summary')?.textContent || '').trim().slice(0, 60)}: by ${(t.id || t.className || t.tagName).toString().slice(0, 30)}`]); break; }
    }
    for (let a = d.parentElement; a && a !== document.body; a = a.parentElement) {
      const cs = getComputedStyle(a), q = a.getBoundingClientRect();
      if (/(hidden|clip)/.test(cs.overflowX) && !/(auto|scroll)/.test(cs.overflowX) && (r.right > q.right + 1 || r.left < q.left - 1)) {
        out.push(['details clipped', `${(d.id || d.querySelector('summary')?.textContent || '').trim().slice(0, 60)}: by ${(a.id || a.className || a.tagName).toString().slice(0, 30)}`]); break; }
    }
  }
  return out;
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="file://" + os.path.join(REPO, "index.html"))
    ap.add_argument("--shots", default=None)
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    bad, opened = [], 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w, h in WIDTHS:
            pg = b.new_page(viewport={"width": w, "height": h})
            pg.goto(a.url, wait_until="load")
            pg.wait_for_timeout(1200)
            for scope in ("all", "mar"):
                pg.evaluate(JS_PREP, scope)
                r = pg.evaluate(JS_PANELS)
                opened += r["opened"]
                bad += [(w, scope) + tuple(f) for f in r["fails"]]
                bad += [(w, scope) + tuple(f) for f in pg.evaluate(JS_DETAILS)]
            if a.shots:
                os.makedirs(a.shots, exist_ok=True)
                pg.evaluate("""() => { document.querySelector('#scopebar button[data-s="all"]').click();
                   const el = document.querySelector('.donut [data-fig]'); el.scrollIntoView({block:'center'}); toggleDeriv(el); }""")
                pg.wait_for_timeout(400)
                pg.screenshot(path=os.path.join(a.shots, f"panel-donut-{w}.png"))
            pg.close()
        b.close()
    seen, uniq = set(), []
    for x in bad:
        k = x[2:]
        if k not in seen:
            seen.add(k); uniq.append(x)
    print(f"  panels: {opened} panel openings at {len(WIDTHS)} widths x 2 scopes; {len(uniq)} distinct failure(s)")
    for x in uniq[:40]:
        print("   ", " | ".join(str(y) for y in x))
    return 1 if uniq else 0


if __name__ == "__main__":
    sys.exit(main())
