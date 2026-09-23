# -*- coding: utf-8 -*-
"""Build the weekly edition on this machine, then publish it through publish.sh.

The edition used to be built in a cloud session that could not publish, wrote
its output into the Windows Downloads folder and asked for a manual push. On
21 September nobody pushed and a complete edition sat there all day. Every
piece it needed now lives here, so the build runs here and the cloud session
is reduced to a watchdog.

THIS SCRIPT BUILDS; tools/publish.sh GATES AND PUBLISHES. Until 23 September
this script carried its own gate list - the render gate and the consistency
checker - and committed and pushed itself, so the automated edition skipped
the figure census, the prose gate, the link check and the migration check that
every manual publish runs. There is now one gate list, in publish.sh, and both
paths go through it: a dry run calls `publish.sh --check-only`, a real run
calls `publish.sh -m`. publish.sh also archives the outgoing edition.

The working tree is clean before anything starts and HEAD is remembered; any
failure after the first write rolls the tree back to it, so a half-built
edition can never be left behind - and never published.

SAFE TO RUN MORE THAN ONCE A WEEK. A second run in the same ISO week pulls
live mWater again and republishes OVER the current edition: same week, same
edition number, today's issue date. The outgoing edition is archived only when
the incoming one belongs to a later week (tools/archive_edition.py), so a
mid-week update adds nothing to editions/ and cannot duplicate an entry.
The scheduled retries (every two hours on Mondays) exist for a machine that
was off, so once today's edition is out a retry does nothing - unless an
update was asked for: the desktop shortcut "Update water report now" drops
logs/update_requested before starting the task, and that forces one rebuild.

A candidate in Downloads is still considered, and preferred only when its
data is genuinely newer than what this build produced; it goes through the
same publish.sh gates as the local build.

    python3 tools/weekly_build.py --dry-run   # build, run every gate, stop before commit/push, roll back
    python3 tools/weekly_build.py             # and publish through publish.sh
    python3 tools/weekly_build.py --force     # rebuild even if today's edition is out
"""
import datetime, io, json, os, re, shutil, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = "/home/bushp/sdws1/venv/bin/python"
PW = "/home/bushp/.cache/ms-playwright"
LOG = os.path.join(REPO, "logs", "publisher.log")
DROP = os.environ.get("SANITAP_DROP", "/mnt/c/Users/bushp/Downloads")
SITE = "https://sanitap-water.github.io/sanitap-water-report/"
# Dropped by the desktop shortcut before it starts the scheduled task, so an
# on-demand run is told apart from a scheduled retry. Consumed on read.
REQUEST = os.path.join(REPO, "logs", "update_requested")

# (script, args, must it succeed?)  Order matters: pull first, render last.
# BUILD STEPS ONLY. The form-snapshot refresh and every gate are run by
# tools/publish.sh, which this script calls at the end - listing gates here as
# well is how the two paths drifted apart. (publish.sh re-runs three of the
# region generators below; regenerating is idempotent, so that is harmless.)
STEPS = [
    ("tools/pull_extract.py",        ["--write"],      True),
    # the whole mWater group, classified silently: a new pump that meets the
    # rule joins PUMPS here, anything unclassifiable is logged for review
    ("tools/classify_register.py",   ["--write"],      True),
    # a pump that joined or left: rerun the WorldPop allocation for it and
    # every pump whose 1 km area overlaps it, or fail rather than publish blanks
    ("tools/rerun_wpop.py",          ["--write"],      True),
    ("tools/rebuild_activity.py",    ["--write"],      True),
    # water-quality result and roof count, for every portfolio pump
    ("tools/rebuild_pump_inputs.py", ["--write"],      True),
    ("tools/build_call_tables.py",   ["--write"],      True),
    ("tools/rebuild_ttr.py",         ["--write"],      True),
    ("tools/rebuild_summary.py",     ["--write"],      True),
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
    ("tools/render_ttr_table.py",    ["--write"],      True),
    ("tools/render_actions.py",      ["--write"],      True),
    # the Endur'O block and the inlined datasets, so every figure the prose
    # quotes is reachable from the page's own data
    # the carbon denominator is derived from the register, so it must be
    # recomputed before the datasets are inlined
    ("tools/carbon_denominator.py",  ["--write"],      True),
    # the semantic layer, and everything that renders from it
    ("tools/populations.py",         ["--json", "data/populations.json"], True),
    # REG counts that are populations, written from them (REG.succ was stored)
    ("tools/sync_reg_populations.py", ["--write"],     True),
    ("tools/render_derivations.py",  ["--write"],      True),
    ("tools/render_definitions.py",  ["--write"],      True),
    ("tools/rebuild_sdws26.py",      ["--write"],      True),
    ("tools/render_sdws26.py",       ["--write"],      True),
    ("tools/render_carbon_params.py",["--write"],      True),
    ("tools/render_enduro.py",       ["--write"],      True),
    ("tools/render_datasets.py",     ["--write"],      True),
    # the portfolio map page, from the report's own PUMPS and WPOP
    ("tools/render_portfolio.py",    ["--write"],      True),
]


