# -*- coding: utf-8 -*-
"""Render the masthead, with the extract date beside the issue date.

The masthead used to be prose: "week 38 · issued Fri 18 Sep 2026 · edition 10",
hand-typed and three days stale by the time anyone read it. Worse, it said
nothing about the age of the DATA, so a reader had no way to tell that the
figures under it described a fortnight ago. Both dates now sit side by side and
the gap between them is spelled out.

    python3 tools/render_masthead.py --write | --check
"""
import datetime, difflib, json, os, re, subprocess, sys

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


LEDGER = "logs/editions_issued.tsv"


def edition():
    """Editions this week - from the archive AND from the issue ledger.

    The archive alone is not a counter, it is a headcount of files on disk.
    On 21 September the proof run archived week 39 edition 1, so the next
    build correctly read edition 2; the run was then rolled back with
    git reset --hard and git clean -fd editions, the archived file went with
    it, and the number silently returned to 1. Nothing recorded that an
    edition 2 had ever been built, because nothing outside the working tree
    recorded anything at all.

    The ledger is append-only and untracked, so rolling the tree back cannot
    lower it. Whichever source is higher wins: a fresh clone still counts the
    archive, a rolled-back tree still counts what was issued.
    """
    today = datetime.date.today()
    wk = today.isocalendar()[1]
    # A mid-week update republishes OVER the current edition: if the edition
    # at HEAD is this ISO week's, keep its number (tools/archive_edition.py
    # does not archive it, so counting would not move anyway - this makes it
    # explicit and independent of what the ledger holds).
    r = subprocess.run(["git", "show", "HEAD:index.html"], cwd=REPO,
                       capture_output=True, text=True)
    m = re.search(r"week\s+(\d+)\s*(?:&middot;|·)\s*issued\s+\w{3}\s+(\d{1,2})\s+"
                  r"(\w+)\s+(\d{4}).{0,40}?edition\s+(\d+)", r.stdout or "", re.S)
    if m:
        for fmt in ("%d %b %Y", "%d %B %Y"):
            try:
                hd = datetime.datetime.strptime(
                    f"{m.group(2)} {m.group(3)} {m.group(4)}", fmt).date()
            except ValueError:
                continue
            if hd.isocalendar()[:2] == today.isocalendar()[:2]:
                return int(m.group(5))
    d = os.path.join(REPO, "editions")
    from_archive = 0
    if os.path.isdir(d):
        from_archive = len({f.split("-ed")[0] for f in os.listdir(d)
                            if f.startswith(today.strftime("%Y-"))
                            and f"wk{wk}" in f and f.endswith(".html")})
    from_ledger = 0
    lp = os.path.join(REPO, LEDGER)
    if os.path.isfile(lp):
        seen = set()
        for line in open(lp, encoding="utf8"):
            f = line.rstrip("\n").split("\t")
            if (len(f) >= 3 and f[0].startswith(today.strftime("%Y-"))
                    and f[1] == f"wk{wk}"):
                seen.add(f[2])
        from_ledger = len(seen)
    return 1 + max(from_archive, from_ledger)


def record_issued(date, wk, ed):
    """Append one line to the ledger, when an edition is archived."""
    lp = os.path.join(REPO, LEDGER)
    os.makedirs(os.path.dirname(lp), exist_ok=True)
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    with open(lp, "a", encoding="utf8") as fh:
        fh.write(f"{date}\twk{wk}\ted{ed}\t{stamp}\n")
    return f"{LEDGER}: {date} wk{wk} ed{ed}"


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
