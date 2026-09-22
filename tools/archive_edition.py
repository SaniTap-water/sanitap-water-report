# -*- coding: utf-8 -*-
"""Freeze the outgoing edition before index.html is overwritten.

WHY THIS EXISTS AS ITS OWN TOOL
-------------------------------
Archiving lived inside tools/weekly_build.py and was called from nowhere else.
Every edition published through tools/publish.sh - which is how every edition
since 18 September went out - was therefore never archived. Week 39 has no
archive at all, which is also why the edition counter could reset: it counted
files in editions/, and there were none for the week.

So the archive step is its own tool, publish.sh calls it before it overwrites
anything, and --assert refuses to let a publish proceed if the outgoing
edition is not on disk.

    python3 tools/archive_edition.py            # archive the current index.html
    python3 tools/archive_edition.py --assert   # fail unless it is archived
"""
import datetime, io, os, re, shutil, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ED = os.path.join(REPO, "editions")


def masthead_of(path):
    try:
        t = io.open(path, encoding="utf8", errors="replace").read()
    except OSError:
        return None, None
    m = re.search(r"week\s+(\d+)\s*(?:&middot;|·)\s*issued\s+\w{3}\s+(\d{1,2})\s+"
                  r"(\w+)\s+(\d{4}).{0,40}?edition\s+(\d+)", t, re.S)
    if not m:
        return None, None
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            d = datetime.datetime.strptime(
                f"{m.group(2)} {m.group(3)} {m.group(4)}", fmt).date()
            return d, (int(m.group(1)), int(m.group(5)))
        except ValueError:
            pass
    return None, None


def names(d, wk, ed):
    for src, suffix in (("index.html", ""), ("routes.html", "-routes"),
                        ("portfolio.html", "-portfolio")):
        yield src, f"{d.isoformat()}-wk{wk}-ed{ed}{suffix}.html"


def from_head(name):
    """The OUTGOING edition is the one at git HEAD, not the working tree.

    By the time publish.sh runs, index.html already holds the new edition, so
    archiving the working tree would freeze the incoming edition under the
    outgoing one's name. The outgoing edition is whatever is committed.
    """
    import subprocess, tempfile
    r = subprocess.run(["git", "show", f"HEAD:{name}"], cwd=REPO,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    fd, tmp = tempfile.mkstemp(suffix=".html")
    os.write(fd, r.stdout.encode("utf8")); os.close(fd)
    return tmp


def main():
    head = from_head("index.html")
    if head is None:
        print("archive: nothing committed yet; nothing to freeze")
        return 0
    d, wk_ed = masthead_of(head)
    if not d or not wk_ed:
        print("archive: cannot read the masthead of index.html")
        return 2
    wk, ed = wk_ed
    srcs = {s: from_head(s) for s, _ in names(d, wk, ed)}
    want = [(s, n) for s, n in names(d, wk, ed) if srcs.get(s)]
    missing = [n for _, n in want if not os.path.isfile(os.path.join(ED, n))]

    if "--assert" in sys.argv:
        if missing:
            print(f"ARCHIVE MISSING for the outgoing edition "
                  f"{d.isoformat()} wk{wk} ed{ed}:")
            for n in missing:
                print(f"   {n}")
            print("Run: python3 tools/archive_edition.py")
            return 1
        print(f"outgoing edition archived: {d.isoformat()} wk{wk} ed{ed} "
              f"({len(want)} file(s))")
        return 0

    os.makedirs(ED, exist_ok=True)
    done = []
    for src, n in want:
        dst = os.path.join(ED, n)
        if os.path.isfile(dst):
            continue
        shutil.copy2(srcs[src], dst)
        done.append(n)
    if done:
        print(f"archived {d.isoformat()} wk{wk} ed{ed}: " + ", ".join(done))
    else:
        print(f"already archived: {d.isoformat()} wk{wk} ed{ed}")
    # record it outside the tree too, so a rollback cannot lower the counter
    try:
        sys.path.insert(0, os.path.join(REPO, "tools"))
        import render_masthead as rm
        print("  " + rm.record_issued(d.isoformat(), wk, ed))
    except Exception as e:                                     # noqa: BLE001
        print(f"  edition ledger NOT written: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
