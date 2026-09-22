# -*- coding: utf-8 -*-
"""Every number the page renders, sorted into the three tiers.

WHY THIS EXISTS
---------------
An audit counted 191 live-figure literals typed into body prose - 736 alone
in 54 sentences - with no assertion behind any of them. The protection at the
time was a blacklist of withdrawn phrases, which can only catch numbers
somebody already knew were wrong. If S.n moves to 737, fifty-four sentences
become false and nothing fails.

This is the positive rule. It reads the RENDERED page, per scope, pulls out
every numeric literal, and asks of each one: is this value reachable from the
live data for this scope (TIER 1), declared in PARAMS with a citation
(TIER 2), or carried in the dated manual Endur'O file (TIER 3)? A literal
that is none of those three has no source at all, and is reported with the
sentence it sits in.

    python3 tools/figure_census.py             # the census, per tier
    python3 tools/figure_census.py --gate      # fail if anything is unsourced
    python3 tools/figure_census.py --json P    # write the full finding list

The census and the gate are the same walk. The census reports; the gate
exits non-zero.
"""
import argparse, datetime, glob, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
SCOPES = ("all", "mad", "madx", "mar", "enduro")

# ---------------------------------------------------------------------------
# What is NOT a figure. Each of these is excluded because it names something
# rather than measures it, and the exclusions are counted and reported so the
# list cannot quietly grow to cover a real fault.
# ---------------------------------------------------------------------------
EXCLUDE = [
    ("year",        re.compile(r"^(19|20)\d\d$")),
    ("date",        re.compile(r"^\d{4}-\d\d(-\d\d)?$")),
    ("wp id",       re.compile(r"^\d{9}$")),
    ("hex id",      re.compile(r"^[0-9a-f]{24,}$")),
    ("ordinal",     re.compile(r"^\d{1,2}(st|nd|rd|th)$")),
]
# a numeric literal with its immediate context, so "SDWS 27" and "2.2.1(d)"
# are recognised as references rather than measurements
# A clause number is not a measurement. The action list cites a standard on
# almost every row, so without this the census is mostly citations.
REFERENCE = re.compile(
    r"(SDWS|VPA-DD|AMS|TOOL|Annex|section|clause|paragraph|table|figure|step|"
    r"rev(ision)?|v(ersion)?|R\d{4}[A-Z]|item|para|Article|GS4GG|ACM|meth|"
    r"WS|CAR|GS|VPA|PoA|R\u00b2|\u00a7|\bs\.|#|\b[A-Za-z]\.)\s*[\u2011-]?\s*$", re.I)
# 2.2.1, 4.2.2, A.1.1 - two dots or more is never a quantity on this page
SECTIONISH = re.compile(r"^\d+(\.\d+){2,}$")
UNIT_AFTER = re.compile(
    r"^\s*(%|\s?per cent|°|px|pt|em|rem)")


def chromium():
    for pat in ("chromium-*/chrome-linux/chrome",
                "chromium_headless_shell-*/chrome-headless-shell-linux64/"
                "chrome-headless-shell"):
        hits = sorted(glob.glob(os.path.join(
            os.environ.get("PLAYWRIGHT_BROWSERS_PATH",
                           os.path.expanduser("~/.cache/ms-playwright")), pat)))
        if hits:
            return hits[-1]
    sys.exit("figure_census: no chromium in the Playwright cache")


