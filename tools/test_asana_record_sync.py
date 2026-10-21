# -*- coding: utf-8 -*-
"""Negative test: a record deadline that differs from Asana, and did not come
from the Asana sync, must fail the consistency check (21 Oct 2026).

Asana is the source of truth for due dates; tools/asana_pull.py copies them
into data/action_owners.json (sync_from_asana). The consistency check's copy
scan names that one line as not a figure (NOT_A_FIGURE, ("asana_pull.py",
"deadline")). This holds the check to the rest: the page shows Asana's date, so
a record date set any other way, and not equal to Asana's, must still fail
"owners record: the page shows each recorded deadline on its row".

Runs in a temporary git worktree of HEAD, so the real files are not touched;
reads the committed data/asana_pull.json (no Asana call) and the extracts in
~/mwater-exports (no mWater call). Four cases:

  A  the record as committed                       -> passes
  B  one deadline edited by hand, not Asana's      -> fails, naming the action
  C  the record after the sync                     -> passes
  D  the sync, then one deadline edited by hand    -> fails, naming the action

    python3 tools/test_asana_record_sync.py
"""
import json, os, re, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = "owners record: the page shows each recorded deadline on its row"
ACT = "act-call-no-followup"
HAND = "2026-11-20"          # not the task's due date in Asana


def py():
    venv = os.path.expanduser("~/sdws1/venv/bin/python")
    return venv if os.access(venv, os.X_OK) else sys.executable


def deadline_check(wt):
    """-> (PASS or FAIL, the check's line) from the worktree's checker."""
    r = subprocess.run([py(), "tools/check_consistency.py", "index.html", "portfolio.html"],
                       cwd=wt, capture_output=True, text=True,
                       env=dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=os.path.expanduser("~/.cache/ms-playwright")))
    line = next((l for l in r.stdout.splitlines() if CHECK in l), None)
    if line is None:
        sys.exit(f"the check did not run:\n{(r.stdout + r.stderr)[-1500:]}")
    return ("FAIL" if re.search(r"\bFAIL\b", line) else "PASS"), " ".join(line.split())


def edit(wt, fn):
    p = os.path.join(wt, "data", "action_owners.json")
    own = json.load(open(p, encoding="utf8"))
    fn(own)
    open(p, "w", encoding="utf8").write(json.dumps(own, indent=1, ensure_ascii=False) + "\n")


def sync(wt):
    sys.path.insert(0, os.path.join(wt, "tools"))
    import asana_pull as P
    pull = json.load(open(os.path.join(wt, "data", "asana_pull.json"), encoding="utf8"))["tasks"]
    edit(wt, lambda own: P.sync_from_asana(own, pull))
    return pull


def main():
    tmp = tempfile.mkdtemp(prefix="asana-sync-test-")
    wt = os.path.join(tmp, "wt")
    subprocess.run(["git", "-C", REPO, "worktree", "add", "-q", "--detach", wt, "HEAD"], check=True)
    fails = []
    try:
        asana_due = json.load(open(os.path.join(wt, "data", "asana_pull.json"),
                                   encoding="utf8"))["tasks"][ACT]["due_on"]
        assert asana_due != HAND, "pick a hand date that differs from Asana's"
        orig = json.load(open(os.path.join(wt, "data", "action_owners.json"), encoding="utf8"))

        def expect(case, want, named=None):
            got, line = deadline_check(wt)
            ok = got == want and (named is None or named in line)
            print(f"  {'ok  ' if ok else 'BAD '} {case}: {got} (want {want})\n        {line[:230]}")
            if not ok:
                fails.append(case)

        expect("A  the record as committed", "PASS")
        edit(wt, lambda own: own["owners"][ACT].__setitem__("deadline", HAND))
        expect(f"B  {ACT} set by hand to {HAND}, Asana {asana_due}", "FAIL", ACT)
        open(os.path.join(wt, "data", "action_owners.json"), "w", encoding="utf8").write(
            json.dumps(orig, indent=1, ensure_ascii=False) + "\n")
        sync(wt)
        expect("C  the record after the Asana sync", "PASS")
        edit(wt, lambda own: own["owners"][ACT].__setitem__("deadline", HAND))
        expect(f"D  after the sync, {ACT} set by hand to {HAND}", "FAIL", ACT)
    finally:
        subprocess.run(["git", "-C", REPO, "worktree", "remove", "--force", wt])
        shutil.rmtree(tmp, ignore_errors=True)
    print("PASS: a record date not from the Asana sync fails the check" if not fails
          else f"FAILED: {', '.join(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
