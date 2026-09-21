# -*- coding: utf-8 -*-
"""Render the week caption from data/data_freshness.json.

The caption states the age of the data rather than implying it is current.
It used to be written in the browser from max(PUMPS.last_visit), which is a
maintenance-visit date dressed up as "activity logged in mWater".

    python3 tools/render_freshness.py --write | --check
"""
import datetime, difflib, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEGIN = ("<!-- BEGIN GENERATED week-caption :: tools/render_freshness.py "
         ":: do not edit between these markers -->")
END = "<!-- END GENERATED week-caption -->"
NAMES = {"preventive-maintenance": "preventive maintenance",
         "repair-after-breakdown": "repairs",
         "call-centre": "call-centre contacts",
         "premiere-rehabilitation": "first rehabilitations"}


def nice(d):
    x = datetime.date.fromisoformat(d)
    return f"{x.day} {x.strftime('%B')} {x.year}"


def caption():
    f = json.load(open(os.path.join(REPO, "data", "data_freshness.json")))
    ex, mw, lag = f["extract_newest"], f["mwater_newest"], f["lag_days"]
    per = ", ".join(f"{NAMES.get(k, k)} to {nice(v)}"
                    for k, v in sorted(f["latest_in_mwater"].items()) if v)
    if not lag:
        return ('<p id="weekcap">Activity logged in mWater in the <b>7 days to '
                f'{nice(ex)}</b>, against the previous 7 days and the last 28. '
                '<span class="muted">The extract is current with mWater as of '
                f'{nice(f["checked"])}.</span></p>')
    return (
        '<p id="weekcap">Activity in the <b>7 days to ' + nice(ex) + '</b>, '
        'against the previous 7 days and the last 28. '
        '<b>That is not the current week.</b> The newest record in the extract '
        'this page is built from is ' + nice(ex) + '; mWater itself holds '
        'records to ' + nice(mw) + ' &mdash; ' + per + '. '
        f'<b>The counts below run {lag} days behind mWater</b> and describe the '
        'week to ' + nice(ex) + '. '
        '<span class="muted">Checked against mWater on ' + nice(f["checked"])
        + '; <a href="#act-refresh-extract">refresh the extract</a>.</span></p>')


def splice(b):
    p = os.path.join(REPO, "index.html")
    idx = open(p, encoding="utf8").read()
    if BEGIN not in idx:
        sys.exit("index.html has no week-caption markers")
    a = idx.index(BEGIN) + len(BEGIN)
    z = idx.index(END)
    return idx[a:z], idx[:a] + b + idx[z:]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    b = caption()
    cur, whole = splice(b)
    if mode == "--write":
        open(os.path.join(REPO, "index.html"), "w", encoding="utf8").write(whole)
        print("index.html: week caption %s"
              % ("unchanged" if cur == b else "rewritten"))
        return 0
    if mode == "--check":
        if cur == b:
            print("index.html week caption matches its generator")
            return 0
        print("\n".join(list(difflib.unified_diff(
            cur.splitlines(), b.splitlines(), "index.html",
            "render_freshness.py", lineterm="", n=1))[:20]))
        return 1
    sys.exit("usage: render_freshness.py --write | --check")


if __name__ == "__main__":
    sys.exit(main())