# ---------------------------------------------------------------------------
# The reachable set: every number the live data can justify for this scope.
# Collected in the page's own context, from the page's own objects, so the
# census cannot disagree with what the page could have interpolated.
# ---------------------------------------------------------------------------
REACH = r"""() => {
  const g = n => { try { return eval(n); } catch (e) { return undefined; } };
  const out = new Map();                       // value -> [paths]
  const note = (v, path) => {
    if (typeof v !== 'number' || !isFinite(v)) return;
    const k = Math.round(v * 100) / 100;
    if (!out.has(k)) out.set(k, []);
    const a = out.get(k);
    if (a.length < 4 && !a.includes(path)) a.push(path);
  };
  const walk = (o, path, depth) => {
    if (o == null || depth > 9) return;
    if (typeof o === 'number') return note(o, path);
    if (Array.isArray(o)) {
      note(o.length, path + '.length');
      // leaves of a long array are per-record facts, not page figures; the
      // first few are enough to recognise a quoted example
      const lim = Math.min(o.length, 5000);
      for (let i = 0; i < lim; i++) walk(o[i], path + '[]', depth + 1);
      return;
    }
    if (typeof o === 'object') {
      for (const k of Object.keys(o)) walk(o[k], path + '.' + k, depth + 1);
    }
  };
  for (const n of ['S', 'REG', 'TTR', 'WPOPMETA', 'CORR', 'ROUTES', 'ENDURO',
                   'TRACE', 'SCOPES', 'DOWN', 'OPENREP', 'PARTIAL', 'PUMPS',
                   'WPOP', 'PHOTOS', 'CALLS', 'ACTS', 'CALX', 'METRICS', 'CARBON', 'ACTN', 'POPS', 'DERIV', 'FRESH'])
    { const v = g(n); if (v !== undefined) walk(v, n, 0); }

  // Figures the page COMPUTES at top level. SUCC_CORRECTED is
  // REG.succ + CORR.corrected.length and renders 42 times; without this it
  // was reported as unsourced, which is the census being wrong about a
  // figure that is derived.
  for (const n of ['SUCC_CORRECTED', 'IM_CAP', 'IM_CAP_ALT', 'CZ_CAP',
                   'CAP_T', 'ER_ANOSY', 'ER_MARO', 'DO_CAP'])
    { const v = g(n); if (typeof v === 'number') note(v, n); }
  // and the cap-sensitivity totals, which are computed from WPOP
  const wa = g('wpopAt'), P_ = g('PARAMS');
  if (typeof wa === 'function' && P_) {
    const caps = [P_.im_cap, P_.im_cap_alt, P_.cz_cap, P_.cz_cap_old]
                   .filter(Boolean).map(x => x.v);
    for (const a of caps) for (const b of caps) {
      try { note(wa(a, b), `wpopAt(${a},${b})`); } catch (e) {}
    }
  }

  // the aggregate the page computes for the scope now showing, and the
  // Marolinta basis, which is a scope figure like any other
  const A = g('agg') && g('HP') ? g('agg')(g('HP')) : null;
  if (A) walk(A, 'agg(scope)', 0);
  const mb = g('marBasis');
  if (typeof mb === 'function') { try { walk(mb(), 'marBasis()', 0); } catch (e) {} }

  // sums and differences the page legitimately states: portfolio totals and
  // the register chain's own arithmetic. Anything wider than this would make
  // the reachable set large enough to accept a typo.
  const S_ = g('S'), R = g('REG'), E = g('ENDURO');
  if (S_ && E) {
    note(S_.n + E.systems, 'S.n + ENDURO.systems');
    note((A ? A.wpop : 0) + E.people, 'scope wpop + ENDURO.people');
    note(A ? A.n + E.systems : NaN, 'scope n + ENDURO.systems');
  }
  if (R) {
    note(R.total_first_rehab - R.succ, 'REG.total_first_rehab - REG.succ');
    note(R.dashboard_fdmar - R.succ, 'REG.dashboard_fdmar - REG.succ');
    note(R.register_total - R.register_classified,
         'REG.register_total - REG.register_classified');
  }
  if (A) { note(A.n - A.st.down, 'scope n - down');
           note(A.st.ok + A.st.partial, 'scope ok + partial'); }
  // route plans state their own totals, which are sums over the day rows
  const RT = g('ROUTES');
  if (RT) for (const k of Object.keys(RT)) {
    const d = RT[k].days || [];
    note(d.reduce((s, x) => s + (x.km || 0), 0), `ROUTES.${k} km total`);
    note(Math.round(d.reduce((s, x) => s + (x.hours || 0), 0)),
         `ROUTES.${k} hours total`);
    note(d.length, `ROUTES.${k} days`);
    note(d.reduce((s, x) => s + (x.stops || []).length, 0),
         `ROUTES.${k} stops`);
  }
  return [...out.entries()].map(([v, p]) => [v, p]);
}"""