def log(line):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    io.open(LOG, "a", encoding="utf8").write(f"{ts}  {line}\n")
    print(line)


def said(sentence):
    """The one plain sentence tools/weekly_build.sh writes as the run's last
    log line ("OUTCOME: ..."), for the Monday watchdog to quote."""
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    io.open(os.path.join(os.path.dirname(LOG), "last_outcome.txt"), "w",
            encoding="utf8").write(sentence.rstrip(".") + ".")


def plain_refusal(lines):
    """Why publish.sh stopped, as one sentence: its ABORT line, plus the first
    specific item it names (a failing check, or the figure with no source)."""
    if any("git push FAILED" in l for l in lines):
        return ("the edition passed every gate and was committed, but GitHub "
                "refused the push, so the commit was rolled back")
    abort = next((l for l in lines if l.startswith("ABORT")), None)
    why = (abort.split(":", 1)[1].strip().rstrip(".") if abort
           else (lines[-1] if lines else "it gave no reason"))
    detail = next((l.split("FAIL")[0].strip() for l in lines if "FAIL !" in l), None)
    if not detail:
        # the figure gates name the value and the section on an indented line
        for i, l in enumerate(lines):
            if "GATE FAILED" in l:
                vals = [x.strip() for x in lines[i + 1:i + 6]
                        if x.strip() and not x.strip().startswith(("Each", "Make"))]
                detail = vals[0] if vals else None
                break
    why = re.sub(r"\s*\(exit \d+\)", "", why)
    detail = re.sub(r"\s+", " ", detail) if detail else detail
    return f"publish.sh refused the edition because {why}" + (
        f" (first: {detail})" if detail else "")


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


def publish_sh(dry, msg):
    """THE gate list, and the only way anything is published.

    --check-only runs every gate and stops before commit and push; -m runs the
    same gates, then commits and pushes. Returns (ok, one-line summary, tally).
    """
    args = ["--check-only"] if dry else ["-m", msg]
    r = run(["bash", "tools/publish.sh"] + args)
    out = (r.stdout or "") + (r.stderr or "")
    io.open(os.path.join(REPO, "logs", "last_publish_sh.txt"), "w",
            encoding="utf8").write(out)
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    tally = next((l for l in lines if re.search(r"\d+ checks,", l)), "")
    if r.returncode != 0:
        why = next((l for l in lines if l.startswith("ABORT") or "FAILED" in l),
                   lines[-1] if lines else "no output")
        fails = [l.split("FAIL")[0].strip() for l in lines if "FAIL !" in l][:4]
        return False, plain_refusal(lines), tally
    return True, (lines[-1] if lines else ""), tally


