# -*- coding: utf-8 -*-
"""A field nothing can move is a field nobody is checking.

Five published figures - WPOP_C250, 727, 723, 628 and S.wq_tested - were values
computed once, frozen into the page and never recomputed. Every one was found
by a person noticing. This is the check that would have found them.

It asserts three things:

  1. every field of every embedded data object resolves to a generator, a
     population, or the dated ungenerated-field backlog;
  2. the backlog only ever shrinks - a new ungenerated field fails the build;
  3. every field declared to come from a population still equals that
     population's size.

    python3 tools/check_generators.py
"""
import json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
BACKLOG = os.path.join(REPO, "data", "ungenerated_fields.json")
POPS = os.path.join(REPO, "data", "populations.json")


def main():
    import embedded_fields as EF
    from generator_registry import POPULATION, resolve

    back = json.load(open(BACKLOG, encoding="utf8"))
    known = {r["field"] for r in back["fields"]}
    fails, present = [], set()

    for name, _line, val in EF.objects():
        if name in EF.FURNITURE:
            continue
        for f, _k, brief in EF.fields(name, val):
            key = f"{name}.{f}"
            present.add(key)
            if resolve(name, f) is None and key not in known:
                fails.append(f"{key} = {brief}: no generator, and not in the backlog")

    # 2. shrink-only
    gone = known - present
    still = known & present
    if len(still) > back["count"]:
        fails.append(f"the ungenerated backlog grew: {back['count']} -> {len(still)}")

    # 3. population-backed fields must still equal their population
    pops = json.load(open(POPS, encoding="utf8"))["populations"]
    src = open(EF.PAGE, encoding="utf8").read()
    objs = {n: v for n, _l, v in EF.objects(src)}
    for key, pid in sorted(POPULATION.items()):
        obj, field = key.split(".", 1)
        stored = (objs.get(obj) or {}).get(field)
        size = (pops.get(pid) or {}).get("size")
        if stored != size:
            fails.append(f"{key} is {stored} but population {pid} is {size}")
        else:
            print(f"  ok  {key} = {stored} = population {pid}")

    print(f"\nembedded fields: {len(present)}")
    print(f"  with a generator or population : {len(present) - len(still)}")
    print(f"  on the ungenerated backlog     : {len(still)}"
          + (f"  ({len(gone)} cleared since {back['recorded']})" if gone else ""))
    if fails:
        print("\nFAILED:")
        for f in fails:
            print("  " + f)
        return 1
    print("\nevery embedded field is accounted for.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
