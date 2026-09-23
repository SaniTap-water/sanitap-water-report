# -*- coding: utf-8 -*-
"""Recompute each portfolio pump's water-quality result and roof count.

WHY THIS EXISTS
---------------
PUMPS[].wq, wq_date and benef were written once, when the page was first
built, and never recomputed: no tool in this repository wrote them. So when
742894057 joined the portfolio on 23 September it arrived with all three blank,
and the page counted it as untested although mWater held a passing result.
This recomputes them for EVERY portfolio pump on every build, from the live
extracts, by the rules the stored values were built with. Both rules were
proved against the stored values before this replaced them: they reproduce
729 of 729 water-quality results and 724 of 724 roof counts exactly.

WATER QUALITY (SDWS 3): the latest result on the live water-quality results
form (wq_results.json), by its result date (WS7.10); "Pass" when E. coli
(WS7.11) is 0 CFU/100 mL, otherwise "Fail". wq_date is that result date.
wq_status is "tested" or "not tested", on every row, so a missing result is a
stated fact rather than a blank.

ROOF COUNT (the roof-count census): the pump's record on the beneficiary
roof-count form (roof_count.json), people = roofs / 2.5 x 4.5, rounded half
up. A pump with no roof-count record has none, and says so by being null.

    python3 tools/rebuild_pump_inputs.py            # show what would change
    python3 tools/rebuild_pump_inputs.py --write
"""
import collections, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
PAGE = os.path.join(REPO, "index.html")
EXPORTS = os.path.expanduser("~/mwater-exports")

Q_WQ_DATE = "630ccd46f76f420692572e0db2d86ad8"    # WS7.10 result date & time
Q_WQ_ECOLI = "892f1d81bf1a4c4483e53271dda474a5"   # WS7.11 E. coli CFU/100 mL
Q_ROOF_WP = "e796e451be1243d58b547bc0f6c1d5b4"    # ID du point d'eau
Q_ROOFS = "00ae079e071a40349e0706c659430f9b"      # Nombre de toits
ROOF_TO_PEOPLE = 4.5 / 2.5


def compute():
    import populations as P
    wq = collections.defaultdict(list)
    for r in P._wq_results():
        if r.get("status") in ("draft", "rejected"):
            continue
        d = str(P._answer(r, Q_WQ_DATE) or r.get("submittedOn") or "")[:10]
        wq[P._point_of(r)].append((d, P._answer(r, Q_WQ_ECOLI)))
    p = os.path.join(EXPORTS, "roof_count.json")
    if not os.path.isfile(p):
        sys.exit("The roof-count extract (roof_count.json) is missing, so the "
                 "per-pump roof counts could not be recomputed.")
    roofs = collections.defaultdict(list)
    for r in json.load(open(p, encoding="utf8")):
        if r.get("status") in ("draft", "rejected"):
            continue
        site = P._answer(r, Q_ROOF_WP)
        code = site.get("code") if isinstance(site, dict) else None
        n = P._answer(r, Q_ROOFS)
        if code and n is not None:
            roofs[code].append((r.get("submittedOn") or "", n))
    out = {}
    for code in set(wq) | set(roofs):
        v = {}
        if wq.get(code):
            date, ec = sorted(wq[code])[-1]
            v["wq_date"] = date or None
            v["wq"] = "Pass" if ec == 0 else ("Fail" if ec is not None else None)
        if roofs.get(code):
            n = sorted(roofs[code])[-1][1]
            v["benef"] = int(n * ROOF_TO_PEOPLE + 0.5)
        out[code] = v
    return out


def apply(rows, got):
    moved = []
    for row in rows:
        v = got.get(row["wp"], {})
        want = {"wq": v.get("wq"), "wq_date": v.get("wq_date"),
                "benef": v.get("benef")}
        want["wq_status"] = "tested" if want["wq"] else "not tested"
        for k, x in want.items():
            if row.get(k) != x:
                moved.append((row["wp"], k, row.get(k), x))
                row[k] = x
    return moved


def main():
    got = compute()
    src = open(PAGE, encoding="utf8").read()
    moved_all = []
    for name in ("PUMPS", "DOWN"):
        m = re.search(r"\bconst %s\s*=\s*" % name, src)
        if not m:
            continue
        i = m.end()
        j = src.index("];", i) + 1
        rows = json.loads(src[i:j])
        if name == "DOWN" and rows and "wq_date" not in rows[0]:
            continue
        moved = apply(rows, got)
        moved_all += [(name,) + x for x in moved]
        src = src[:i] + json.dumps(rows, ensure_ascii=False) + src[j:]
    real = [x for x in moved_all if x[2] != "wq_status"]
    print(f"per-pump inputs: {len(real)} value(s) differ from what the page held"
          + (f"; wq_status set on every row" if any(x[2] == "wq_status" for x in moved_all) else ""))
    for x in real[:12]:
        print(f"  {x[0]} {x[1]} {x[2]}: {x[3]!r} -> {x[4]!r}")
    if "--write" in sys.argv:
        open(PAGE, "w", encoding="utf8").write(src)
    return 0


if __name__ == "__main__":
    sys.exit(main())
