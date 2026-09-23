# -*- coding: utf-8 -*-
"""WPOPMETA against the WorldPop run's own summary.

Six WPOPMETA fields were on the ungenerated backlog as "hand-maintained by
design". They are not hand-maintained: the allocation run writes every one of
them to sdws1_summary_equal.json and always did. The repository just never kept
a copy, so a figure the run computed sat on the page with nothing able to check
it - the same shape as S.wq_tested, one directory away.

    python3 tools/check_wpopmeta.py
"""
import json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
ART = os.path.join(REPO, "data", "sdws1_summary_equal.json")

# page field -> field in the run summary
FROM_RUN = {
    "rows": "points",
    "points_with_a_barrier": "points_with_a_barrier",
    "points_cut_over_10pct": "points_cut_over_10pct",
    "points_at_the_cap": "points_at_the_cap",
    "raster_national_sum": "raster_national_sum",
    "raster": "raster",
}


def main():
    run = json.load(open(ART, encoding="utf8"))
    src = open(PAGE, encoding="utf8").read()
    m = re.search(r"^const WPOPMETA\s*=\s*", src, re.M)
    if not m:
        print("check_wpopmeta: WPOPMETA not found")
        return 2
    page = json.loads(src[m.end():src.index("};", m.end()) + 1])

    fails = []
    print(f'{"FIELD":24} {"PAGE":>22}  {"RUN SUMMARY":>22}')
    for pf, rf in FROM_RUN.items():
        a, b = page.get(pf), run.get(rf)
        ok = a == b
        if not ok:
            fails.append(f"WPOPMETA.{pf} is {a!r}; the run wrote {b!r}")
        print(f"{pf:24} {str(a)[:22]:>22}  {str(b)[:22]:>22}  {'ok' if ok else '** DIFFERS **'}")
    print(f"\nrun: {run.get('_run')}, copied {run.get('_copied')}")
    if fails:
        print("\nFAILED:")
        for f in fails:
            print("  " + f)
        print("\nRe-copy the run summary, or re-run the allocation. Do not edit "
              "the page to match.")
        return 1
    print("every WPOPMETA field the run produces matches the run's own summary.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
