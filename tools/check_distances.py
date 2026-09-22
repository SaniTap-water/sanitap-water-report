# -*- coding: utf-8 -*-
"""Every "nearest other point" distance, recomputed from its population.

The corrections log states distances - 827 m, 471 m, 446 m, 1,364 m - as
evidence that a dormant point is not a duplicate of its neighbour. They were
measured by hand against no stated set, which made them the same shape of
figure as 628: written down once, checked by nobody.

The set is now declared. located_register_points is every register record
carrying a coordinate - the whole register, not the managed fleet, because the
nearest point to a dormant one is sometimes a working point and sometimes
another dormant one. This recomputes each stated distance from that population
and fails if any has drifted.

    python3 tools/check_distances.py
"""
import json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
PAGE = os.path.join(REPO, "index.html")

# "Nearest other point 827 m (742895357, also dormant)" / "Nearest other water
# point 1,364 m - not a duplicate."
PAT = re.compile(r"[Nn]earest other (?:water )?point\s+([\d,]+)\s*m")
# "471 m from 742894916, a working India Mark in Ranopiso."
PAT2 = re.compile(r"\b([\d,]+)\s*m from\s+(\d{6,})")


def main():
    import populations as P

    src = open(PAGE, encoding="utf8").read()
    m = re.search(r"^const CORR\s*=\s*", src, re.M)
    if not m:
        print("check_distances: CORR not found")
        return 2
    corr = json.loads(src[m.end():src.index("};", m.end()) + 1])

    rows, fails = [], []
    for key in ("corrected", "excluded", "eligibility_flags"):
        for e in corr.get(key) or []:
            ev = str(e.get("evidence") or "")
            hit = PAT.search(ev) or PAT2.search(ev)
            if not hit:
                continue
            stated = int(hit.group(1).replace(",", ""))
            wp = str(e.get("wp") or "")
            metres, other = P.nearest_other(wp)
            if metres is None:
                fails.append(f"{wp}: states {stated} m but the point carries no "
                             f"coordinate in the register")
                continue
            got = round(metres)
            rows.append((wp, stated, got, other))
            if got != stated:
                fails.append(f"{wp}: states {stated} m, population gives {got} m "
                             f"(nearest is {other})")

    # Write the derived distances out as an artefact, so they are values the
    # repo produces rather than numbers only this script knows.
    out = {"note": "Nearest other located register point, per water point cited "
                   "in the corrections log. Derived from the population "
                   "located_register_points on every build.",
           "population": "located_register_points",
           "computed": __import__("datetime").date.today().isoformat(),
           "distances": {wp: {"metres": got, "nearest": other}
                         for wp, _st, got, other in sorted(rows)}}
    json.dump(out, open(os.path.join(REPO, "data", "nearest_point_distances.json"),
                        "w", encoding="utf8"), indent=1, ensure_ascii=False)

    pop = len(P.located_register_points())
    print(f"population located_register_points: {pop} points with a coordinate\n")
    print(f'{"POINT":14} {"STATED":>7} {"DERIVED":>8}  NEAREST')
    for wp, stated, got, other in sorted(rows):
        flag = "" if got == stated else "   ** DRIFTED **"
        print(f"{wp:14} {stated:7} {got:8}  {other}{flag}")
    print(f"\n{len(rows)} distance(s) checked")
    if fails:
        print("\nFAILED:")
        for f in fails:
            print("  " + f)
        return 1
    print("every stated distance reproduces from located_register_points.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
