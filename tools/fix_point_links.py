# -*- coding: utf-8 -*-
"""Rewrite every water-point deep link to a route that actually resolves.

WHAT WAS WRONG
--------------
56 anchors pointed at https://portal.mwater.co/#/water_point/<uuid>. That route
does not exist. Neither does #/entities/<type>/<uuid>, #/entity/... or
#/sites/<uuid>. This is not an authentication problem: forms and responses
resolve from the same session.

The portal's own route table - read out of its JavaScript bundle rather than
guessed at - has no route to an individual entity at all:

    /entities(/:id)        redirects to /entity_views/:id
    /entity_views(/:id)    :id is a saved VIEW document, not a water point
    /water_systems/:id     an asset, not a site
    /admin/archives/:table/:id    admin only

and the application never builds an href to an entity: every href:"#/..." in
the bundle is to a section, never to a record. So there is no deep link to a
water point to be had.

WHAT WORKS INSTEAD
------------------
#/responses/<id> resolves, and is the better link anyway: it opens the record
that says something about the point - the rehabilitation, the visit, the call -
which is what a verifier following the link actually wants to see. Every point
that has any record at all can be linked this way.

A point with no record gets no link: the code is shown as plain text with the
Sites browser offered separately, rather than a link that lands nowhere.

    python3 tools/fix_point_links.py --dry
    python3 tools/fix_point_links.py --write
"""
import json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(REPO, "data", "mwater_point_responses.json")
RESP_BASE = "https://portal.mwater.co/#/responses/"
SITES = "https://portal.mwater.co/#/entity_views"
# the record most worth opening, in order of preference
PREFER = ("works", "borehole", "repair", "pm", "call")

# the label may be a <span class="mono">code</span>, not bare text
# the uuid may be absent entirely and there may be no title, so the code is
# taken from the title when there is one and from the label otherwise
BROKEN = re.compile(
    r'<a class="wp" href="https://portal\.mwater\.co/#/water_point/[0-9a-f-]*"'
    r'(?:[^>]*?title="([^"]*)")?[^>]*>(.*?)</a>', re.S)


def best(m, code):
    d = m.get(code) or {}
    for k in PREFER:
        if d.get(k):
            return k, d[k]
    return None, None


def rewrite(text, m, stats):
    def sub(mo):
        title, label = mo.group(1) or "", mo.group(2)
        cm = re.search(r"(\d{9})", title) or re.search(r"(\d{9})", label)
        code = cm.group(1) if cm else None
        kind, rid = best(m, code) if code else (None, None)
        if rid:
            stats[kind] = stats.get(kind, 0) + 1
            what = {"works": "first-rehabilitation record",
                    "borehole": "borehole-progress record",
                    "repair": "repair record", "pm": "maintenance visit",
                    "call": "call-centre record"}[kind]
            return (f'<a class="wp" href="{RESP_BASE}{rid}" target="_blank" '
                    f'rel="noopener" title="Open the {what} for water point '
                    f'{code} in mWater">{label}</a>')
        stats["no record"] = stats.get("no record", 0) + 1
        return (f'<span class="mono" title="No mWater record links to water '
                f'point {code or title}; search for it in the Sites browser">'
                f'{label}</span>')
    return BROKEN.sub(sub, text)


def main():
    write = "--write" in sys.argv
    m = json.load(open(MAP, encoding="utf8"))
    stats = {}
    touched = []
    for rel in ("index.html", "portfolio.html", "routes.html"):
        p = os.path.join(REPO, rel)
        if not os.path.isfile(p):
            continue
        t = open(p, encoding="utf8").read()
        n = len(BROKEN.findall(t))
        if not n:
            continue
        out = rewrite(t, m, stats)
        touched.append((rel, n))
        if write:
            open(p, "w", encoding="utf8").write(out)
    # the generated action list comes from here, so fix the source too
    ad = os.path.join(REPO, "data", "action_details.json")
    d = json.load(open(ad, encoding="utf8"))
    nd = 0
    for aid, rec in d.items():
        for f in ("detail", "schedule"):
            t = rec.get(f)
            if t and BROKEN.search(t):
                nd += len(BROKEN.findall(t))
                rec[f] = rewrite(t, m, stats)
    if nd:
        touched.append(("data/action_details.json", nd))
        if write:
            json.dump(d, open(ad, "w", encoding="utf8"),
                      ensure_ascii=False, indent=1, sort_keys=True)
    print(f"  broken water-point anchors found: "
          f"{sum(n for _, n in touched)}")
    for rel, n in touched:
        print(f"    {rel:32} {n}")
    print("  rewritten to:")
    for k, v in sorted(stats.items(), key=lambda kv: -kv[1]):
        print(f"    {k:22} {v}")
    print("  written" if write else "  dry run - nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