def main():
    argv = sys.argv[1:]
    dry = "--dry-run" in argv
    tag = "[dry-run] " if dry else ""
    requested = os.path.isfile(REQUEST)
    if requested:
        # consume it now: one click asks for one rebuild, not a standing one
        try:
            os.remove(REQUEST)
        except OSError:
            pass
        log(f"{tag}update requested on demand (desktop shortcut)")
    dirty = [l for l in run(["git", "status", "--porcelain"]).stdout.splitlines()
             if l.strip() and not l[3:].startswith("logs/")]
    if dirty:
        log(f"{tag}REFUSED: working tree is not clean, {len(dirty)} path(s): "
            + ", ".join(l[3:] for l in dirty[:3]))
        said("Not published: the working tree had uncommitted changes ("
             + ", ".join(l[3:] for l in dirty[:3]) + "), so nothing was built")
        return 1
    # The scheduled retries exist for a machine that was off, not to republish
    # every two hours. Once today's edition is out a retry does nothing - unless
    # an update was asked for (the shortcut), --force, or --dry-run. A run on
    # any later day of the week rebuilds and republishes over the current
    # edition; publish.sh archives only across a week boundary.
    today = datetime.date.today()
    issued, _ = masthead_of(os.path.join(REPO, "index.html"))
    if issued == today and not (requested or dry or "--force" in argv):
        log(f"already built today: the published edition is issued {issued}")
        said(f"Nothing to do: today's edition ({issued}) is already published "
             "and no update was asked for")
        return 0
    head = run(["git", "rev-parse", "HEAD"]).stdout.strip()

    def rollback(why, sentence=None):
        run(["git", "reset", "--hard", head])
        run(["git", "clean", "-fd", "editions", "data"])
        log(f"{tag}REFUSED and ROLLED BACK to {head[:8]}: {why}")
        if sentence:
            said(sentence)

    try:
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
        d, wk_ed = masthead_of(os.path.join(REPO, "index.html"))
        built_rec = newest_record(os.path.join(REPO, "index.html"))
    except Exception as e:                                     # noqa: BLE001
        rollback(str(e), ("Dry run failed" if dry else "Not published")
                 + f": the build step {e}, so the tree was rolled back")
        return 1

    # A Downloads candidate is still considered, and preferred only when its
    # DATA is genuinely newer than what we just built. It is gated by the same
    # publish.sh as everything else; if it fails, the local build goes back in.
    source = "built on this machine by tools/weekly_build.py"
    cand = os.path.join(DROP, "index.html")
    if os.path.isfile(cand):
        c_rec = newest_record(cand)
        if c_rec and built_rec and c_rec > built_rec:
            keep = {f: io.open(os.path.join(REPO, f), encoding="utf8").read()
                    for f in ("index.html", "routes.html")
                    if os.path.isfile(os.path.join(REPO, f))}
            for f in ("index.html", "routes.html"):
                if os.path.isfile(os.path.join(DROP, f)):
                    shutil.copy2(os.path.join(DROP, f), os.path.join(REPO, f))
            c_ok, c_why, _ = publish_sh(True, None)
            if c_ok:
                log(f"{tag}the Downloads candidate holds newer data "
                    f"({c_rec} against {built_rec}) and passed publish.sh - "
                    "preferring it over the local build")
                source = f"taken from the Downloads drop (data to {c_rec})"
                d, wk_ed = masthead_of(os.path.join(REPO, "index.html"))
                built_rec = c_rec
            else:
                for f, t in keep.items():
                    io.open(os.path.join(REPO, f), "w", encoding="utf8").write(t)
                log(f"{tag}the Downloads candidate holds newer data ({c_rec}) but "
                    f"failed publish.sh, so the local build stands: {c_why[:200]}")

    nonfatal = (" optional step(s) skipped: " + ", ".join(failures)) if failures else ""
    wk, ed = wk_ed if wk_ed else ("?", "?")
    msg = (f"Week {wk} edition {ed}, issued {d}: {source}\n\n"
           f"Extracts pulled, activity and call tables rebuilt, every generated "
           f"region re-rendered, then gated and published by tools/publish.sh. "
           f"Data to {built_rec}.{nonfatal}")
    ok, why, tally = publish_sh(dry, msg)
    if not ok:
        rollback("publish.sh refused: " + why,
                 ("Dry run failed" if dry else "Not published") + ": " + why)
        return 1
    log(f"{tag}built week {wk} edition {ed}, issued {d}, data to {built_rec}; "
        f"every publish.sh gate passed ({tally}).{nonfatal}")

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
        rollback("--dry-run: stopped before commit and push, nothing published")
        said(f"Dry run passed: week {wk} edition {ed} was built from data to "
             f"{built_rec}, every publish.sh gate passed ({tally}), and it "
             "stopped before commit and push as asked")
        return 0

    sha = run(["git", "rev-parse", "HEAD"]).stdout.strip()[:8]
    bad_urls = []
    for u in (SITE, SITE + "routes.html"):
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                            "-L", "--max-time", "30", u], capture_output=True, text=True)
        if r.stdout.strip() != "200":
            bad_urls.append(f"{u} -> {r.stdout.strip() or 'no response'}")
    said(f"Published week {wk} edition {ed}, issued {d}, as commit {sha}")
    log(f"PUBLISHED week {wk} edition {ed} as {sha}"
        + (f"; live check: {'; '.join(bad_urls)} (Pages can lag)" if bad_urls
           else "; live URLs returned 200"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
