# -*- coding: utf-8 -*-
"""Enforce the formatting and readability rule on the rendered report.

The rule is Adriaan Mol's, 28 Sep 2026, and is written out in CONTRIBUTING.md
("Formatting and readability"). This loads index.html in headless Chromium
at 1366 px and 390 px, in the light and the dark theme, opens every collapsed
block and the by-owner view so every table is on screen, and asserts:

  * every table is fixed-layout with a colgroup (table-layout: fixed);
  * number columns are right-aligned, do not wrap and are not clipped;
  * at 1366 px no text column is narrower than MIN_TEXT px;
  * a table over 12 visible rows sits in a scroll box no taller than 60vh,
    with a sticky header and a "N lignes - faites defiler" line above it
    giving the right N;
  * the page never scrolls sideways, at 1366 px or at 390 px;
  * header and body text keep a contrast of at least 4.5:1 in both themes.

It lists every table with its narrowest text column, and writes a screenshot
of each table in each theme to --shots (default: a temporary directory), so
the themes are checked on real renders, not on CSS.

    ~/sdws1/venv/bin/python tools/test_readability.py [--shots DIR] [--only ID]

Exit 0 when every rule holds, 1 otherwise. Run by tools/publish.sh.
A column is numeric when its header is th.num or more than 60% of its body
cells are td.num - the same test layoutTables() uses on the page.
"""
import argparse, functools, http.server, os, sys, tempfile, threading

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_TEXT = 110
MAX_ROWS = 12

