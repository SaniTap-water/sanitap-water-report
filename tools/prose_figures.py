# -*- coding: utf-8 -*-
"""No number may be TYPED into the body prose. The source gate.

tools/figure_census.py reads the rendered page and asks whether each number
has a source. It cannot ask the other question - was this typed, or rendered
from the data? - because a JavaScript-built table and a hand-typed sentence
look identical in the DOM.

The source can answer it exactly. A rendered figure is written
<span data-fig="S.n"></span>, which carries no digits at all. So every digit
left in the body prose is, by definition, typed by hand. That is the rule:

  a figure with an mWater source is interpolated,
  a parameter is declared in PARAMS with its citation,
  a hand-entered figure lives in a dated manual file with an owner,
  and nothing else may appear as a number on the page.

Moving S.n from 736 to 737 left thirty-five sentences reading 736 and the
census still passed them, because 736 remained reachable from WPOPMETA.rows.
This catches them, because they are typed - whatever their value.

    python3 tools/prose_figures.py                 # the worklist
    python3 tools/prose_figures.py --gate          # fail on anything new
    python3 tools/prose_figures.py --record        # record today's backlog
"""
import datetime, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
BACKLOG = os.path.join(REPO, "data", "prose_figure_backlog.json")

NOT_PROSE = [
    re.compile(r"<script\b[^>]*>.*?</script>", re.S),
    re.compile(r"<style\b[^>]*>.*?</style>", re.S),
    re.compile(r"<!--.*?-->", re.S),
    re.compile(r'<span class="mono">[^<]*</span>'),
    re.compile(r"<[a-zA-Z/][^>]*>"),
]
# the same exclusions the census uses: a citation is not a measurement
# The grouped branch needs at least ONE separator group, or it matches "202"
# out of "2026" and every year on the page is reported as a figure.
NUM = re.compile(r"\d{1,3}(?:[,   ]\d{3})+(?:\.\d+)?"
                 r"|\d+(?:\.\d+)*")
REFERENCE = re.compile(
    r"(SDWS|VPA-DD|AMS|TOOL|Annex|section|clause|paragraph|table|figure|step|"
    r"rev(ision)?|v(ersion)?|R\d{4}[A-Z]|item|para|Article|GS4GG|ACM|meth|"
    r"WS|CAR|GS|§|\bs\.|#|\b[A-Za-z]\.)\s*[‑-]?\s*$", re.I)
SECTIONISH = re.compile(r"^\d+(\.\d+){2,}$")
UNIT_AFTER = re.compile(r"^\s*(%|\s?per cent|°)")
EXCLUDE = [("year", re.compile(r"^(19|20)\d\d$")),
           ("date", re.compile(r"^\d{4}-\d\d(-\d\d)?$")),
           ("wp id", re.compile(r"^\d{9}$")),
           ("ordinal", re.compile(r"^\d{1,2}(st|nd|rd|th)$"))]


def prose_spans(html):
    """The byte ranges that ARE body prose."""
    bad = []
    for rx in NOT_PROSE:
        bad += [(m.start(), m.end()) for m in rx.finditer(html)]
    bad.sort()
    out, cur = [], 0
    for a, b in bad:
        if a > cur:
            out.append((cur, a))
        cur = max(cur, b)
    if cur < len(html):
        out.append((cur, len(html)))
    return out


def scan(page=PAGE):
    html = open(page, encoding="utf8").read()
    lines = [0]
    for ch in html:
        lines.append(lines[-1] + (1 if ch == "\n" else 0))
    hits, dropped = [], {}
    for a, b in prose_spans(html):
        seg = html[a:b]
        if not seg.strip():
            continue
        for m in NUM.finditer(seg):
            raw = m.group(0)
            norm = re.sub(r"[,   ]", "", raw)
            why = None
            before, after = seg[:m.start()], seg[m.end():]
            if SECTIONISH.match(raw):
                why = "section number"
            elif UNIT_AFTER.match(after):
                why = "percentage"
            elif REFERENCE.search(before[-24:]):
                why = "reference"
            else:
                for nm, rx in EXCLUDE:
                    if rx.match(norm):
                        why = nm
                        break
            if why:
                dropped[why] = dropped.get(why, 0) + 1
                continue
            # the sentence, not the text run. Prose is chopped into short
            # runs by <b> and <span>, so a window inside the run says
            # "736 of 736" and tells nobody where to look. Take the window
            # from the whole file and strip the tags out of it.
            at = a + m.start()
            wide = html[max(0, at - 220):at + 220]
            ctx = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", wide)).strip()
            hits.append({"raw": raw, "line": lines[at] + 1,
                         "ctx": ctx[:220]})
    return hits, dropped


def main():
    hits, dropped = scan()
    by = {}
    for h in hits:
        by.setdefault(h["raw"], []).append(h)
    print()
    print(f"  TYPED INTO BODY PROSE - {len(hits)} literal(s), "
          f"{len(by)} distinct value(s)")
    print("  excluded as not-figures: "
          + ", ".join(f"{k} {v}" for k, v in sorted(dropped.items())))
    if "--record" in sys.argv:
        doc = {"recorded": datetime.date.today().isoformat(),
               "note": "Numbers still typed into the body prose of index.html. "
                       "Every one of these should become a data-fig span, a "
                       "PARAMS entry, or a figure in a dated manual file. "
                       "This list may only shrink: tools/prose_figures.py "
                       "--gate fails on any literal not on it.",
               "values": {k: {"n": len(v), "line": v[0]["line"],
                              "ctx": v[0]["ctx"]}
                          for k, v in sorted(by.items())}}
        json.dump(doc, open(BACKLOG, "w", encoding="utf8"),
                  indent=1, ensure_ascii=False, sort_keys=True)
        print(f"  backlog recorded: {len(by)} distinct value(s) in {BACKLOG}")
        return 0
    if "--gate" in sys.argv:
        b = (json.load(open(BACKLOG, encoding="utf8"))
             if os.path.isfile(BACKLOG) else {"values": {}, "recorded": None})
        known = set(b.get("values", {}))
        new = {k: v for k, v in by.items() if k not in known}
        cleared = sorted(known - set(by))
        print(f"  recorded backlog: {len(known)} distinct, "
              f"recorded {b.get('recorded')}")
        if cleared:
            print(f"  {len(cleared)} value(s) no longer typed - remove them "
                  f"from {os.path.basename(BACKLOG)}: "
                  + ", ".join(cleared[:12]))
        if new:
            print(f"\n  PROSE FIGURE GATE FAILED: {len(new)} value(s) are "
                  "typed into the prose and are not on the recorded backlog.")
            for k, v in sorted(new.items(), key=lambda kv: -len(kv[1]))[:20]:
                print(f"\n    {k}  x{len(v)}  index.html:{v[0]['line']}")
                print(f"      {v[0]['ctx']}")
            return 1
        if cleared:
            print("\n  PROSE FIGURE GATE FAILED: the backlog is out of date.")
            return 1
        print("\n  prose figure gate: nothing typed that is not on the "
              "recorded backlog.")
        return 0
    for k, v in sorted(by.items(), key=lambda kv: -len(kv[1]))[:30]:
        print(f"    {k:>12}  x{len(v):<3} index.html:{v[0]['line']}")
        print(f"                  {v[0]['ctx'][:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
