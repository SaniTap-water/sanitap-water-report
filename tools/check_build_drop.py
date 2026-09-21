# -*- coding: utf-8 -*-
"""Detect a build that ran, succeeded, and published nothing.

The weekly build runs in a CLOUD session, not on this computer - which is why
no cron entry, systemd timer or Windows task exists here, and why looking for
one locally proved nothing. Its instructions say that if the push is refused
it writes index.html and routes.html into the Windows Downloads folder and
asks for a manual push.

That is what happened on 21 September. The build ran 05:09-06:01 UTC, pulled
mWater, built a complete week 39 edition - and could not push. The files were
written at 05:59 UTC and sat there. The published page kept its 7 September
data and every staleness check passed, because the page itself was internally
consistent. "Succeeded" from the scheduled task does not mean "published".

This records the drop so the checker can fail on exactly that gap.

    python3 tools/check_build_drop.py --write | --show
"""
import datetime, json, os, re, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "build_drop.json")
DROP = "/mnt/c/Users/bushp/Downloads"
WANT = ("index.html", "routes.html")


def issue_date(path):
    """(issue date, edition, newest record) from a built page's masthead."""
    try:
        t = open(path, encoding="utf8", errors="replace").read()
    except OSError:
        return None, None, None
    m = re.search(r"issued\s+\w{3}\s+(\d{1,2})\s+(\w+)\s+(\d{4})"
                  r".{0,40}?edition\s+(\d+)", t, re.S)
    d = e = None
    if m:
        for fmt in ("%d %b %Y", "%d %B %Y"):
            try:
                d = datetime.datetime.strptime(
                    f"{m.group(1)} {m.group(2)} {m.group(3)}", fmt).date().isoformat()
                break
            except ValueError:
                pass
        e = int(m.group(4))
    newest = None
    pm = re.search(r"\bconst PUMPS\s*=\s*", t)
    if pm:
        try:
            arr = json.loads(t[pm.end():t.index("];", pm.end()) + 1])
            ds = sorted(p["last_visit"] for p in arr if p.get("last_visit"))
            newest = ds[-1] if ds else None
        except (ValueError, IndexError):
            pass
    return d, e, newest


def last_publish():
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cI"], cwd=REPO,
                             capture_output=True, text=True).stdout.strip()
        return out or None
    except OSError:
        return None


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--show"
    if mode == "--show":
        print(json.dumps(json.load(open(OUT)), indent=1, sort_keys=True)
              if os.path.isfile(OUT) else "no data/build_drop.json yet")
        return 0
    if mode != "--write":
        sys.exit("usage: check_build_drop.py --write | --show")
    files, newest_mtime = [], None
    if os.path.isdir(DROP):
        for n in WANT:
            p = os.path.join(DROP, n)
            if not os.path.isfile(p):
                continue
            mt = datetime.datetime.fromtimestamp(
                os.path.getmtime(p), datetime.timezone.utc)
            files.append({"name": n, "bytes": os.path.getsize(p),
                          "written_utc": mt.isoformat(timespec="seconds")})
            newest_mtime = max(newest_mtime or mt, mt)
    d, e, rec = issue_date(os.path.join(DROP, "index.html"))
    pub = last_publish()
    doc = {"checked": datetime.datetime.now(
               datetime.timezone.utc).isoformat(timespec="seconds"),
           "drop_dir": DROP,
           "files": files,
           "built_issue_date": d,
           "built_edition": e,
           "built_newest_record": rec,
           "built_at_utc": newest_mtime.isoformat(timespec="seconds")
           if newest_mtime else None,
           "last_publish_utc": pub,
           "note": ("A build whose push is refused writes here and asks for a "
                    "manual push. If these files are newer than the last "
                    "publish, an edition was built and never went out.")}
    if newest_mtime and pub:
        try:
            doc["unpublished"] = newest_mtime > datetime.datetime.fromisoformat(pub)
        except ValueError:
            doc["unpublished"] = None
    else:
        doc["unpublished"] = False if not files else None
    json.dump(doc, open(OUT, "w"), indent=1, sort_keys=True)
    print(json.dumps(doc, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