MEASURE = r"""(minText)=>{
  const out=[];
  const lum=c=>{const m=c.match(/[\d.]+/g); if(!m) return null; const [r,g,b]=m.slice(0,3).map(Number).map(v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)}); return {L:.2126*r+.7152*g+.0722*b, a:m.length>3?+m[3]:1};};
  const bgOf=el=>{for(let e=el;e;e=e.parentElement){const c=getComputedStyle(e).backgroundColor; const l=lum(c); if(l&&l.a>0.5) return l.L;} return 1;};
  const contrast=el=>{if(!el) return null; const f=lum(getComputedStyle(el).color); if(!f) return null; const b=bgOf(el); const [hi,lo]=f.L>b?[f.L,b]:[b,f.L]; return (hi+.05)/(lo+.05);};
  const tables=[...document.querySelectorAll('table')];
  tables.forEach((t,i)=>{
    const r=t.getBoundingClientRect(); if(!(r.width>0&&r.height>0)) return;
    const rows=[...t.rows]; let n=0; for(const row of rows){let k=0; for(const c of row.cells) k+=c.colSpan||1; n=Math.max(n,k);}
    const ref=rows.find(row=>row.cells.length===n&&[...row.cells].every(c=>(c.colSpan||1)===1));
    const isNum=ci=>{let a=0,m=0; for(const row of rows){ if(row.cells.length<=ci) continue; const c=row.cells[ci]; if((c.colSpan||1)>1) continue;
       if(c.tagName==='TH'){ if(c.classList.contains('num')) return true; continue; } m++; if(c.classList.contains('num')) a++; } return m>0&&a/m>0.6;};
    const widths=ref?[...ref.cells].map(c=>c.getBoundingClientRect().width):[];
    const head=t.tHead?[...t.tHead.rows[t.tHead.rows.length-1].cells].map(c=>c.textContent.trim().slice(0,24)):[];
    const txt=[],numBad=[];
    for(let ci=0;ci<n;ci++){
      if(isNum(ci)){
        for(const row of rows){ const c=row.cells[ci]; if(!c||c.tagName!=='TD'||(c.colSpan||1)>1||!c.classList.contains('num')) continue;
          const cs=getComputedStyle(c);
          if(cs.textAlign!=='right'&&cs.textAlign!=='end') {numBad.push(`col ${ci+1} not right-aligned`); break;}
          if(cs.whiteSpace!=='nowrap'&&cs.whiteSpace!=='pre') {numBad.push(`col ${ci+1} wraps`); break;}
          if(c.scrollWidth>c.clientWidth+2) {numBad.push(`col ${ci+1} clipped (${c.scrollWidth}>${c.clientWidth})`); break;}
        }
      } else if(widths.length) txt.push([Math.round(widths[ci]),head[ci]||('col '+(ci+1))]);
    }
    txt.sort((a,b)=>a[0]-b[0]);
    const box=t.closest('.tablewrap,.tablescroll')||t.parentElement, bs=getComputedStyle(box);
    const vis=[...t.tBodies].reduce((a,b)=>a+[...b.rows].filter(x=>x.getBoundingClientRect().height>0).length,0);
    const cap=box.previousElementSibling&&box.previousElementSibling.classList.contains('tcount')?box.previousElementSibling.textContent:'';
    const th=t.querySelector('thead th');
    out.push({i, id:t.id||t.dataset.table||'', section:(t.closest('section[id]')||{}).id||'', n, rows:vis,
      fixed:getComputedStyle(t).tableLayout==='fixed', colgroup:!!t.querySelector(':scope>colgroup'),
      narrow:txt.length?txt[0]:null, numBad,
      boxMax:bs.maxHeight, boxOverflow:bs.overflowY, boxH:box.getBoundingClientRect().height,
      sticky:th?getComputedStyle(th).position:'', cap,
      cHead:contrast(th), cBody:contrast(t.querySelector('tbody td'))});
  });
  return out;
}"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def run(args):
    from playwright.sync_api import sync_playwright
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=REPO))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/index.html"
    shots = args.shots or tempfile.mkdtemp(prefix="readability-")
    os.makedirs(shots, exist_ok=True)
    fails, listing = [], {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for scheme in ("light", "dark"):
            for width in (1366, 390):
                pg = b.new_page(viewport={"width": width, "height": 900})
                pg.emulate_media(color_scheme=scheme)
                errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto(url)
                pg.wait_for_function("typeof layoutTables==='function'")
                pg.wait_for_timeout(1500)
                pg.evaluate("document.querySelectorAll('details').forEach(d=>d.open=true)")
                pg.wait_for_timeout(600)
                views = [("default", None), ("by owner", "#av-owner")]
                for view, btn in views:
                    if btn and pg.locator(btn).count():
                        pg.click(btn)
                        pg.wait_for_timeout(600)
                    pg.evaluate("layoutTables()")
                    pg.wait_for_timeout(300)
                    vh = pg.evaluate("innerHeight")
                    sw = pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")
                    tag = f"{scheme} {width}px {view}"
                    if sw[0] > sw[1] + 1:
                        fails.append(f"{tag}: the page scrolls sideways ({sw[0]} > {sw[1]} px)")
                    for t in pg.evaluate(MEASURE, MIN_TEXT):
                        name = t["id"] or f"#{t['i']} in {t['section'] or '?'}"
                        if args.only and args.only != t["id"]:
                            continue
                        where = f"{tag}: table {name}"
                        if not (t["fixed"] and t["colgroup"]):
                            fails.append(f"{where}: not fixed-layout with a colgroup")
                        for m in t["numBad"]:
                            fails.append(f"{where}: number {m}")
                        if width == 1366 and t["narrow"] and t["narrow"][0] < MIN_TEXT - 0.5:
                            fails.append(f"{where}: text column '{t['narrow'][1]}' is {t['narrow'][0]} px (< {MIN_TEXT})")
                        if t["rows"] > MAX_ROWS:
                            mh = t["boxMax"]
                            ok_h = mh.endswith("px") and float(mh[:-2]) <= 0.6 * vh + 2
                            if not ok_h or t["boxOverflow"] not in ("auto", "scroll"):
                                fails.append(f"{where}: {t['rows']} rows but no 60vh scroll box (max-height {mh}, overflow {t['boxOverflow']})")
                            if t["sticky"] != "sticky":
                                fails.append(f"{where}: header is not sticky")
                            if t["cap"] != f"{t['rows']} lignes — faites défiler":
                                fails.append(f"{where}: caption is {t['cap']!r}, want '{t['rows']} lignes — faites défiler'")
                        for k, v in (("header", t["cHead"]), ("body", t["cBody"])):
                            if v is not None and v < 4.5:
                                fails.append(f"{where}: {k} text contrast {v:.2f}:1 (< 4.5)")
                        if width == 1366:
                            listing.setdefault((view, name), {})[scheme] = t
                            if not args.no_shots:
                                el = pg.locator("table").nth(t["i"])
                                box = el.locator("xpath=ancestor::div[contains(@class,'tablewrap') or contains(@class,'tablescroll')][1]")
                                target = box if box.count() else el
                                safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
                                try:
                                    target.screenshot(path=os.path.join(shots, f"{safe}_{view.replace(' ', '-')}_{scheme}.png"))
                                except Exception:
                                    pass
                    if errs:
                        fails.append(f"{tag}: page error {errs[0][:100]}")
                pg.close()
        b.close()
    srv.shutdown()
    print(f"  {'table':34s} {'view':9s} {'rows':>5s} {'cols':>4s}  narrowest text column at 1366 px")
    for (view, name), by in sorted(listing.items(), key=lambda x: (x[0][0], x[0][1])):
        t = by.get("light") or by.get("dark")
        nw = f"{t['narrow'][0]} px ({t['narrow'][1]})" if t["narrow"] else "no text column"
        print(f"  {name[:34]:34s} {view:9s} {t['rows']:5d} {t['n']:4d}  {nw}")
    print(f"\n  {len(listing)} tables measured; screenshots in {shots}")
    if fails:
        print(f"\n  READABILITY RULE BROKEN - {len(fails)} finding(s):")
        for f in fails[:80]:
            print("   ", f)
        return 1
    print("  readability rule: every table holds, in both themes, at 1366 px and 390 px")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=None)
    ap.add_argument("--only", default=None)
    ap.add_argument("--no-shots", action="store_true")
    sys.exit(run(ap.parse_args()))