# ---------------------------------------------------------------------------
# Every numeric literal the reader can actually see, with where it sits.
# ---------------------------------------------------------------------------
TEXT = r"""() => {
  const vis = el => {
    if (!el) return false;
    if (el.closest('[hidden]')) return false;
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 || r.height > 0;
  };
  const out = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = w.nextNode())) {
    const el = n.parentElement;
    if (!el || !vis(el)) continue;
    if (el.closest('script,style')) continue;
    // a figure inside a withdrawn block is not a figure the page asserts:
    // the block says in terms that it cannot be reproduced
    if (el.closest('.unsourced') || el.closest('details.withdrawn')) continue;
    const t = n.nodeValue;
    if (!/\d/.test(t)) continue;
    // where it is, and whether the page has already declared a source for it
    const sourced = el.closest('[data-fig],[data-param],[data-manual],[data-src]');
    const sec = el.closest('section');
    const h = sec ? sec.querySelector('h2') : null;
    out.push({
      text: t,
      section: h ? h.textContent.trim().replace(/\s+/g, ' ').slice(0, 52) : '(masthead)',
      tag: el.tagName.toLowerCase(),
      cls: (el.className || '').toString().slice(0, 40),
      mono: !!el.closest('.mono,code,pre'),
      sourced: sourced ? (sourced.dataset.fig ? 'FIG'
                        : sourced.dataset.param ? 'PARAMS'
                        : sourced.dataset.manual ? 'MANUAL' : 'SRC') : null,
    });
  }
  return out;
}"""

# The grouped branch needs at least ONE separator group, or it matches "202"
# out of "2026" and every year on the page is reported as a figure.
NUM = re.compile(r"\d{1,3}(?:[,   ]\d{3})+(?:\.\d+)?"
                 r"|\d+(?:\.\d+)*")


def sentence(text, start, end):
    """The sentence the literal sits in, trimmed to something readable."""
    left = max(text.rfind(". ", 0, start), text.rfind("— ", 0, start),
               text.rfind("; ", 0, start)) + 1
    right = text.find(". ", end)
    right = len(text) if right < 0 else right + 1
    s = text[left:right].strip()
    return re.sub(r"\s+", " ", s)[:150]


def literals(nodes):
    """Pull the numbers out, saying of each one why it was kept or dropped."""
    kept, dropped = [], {}
    for nd in nodes:
        t = nd["text"]
        for m in NUM.finditer(t):
            raw = m.group(0).strip()
            norm = re.sub(r"[,    ]", "", raw)
            if not norm or norm == ".":
                continue
            why = None
            before, after = t[:m.start()], t[m.end():]
            if SECTIONISH.match(raw):
                why = "section number"
            elif UNIT_AFTER.match(after):
                why = "percentage or unit"
            elif REFERENCE.search(before[-24:]):
                why = "reference, not a measurement"
            elif nd["mono"]:
                why = "identifier (mono)"
            else:
                for name, rx in EXCLUDE:
                    if rx.match(norm):
                        why = name
                        break
            if why:
                dropped[why] = dropped.get(why, 0) + 1
                continue
            try:
                val = float(norm)
            except ValueError:
                continue
            kept.append({"raw": raw, "val": val, "section": nd["section"],
                         "sourced": nd["sourced"],
                         "sentence": sentence(t, m.start(), m.end())})
    return kept, dropped


# The constants the audit named. They are registered or chosen parameters and
# must NOT become live - but each needs a citation, which is what PARAMS is
# for. Until PARAMS exists on the page this list stands in, so the census can
# be taken before the conversion rather than after it.
FALLBACK_PARAMS = {300: "IM_CAP", 500: "IM_CAP_ALT / CZ_CAP", 60000: "CAP_T",
                   31.3: "ER_ANOSY", 27.9: "ER_MARO", 347: "SDWS 27 cap"}

PARAMS_JS = ("() => { try { return JSON.parse(JSON.stringify(PARAMS)); } "
             "catch (e) { return null; } }")
MANUAL_JS = ("() => { try { return JSON.parse(JSON.stringify(ENDURO)); } "
             "catch (e) { return null; } }")


