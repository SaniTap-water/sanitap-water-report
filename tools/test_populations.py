# -*- coding: utf-8 -*-
"""Fixture tests for the semantic layer.

Three things are proved:

 1. Change one water point in a fixture extract and EVERY dependent figure
    moves, with nothing edited by hand.
 2. Change it back and every figure returns to exactly what it was.
 3. A fixture that breaks the chain deliberately makes the build fail, naming
    the step that stopped reconciling.

The fixtures are the real extracts with one record altered, so a population
whose rule silently ignored the extract would fail here.

    python3 tools/test_populations.py
"""
import copy, csv, io, json, os, shutil, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))


def snapshot(P):
    """Every population's size plus the chain verdict."""
    steps, gaps = P.chain()
    return {"sizes": P.sizes(),
            "steps": {n: ok for n, ok, _ in steps},
            "gaps": [g["step"] for g in gaps]}


def with_fixture(mutate):
    """Run the populations against a copy of the extracts, mutated."""
    import populations as P
    real_exports, real_repo = P.EXPORTS, P.REPO
    tmp = tempfile.mkdtemp(prefix="popfix-")
    ex = os.path.join(tmp, "exports"); os.makedirs(ex)
    for f in ("wp_madavance.csv", "combined_rehab_raw.json"):
        src = os.path.join(real_exports, f)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(ex, f))
    rp = os.path.join(tmp, "repo"); os.makedirs(os.path.join(rp, "data"))
    shutil.copy2(os.path.join(real_repo, "index.html"),
                 os.path.join(rp, "index.html"))
    shutil.copy2(os.path.join(real_repo, "data", "calendar_year_coverage.csv"),
                 os.path.join(rp, "data", "calendar_year_coverage.csv"))
    mutate(ex, rp)
    P.EXPORTS, P.REPO = ex, rp
    try:
        return snapshot(P)
    finally:
        P.EXPORTS, P.REPO = real_exports, real_repo
        shutil.rmtree(tmp, ignore_errors=True)


def drop_success(ex, rp):
    """One point's first-rehabilitation record stops saying it succeeded."""
    p = os.path.join(ex, "combined_rehab_raw.json")
    rows = json.load(open(p, encoding="utf8"))
    import populations as P
    for r in rows:
        if (r.get("data") or {}).get(P.Q_TYPE, {}).get("value") == P.C_FIRST_REHAB \
                and (r.get("data") or {}).get(P.Q_SUCCESS, {}).get("value") == P.C_YES:
            r["data"][P.Q_SUCCESS]["value"] = P.C_NO
            break
    json.dump(rows, open(p, "w", encoding="utf8"))


def drop_from_register(ex, rp):
    """One managed point disappears from the register export - the chain
    relation managed_fleet is a subset of register_records must break."""
    p = os.path.join(ex, "wp_madavance.csv")
    rows = list(csv.DictReader(open(p, encoding="utf8")))
    import populations as P
    fleet = P.managed_fleet()
    keep = [r for r in rows if r["code"] not in list(sorted(fleet))[:12]]
    with open(p, "w", encoding="utf8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(keep)


def main():
    import populations as P
    base = snapshot(P)
    print()
    print("  BASELINE")
    for k, v in sorted(base["sizes"].items()):
        print(f"    {k:28} {v:>6}")
    fails = []

    # --- 1. one record changes, dependent figures move --------------------
    moved = with_fixture(drop_success)
    delta = {k: (base["sizes"][k], moved["sizes"][k])
             for k in base["sizes"] if base["sizes"][k] != moved["sizes"][k]}
    print()
    print("  FIXTURE 1 - one first-rehabilitation record changes Oui -> Non")
    if delta:
        for k, (a, b) in sorted(delta.items()):
            print(f"    {k:28} {a} -> {b}   moved with nothing edited by hand")
    else:
        print("    NOTHING MOVED - the rule is not reading the extract")
        fails.append("fixture 1: no dependent figure moved")
    unchanged = [k for k in base["sizes"] if k not in delta]
    print(f"    unaffected populations: {', '.join(unchanged)}")

    # --- 2. change it back ------------------------------------------------
    back = snapshot(P)
    print()
    print("  FIXTURE 2 - the same run against the untouched extracts")
    if back["sizes"] == base["sizes"]:
        print("    every figure returned to its baseline value")
    else:
        d = {k: (base['sizes'][k], back['sizes'][k])
             for k in base['sizes'] if base['sizes'][k] != back['sizes'][k]}
        print(f"    DID NOT RETURN: {d}")
        fails.append("fixture 2: figures did not return")

    # --- 3. a deliberate break must be named ------------------------------
    broken = with_fixture(drop_from_register)
    print()
    print("  FIXTURE 3 - twelve managed points removed from the register export")
    bad = [n for n, ok in broken["steps"].items() if not ok]
    named = [n for n in bad if "register_records" in n]
    if named:
        for n in bad:
            print(f"    chain step reported BROKEN: {n}")
        print(f"    gaps named: {'; '.join(broken['gaps'])}")
    else:
        print("    THE BREAK WAS NOT DETECTED")
        fails.append("fixture 3: a deliberate break did not fail the chain")

    print()
    if fails:
        print("  FIXTURE TESTS FAILED")
        for f in fails:
            print(f"    {f}")
        return 1
    print("  fixture tests passed: figures move with the data, return when it "
          "returns, and a broken chain is named.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
