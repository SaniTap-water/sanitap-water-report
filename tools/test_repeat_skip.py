# -*- coding: utf-8 -*-
"""A repeat of the Monday trigger, once this week's edition is out, does
nothing (21 Oct 2026).

SaniTapWeeklyPublish fires Mondays 09:15 and repeats every 2 h for 14 h, so
every repeat falls on the day the edition was issued. Such a run must stop with
"Nothing to do" and do nothing else: no build step (the extract pull is the
first), no publish.sh, no Asana write, no Downloads candidate
(tools/publish_waiting.py), no commit.

This runs the real tools/weekly_build.sh in a temporary git worktree of HEAD
(SANITAP_BUILD_DIR), on the day its edition was issued (SANITAP_TODAY), with
mWater and Asana writes switched off as a backstop (SANITAP_NO_MWATER,
SANITAP_NO_ASANA_WRITE) and an empty Downloads folder (SANITAP_DROP). The
fetch, reset and hour guard are skipped (SANITAP_SYNCED=1): they touch only
the build clone and its run stamp. A control runs publish_waiting.py on the
same empty folder, to show its line is the one the test looks for.

    python3 tools/test_repeat_skip.py
"""
import os, re, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS = os.path.expanduser("~/mwater-exports")


def snapshot(d):
    return {n: os.path.getmtime(os.path.join(d, n)) for n in sorted(os.listdir(d))} if os.path.isdir(d) else {}


def issued(index):
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import weekly_build as W
    d, _ = W.masthead_of(index)
    return d


def main():
    tmp = tempfile.mkdtemp(prefix="repeat-skip-test-")
    wt, drop = os.path.join(tmp, "wt"), os.path.join(tmp, "downloads")
    os.makedirs(drop)
    subprocess.run(["git", "-C", REPO, "worktree", "add", "-q", "--detach", wt, "HEAD"], check=True)
    fails = []

    def expect(what, ok):
        print(f"  {'ok  ' if ok else 'BAD '} {what}")
        if not ok:
            fails.append(what)

    try:
        day = issued(os.path.join(wt, "index.html"))
        head = subprocess.run(["git", "-C", wt, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        before = snapshot(EXPORTS)
        env = dict(os.environ, SANITAP_BUILD_DIR=wt, SANITAP_SYNCED="1", SANITAP_TODAY=day.isoformat(),
                   SANITAP_NO_MWATER="1", SANITAP_NO_ASANA_WRITE="1", SANITAP_DROP=drop)
        r = subprocess.run(["bash", os.path.join(wt, "tools", "weekly_build.sh")],
                           cwd=wt, env=env, capture_output=True, text=True, timeout=600)
        out = r.stdout + r.stderr
        log = open(os.path.join(wt, "logs", "publisher.log"), encoding="utf8").read() \
            if os.path.isfile(os.path.join(wt, "logs", "publisher.log")) else ""
        print(f"  run on {day} (the edition's issue date): exit {r.returncode}")
        for l in out.strip().splitlines()[-3:]:
            print(f"        {l[:200]}")
        expect("exits 0", r.returncode == 0)
        expect("outcome is 'Nothing to do'", re.search(r"OUTCOME: Nothing to do", out) is not None)
        expect("no build step or publish.sh started (no logs/current_step)",
               not os.path.exists(os.path.join(wt, "logs", "current_step")))
        expect("no Asana write attempted", "asana (no write)" not in out + log and "run-failed" not in out + log)
        expect("no mWater call attempted", "SANITAP_NO_MWATER" not in out + log)
        expect("no Downloads candidate looked at (publish_waiting.py not run)",
               "nothing waiting" not in out + log and "candidate" not in out + log)
        expect("~/mwater-exports untouched", snapshot(EXPORTS) == before)
        now = subprocess.run(["git", "-C", wt, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", wt, "status", "--porcelain"], capture_output=True, text=True).stdout
        expect("no commit and a clean tree", now == head and not [l for l in dirty.splitlines() if "logs/" not in l])

        # control: the Downloads step, run on its own, says the line looked for above
        c = subprocess.run([sys.executable, os.path.join(wt, "tools", "publish_waiting.py"), "--dry-run"],
                           cwd=wt, env=env, capture_output=True, text=True, timeout=120)
        expect("control: publish_waiting.py on its own prints 'nothing waiting'", "nothing waiting" in c.stdout)
    finally:
        subprocess.run(["git", "-C", REPO, "worktree", "remove", "--force", wt])
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASS: a repeat after this week's edition does nothing" if not fails else f"FAILED: {len(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
