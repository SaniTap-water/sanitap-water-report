# -*- coding: utf-8 -*-
"""Browser test of the route page's exports (routes.html), 16 Oct 2026.

The route plans are for the field teams, so what matters is what leaves the
page: the CSV a field lead downloads and the day sheets printed or saved as
PDF. This drives routes.html in headless Chromium and asserts:

  1. for every site, "CSV (all days)" downloads <site>-catch-up-routes-<date>.csv
     whose data rows are exactly the site's routed pumps, with the itinerary.csv
     columns plus a Google Maps link per pump, and the field-lead sentence;
  2. "Print day sheet (PDF)" builds one sheet for the selected day - site,
     day, road km, hours, the field-lead sentence, the day's map with its route
     drawn, and one stop row per pump - and calls window.print() only after the
     route line is on the map;
  3. "Print all days (PDF)" builds one sheet per day, and the printed PDF has
     one page per day (the smallest site, to keep the run short);
  4. the print view opened from a URL (the way the report's embedded maps open
     it, in a new tab) shows the day asked for;
  5. nothing above writes an error to the console.

    ~/sdws1/venv/bin/python tools/test_routes_page.py

Exit 0 when every assertion holds; 1 with the failures listed otherwise.
Run by tools/publish.sh with the render gate.
"""
import csv, functools, http.server, io, json, os, re, sys, threading

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import build_routes as BR

FAIL = []
NOTE = ("A day is one field team's working day; how many technicians go is decided by "
        "the field lead (Adriaan Mol, 16 Oct 2026).")


def check(what, ok, got=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {what}" + (f"  ({got})" if not ok and got != "" else ""))
    if not ok:
        FAIL.append(what)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                          functools.partial(Quiet, directory=REPO))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    from playwright.sync_api import sync_playwright
    routes = BR.const(io.open(BR.INDEX, encoding="utf8").read(), "ROUTES")[2]
    if not routes:
        print("  no route plans on the page: nothing to export")
        return 0
    srv = serve()
    base = f"http://127.0.0.1:{srv.server_address[1]}/routes.html"
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(accept_downloads=True, viewport={"width": 1280, "height": 800})
        # window.print() would block on a dialog; record the call instead
        ctx.add_init_script("window.__printed=0;window.print=()=>{window.__printed++}")

        def page():
            pg = ctx.new_page()
            pg.on("console", lambda m: m.type == "error" and errors.append(f"{pg.url}: {m.text}"))
            pg.on("pageerror", lambda e: errors.append(f"{pg.url}: {e}"))
            return pg

        pg = page()
        pg.goto(base, wait_until="load")
        pg.wait_for_function("window.ROUTES_PAGE")

        # 1. CSV per site
        for site, R in routes.items():
            pg.select_option("#site", site)
            stops = [s for d in R["days"] for s in d["stops"]]
            with pg.expect_download() as dl:
                pg.click("#csv")
            d = dl.value
            want = f"{site}-catch-up-routes-{R['drawn']}.csv"
            check(f"{site}: CSV file name is {want}", d.suggested_filename == want, d.suggested_filename)
            text = open(d.path(), encoding="utf-8-sig").read()
            rows = list(csv.reader(io.StringIO(text)))
            head, body = rows[0], []
            for r in rows[1:]:
                if not r or not any(r):
                    break
                body.append(r)
            check(f"{site}: CSV columns are itinerary.csv's plus a Google Maps link",
                  head == BR.ITIN_COLS + ["google_maps"], head)
            check(f"{site}: CSV has one row per routed pump ({len(stops)})", len(body) == len(stops), len(body))
            check(f"{site}: CSV rows are the routed pumps, in visiting order",
                  [r[3] for r in body] == [s["wp"] for s in stops])
            link = re.compile(r"^https://www\.google\.com/maps/dir/\?api=1&destination=-?\d+(\.\d+)?,-?\d+(\.\d+)?$")
            check(f"{site}: every CSV row carries a Google Maps link to the pump",
                  all(link.match(r[-1]) and r[-1].endswith(f"{r[10]},{r[11]}") for r in body))
            check(f"{site}: CSV carries the field-lead sentence", NOTE in text)

        # 2. one day sheet, for the first site, its second day if it has one
        site = next(iter(routes))
        R = routes[site]
        di = 1 if len(R["days"]) > 1 else 0
        pg.select_option("#site", site)
        pg.select_option("#day", str(R["days"][di]["day"]))
        before = pg.evaluate("window.__printed")
        pg.click("#pday")
        pg.wait_for_selector("body[data-print-ready='1']", timeout=120000)
        sheets = pg.locator("#sheets .sheet")
        d = R["days"][di]
        txt = sheets.first.inner_text() if sheets.count() else ""
        check(f"{site}: day sheet shows one sheet", sheets.count() == 1, sheets.count())
        check(f"{site}: day sheet names the site and day {d['day']}",
              f"{site} — catch-up route, day {d['day']} of {len(R['days'])}" in txt)
        check(f"{site}: day sheet gives road km and hours",
              f"{d['km']} road km" in txt and f"{d['hours']} h" in txt)
        check(f"{site}: day sheet carries the field-lead sentence", NOTE in txt)
        check(f"{site}: day sheet has one stop row per pump ({len(d['stops'])})",
              pg.locator("#sheets .sheet tbody tr").count() == len(d["stops"]))
        check(f"{site}: day sheet stop table lists the day's pumps",
              all(s["wp"] in txt for s in d["stops"]))
        check(f"{site}: day sheet map shows the day's route line",
              pg.locator("#sheets .smap path.leaflet-interactive").count() >= 1)
        check(f"{site}: window.print() called once, after the route was drawn",
              pg.evaluate("window.__printed") == before + 1)
        pg.click("#pvclose")

        # 3. every day, for the site with the fewest days; one printed page per day
        site = min(routes, key=lambda s: len(routes[s]["days"]))
        R = routes[site]
        pg.select_option("#site", site)
        pg.click("#pall")
        pg.wait_for_selector("body[data-print-ready='1']", timeout=60000 + 4000 * len(R["days"]))
        n = pg.locator("#sheets .sheet").count()
        check(f"{site}: all-days view has one sheet per day ({len(R['days'])})", n == len(R["days"]), n)
        check(f"{site}: every sheet's map has its route line",
              pg.locator("#sheets .smap").count() == n
              and all(pg.locator(f"#smap-{i} path.leaflet-interactive").count() >= 1 for i in range(n)))
        pg.emulate_media(media="print")
        pdf = pg.pdf(format="A4", print_background=True)
        pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf))
        check(f"{site}: printed PDF has one page per day ({len(R['days'])})", pages == len(R["days"]), pages)
        pg.emulate_media(media="screen")

        # 4. the print view opened by URL, as the embedded maps open it
        site = next(iter(routes))
        R = routes[site]
        dn = R["days"][-1]["day"]
        pg2 = page()
        pg2.goto(f"{base}?site={site}&print=day&day={dn}", wait_until="load")
        pg2.wait_for_selector("body[data-print-ready='1']", timeout=120000)
        t2 = pg2.locator("#sheets .sheet").first.inner_text()
        check(f"{site}: print view opened by URL shows day {dn}",
              f"day {dn} of {len(R['days'])}" in t2 and pg2.evaluate("window.__printed") == 1)
        b.close()
    srv.shutdown()

    # 5. console
    check("no console errors", not errors, "; ".join(errors[:5]))
    if FAIL:
        print(f"\n  ROUTE PAGE TEST FAILED: {len(FAIL)} assertion(s)")
        return 1
    print("\n  route page exports: every assertion holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
