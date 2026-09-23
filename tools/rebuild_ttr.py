# -*- coding: utf-8 -*-
"""Recompute the time-to-repair statistics from the population they are over.

All thirteen TTR fields were stored and computed by nothing - the median, the
mean, the within-3-day and within-7-day shares, and the site and year splits,
all of them carrying the repair-time figures the page reports. The stored
sample size of 606 reproduced from no rule and was withdrawn; the population
repairs_time_measured is 617, and the median of 1.0 days and mean of 3.6 days
reproduce exactly on it, so nothing published moves.

This computes the eight ttr_* fields from that population. It does NOT compute
the five call_* fields: no filter on the call-centre extract reproduces their
122 / 90 / 32, and inventing one to make them fit is the fault this whole
exercise exists to stop. They stay on the ungenerated backlog and are named
there.

    python3 tools/rebuild_ttr.py            # show what it would write
    python3 tools/rebuild_ttr.py --write
"""
import json, os, re, statistics, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
PAGE = os.path.join(REPO, "index.html")

# Computed here; anything else in TTR is left exactly as it was.
OWNED = ["ttr_n", "ttr_median", "ttr_mean", "ttr_3d", "ttr_7d",
         "ttr_Maroantsetra", "ttr_Fort-Dauphin", "ttr_2026"]


def stats(vals):
    """[median, mean, n] - the shape the page already reads."""
    if not vals:
        return [None, None, 0]
    return [float(round(statistics.median(vals), 1)),
            float(round(statistics.mean(vals), 1)), len(vals)]


def compute():
    import populations as P
    keep = P.repairs_time_measured()
    site = {p["wp"]: p.get("site") for p in P._page_pumps()}
    rows = []
    for src, r in P._repair_records():
        if r["_id"] not in keep:
            continue
        d = P._repair_interval(src, r)
        if d is None:
            continue
        rows.append((d, site.get(P._point_of(r)),
                     str(r.get("submittedOn") or "")[:4]))
    days = [d for d, _s, _y in rows]
    out = {
        "ttr_n": len(days),
        "ttr_median": float(round(statistics.median(days), 1)),
        "ttr_mean": float(round(statistics.mean(days), 1)),
        "ttr_3d": round(100 * sum(1 for d in days if d <= 3) / len(days)),
        "ttr_7d": round(100 * sum(1 for d in days if d <= 7) / len(days)),
    }
    for s in ("Maroantsetra", "Fort-Dauphin"):
        out[f"ttr_{s}"] = stats([d for d, st, _y in rows if st == s])
    out["ttr_2026"] = stats([d for d, _s, y in rows if y == "2026"])
    return out, rows


def main():
    write = "--write" in sys.argv
    new, rows = compute()
    src = open(PAGE, encoding="utf8").read()
    m = re.search(r"^const TTR\s*=\s*", src, re.M)
    if not m:
        sys.exit("rebuild_ttr: const TTR not found")
    j = src.index("};", m.end())
    cur = json.loads(src[m.end():j + 1])

    print(f'{"FIELD":18} {"STORED":>16}  {"COMPUTED":>16}')
    moved = 0
    for k in OWNED:
        a, b = cur.get(k), new[k]
        flag = "" if a == b else "   <-- moves"
        if a != b:
            moved += 1
        print(f"{k:18} {str(a):>16}  {str(b):>16}{flag}")
    unowned = [k for k in cur if k not in OWNED]
    print(f"\nleft untouched (no rule reproduces them): {', '.join(unowned)}")
    print(f"{len(rows)} timed repairs; {moved} of {len(OWNED)} fields move")

    if not write:
        print("\n--dry run: nothing written")
        return 0
    cur.update(new)
    out = (src[:m.end()] + json.dumps(cur, separators=(", ", ": "))
           + src[j + 1:])
    open(PAGE, "w", encoding="utf8").write(out)
    print(f"\nindex.html: TTR rewritten, {len(OWNED)} fields computed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
