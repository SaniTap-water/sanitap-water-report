# -*- coding: utf-8 -*-
"""Render the masthead, with the extract date beside the issue date.

The masthead used to be prose: "week 38 · issued Fri 18 Sep 2026 · edition 10",
hand-typed and three days stale by the time anyone read it. Worse, it said
nothing about the age of the DATA, so a reader had no way to tell that the
figures under it described a fortnight ago. Both dates now sit side by side and
the gap between them is spelled out.

    python3 tools/render_masthead.py --write | --check
"""
import datetime, difflib, json, os, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEGIN = ("<!-- BEGIN GENERATED masthead :: tools/render_masthead.py "
         ":: do not edit between these markers -->")
END = "<!-- END GENERATED masthead -->"
# The build fails above this. A weekly build pulling on the day it runs has a
# lag of 0-1 days; three allows for a pull late on the Friday before.
MAX_EXTRACT_AGE_DAYS = 3


def nice(d):
    x = datetime.date.fromisoformat(d)
    return f"{x.strftime('%a')} {x.day} {x.strftime('%B')} {x.year}"


def edition():
    """Editions this week, counted from the archive, not from memory."""
    d = os.path.join(REPO, "editions")
    if not os.path.isdir(d):
        return 1
    wk = datetime.date.today().isocalendar()[1]
    return 1 + len({f.split("-ed")[0] for f in os.listdir(d)
                    if f.startswith(datetime.date.today().strftime("%Y-"))
                    and f"wk{wk}" in f and f.endswith(".html")})


def masthead():
    f = json.load(open(os.path.join(REPO, "data", "data_freshness.json")))
    today = datetime.date.today()
    ex = f.get("extract_newest")
    age = f.get("page_age_days")
    if ex and age is not None and age > MAX_EXTRACT_AGE_DAYS:
        gap = (f'<span class="pill crit">DATA {age} DAYS OLD</span> '
               f'<b>the figures below describe {nice(ex)}</b>, not today')
    elif ex:
        gap = (f'data to <b>{nice(ex)}</b>'
               + (f", {age} day{'s' if age != 1 else ''} old" if age else ", current"))
    else:
        gap = '<span class="pill crit">NO EXTRACT DATE</span>'
    return (f'<div class="eyebrow">SaniTap &middot; weekly water programme report '
            f'&middot; week {today.isocalendar()[1]} &middot; issued '
            f'{nice(today.isoformat())} &middot; edition {edition()}</div>\n'
            f'<div class="eyebrow" style="margin-top:4px;text-transform:none;'
            f'letter-spacing:0;font-size:.8rem">{gap}</div>')


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    b = masthead()
    p = os.path.join(REPO, "index.html")
    idx = open(p, encoding="utf8").read()
    if BEGIN not in idx:
        sys.exit("index.html has no masthead markers")
    a = idx.index(BEGIN) + len(BEGIN)
    z = idx.index(END)
    cur, want = idx[a:z], "\n" + b + "\n"
    if mode == "--write":
        open(p, "w", encoding="utf8").write(idx[:a] + want + idx[z:])
        print("index.html: masthead %s"
              % ("unchanged" if cur == want else "rewritten"))
        return 0
    if mode == "--check":
        if cur == want:
            print("index.html masthead matches its generator")
            return 0
        print("\n".join(list(difflib.unified_diff(
            cur.splitlines(), want.splitlines(), "index.html",
            "render_masthead.py", lineterm="", n=1))[:20]))
        return 1
    sys.exit("usage: render_masthead.py --write | --check")


if __name__ == "__main__":
    sys.exit(main())
