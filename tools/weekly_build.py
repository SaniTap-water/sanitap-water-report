# -*- coding: utf-8 -*-
"""Build and publish the weekly edition, on this machine, start to finish.

The edition used to be built in a cloud session that could not publish, wrote
its output into the Windows Downloads folder and asked for a manual push. On
21 September nobody pushed and a complete edition sat there all day. Every
piece it needed now lives here - the extract pull, the call tables, the region
generators, both gates and the publisher - so the build runs here and the
cloud session is reduced to a watchdog.

The order is the safeguard. The working tree is clean before anything starts,
HEAD is remembered, the outgoing edition is archived, everything is rebuilt,
and BOTH gates must pass before a single byte is committed. Any failure after
the first write rolls the tree back to the remembered HEAD, so a half-built
edition can never be left behind - and never published.

A candidate in Downloads is still considered, gated identically, and preferred
only when its data is genuinely newer than what this build produced. That
keeps a route open if this machine is unavailable for a long stretch.

    python3 tools/weekly_build.py --dry-run   # build, gate, report, roll back
    python3 tools/weekly_build.py             # and publish if both gates pass
"""
import datetime, io, json, os, re, shutil, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = "/home/bushp/sdws1/venv/bin/python"
PW = "/home/bushp/.cache/ms-playwright"
LOG = os.path.join(REPO, "logs", "publisher.log")
DROP = os.environ.get("SANITAP_DROP", "/mnt/c/Users/bushp/Downloads")
SITE = "https://sanitap-water.github.io/sanitap-water-report/"

# (script, args, must it succeed?)  Order matters: pull first, render last.
STEPS = [
    ("tools/pull_extract.py",        ["--write"],      True),
    ("tools/refresh_form_snapshot.py", ["--if-possible"], False),
    ("tools/rebuild_activity.py",    ["--write"],      True),
    ("tools/build_call_tables.py",   ["--write"],      True),
    ("tools/marolinta_admin.py",     ["--write"],      False),
    ("tools/check_freshness.py",     ["--write"],      True),
    ("tools/action_metrics.py",      ["--write"],      False),
    ("tools/eval_conditions.py",     ["--write"],      True),
    ("tools/check_build_drop.py",    ["--write"],      False),
    ("tools/render_masthead.py",     ["--write"],      True),
    ("tools/render_freshness.py",    ["--write"],      True),
    ("tools/render_marolinta.py",    ["--write"],      True),
    ("tools/render_block.py",        ["--write"],      True),
    ("tools/render_form_freshness.py", ["--write"],    True),
    ("tools/render_actions.py",      ["--write"],      True),
    # the Endur'O block and the inlined datasets, so every figure the prose
    # quotes is reachable from the page's own data
    ("tools/render_enduro.py",       ["--write"],      True),
    ("tools/render_datasets.py",     ["--write"],      True),
]


def log(line):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    io.open(LOG, "a", encoding="utf8").write(f"{ts}  {line}\n")
    print(line)


def run(cmd, **kw):
    env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=PW)
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                          env=env, **kw)


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


def newest_record(path):
    try:
        t = io.open(path, encoding="utf8", errors="replace").read()
        m = re.search(r"\bconst PUMPS\s*=\s*", t)
        arr = json.loads(t[m.end():t.index("];", m.end()) + 1])
        ds = sorted(p["last_visit"] for p in arr if p.get("last_visit"))
        return ds[-1] if ds else None
    except Exception:                                          # noqa: BLE001
        return None


def archive():
    """Freeze the outgoing edition before it is overwritten."""
    d, wk_ed = masthead_of(os.path.join(REPO, "index.html"))
    if not d or not wk_ed:
        return []
    wk, ed = wk_ed
    out = []
    os.makedirs(os.path.join(REPO, "editions"), exist_ok=True)
    for src, suffix in (("index.html", ""), ("routes.html", "-routes"),
                        ("portfolio.html", "-portfolio")):
        p = os.path.join(REPO, src)
        if not os.path.isfile(p):
            continue
        name = f"{d.isoformat()}-wk{wk}-ed{ed}{suffix}.html"
        shutil.copy2(p, os.path.join(REPO, "editions", name))
        out.append(f"editions/{name}")
    # Record it outside the tree as well. editions/ is a working-tree
    # artefact: a rollback removes it and the edition number goes backwards
    # with nothing left to say it ever went forwards.
    try:
        sys.path.insert(0, os.path.join(REPO, "tools"))
        import render_masthead as _rm
        out.append(_rm.record_issued(d.isoformat(), wk, ed))
    except Exception as e:                                     # noqa: BLE001
        out.append(f"edition ledger NOT written: {e}")
    return out