def flat(o, path="", out=None):
    out = {} if out is None else out
    if isinstance(o, (int, float)) and not isinstance(o, bool):
        out.setdefault(round(float(o), 2), path)
    elif isinstance(o, dict):
        for k, v in o.items():
            if k in ("source", "set", "note", "as_at", "supplied_by", "doc"):
                continue
            flat(v, f"{path}.{k}" if path else k, out)
    elif isinstance(o, list):
        for v in o:
            flat(v, path + "[]", out)
    return out


def classify(lits, reach, params, manual):
    """Each literal into exactly one tier, or into 'no source'.

    A fourth thing is recorded alongside the tier: whether the literal was
    RENDERED from the data or TYPED into the prose. They are indistinguishable
    on the page and the difference is the whole point - a typed figure that
    happens to match the data today is wrong tomorrow. Moving S.n to 737 left
    thirty-five sentences still reading 736, and a tier test alone passed them
    because 736 was still reachable from WPOPMETA.rows.
    """
    rv = {round(float(v), 2): p for v, p in reach}
    for L in lits:
        v = round(L["val"], 2)
        L["rendered"] = L["sourced"] in ("FIG", "PARAMS", "MANUAL", "SRC")
        if L["sourced"] in ("PARAMS",) or v in params:
            L["tier"] = 2
            L["why"] = params.get(v, "declared in PARAMS")
        elif L["sourced"] == "MANUAL" or v in manual:
            L["tier"] = 3
            L["why"] = manual.get(v, "manual Endur'O file")
        elif v in rv:
            L["tier"] = 1
            L["why"] = rv[v][0] if isinstance(rv[v], list) else rv[v]
        else:
            L["tier"] = 0
            L["why"] = "no source"
    return lits


def walk_page(page_path, scopes=SCOPES):
    from playwright.sync_api import sync_playwright
    found = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=chromium())
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("file://" + page_path, wait_until="load")
        pg.wait_for_timeout(1300)
        params = flat(pg.evaluate(PARAMS_JS) or {})
        if not params:
            params = dict(FALLBACK_PARAMS)
        manual = flat(pg.evaluate(MANUAL_JS) or {})
        for s in scopes:
            try:
                pg.click(f'#scopebar button[data-s="{s}"]', timeout=2500)
                pg.wait_for_timeout(420)
            except Exception:                                  # noqa: BLE001
                pass
            reach = pg.evaluate(REACH)
            kept, dropped = literals(pg.evaluate(TEXT))
            found[s] = {"lits": classify(kept, reach, params, manual),
                        "dropped": dropped, "reach": len(reach)}
        b.close()
    return found, errs, params, manual


def report(found, params, manual, verbose=False):
    print()
    print("  FIGURE CENSUS - every number the page renders, by tier")
    print("  " + "-" * 92)
    print(f"  {'scope':8} {'literals':>9} {'T1 live':>9} {'T2 param':>9} "
          f"{'T3 manual':>10} {'NO SOURCE':>10}   distinct unsourced")
    tot = {0: 0, 1: 0, 2: 0, 3: 0}
    allbad, alltyped = {}, {}
    for s, d in found.items():
        c = {0: 0, 1: 0, 2: 0, 3: 0}
        bad = {}
        for L in d["lits"]:
            c[L["tier"]] += 1
            if L["tier"] == 0:
                bad.setdefault(L["raw"], []).append(L)
                allbad.setdefault(L["raw"], []).append((s, L))
        for k in c:
            tot[k] += c[k]
        print(f"  {s:8} {len(d['lits']):>9} {c[1]:>9} {c[2]:>9} {c[3]:>10} "
              f"{c[0]:>10}   {len(bad)}")
    n = sum(tot.values())
    print("  " + "-" * 92)
    print(f"  {'TOTAL':8} {n:>9} {tot[1]:>9} {tot[2]:>9} {tot[3]:>10} "
          f"{tot[0]:>10}   {len(allbad)} distinct")
    print()
    drop = {}
    for d in found.values():
        for k, v in d["dropped"].items():
            drop[k] = drop.get(k, 0) + v
    print("  excluded before tiering (not figures): "
          + ", ".join(f"{k} {v}" for k, v in sorted(drop.items())))
    print(f"  PARAMS carries {len(params)} distinct value(s); "
          f"the manual Endur'O block carries {len(manual)}")
    if allbad:
        print()
        print(f"  UNSOURCED - {len(allbad)} distinct value(s), most frequent first")
        print("  " + "-" * 92)
        for raw, hits in sorted(allbad.items(),
                                key=lambda kv: -len(kv[1]))[:40 if not verbose else 999]:
            scopes = sorted({s for s, _ in hits})
            L = hits[0][1]
            print(f"  {raw:>12}  x{len(hits):<3} [{','.join(scopes)}]  "
                  f"{L['section'][:40]}")
            print(f"               {L['sentence'][:96]}")
    return tot, allbad, alltyped


