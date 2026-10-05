# -*- coding: utf-8 -*-
"""Managed figures count only the managed portfolio (Adriaan Mol, 5 Oct 2026).

The investigation of 5 October found "876 water points in scope" and "271,710
people served" at All SaniTap scope: 745 managed hand pumps plus 131 Endur'O
programme sites from the hand-entered file, and 125,710 people from the SDWS 1
run plus 146,000 from the same file, a figure whose source is "not recorded".
None of the 131 has a status in data/piped_systems_status.json, so the join
rule of 25 September never saw them, and every gate checked only that the
hand-entered number was carried consistently.

This gate, called from tools/check_consistency.py, fails when:

  1. page code (outside the generated data blocks) adds ENDURO.systems,
     ENDURO.people, MF('systems') or MF('people') to anything: those figures
     are Endur'O programme figures and are not in the managed portfolio;
  2. in any scope, a figure showing ENDURO.systems / ENDURO.people (a data-fig
     or a data-manual span) stands outside the Endur'O card
     ([data-enduro-programme]);
  3. a "water points" managed figure ([data-q="points"]: the tile, the impact
     line, the partner table's portfolio column, and the scope note's lead
     figure) differs from the managed hand pumps in scope plus, where the scope
     covers Endur'O, the systems with status "managed" in
     data/piped_systems_status.json;
  4. a "people served" managed figure ([data-q="people"]) differs from the
     SDWS 1 run's allocation summed over the hand pumps in scope (WPOP, which
     check_consistency ties to the run's reported_after_cap), or shows a number
     where the scope has no allocated point, or does not say "not yet
     allocated" where a managed piped system in scope has no SDWS 1 figure;
  5. a managed figure reads an input whose source is recorded as "not
     recorded" (a hand-entered figure in data/enduro_manual.json).

  6. the people-served tiles do not add up across scopes: MadAvance - all must
     equal MadAvance excl. Marolinta + Marolinta only, and All SaniTap must
     equal MadAvance - all (the managed piped system is not yet allocated).

People served come from the SDWS 1 run in every scope, Marolinta included
(Adriaan Mol, 5 Oct 2026): check 4 applies to the Marolinta-only scope too.
That scope's water-points figure stands on the 2026 works records and is
labelled so; check 3 does not apply to it.

    python3 tools/check_managed.py        # print the results, exit 1 on a failure
"""
import json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOPES = ["all", "mad", "madx", "mar", "enduro"]
BANNED = re.compile(r"ENDURO\.(?:systems|people)\b|\bMF\(\s*['\"](?:systems|people)['\"]")
GENERATED = re.compile(r"/\* BEGIN GENERATED (\w[\w-]*) .*?/\* END GENERATED \1 \*/", re.S)


def _const(idx, name):
    m = re.search(r"const " + name + r"\s*=\s*", idx)
    if not m:
        return None
    dec = json.JSONDecoder()
    return dec.raw_decode(idx[m.end():])[0]


def static_hits(idx):
    """ENDURO.systems / ENDURO.people / MF('systems'|'people') in page code,
    the generated data blocks (derivations, datasets, the ENDURO block)
    excepted, and HTML outside the Endur'O card is checked in the browser."""
    hits = []
    for sm in re.finditer(r"<script\b[^>]*>(.*?)</script>", idx, re.S):
        code = GENERATED.sub("", sm.group(1))
        code = re.sub(r"^const (?:ENDURO|ENDURO_SRC|DERIV|DERIV_RULES)\s*=.*$", "", code, flags=re.M)
        for m in BANNED.finditer(code):
            line = code[:m.start()].count("\n")
            ctx = code[max(0, m.start() - 50):m.end() + 10].replace("\n", " ")
            hits.append(f"{m.group(0)} in script (…{ctx.strip()}…)")
            if len(hits) > 40:
                return hits
    return hits


