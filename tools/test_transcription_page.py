# -*- coding: utf-8 -*-
"""Browser test of the transcription page (transcription/index.html).

Written 28 Sep 2026, after a first full pass exported 22 of 83 calendars: a
calendar viewed and left empty - a pump with no breakdown - was neither
counted nor exported. This drives the page in headless Chromium and asserts:

  1. view 3 calendars, mark 1, confirm 2 as "vérifié - aucune croix" (one by
     the button under the grid, one by answering Oui when Suivant asks),
     reload, export: exactly those 3 calendars are in the CSV, with statut
     marque / vide_verifie, and no calendar that was never shown;
  2. a store saved by the earlier page (no statut, no ok field) is read as
     before: a calendar with time recorded and no marks is exported as
     vu_sans_confirmation - never as checked-empty - and the review mode
     walks exactly those calendars and confirms them.

    ~/sdws1/venv/bin/python tools/test_transcription_page.py

Exit 0 when every assertion holds; 1 with the failures listed otherwise.
Run by tools/publish.sh with the render gate.
"""
import csv, functools, http.server, io, json, os, sys, threading

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = "sanitap-transcription-v2"
FAIL = []


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


def export(pg):
    with pg.expect_download() as dl:
        pg.click("#exp")
    rows = list(csv.DictReader(io.StringIO(
        open(dl.value.path(), encoding="utf-8-sig").read())))
    by = {}
    for r in rows:
        by.setdefault(r["calendrier"], set()).add(r["statut"])
    return rows, by


def openable(pg):
    """indices of calendars with at least one observable cell, worked out from
    the manifest without showing any of them (showing one records it as seen)"""
    return pg.evaluate("""CAL.map((c,i)=>i).filter(i=>{const w=windowFor(CAL[i]);
        return w.last!==-1;})""")


