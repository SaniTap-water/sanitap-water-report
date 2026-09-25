# -*- coding: utf-8 -*-
"""Negative test: hold one extract back a week and the build must fail, naming it.

A gate that has never been seen to fail is not known to work. This doctors a
copy of the manifest - the real one is not touched - sets one extract's pull
date a week into the past, and asserts that check_vintage.py exits non-zero and
says which file.

    python3 tools/test_vintage.py
"""
import datetime, json, os, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO, "data", "extract_manifest.json")
CHECK = os.path.join(REPO, "tools", "check_vintage.py")


def run(path, asof):
    r = subprocess.run([sys.executable, CHECK, "--manifest", path,
                        "--as-of", asof, "--no-write"],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    man = json.load(open(MANIFEST, encoding="utf8"))
    files = man.get("files") or {}
    asof = datetime.date.today().isoformat()
    fails = []

    rc, out = run(MANIFEST, asof)
    print(f"1. the real manifest, unmodified            -> exit {rc}")
    if rc != 0:
        fails.append("the unmodified manifest should pass and did not:\n" + out[-400:])

    # pick an extract pulled by the build, not the separately-pulled register
    victim = next((k for k in sorted(files)
                   if k != "wp_madavance.csv" and files[k].get("written")), None)
    if not victim:
        print("no candidate extract in the manifest; cannot run the negative test")
        return 2

    doctored = json.loads(json.dumps(man))
    was = doctored["files"][victim]["written"]
    back = (datetime.date.fromisoformat(was[:10])
            - datetime.timedelta(days=7)).isoformat()
    doctored["files"][victim]["written"] = back + was[10:]
    tmp = os.path.join(tempfile.gettempdir(), "vintage_negative.json")
    json.dump(doctored, open(tmp, "w", encoding="utf8"))

    rc, out = run(tmp, asof)
    named = victim in out
    print(f"2. {victim} held back 7 days ({was[:10]} -> {back})")
    print(f"   -> exit {rc}, names the file: {named}")
    if rc == 0:
        fails.append(f"a week-old {victim} did NOT fail the build")
    if not named:
        fails.append(f"the failure did not name {victim}")
    for line in out.splitlines():
        if victim in line and ("STALE" in line or "before this build" in line):
            print("   " + line.strip())

    # The floor is the minimum across ALL extracts, so holding one back only
    # moves it when that file becomes the oldest. Assert the floor IS the
    # minimum - not that it equals the victim, which was the first version of
    # this test and was simply wrong: wp_madavance.csv is pulled separately and
    # was already older.
    pulls = {k: v["written"][:10] for k, v in doctored["files"].items()
             if v.get("written")}
    floor = min(pulls.values())
    rc2, out2 = run(tmp, asof)
    ok = f"data to (OLDEST pull)      : {floor}" in out2
    who = [k for k, v in pulls.items() if v == floor]
    print(f"3. the stated 'data to' is the true minimum {floor} "
          f"[{', '.join(who)}]: {ok}")
    if not ok:
        fails.append(f"the vintage floor is not the oldest pull ({floor})")

    # and when the victim IS the oldest, the floor must follow it
    deep = json.loads(json.dumps(doctored))
    for k in deep["files"]:
        if k != victim and deep["files"][k].get("written"):
            deep["files"][k]["written"] = was
    deep["files"][victim]["written"] = back + was[10:]
    tmp2 = os.path.join(tempfile.gettempdir(), "vintage_negative2.json")
    json.dump(deep, open(tmp2, "w", encoding="utf8"))
    rc3, out3 = run(tmp2, asof)
    followed = f"data to (OLDEST pull)      : {back}" in out3
    print(f"4. with {victim} the oldest, the floor follows it to {back}: {followed}")
    if not followed:
        fails.append("the floor did not follow the oldest extract down")

    # 5. the run-level rule: a file written the same day but before this run
    # started passes the day rule and must still fail. Every extract is made
    # current, then one is set a second before the run's start.
    same = json.loads(json.dumps(man))
    start = datetime.datetime.now().replace(microsecond=0)
    for k in same["files"]:
        same["files"][k]["written"] = (start + datetime.timedelta(seconds=5)).isoformat()
    tmp3 = os.path.join(tempfile.gettempdir(), "vintage_negative3.json")
    json.dump(same, open(tmp3, "w", encoding="utf8"))
    since = ["--since", start.isoformat()]
    r_ok = subprocess.run([sys.executable, CHECK, "--manifest", tmp3, "--as-of", asof,
                           "--no-write"] + since, capture_output=True, text=True)
    same["files"][victim]["written"] = (start - datetime.timedelta(seconds=1)).isoformat()
    json.dump(same, open(tmp3, "w", encoding="utf8"))
    r_bad = subprocess.run([sys.executable, CHECK, "--manifest", tmp3, "--as-of", asof,
                            "--no-write"] + since, capture_output=True, text=True)
    named5 = victim in r_bad.stdout and "before this run started" in r_bad.stdout
    print(f"5. every extract written by this run -> exit {r_ok.returncode}; "
          f"{victim} written 1 s before the run started -> exit {r_bad.returncode}, "
          f"names it: {named5}")
    if r_ok.returncode != 0:
        fails.append("extracts all written by this run should pass the run rule")
    if r_bad.returncode == 0 or not named5:
        fails.append(f"an extract written before this run started did NOT fail and name {victim}")

    print()
    if fails:
        print("TEST FAILED:")
        for f in fails:
            print("  " + f)
        return 1
    print("negative test passed: a stale extract fails the build and is named, "
          "and the stated vintage follows it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