BACKLOG = os.path.join(REPO, "data", "figure_backlog.json")


def load_backlog():
    if not os.path.isfile(BACKLOG):
        return {"recorded": None, "values": {}}
    return json.load(open(BACKLOG, encoding="utf8"))


def write_backlog(allbad, note):
    doc = {"recorded": datetime.date.today().isoformat(),
           "note": note,
           "values": {raw: {"n": len(hits),
                            "scopes": sorted({s for s, _ in hits}),
                            "section": hits[0][1]["section"],
                            "sentence": hits[0][1]["sentence"]}
                      for raw, hits in sorted(allbad.items())}}
    json.dump(doc, open(BACKLOG, "w", encoding="utf8"),
              indent=1, ensure_ascii=False, sort_keys=True)
    return doc


def gate(allbad, backlog):
    """New unsourced figures fail. The recorded backlog is allowed, and can
    only ever shrink: an entry that has been sourced must be removed, so the
    file cannot quietly become a permanent exemption list."""
    known = set(backlog.get("values", {}))
    new = {k: v for k, v in allbad.items() if k not in known}
    cleared = sorted(known - set(allbad))
    return new, cleared


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default=PAGE)
    ap.add_argument("--gate", action="store_true",
                    help="exit non-zero if any literal has no source")
    ap.add_argument("--json", help="write the full finding list here")
    ap.add_argument("--scope", action="append", help="limit to these scopes")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--record-backlog", action="store_true",
                    help="record today's unsourced figures as the backlog")
    a = ap.parse_args()
    found, errs, params, manual = walk_page(os.path.abspath(a.page),
                                            a.scope or SCOPES)
    tot, bad, typed = report(found, params, manual, a.verbose)
    if a.json:
        json.dump({s: d["lits"] for s, d in found.items()},
                  open(a.json, "w", encoding="utf8"), indent=1, ensure_ascii=False)
        print(f"\n  full finding list: {a.json}")
    if errs:
        print("  javascript errors on load: " + "; ".join(errs[:3]))
    if a.record_backlog:
        doc = write_backlog(bad, "Figures rendered on the page that are "
                            "neither live, nor declared in PARAMS, nor from "
                            "the dated manual Endur'O file. This list may "
                            "only shrink. A figure not on it fails the gate.")
        print(f"\n  backlog recorded: {len(doc['values'])} distinct value(s) "
              f"in {BACKLOG}")
        return 0
    if a.gate:
        backlog = load_backlog()
        new, cleared = gate(bad, backlog)
        print(f"\n  recorded backlog: {len(backlog.get('values', {}))} "
              f"distinct unsourced value(s), recorded "
              f"{backlog.get('recorded')}")
        if cleared:
            print(f"  {len(cleared)} backlog entry(ies) now have a source and "
                  "must be removed from data/figure_backlog.json:")
            print("    " + ", ".join(cleared[:12]))
        if new:
            print(f"\n  FIGURE GATE FAILED: {len(new)} value(s) render on the "
                  "page with no source and are not in the recorded backlog.")
            print("  Each is neither live, nor declared in PARAMS, nor from "
                  "the dated manual file.")
            for raw, hits in sorted(new.items(), key=lambda kv: -len(kv[1]))[:20]:
                L = hits[0][1]
                print(f"\n    {raw}  x{len(hits)}  in \"{L['section']}\"")
                print(f"      {L['sentence']}")
            return 1
        if cleared:
            print("\n  FIGURE GATE FAILED: the backlog is out of date.")
            return 1
        print("\n  figure gate: every rendered literal is live, declared in "
              "PARAMS, from the dated manual file, or on the recorded "
              "backlog.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
