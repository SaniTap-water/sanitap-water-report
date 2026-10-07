# -*- coding: utf-8 -*-
"""Freeze the outgoing edition's DATA before index.html is overwritten.

7 Oct 2026: a JSON data snapshot per edition (editions/<date>-wk<NN>-ed<N>.json),
no longer frozen HTML pages and maps; the pages archived before then stay.

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

One edition per ISO week reaches the archive. A mid-week update republishes
OVER the current edition (tools/weekly_build.py), so when the outgoing and
incoming pages belong to the same week the outgoing one is being replaced, not
superseded: it is not archived, and --assert accepts that. The week's last
version is frozen when the next week's edition replaces it.

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
    """(7 Oct 2026) One data snapshot per outgoing edition. Frozen HTML pages
    and maps are no longer written: archived pages are not read (decision of
    Adriaan Mol, 7 Oct 2026). The snapshot is what the approval gate and the
    fleet-churn check compare against, and the audit trail."""
    yield "index.html", f"{d.isoformat()}-wk{wk}-ed{ed}.json"


def snapshot(page_path, d, wk, ed):
    """Per-point data and headline inputs of the outgoing edition, from its page."""
    import json, subprocess
    h = io.open(page_path, encoding="utf8").read()
    def obj(name):
        m = re.search(r"^const " + name + r"\s*=\s*", h, re.M)
        if not m:
            return None
        i = m.end(); close = "};" if h[i] == "{" else "];"
        try:
            return json.loads(h[i:h.index(close, i) + 1])
        except ValueError:
            return None
    pumps = obj("PUMPS") or []
    wpop = obj("WPOP") or {}
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    chg = subprocess.run(["git", "show", "HEAD:data/change_review.json"], cwd=REPO, capture_output=True, text=True).stdout
    return {"edition": f"{d.isoformat()} wk{wk} ed{ed}", "commit": sha, "S": obj("S"),
            "headline": (json.loads(chg).get("figures") if chg else None),
            "pumps": [{"wp": p["wp"], "site": p.get("site"), "status": p.get("status"), "wq": p.get("wq"),
                       "wq_date": p.get("wq_date"), "comm": p.get("comm"),
                       "wpop": (wpop.get(p["wp"]) or [None, None])[1]} for p in pumps]}


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
    # the incoming edition: the working tree's masthead, else today
    inc, _ = masthead_of(os.path.join(REPO, "index.html"))
    inc = inc or datetime.date.today()
    if inc.isocalendar()[:2] == d.isocalendar()[:2]:
        print(f"outgoing edition {d.isoformat()} wk{wk} ed{ed} is this week's: "
              "replaced in place, not archived")
        return 0
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
    import json
    for src, n in want:
        dst = os.path.join(ED, n)
        if os.path.isfile(dst):
            continue
        json.dump(snapshot(srcs[src], d, wk, ed), open(dst, "w", encoding="utf8"), ensure_ascii=False)
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
