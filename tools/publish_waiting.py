# -*- coding: utf-8 -*-
"""Publish the edition the cloud build left in Downloads, or explain why not.

The weekly build runs in a cloud session and pushes if it can. When the push
is refused it writes index.html and routes.html into the Windows Downloads
folder and asks for a manual push - and on 21 September nobody pushed, so a
complete edition sat there all day while the site showed a fortnight-old page
and every check passed. This removes the person from that loop.

It gates and publishes through tools/publish.sh and nothing else. Until 23
September it carried its own two-gate list and committed and pushed itself,
so a Downloads edition skipped the figure census, the prose gate, the link
check and the migration check. Now: remember HEAD, copy the candidate in, run
publish.sh; any failure resets the tree to HEAD, so a half-written repository
is never left behind. A dry run runs `publish.sh --check-only` and always
resets.

    python3 tools/publish_waiting.py            # the real thing
    python3 tools/publish_waiting.py --dry-run  # gate and report, then roll back
"""
import datetime, json, os, re, shutil, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# SANITAP_DROP lets the proof runs point at a fixture directory. The real
# schedule never sets it, so the default is the build's actual fallback.
DROP = os.environ.get("SANITAP_DROP", "/mnt/c/Users/bushp/Downloads")
LOG = os.path.join(REPO, "logs", "publisher.log")
PY = "/home/bushp/sdws1/venv/bin/python"
PW = "/home/bushp/.cache/ms-playwright"
PAGES = ("index.html", "routes.html")
SITE = "https://sanitap-water.github.io/sanitap-water-report/"


def log(line):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    with open(LOG, "a", encoding="utf8") as fh:
        fh.write(f"{stamp}  {line}\n")
    print(line)


def run(cmd, **kw):
    env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=PW)
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                          env=env, **kw)


def issue_date(path):
    try:
        t = open(path, encoding="utf8", errors="replace").read()
    except OSError:
        return None, None
    m = re.search(r"issued\s+\w{3}\s+(\d{1,2})\s+(\w+)\s+(\d{4})"
                  r".{0,60}?edition\s+(\d+)", t, re.S)
    if not m:
        return None, None
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return (datetime.datetime.strptime(
                f"{m.group(1)} {m.group(2)} {m.group(3)}", fmt).date(),
                int(m.group(4)))
        except ValueError:
            pass
    return None, int(m.group(4))


def publish_sh(args):
    """THE gate list (tools/publish.sh). Returns (ok, reason)."""
    r = run(["bash", "tools/publish.sh"] + args)
    lines = [l.strip() for l in ((r.stdout or "") + (r.stderr or "")).splitlines()
             if l.strip()]
    if r.returncode == 0:
        return True, ""
    why = next((l for l in lines if l.startswith("ABORT") or "FAILED" in l),
               lines[-1] if lines else "no output")
    fails = [l.split("FAIL")[0].strip() for l in lines if "FAIL !" in l][:4]
    return False, why + (" | " + "; ".join(fails) if fails else "")


def main():
    dry = "--dry-run" in sys.argv[1:]
    tag = "[dry-run] " if dry else ""

    cand = os.path.join(DROP, "index.html")
    if not all(os.path.isfile(os.path.join(DROP, p)) for p in PAGES):
        log(f"{tag}nothing waiting: no index.html+routes.html in {DROP}")
        return 0
    c_date, c_ed = issue_date(cand)
    p_date, p_ed = issue_date(os.path.join(REPO, "index.html"))
    if not c_date:
        log(f"{tag}REFUSED: candidate carries no readable issue date")
        return 1
    if p_date and c_date <= p_date:
        log(f"{tag}nothing newer: candidate {c_date} (ed {c_ed}) is not after "
            f"published {p_date} (ed {p_ed})")
        return 0

    # logs/ is this tool's own bookkeeping - it writes a line every run, so
    # counting it as "someone's uncommitted work" would make the second run
    # of the day refuse because the first one logged.
    dirty = [l for l in run(["git", "status", "--porcelain"]).stdout.splitlines()
             if l.strip() and not l[3:].startswith("logs/")]
    if dirty:
        log(f"{tag}REFUSED: working tree is not clean, {len(dirty)} path(s) "
            "modified - publishing would mix someone's work into the edition: "
            + ", ".join(l[3:] for l in dirty[:3]))
        return 1

    head = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    copied = []
    try:
        for p in PAGES:
            shutil.copy2(os.path.join(DROP, p), os.path.join(REPO, p))
            copied.append(p)
        # carry across whatever the build archived
        for d in sorted(os.listdir(DROP)):
            src = os.path.join(DROP, d, "editions")
            if not (d.startswith("sanitap-wk") and os.path.isdir(src)):
                continue
            os.makedirs(os.path.join(REPO, "editions"), exist_ok=True)
            for f in sorted(os.listdir(src)):
                if not f.endswith(".html"):
                    continue
                shutil.copy2(os.path.join(src, f),
                             os.path.join(REPO, "editions", f))
                copied.append(f"editions/{f}")
        wk = c_date.isocalendar()[1]
        msg = (f"Week {wk} edition {c_ed}, issued {c_date}: published from the "
               f"build's Downloads drop by tools/publish_waiting.py\n\n"
               f"The cloud build could not push, so it wrote the edition to "
               f"{DROP}. Copied in, then gated and published by "
               f"tools/publish.sh.\n\nFiles: {', '.join(copied)}")
        ok, why = publish_sh(["--check-only"] if dry else ["-m", msg])
        if not ok:
            raise RuntimeError("publish.sh refused: " + why)
    except Exception as e:                                    # noqa: BLE001
        run(["git", "reset", "--hard", head])
        run(["git", "clean", "-fd", "editions"])
        log(f"{tag}REFUSED and ROLLED BACK to {head[:8]}: {e}")
        return 1
    if dry:
        run(["git", "reset", "--hard", head])
        run(["git", "clean", "-fd", "editions"])
        log(f"{tag}candidate {c_date} (edition {c_ed}) passed publish.sh; "
            "rolled back, nothing published")
        return 0

    urls = [SITE, SITE + "routes.html"]
    arch = [c for c in copied if c.startswith("editions/")]
    if arch:
        urls.append(SITE + arch[-1])
    bad_urls = []
    for u in urls:
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                            "-L", "--max-time", "30", u], capture_output=True,
                           text=True)
        if r.stdout.strip() != "200":
            bad_urls.append(f"{u} -> {r.stdout.strip() or 'no response'}")
    sha = run(["git", "rev-parse", "HEAD"]).stdout.strip()[:8]
    if bad_urls:
        log(f"PUBLISHED week {c_date.isocalendar()[1]} edition {c_ed} as {sha}, "
            f"but the live check did not return 200: {'; '.join(bad_urls)} "
            "(GitHub Pages can lag a few minutes)")
        return 0
    log(f"PUBLISHED week {c_date.isocalendar()[1]} edition {c_ed} as {sha}; "
        f"{len(urls)} live URL(s) returned 200")
    return 0


if __name__ == "__main__":
    sys.exit(main())
