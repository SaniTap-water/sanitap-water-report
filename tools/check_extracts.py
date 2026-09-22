# -*- coding: utf-8 -*-
"""Every extract the build reads, checked for the paging fault.

mWater's skip/limit paging has no sort order, so a paged pull duplicates some
rows and silently drops others. It has produced three artefacts already: 48
phantom repeated points, 46 phantom unexplained points, and 643. Both pullers
now walk bounded date windows and de-duplicate on _id, so the fault should be
dead - but "should be" is what the last three were.

This reads the files themselves rather than trusting the puller: any extract
carrying a repeated _id was paged, whatever wrote it.

It also reports extracts that NO pipeline step refreshes. The seven JSON
extracts the semantic layer reads are pulled by tools/mwater/pull_form.mjs,
which no script invokes - so they are refreshed by hand and age silently.

    python3 tools/check_extracts.py
"""
import csv, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS = os.path.expanduser("~/mwater-exports")
MANIFEST = os.path.join(REPO, "data", "extract_manifest.json")

# Read by populations.py; pulled by pull_form.mjs, which the pipeline does not
# call. Listed so their absence or staleness is visible rather than assumed.
UNPIPELINED = ["combined_rehab.json", "repair.json", "wq_results.json",
               "hygiene.json", "identification.json", "marolinta_borehole.json",
               "first_rehab_current.json"]

# Carry duplicates by design or by history, and nothing reads them as data.
# combined_rehab_raw.json is the fixture that proves the fault in the tests.
INERT = {"combined_rehab_raw.json", "combined_rehab_fresh.json",
         "old_combined_reparation.csv"}


def rows_of(path):
    if path.endswith(".json"):
        v = json.load(open(path, encoding="utf8"))
        return v if isinstance(v, list) else []
    with open(path, encoding="utf8") as fh:
        return list(csv.DictReader(fh))


def main():
    if not os.path.isdir(EXPORTS):
        print(f"no extract directory at {EXPORTS}")
        return 2
    fails, checked = [], 0
    print(f'{"EXTRACT":32} {"ROWS":>6} {"UNIQUE":>7} {"DUPES":>6}')
    for f in sorted(os.listdir(EXPORTS)):
        p = os.path.join(EXPORTS, f)
        if not os.path.isfile(p) or not f.endswith((".json", ".csv")):
            continue
        try:
            rows = rows_of(p)
        except Exception as e:
            fails.append(f"{f}: unreadable ({e})")
            continue
        ids = [r.get("_id") for r in rows if isinstance(r, dict) and r.get("_id")]
        dup = len(ids) - len(set(ids))
        checked += 1
        flag = ""
        if dup:
            if f in INERT:
                flag = "  (inert: nothing reads it as data)"
            else:
                flag = "  ** PAGED **"
                fails.append(f"{f}: {dup} repeated _id(s) - this extract was paged")
        print(f"{f:32} {len(rows):6} {len(set(ids)):7} {dup:6}{flag}")

    missing = [f for f in UNPIPELINED if not os.path.isfile(os.path.join(EXPORTS, f))]
    if missing:
        fails.append("extracts the semantic layer reads are absent: "
                     + ", ".join(missing))
    print(f"\n{checked} extract(s) checked")
    print(f"{len(UNPIPELINED)} of them are refreshed by hand, not by the build:")
    for f in UNPIPELINED:
        p = os.path.join(EXPORTS, f)
        age = ("absent" if not os.path.isfile(p) else
               f"written {__import__('datetime').date.fromtimestamp(os.path.getmtime(p))}")
        print(f"    {f:30} {age}")
    if fails:
        print("\nFAILED:")
        for x in fails:
            print("  " + x)
        return 1
    print("\nno extract the build reads carries a repeated _id: the paging fault "
          "is not present in the data in use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