JS = r"""(a) => {
  const [scope, exp] = a;
  const b = document.querySelector(`#scopebar button[data-s="${scope}"]`); if (b) b.click();
  const out = [], sc = SCOPES[SCOPE];
  const num = s => { const m = String(s).replace(/−/g,'-').match(/-?\d[\d,  ]*(?:\.\d+)?/); return m ? parseFloat(m[0].replace(/[,  ]/g,'')) : null; };
  const vis = el => el.getClientRects().length > 0;
  const hidden = el => { const s = el.closest('[data-scopes]'); return (s && !s.dataset.scopes.split(/\s+/).includes(scope)) || el.closest('[hidden]'); };
  const where = el => (el.closest('[id]') || {}).id || el.tagName;
  // 2. Endur'O programme figures only on the Endur'O card
  for (const el of document.querySelectorAll('[data-fig],[data-manual]')) {
    if (el.closest('script,template,.deriv') || hidden(el)) continue;
    const e = el.dataset.fig || '', mk = el.dataset.manual || '';
    if ((/ENDURO\.(systems|people)\b/.test(e) || /^(systems|people)$/.test(mk)) && !el.closest('[data-enduro-programme]'))
      out.push(['programme figure outside the Endur’O card', `${e || 'data-manual=' + mk} = ${el.textContent.trim()} in #${where(el)}`]);
  }
  // the managed figures: everything marked data-q points/people, and the
  // scope note's lead figure
  const managed = [...document.querySelectorAll('[data-q="points"],[data-q="people"]')].filter(el => !hidden(el) && !el.closest('.deriv'));
  const lead = document.querySelector('#scopenote b');
  // 5. no input whose source is not recorded
  for (const el of [...managed, ...(lead ? [lead] : [])]) {
    const exprs = [...el.querySelectorAll('[data-fig],[data-manual]')].map(x => x.dataset.fig || ('ENDURO.' + x.dataset.manual));
    if (el.dataset.fig) exprs.push(el.dataset.fig);
    for (const e of exprs) for (const m of e.matchAll(/ENDURO\.([\w.]+)/g)) {
      const src = exp.manual[m[1]];
      if (src && /not recorded/i.test(src)) out.push(['managed figure reads an input whose source is not recorded', `ENDURO.${m[1]} (${src.slice(0, 80)}) in #${where(el)}`]);
    }
  }
  const sites = SITEMAP[scope] || [];
  const pts = exp.pumps.filter(p => sites.includes(p.site));
  const wantPts = pts.length + (sc.enduro ? exp.piped_managed : 0);
  const wantPeople = pts.reduce((s, p) => s + (exp.wpop[p.wp] || 0), 0);
  const unalloc = sc.enduro && exp.piped_managed > 0;
  const shownVal = el => { const v = el.querySelector('.v,[data-v]') || el; return v.textContent.trim(); };
  for (const el of managed) {
    const t = shownVal(el), v = num(t), q = el.dataset.q, full = el.textContent;
    if (q === 'points' && scope === 'mar') continue;   // works basis, labelled so
    if (q === 'points') {
      if (v !== wantPts) out.push(['water points figure is not the managed portfolio', `#${where(el)} shows ${t}; managed hand pumps in scope ${pts.length} + managed piped systems ${sc.enduro ? exp.piped_managed : 0} = ${wantPts}`]);
    } else {
      if (pts.length && v !== wantPeople) out.push(['people served is not the SDWS 1 allocation for the points in scope', `#${where(el)} shows ${t}; SDWS 1 over ${pts.length} hand pumps = ${wantPeople}`]);
      if (!pts.length && v !== null) out.push(['people served shows a number with no allocated point in scope', `#${where(el)} shows ${t}`]);
      if (unalloc && !/not yet allocated/.test((el.closest('tr') || el).textContent)) out.push(['people served does not say the managed piped system is not yet allocated', `#${where(el)}: "${full.trim().slice(0, 90)}"`]);
    }
  }
  if (lead && scope !== 'mar' && num(lead.textContent) !== wantPts) out.push(['scope note lead figure is not the managed portfolio', `shows ${lead.textContent.trim()}; want ${wantPts}`]);
  if (!managed.some(el => el.dataset.q === 'points' && el.closest('#tiles'))) out.push(['no water points tile found', 'expected #tiles .tile[data-q=points]']);
  const tp = document.querySelector('#tiles [data-q="people"]');
  return {scope: sc.lab, managed: managed.length, out, tilePeople: tp ? num(shownVal(tp)) : null,
          want: {points: scope === 'mar' ? 'works basis' : wantPts, people: unalloc && !pts.length ? 'not yet allocated' : wantPeople}};
}"""


