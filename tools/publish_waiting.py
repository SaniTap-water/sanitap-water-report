# -*- coding: utf-8 -*-
"""Publish the edition the cloud build left in Downloads, or explain why not.

The weekly build runs in a cloud session and pushes if it can. When the push
is refused it writes index.html and routes.html into the Windows Downloads
folder and asks for a manual push - and on 21 September nobody pushed, so a
complete edition sat there all day while the site showed a fortnight-old page
and every check passed. This removes the person from that loop.

The order matters and is not negotiable: VERIFY the candidate where it lies,
THEN copy, THEN commit. Copying first and checking after leaves the repository
half-written when the check fails, which is worse than not publishing at all.
Any failure after the first byte is copied rolls the working tree back.

    python3 tools/publish_waiting.py            # the real thing
    python3 tools/publish_waiting.py --dry-run  # verify and report, never write
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


def gates(candidate_index):
    """Both gates against the candidate, in place. Returns (ok, [reasons])."""
    bad = []
    r = run([PY, "tools/render_check.py", "--page", candidate_index])
    if r.returncode != 0:
        head = [l.strip() for l in (r.stdout or "").splitlines() if l.strip()][:4]
        bad.append("render gate: " + "; ".join(head))
    r = run([PY, "tools/check_consistency.py", candidate_index, "portfolio.html"])
    if r.returncode != 0:
        fails = [l.split("FAIL")[0].strip()
                 for l in (r.stdout or "").splitlines() if "FAIL !" in l]
        tally = next((l.strip() for l in (r.stdout or "").splitlines()
                      if re.search(r"\d+ checks,", l)), "")
        bad.append(f"consistency: {tally} | first: " + "; ".join(fails[:4]))
    return (not bad), bad


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

    dirty = run(["git", "status", "--porcelain"]).stdout.strip()
    if dirty:
        log(f"{tag}REFUSED: working tree is not clean, "
            f"{len(dirty.splitlines())} path(s) modified - publishing would "
            "mix someone's work into the edition")
        return 1

    ok, why = gates(cand)
    if not ok:
        log(f"{tag}REFUSED: candidate {c_date} (ed {c_ed}) failed the gates, "
            "nothing copied. " + " || ".join(why))
        return 1
    log(f"{tag}candidate {c_date} (edition {c_ed}) passed both gates")
    if dry:
        log(f"{tag}stopping before any write, as asked")
        return 0

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
        ok2, why2 = gates(os.path.join(REPO, "index.html"))
        if not ok2:
            raise RuntimeError("in-repo re-check failed: " + " || ".join(why2))
        wk = c_date.isocalendar()[1]
        run(["git", "add", "-A"])
        msg = (f"Week {wk} edition {c_ed}, issued {c_date}: published from the "
               f"build's Downloads drop by tools/publish_waiting.py\n\n"
               f"The cloud build could not push, so it wrote the edition to "
               f"{DROP}. Verified there with the render gate and the "
               f"consistency checker before anything was copied, re-verified "
               f"in the repository, then committed.\n\n"
               f"Files: {', '.join(copied)}")
        r = run(["git", "commit", "-m", msg])
        if r.returncode != 0:
            raise RuntimeError("commit failed: " + (r.stderr or r.stdout)[:200])
        r = run(["git", "push"])
        if r.returncode != 0:
            raise RuntimeError("push failed: " + (r.stderr or r.stdout)[:200])
    except Exception as e:                                    # noqa: BLE001
        run(["git", "reset", "--hard", head])
        run(["git", "clean", "-fd", "editions"])
        log(f"REFUSED and ROLLED BACK to {head[:8]}: {e}")
        return 1

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