def gates(page):
    bad = []
    r = run([PY, "tools/render_check.py", "--page", page])
    if r.returncode != 0:
        head = [l.strip() for l in (r.stdout or "").splitlines() if l.strip()][:4]
        bad.append("render gate: " + "; ".join(head))
    r = run([PY, "tools/check_consistency.py", page, "portfolio.html"])
    tally = next((l.strip() for l in (r.stdout or "").splitlines()
                  if re.search(r"\d+ checks,", l)), "")
    if r.returncode != 0:
        fails = [l.split("FAIL")[0].strip()
                 for l in (r.stdout or "").splitlines() if "FAIL !" in l]
        bad.append(f"consistency: {tally} | " + "; ".join(fails[:4]))
    return (not bad), bad, tally


def main():
    dry = "--dry-run" in sys.argv[1:]
    tag = "[dry-run] " if dry else ""
    dirty = [l for l in run(["git", "status", "--porcelain"]).stdout.splitlines()
             if l.strip() and not l[3:].startswith("logs/")]
    if dirty:
        log(f"{tag}REFUSED: working tree is not clean, {len(dirty)} path(s): "
            + ", ".join(l[3:] for l in dirty[:3]))
        return 1
    # The retries exist for a machine that was off, not to publish an edition
    # an hour after the last one. Once today's edition is out, later runs in
    # the same day do nothing - unless --force, or a Downloads candidate turns
    # up with newer data, which publish_waiting.py handles on its own.
    today = datetime.date.today()
    issued, _ = masthead_of(os.path.join(REPO, "index.html"))
    if issued == today and "--force" not in sys.argv[1:] and not dry:
        log(f"already built today: the published edition is issued {issued}")
        return 0
    head = run(["git", "rev-parse", "HEAD"]).stdout.strip()

    def rollback(why):
        run(["git", "reset", "--hard", head])
        run(["git", "clean", "-fd", "editions", "data", "logs"])
        log(f"{tag}REFUSED and ROLLED BACK to {head[:8]}: {why}")

    try:
        archived = archive()
        failures = []
        # The extract pull is by far the slowest step - it walks date windows
        # per form and takes a quarter of an hour. SANITAP_SKIP_PULL lets a
        # proof run exercise everything else against extracts already on disk.
        # The schedule never sets it.
        skip = os.environ.get("SANITAP_SKIP_PULL") == "1"
        for script, args, required in STEPS:
            if skip and script.endswith("pull_extract.py"):
                log(f"{tag}SKIPPING the extract pull (SANITAP_SKIP_PULL=1); "
                    "using the extracts already on disk")
                continue
            r = run([PY, script] + args)
            if r.returncode != 0:
                msg = (r.stderr or r.stdout or "").strip().splitlines()
                msg = msg[-1][:160] if msg else "no output"
                if required:
                    raise RuntimeError(f"{script} failed: {msg}")
                failures.append(f"{os.path.basename(script)} ({msg[:60]})")
        ok, why, tally = gates(os.path.join(REPO, "index.html"))
        d, wk_ed = masthead_of(os.path.join(REPO, "index.html"))
        built_rec = newest_record(os.path.join(REPO, "index.html"))
    except Exception as e:                                     # noqa: BLE001
        rollback(str(e))
        return 1

    # A Downloads candidate is still considered - gated the same way - and
    # preferred only when its DATA is genuinely newer than what we just built.
    cand = os.path.join(DROP, "index.html")
    if os.path.isfile(cand):
        c_rec = newest_record(cand)
        if c_rec and built_rec and c_rec > built_rec:
            c_ok, c_why, _ = gates(cand)
            if c_ok:
                log(f"{tag}the Downloads candidate holds newer data "
                    f"({c_rec} against {built_rec}) and passed both gates - "
                    "preferring it over the local build")
                for f in ("index.html", "routes.html"):
                    if os.path.isfile(os.path.join(DROP, f)):
                        shutil.copy2(os.path.join(DROP, f), os.path.join(REPO, f))
                ok, why = True, []
            else:
                log(f"{tag}the Downloads candidate holds newer data ({c_rec}) but "
                    "failed the gates, so the local build stands: "
                    + " || ".join(c_why)[:200])

    if not ok:
        rollback("gates failed after a full rebuild. " + " || ".join(why))
        return 1
    nonfatal = (" optional step(s) skipped: " + ", ".join(failures)) if failures else ""
    log(f"{tag}built week {wk_ed[0]} edition {wk_ed[1]}, issued {d}, "
        f"data to {built_rec}; both gates pass ({tally}); "
        f"archived {len(archived)} file(s).{nonfatal}")
    if dry:
        # say what it WOULD have published, before the tree goes back
        was = run(["git", "show", "HEAD:index.html"]).stdout
        now = io.open(os.path.join(REPO, "index.html"), encoding="utf8").read()

        def figs(src):
            out = {}
            for name, close in (("S", "};"), ("REG", "};")):
                m = re.search(r"\bconst %s\s*=\s*" % name, src)
                if m:
                    try:
                        out[name] = json.loads(src[m.end():src.index(close, m.end()) + 1])
                    except ValueError:
                        pass
            for name in ("PUMPS", "DOWN", "PARTIAL", "OPENREP"):
                m = re.search(r"\bconst %s\s*=\s*" % name, src)
                if m:
                    try:
                        out["n_" + name] = len(json.loads(
                            src[m.end():src.index("];", m.end()) + 1]))
                    except ValueError:
                        pass
            return out

        a_, b_ = figs(was), figs(now)
        diffs = []
        for k in ("n_PUMPS", "n_DOWN", "n_PARTIAL", "n_OPENREP"):
            if a_.get(k) != b_.get(k):
                diffs.append(f"{k[2:]}: {a_.get(k)} -> {b_.get(k)}")
        for grp in ("S", "REG"):
            for k in sorted(set(a_.get(grp, {})) | set(b_.get(grp, {}))):
                va, vb = a_.get(grp, {}).get(k), b_.get(grp, {}).get(k)
                if va != vb:
                    diffs.append(f"{grp}.{k}: {va} -> {vb}")
        if diffs:
            log(f"{tag}would change {len(diffs)} figure(s) against what is live:")
            for d_ in diffs:
                log(f"{tag}    {d_}")
        else:
            log(f"{tag}no figure differs from what is live")
        rollback("--dry-run: reporting only, nothing published")
        return 0

    run(["git", "add", "-A"])
    msg = (f"Week {wk_ed[0]} edition {wk_ed[1]}, issued {d}: built and published "
           f"on this machine by tools/weekly_build.py\n\n"
           f"Extracts pulled, activity and call tables rebuilt, every generated "
           f"region re-rendered, the outgoing edition archived, both gates run "
           f"before anything was committed. Data to {built_rec}. {tally}.")
    for cmd, what in ((["git", "commit", "-m", msg], "commit"),
                      (["git", "push"], "push")):
        r = run(cmd)
        if r.returncode != 0:
            rollback(f"{what} failed: " + (r.stderr or r.stdout)[:200])
            return 1
    sha = run(["git", "rev-parse", "HEAD"]).stdout.strip()[:8]
    bad_urls = []
    for u in (SITE, SITE + "routes.html"):
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                            "-L", "--max-time", "30", u], capture_output=True, text=True)
        if r.stdout.strip() != "200":
            bad_urls.append(f"{u} -> {r.stdout.strip() or 'no response'}")
    log(f"PUBLISHED week {wk_ed[0]} edition {wk_ed[1]} as {sha}"
        + (f"; live check: {'; '.join(bad_urls)} (Pages can lag)" if bad_urls
           else "; live URLs returned 200"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
