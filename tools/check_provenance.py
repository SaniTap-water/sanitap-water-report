# -*- coding: utf-8 -*-
"""Every "How this figure is produced" panel follows the scope buttons.

Loads the built page in Chromium (Playwright; preinstalled) and, in each of the
five scopes (All SaniTap, MadAvance — all, MadAvance excl. Marolinta, Marolinta
only, Endur'O), builds the panel of every live figure (data-fig) that the
scope shows - the tiles first, then every figure in the sections the scope
keeps - exactly as a click would (derivPanel). It fails when:

  1. the panel's arithmetic does not end on the figure's own value: the last
     number in the arithmetic row must equal the number the figure shows;
  2. a panel names a source its scope does not use: Endur'O's hand-entered
     manual file (its supplier, its source document, the word "manual"
     beside Endur'O) in a scope without Endur'O, or a MadAvance mWater form
     in the Endur'O-only scope;
  3. a figure that adds Endur'O to the hand pumps does not show the sum,
     MadAvance figure + Endur'O figure = total, in a scope that has both;
  5. a managed figure (the water points and people-served figures marked
     data-q, and the scope note's lead figure) has a panel whose composite
     names Endur'O's hand-entered file (data/enduro_manual.json: "manual
     file", "hand-entered", its supplier or source document): the Endur'O
     programme figures are not in the managed portfolio (Adriaan Mol,
     5 Oct 2026);
  4. a panel has no scope row, or a figure in a programme-wide section (the
     action list, the register trace; marked data-programme-wide) has a
     panel that does not say the figure is programme-wide.

Shown failing on 1 Oct 2026 by breaking the people-served panel (the
arithmetic told to print one more than the tile): see docs/decision_log.md.

    python3 tools/check_provenance.py            # the built index.html
    python3 tools/check_provenance.py --list     # every failure, not the first 25
"""
import argparse, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOPES = ["all", "mad", "madx", "mar", "enduro"]

JS = r"""(scope) => {
  const btn = document.querySelector(`#scopebar button[data-s="${scope}"]`);
  if (btn) btn.click();
  const sc = SCOPES[SCOPE];
  const out = [], seen = new Set();
  const num = s => { const m = String(s).replace(/−/g, '-').match(/-?\d[\d,   ]*(?:\.\d+)?/g); return m ? m.map(x => parseFloat(x.replace(/[,   ]/g, ''))) : []; };
  const hiddenByScope = el => { const s = el.closest('[data-scopes]'); return s && !s.dataset.scopes.split(/\s+/).includes(scope); };
  const hasMad = SITES.length > 0;
  const els = [...document.querySelectorAll('#tiles [data-fig]'), ...document.querySelectorAll('[data-fig]')];
  for (const el of els) {
    if (seen.has(el)) continue; seen.add(el);
    if (el.closest('.deriv') || el.closest('[hidden]') || hiddenByScope(el)) continue;
    if (el.closest('script,template')) continue;
    const shown = num(el.textContent);
    if (!shown.length) continue;                       // text-valued figure
    let panel;
    try { panel = derivPanel(el); } catch (e) { out.push([el.dataset.fig, 'panel threw: ' + e.message, el.textContent]); continue; }
    const rows = {};
    panel.querySelectorAll('dt').forEach(dt => { rows[dt.textContent] = dt.nextElementSibling ? dt.nextElementSibling.textContent : ''; });
    const text = panel.textContent;
    const sec = el.closest('section'), h = sec && sec.querySelector('h2');
    const where = el.closest('#tiles') ? 'tile' : ((sec && sec.id) || '') + ' / ' + (h ? h.textContent.trim().slice(0, 50) : '') + (el.closest('#actions') ? ' / ' + ((el.closest('details.act-detail') || {}).id || '') : '');
    const ar = rows['arithmetic'];
    const shownText = el.textContent.trim().replace(/\s+/g, ' ');
    if (ar !== undefined) {
      // the arithmetic must arrive at the figure as shown: its displayed text
      // as a whole token, not merely some number
      const esc = shownText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      if (!new RegExp('(^|[^0-9.,])' + esc + '($|[^0-9])').test(ar.replace(/\s+/g, ' ')))
        out.push([el.dataset.fig, `arithmetic does not arrive at ${shownText}: "${ar.slice(-90)}"`, where]);
    }
    const progWide = !!el.closest('[data-programme-wide]');
    if (progWide) {
      // programme-wide sections show the same figures in every scope; their
      // panels must say so rather than pretend to follow the buttons
      if (!/programme-wide/.test(rows['scope'] || ''))
        out.push([el.dataset.fig, 'in a programme-wide section, but the panel does not say it is programme-wide', where]);
      continue;
    }
    if (rows['scope'] === undefined)
      out.push([el.dataset.fig, 'panel has no scope row', where]);
    if (!sc.enduro && /Endur.O/.test(text) && /(hand-entered|manual file|ENDURO|source document|supplier)/i.test(text))
      out.push([el.dataset.fig, "names Endur'O's manual file in a scope without Endur'O", where]);
    if (!hasMad && /portal\.mwater\.co\/#\/forms/.test(panel.innerHTML) && !/ENDURO|PIPEDWQ|piped|moramanga/i.test(el.dataset.fig))
      out.push([el.dataset.fig, 'names a MadAvance form in the Endur’O-only scope', where]);
    const isManaged = !!el.closest('[data-q="points"],[data-q="people"]') || el === document.querySelector('#scopenote b [data-fig]') || el.closest('#scopenote b') !== null;
    if (isManaged && (/enduro_manual\.json|manual file|hand-entered|Endur.O part|source document/i.test(text)))
      out.push([el.dataset.fig, "managed figure's composite names Endur'O's hand-entered file (data/enduro_manual.json)", where]);
    if (sc.enduro && hasMad && /agg\(HP\)[^/]*\+\s*\(SCOPES\[SCOPE\]\.enduro\?ENDURO\.[\w.]+:0\)$/.test(el.dataset.fig) && !/\+.*=/.test(ar || ''))
      out.push([el.dataset.fig, "adds Endur'O but the arithmetic does not show MadAvance + Endur'O = total", where]);
  }
  return {scope: SCOPES[SCOPE].lab, checked: seen.size, fails: out};
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="file://" + os.path.join(REPO, "index.html"))
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    total, bad = 0, []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.goto(a.url, wait_until="load")
        pg.wait_for_timeout(1500)
        for s in SCOPES:
            r = pg.evaluate(JS, s)
            total += r["checked"]
            for f in r["fails"]:
                bad.append((r["scope"],) + tuple(f))
        b.close()
    print(f"  provenance: {total} figure panels built across {len(SCOPES)} scopes; {len(bad)} failure(s)")
    for x in (bad if a.list else bad[:25]):
        print("   ", " | ".join(str(y) for y in x))
    if len(bad) > 25 and not a.list:
        print(f"    ... {len(bad) - 25} more (--list)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
