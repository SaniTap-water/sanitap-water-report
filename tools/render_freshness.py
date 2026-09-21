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
    per = f.get("per_source") or {}
    gaps = f.get("known_gaps") or {}
    ex = f["extract_newest"]
    fresh = [k for k, v in per.items() if v.get("behind_days") == 0]
    late = sorted(((v.get("behind_days") or 0), k) for k, v in per.items()
                  if v.get("behind_days"))
    bits = []
    for k, v in sorted(per.items()):
        if not v.get("page"):
            continue
        tag = (f' &mdash; <b>{v["behind_days"]} days behind</b>'
               if v.get("behind_days") else " &mdash; current")
        bits.append(f'{NAMES.get(k, k)} to {nice(v["page"])}{tag}')
    body = "; ".join(bits)
    head = ('<p id="weekcap">Activity in the <b>7 days to ' + nice(ex) + '</b>, '
            'against the previous 7 days and the last 28. ')
    if not late:
        return (head + '<span class="muted">Every source is level with mWater as '
                'of ' + nice(f["checked"]) + ': ' + body + '.</span></p>')
    worst, wname = late[-1]
    known = wname in gaps
    return (head + f'<b>{NAMES.get(wname, wname)} is {worst} days behind mWater</b> '
            + ('and cannot be rebuilt by any code in this repository yet &mdash; '
               f'<a href="#{gaps[wname]["action"]}">write the builder</a>. '
               if known else
               'and should have been rebuilt &mdash; run the pull and rebuild. ')
            + '<span class="muted">By source: ' + body
            + f'. Checked against mWater on {nice(f["checked"])}; '
            f'{len(fresh)} of {len(per)} sources level.</span></p>')


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
