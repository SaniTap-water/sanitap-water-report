#!/usr/bin/env python3
"""Run one build step under a time limit, and never leave it running (21 Oct 2026).

    python3 tools/limit.py SECONDS STEP -- COMMAND [ARG ...]

The command runs in a session of its own, with this process's stdin, stdout
and stderr, and its exit status is passed through. If it is still running
after SECONDS, every process in that session - the command and anything it
started (node, Chromium) - gets SIGTERM, then SIGKILL 10 s later, and this
exits 124 after printing one line naming the step:

    TIMEOUT: <STEP> ran longer than <N> min and was stopped (process tree killed)

The limits (Adriaan Mol, 21 Oct 2026): each publish.sh gate 10 min, the
extract pull 60 min, the whole run 2 h. A timeout counts as a failure of that
gate - BLOCKING unless data/gate_classes.json makes the gate REVIEW.

SIGTERM or SIGINT sent to this wrapper (a limit around it expiring, Ctrl-C)
is passed on to the whole session the same way, so nested limits also leave
nothing behind.
"""
import os, signal, subprocess, sys, time

TIMEOUT_EXIT = 124


def procs():
    """pid -> (ppid, session) for every live process (Linux /proc)."""
    out = {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat", encoding="utf8", errors="replace") as fh:
                st = fh.read()
            # fields after the ")" of the command name: state ppid pgrp session ...
            f = st[st.rindex(")") + 2:].split()
            if f[0] != "Z":
                out[int(d)] = (int(f[1]), int(f[3]))
        except (OSError, ValueError, IndexError):
            continue
    return out


def session_pids(sid, seen=()):
    """The session's processes, every descendant of them (Playwright starts
    Chromium in a session of its own), and any of `seen` still alive."""
    ps = procs()
    tree = {pid for pid, (_pp, s) in ps.items() if s == sid} | {p for p in seen if p in ps}
    grew = True
    while grew:
        kids = {pid for pid, (pp, _s) in ps.items() if pp in tree} - tree
        grew = bool(kids)
        tree |= kids
    tree.discard(os.getpid())
    return sorted(tree)


def stop(sid):
    """SIGTERM the session's tree, SIGKILL whatever is left after 10 s. The
    tree is taken before anything is killed: an orphan is re-parented to
    init, so its parent link is lost once its parent dies."""
    seen = set(session_pids(sid))
    for sig, grace in ((signal.SIGTERM, 10), (signal.SIGKILL, 2)):
        seen |= set(session_pids(sid, seen))
        for pid in session_pids(sid, seen):
            try:
                os.kill(pid, sig)
            except OSError:
                pass
        end = time.time() + grace
        while time.time() < end and session_pids(sid, seen):
            time.sleep(0.2)
        if not session_pids(sid, seen):
            return []
    return session_pids(sid, seen)


def main(argv):
    if len(argv) < 4 or argv[2] != "--":
        sys.exit(__doc__)
    limit, step, cmd = float(argv[0]), argv[1], argv[3:]
    p = subprocess.Popen(cmd, start_new_session=True)

    def passed_on(signum, _frame):
        left = stop(p.pid)
        print(f"STOPPED: {step} was stopped by signal {signum} (process tree killed"
              + (f"; still running: {left}" if left else "") + ")", flush=True)
        sys.exit(128 + signum)

    signal.signal(signal.SIGTERM, passed_on)
    signal.signal(signal.SIGINT, passed_on)
    try:
        rc = p.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        left = stop(p.pid)
        p.wait()
        print(f"TIMEOUT: {step} ran longer than {limit / 60:g} min and was stopped (process tree killed"
              + (f"; STILL RUNNING: {left}" if left else "") + ")", flush=True)
        return TIMEOUT_EXIT
    # a finished command may have left children behind in its session
    left = stop(p.pid) if session_pids(p.pid) else []
    if left:
        print(f"WARNING: {step} left processes that could not be stopped: {left}", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
