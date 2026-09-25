# -*- coding: utf-8 -*-
"""Regenerate the form-conformance freshness line in index.html.

The page claims things about the live mWater forms - that the calendar
photograph is required where a calendar is present, that no question code is
duplicated. Those claims are only as good as the last time anyone looked at
the forms, so the page says when that was, in its own words, and the build
refuses to publish a claim older than a week.

Written from data/mwater_form_snapshot.json, which is itself written only by
tools/refresh_form_snapshot.py. Nothing here talks to mWater.

    python3 tools/render_form_freshness.py --write
    python3 tools/render_form_freshness.py --check
"""
import datetime, json, os, sys, difflib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# a region that differs only in prerendered figure values is not drift
from prerender_figures import same as _same  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEGIN = ("<!-- BEGIN GENERATED form-freshness :: tools/render_form_freshness.py "
         ":: do not edit between these markers -->")
END = "<!-- END GENERATED form-freshness -->"
MAX_AGE_DAYS = 7


def block():
    snap = json.load(open(os.path.join(REPO, "data", "mwater_form_snapshot.json"),
                          encoding="utf8"))
    fetched = snap["fetched"]
    d = datetime.date.fromisoformat(fetched)
    age = (datetime.date.today() - d).days
    nice = d.strftime("%-d %B %Y")
    forms = snap["forms"]
    nq = sum(len(f["questions"]) for f in forms.values())
    # the counts are the snapshot's own output, reachable on the page as
    # FORMSNAP (tools/render_datasets.py) and marked as that artefact
    art = lambda v: f'<span data-artefact="form_snapshot">{v}</span>'
    revs = ", ".join(f"{k} <span class=\"mono\">_rev</span> {art(v['rev'])}"
                     for k, v in sorted(forms.items())
                     if k in ("preventive-maintenance", "repair-after-breakdown"))
    if age <= 0:
        when = "<b>today</b>"
    elif age == 1:
        when = "<b>yesterday</b>"
    else:
        when = f"<b>{age} days ago</b>"
    return (
        f'<p class="note"><b>How fresh this is.</b> Every statement on this page about what an '
        f'mWater form captures or requires is checked against a snapshot of the live form '
        f'designs, read from mWater on <b>{nice}</b> &mdash; {when}. '
        f'<b>{art(len(forms))}</b> forms, <b>{art(f"{nq:,}")}</b> questions; {revs}. '
        f'<span class="muted">The snapshot is refreshed as part of the weekly build wherever '
        f'the network and credentials are available, and the build <b>fails</b> rather than '
        f'publishes if it is more than <b>{MAX_AGE_DAYS} days</b> old &mdash; so a form changed '
        f'in the mWater designer cannot sit unnoticed behind a conformance claim for longer '
        f'than that. Snapshot: <span class="mono">data/mwater_form_snapshot.json</span>; '
        f'statement by statement in <span class="mono">docs/sop_form_conformance.md</span>.</span></p>')


def splice(b):
    p = os.path.join(REPO, "index.html")
    idx = open(p, encoding="utf8").read()
    if BEGIN not in idx or END not in idx:
        sys.exit("index.html has no form-freshness markers")
    a = idx.index(BEGIN) + len(BEGIN)
    z = idx.index(END)
    return idx[a:z], idx[:a] + "\n" + b.strip() + "\n  " + idx[z:]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    b = block()
    cur, whole = splice(b)
    want = "\n" + b.strip() + "\n  "
    if mode == "--write":
        open(os.path.join(REPO, "index.html"), "w", encoding="utf8").write(whole)
        print("index.html: form-freshness region %s"
              % ("unchanged" if _same(cur, want) else "rewritten"))
        return 0
    if mode == "--check":
        if _same(cur, want):
            print("index.html form-freshness region matches its generator")
            return 0
        print("\n".join(list(difflib.unified_diff(
            cur.splitlines(), want.splitlines(), "index.html (published)",
            "render_form_freshness.py (generator)", lineterm="", n=1))[:30]))
        print("\nRun: python3 tools/render_form_freshness.py --write")
        return 1
    sys.exit("usage: render_form_freshness.py --write | --check")


if __name__ == "__main__":
    sys.exit(main())
