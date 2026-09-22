# -*- coding: utf-8 -*-
"""Every mWater URL the page emits must be a route that exists.

WHY PATTERN-MATCHING WAS NOT ENOUGH
-----------------------------------
56 anchors pointed at #/water_point/<uuid>. They matched their regex perfectly
and every one of them landed on "Page not found". A check on URL SHAPE cannot
catch that, because the shape was never the problem - the route was.

HOW THIS TESTS THE ROUTE
------------------------
A hash fragment is never sent to the server, so fetching the URL tells you
nothing: every #/... on portal.mwater.co returns the same 200 and the same SPA
shell. Rendering it unauthenticated tells you nothing either - valid and
invalid routes both bounce to the login page.

What does settle it is the portal's own route table, which is a literal in its
JavaScript bundle. This extracts it and asserts that every route the page links
to is in it. That is a test of whether the route exists, not of how the URL
looks, and it is the test that would have caught the 56.

The bundle is cached in data/mwater_routes.json so the gate does not download
42 MB on every run; --refresh re-reads it.

    python3 tools/check_links.py            # check the page against the cache
    python3 tools/check_links.py --refresh  # re-read the portal's route table
"""
import json, os, re, sys, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, "data", "mwater_routes.json")
BUNDLE = "https://portal.mwater.co/js/index.js"
PAGES = ("index.html", "portfolio.html", "routes.html")


def refresh():
    req = urllib.request.Request(BUNDLE, headers={"Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        import gzip
        raw = gzip.decompress(raw)
    js = raw.decode("utf8", "replace")
    routes = sorted(set(re.findall(r'this\.match\("([^"]+)"\)', js)))
    if len(routes) < 50:
        sys.exit(f"check_links: only {len(routes)} routes found; the bundle "
                 "shape has changed and this needs looking at")
    doc = {"read_from": BUNDLE, "routes": routes, "count": len(routes)}
    json.dump(doc, open(CACHE, "w", encoding="utf8"), indent=1)
    print(f"portal route table cached: {len(routes)} routes -> {CACHE}")
    return doc


def to_regex(pattern):
    """mWater route patterns -> a regex.

    /forms/:formId(/:tab)   one required segment, one optional
    /entities(/:id)         an optional segment
    /admin(/*)              an optional tail
    /social_signin/*        a required tail
    """
    out, i = "", 0
    while i < len(pattern):
        c = pattern[i]
        if c == "(":
            close = pattern.index(")", i)
            inner = pattern[i + 1:close]
            out += "(?:" + re.sub(r":\w+", "[^/]+", inner).replace("/*", "/.*") + ")?"
            i = close + 1
        elif c == ":":
            m = re.match(r":\w+", pattern[i:])
            out += "[^/]+"
            i += m.end()
        elif c == "*":
            out += ".*"
            i += 1
        else:
            out += re.escape(c)
            i += 1
    return out


def route_matches(path, pattern):
    try:
        return re.fullmatch(to_regex(pattern) + r"/?", path) is not None
    except re.error:
        return False


def main():
    if "--refresh" in sys.argv or not os.path.isfile(CACHE):
        doc = refresh()
    else:
        doc = json.load(open(CACHE, encoding="utf8"))
    routes = doc["routes"]

    found, bad = {}, []
    for rel in PAGES:
        p = os.path.join(REPO, rel)
        if not os.path.isfile(p):
            continue
        html = open(p, encoding="utf8").read()
        for url in set(re.findall(r'https://portal\.mwater\.co/#(/[^"\'\s<>]*)',
                                  html)):
            raw = url.split("?")[0]
            # a trailing slash means this is a base prefix in script code -
            # "https://portal.mwater.co/#/responses/" + id - not a link
            if raw.endswith("/"):
                continue
            found.setdefault(raw, []).append(rel)

    for path, where in sorted(found.items()):
        if not any(route_matches(path, r) for r in routes):
            bad.append((path, where))

    print(f"  {len(found)} distinct portal route(s) linked from the page")
    if bad:
        print(f"\n  LINK CHECK FAILED: {len(bad)} route(s) do not exist in the "
              f"portal's own route table ({doc['count']} routes):")
        for path, where in bad[:12]:
            print(f"    {path}")
            print(f"      linked from {', '.join(sorted(set(where)))}")
        print("\n  The portal has no route to an individual entity. Link to "
              "the RESPONSE that references the point instead:")
        print("    https://portal.mwater.co/#/responses/<response id>")
        return 1
    for path in sorted(found):
        print(f"    ok  {path}")
    print("  every linked route exists in the portal's route table")
    return 0


if __name__ == "__main__":
    sys.exit(main())