def expectations(idx):
    pumps = [{"wp": str(p["wp"]), "site": p.get("site")} for p in (_const(idx, "PUMPS") or []) if isinstance(p, dict)]
    wpop = {str(k): int(v[1]) for k, v in (_const(idx, "WPOP") or {}).items()}
    st = json.load(open(os.path.join(REPO, "data", "piped_systems_status.json"), encoding="utf8"))["systems"]
    man = json.load(open(os.path.join(REPO, "data", "enduro_manual.json"), encoding="utf8"))
    manual = {k: f"{f.get('supplied_by', '')}; {f.get('doc', '')}" for k, f in man.get("figures", {}).items()}
    return dict(pumps=pumps, wpop=wpop, manual=manual,
                piped_managed=sum(1 for s in st.values() if s.get("status") == "managed"))


def run(page=os.path.join(REPO, "index.html")):
    """-> list of (name, ok, expected, actual, note), as check_consistency's check()."""
    idx = open(page, encoding="utf8").read()
    exp = expectations(idx)
    res = []
    hits = static_hits(idx)
    res.append(("managed figures: no ENDURO.systems / ENDURO.people / MF in page code",
                not hits, "0 uses", f"{len(hits)} use(s)" + (": " + "; ".join(hits[:3]) if hits else ""),
                "Endur'O programme figures are not in the managed portfolio (Adriaan Mol, 5 Oct 2026)"))
    pc = _const(idx, "PIPEDWQ") or {}
    page_m = (pc.get("status_counts") or {}).get("managed")
    res.append(("managed piped systems on the page = status 'managed' in piped_systems_status.json",
                page_m == exp["piped_managed"], exp["piped_managed"], page_m, "PIPEDWQ.status_counts.managed"))
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        res.append(("managed figures: rendered check ran", False, "ran", "playwright missing",
                    "a gate that cannot run fails"))
        return res
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("file://" + os.path.abspath(page), wait_until="load")
        pg.wait_for_timeout(1500)
        tiles = {}
        for s in SCOPES:
            r = pg.evaluate(JS, [s, exp])
            tiles[s] = r.get("tilePeople")
            by = {}
            for name, detail in r["out"]:
                by.setdefault(name, []).append(detail)
            want = r.get("want") or {}
            res.append((f"managed figures, scope {r['scope']}: {r['managed']} figure(s) checked",
                        not r["out"], f"points {want.get('points', '—')}, people {want.get('people', '—')}"
                        if want else r.get("note", ""),
                        "ok" if not r["out"] else f"{len(r['out'])} failure(s)",
                        " | ".join(f"{k}: {'; '.join(v[:2])}" + (f" (+{len(v) - 2})" if len(v) > 2 else "")
                                   for k, v in by.items())[:600] or (r.get("note") or "")))
        b.close()
    add = tiles.get("madx") is not None and tiles.get("mar") is not None and tiles.get("mad") == tiles["madx"] + tiles["mar"]
    res.append(("people served adds up: MadAvance - all = excl. Marolinta + Marolinta only", add,
                f"{tiles.get('madx')} + {tiles.get('mar')}", tiles.get("mad"), "the people-served tiles of the three scopes"))
    res.append(("people served adds up: All SaniTap = MadAvance - all (the kiosk not yet allocated)",
                tiles.get("all") == tiles.get("mad"), tiles.get("mad"), tiles.get("all"), ""))
    res.append(("managed figures: page loads without script errors", not errs, "none", "; ".join(errs[:2]) or "none", ""))
    return res


def main():
    bad = 0
    for name, ok, exp, act, note in run():
        bad += not ok
        print(f"  {'PASS' if ok else 'FAIL !'}  {name}\n          expected {exp} | actual {act}" + (f"\n          {note}" if note else ""))
    print(f"  managed figures: {bad} failure(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