def main():
    from playwright.sync_api import sync_playwright
    srv = serve()
    url = f"http://127.0.0.1:{srv.server_address[1]}/transcription/"
    with sync_playwright() as p:
        b = p.chromium.launch()
        # ---- 1. view 3, mark 1, confirm 2, reload, export ------------------
        ctx = b.new_context(accept_downloads=True)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("dialog", lambda d: d.accept())
        pg.goto(url)
        pg.wait_for_function("typeof CAL!=='undefined' && CAL.length>0")
        pg.fill("#whoname", "Test Transcriber")
        pg.click("#whook")
        pg.evaluate("localStorage.removeItem('%s')" % KEY)
        pg.reload()
        pg.wait_for_function("typeof CAL!=='undefined' && CAL.length>0")
        pg.fill("#whoname", "Test Transcriber")
        pg.click("#whook")
        ok = openable(pg)
        # a: marked; b2: confirmed by answering Oui to the Suivant prompt, which
        # moves on to c = b2 + 1; c: confirmed by the button. Exactly three
        # calendars are ever shown.
        b2 = next(i for i in ok if i != 0 and i + 1 < pg.evaluate("CAL.length") and i - 1 != ok[0])
        a, c = ok[0], b2 + 1
        pg.select_option("#pick", str(a))
        pg.locator("#grid .c:not(.na):not(.unobs)").first.click()          # marked
        pg.select_option("#pick", str(b2))
        pg.click("#next")                                                   # Suivant on an empty sheet
        check("Suivant on a calendar with no marks asks for confirmation",
              pg.is_visible("#okmodal"))
        check("the question is the one specified",
              "Aucune croix sur ce calendrier : confirmer comme vérifié ?" in pg.inner_text("#okmodal"))
        pg.click("#okyes")
        check("Oui confirms it and moves on",
              pg.evaluate(f"statut(CAL[{b2}].n)") == "vide_verifie" and pg.evaluate("cur") == c)
        pg.click("#okbtn")                                                  # confirmed by the button
        check("the button records 'vérifié - aucune croix'",
              pg.evaluate("statut(CAL[cur].n)") == "vide_verifie")
        check("exactly three calendars were shown",
              pg.evaluate("Object.values(st).filter(r=>r.vu).length") == 3,
              pg.evaluate("Object.values(st).filter(r=>r.vu).length"))
        pg.reload()
        pg.wait_for_function("typeof CAL!=='undefined' && CAL.length>0")
        check("the header counts verified calendars", "vérifiés 3 / " in pg.inner_text("#counts"),
              pg.inner_text("#counts"))
        rows, by = export(pg)
        n = lambda i: str(pg.evaluate(f"CAL[{i}].n"))
        # the calendar Revenir left open was seen, so it is exported as seen
        answered = by
        check("exactly the 3 calendars are exported",
              set(by) == {n(a), n(b2), n(c)}, sorted(by))
        check("statut: 1 marque, 2 vide_verifie",
              answered.get(n(a)) == {"marque"} and answered.get(n(b2)) == {"vide_verifie"}
              and answered.get(n(c)) == {"vide_verifie"}, answered)
        check("no calendar that was never shown is exported",
              all("non_vu" not in v for v in by.values()), by)
        check("every exported row carries a statut", all(r.get("statut") for r in rows))
        # Revenir keeps the transcriber on the calendar, and confirms nothing
        d = next(i for i in ok if i not in (a, b2, c) and i + 1 < pg.evaluate("CAL.length"))
        pg.select_option("#pick", str(d)); pg.click("#next")
        check("Revenir stays on the calendar and confirms nothing",
              (pg.click("#okback") or True) and pg.evaluate("cur") == d
              and not pg.is_visible("#okmodal") and pg.evaluate("statut(CAL[cur].n)") == "vu_sans_confirmation")
        check("no page error", not errs, errs)
        ctx.close()

        # ---- 2. a store saved by the earlier page ---------------------------
        ctx = b.new_context(accept_downloads=True)
        pg = ctx.new_page()
        pg.on("dialog", lambda d: d.accept())
        pg.goto(url)
        pg.wait_for_function("typeof CAL!=='undefined' && CAL.length>0")
        ns = pg.evaluate("CAL.slice(0,4).map(c=>c.n)")
        old = {"sets": {"sold": {"session_id": "sold", "transcripteur": "Earlier Page",
                                  "cree_le": "2026-09-27T08:00:00.000Z", "cal": {
            str(ns[0]): {"cells": {"0-0": "X"}, "notes": "", "secs": 30, "exclu": "", "motif": ""},
            str(ns[1]): {"cells": {}, "notes": "", "secs": 12, "exclu": "", "motif": ""},
            str(ns[2]): {"cells": {}, "notes": "", "secs": 9, "exclu": "", "motif": ""},
            str(ns[3]): {"cells": {}, "notes": "", "secs": 0, "exclu": "oui", "motif": "panneau"}}}},
               "active": "sold"}
        pg.evaluate("s=>localStorage.setItem('%s',s)" % KEY, json.dumps(old))
        pg.reload()
        pg.wait_for_function("typeof CAL!=='undefined' && CAL.length>0")
        rows, by = export(pg)
        check("earlier store: seen-but-empty calendars export as vu_sans_confirmation",
              by.get(str(ns[1])) == {"vu_sans_confirmation"} and by.get(str(ns[2])) == {"vu_sans_confirmation"}, by)
        check("earlier store: marks and exclusions keep their meaning",
              by.get(str(ns[0])) == {"marque"} and by.get(str(ns[3])) == {"exclu"}, by)
        check("earlier store: no calendar never shown is exported", len(by) == 4, sorted(by))
        check("the review button counts the unconfirmed calendars",
              "(2)" in pg.inner_text("#revbtn") and pg.is_visible("#revbtn"), pg.inner_text("#revbtn"))
        pg.click("#revbtn")
        first = pg.evaluate("CAL[cur].n")
        pg.click("#next"); pg.click("#okyes")
        second = pg.evaluate("CAL[cur].n")
        pg.click("#next"); pg.click("#okyes")
        check("review walks exactly the unconfirmed calendars",
              {first, second} == {ns[1], ns[2]}, (first, second))
        check("review confirms them", pg.evaluate("unconfirmed().length") == 0)
        check("the earlier marks are untouched",
              json.loads(pg.evaluate("localStorage.getItem('%s')" % KEY))["sets"]["sold"]["cal"][str(ns[0])]["cells"] == {"0-0": "X"})
        ctx.close()

        # ---- 3. the sheet year ----------------------------------------------
        ctx = b.new_context(accept_downloads=True)
        pg = ctx.new_page()
        pg.on("dialog", lambda d: d.accept())
        pg.goto(url)
        pg.wait_for_function("typeof CAL!=='undefined' && CAL.length>0")
        pg.fill("#whoname", "Year Tester"); pg.click("#whook")
        check("sheet 6 carries no hard-coded year",
              not pg.evaluate("(CAL.find(c=>c.n===6)||{}).y"))
        i = pg.evaluate("CAL.findIndex(c=>+c.y===2026 && windowFor(c).last!==-1)")
        pg.select_option("#pick", str(i))
        check("the year field is prefilled from the reader",
              pg.input_value("#yearin") == "2026" and "lecteur" in pg.inner_text("#yearsrc"))
        check("a 2026 grid has no 29 February", pg.locator('.c[data-m="1"][data-d="28"]').count() == 0)
        pg.fill("#yearin", "2024"); pg.press("#yearin", "Enter"); pg.locator("#yearin").blur()
        pg.wait_for_timeout(200)
        check("typing 2024 rebuilds the grid with 29 February",
              pg.locator('.c.na[data-m="1"][data-d="28"]').count() == 0
              and pg.evaluate("DIM[1]") == 29)
        pg.locator("#grid .c:not(.na):not(.unobs)").first.click()
        pg.reload(); pg.wait_for_function("typeof CAL!=='undefined' && CAL.length>0")
        pg.select_option("#pick", str(i))
        check("the typed year survives a reload", pg.input_value("#yearin") == "2024"
              and "saisie par vous" in pg.inner_text("#yearsrc"))
        rows, by = export(pg)
        n_i = str(pg.evaluate(f"CAL[{i}].n"))
        mine = [r for r in rows if r["calendrier"] == n_i]
        check("export: annee_feuille 2024, annee_source transcripteur",
              mine and all(r["annee_feuille"] == "2024" and r["annee_source"] == "transcripteur" for r in mine),
              {(r["annee_feuille"], r["annee_source"]) for r in mine})
        check("export: a leap-year grid exports 29 February",
              any(r["mois"] == "2" and r["jour"] == "29" for r in mine))
        # a deduced year is offered, never used until confirmed
        j = pg.evaluate("CAL.findIndex(c=>!c.y)")
        pg.evaluate(f"CAL[{j}].yd=2024")
        pg.select_option("#pick", str(j))
        check("a deduced year is shown as 'a confirmer', not used",
              "année déduite du calendrier — à confirmer" in pg.inner_text("#yearded")
              and pg.evaluate(f"yearOf(CAL[{j}]).y") is None and pg.input_value("#yearin") == "")
        pg.click("#yearok")
        check("confirming it makes it the transcriber's year",
              pg.evaluate(f"yearOf(CAL[{j}]).src") == "transcripteur" and pg.evaluate(f"yearOf(CAL[{j}]).y") == 2024)
        ctx.close()
        b.close()
    srv.shutdown()
    print(f"\n  {len(FAIL)} failure(s)" if FAIL else "\n  transcription page: every assertion holds")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
