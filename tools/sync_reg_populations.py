# -*- coding: utf-8 -*-
"""Write the stored counts that ARE populations from the populations themselves.

REG.succ was a stored 730 that nothing wrote. check_consistency asserts it
equals the population rehabilitated_successfully, so on 23 September - the
first pull after a new successful first rehabilitation reached mWater - the
population said 731 and the weekly build failed on a figure it had no way to
move. S.n was the same: asserted equal to the managed fleet, written by
nothing, and harmless only while the fleet never changed. The first pump to
join through tools/classify_register.py (742894057, 23 September) moved the
fleet to 737 and left S.n at 736, so the headline and its caption disagreed.

Only fields defined as a population are written here; every other field is
left exactly as it is, in the object's own JSON style.

    python3 tools/sync_reg_populations.py            # show what would change
    python3 tools/sync_reg_populations.py --write
"""
import json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
PAGE = os.path.join(REPO, "index.html")

# (object, field) -> the population whose size it is. Every other field of
# these objects is written by its own generator or is on the dated
# ungenerated backlog (data/ungenerated_fields.json).
FIELDS = {("S", "n"): "managed_fleet",
          ("S", "wq_tested"): "water_quality_tested",
          ("REG", "succ"): "rehabilitated_successfully",
          ("REG", "succ_records"): "successful_first_rehabilitation_records",
          ("REG", "total_first_rehab"): "first_rehabilitation_records",
          ("REG", "final_records"): "first_rehabilitation_records_final",
          ("REG", "fail"): "first_rehab_recorded_unsuccessful",
          ("REG", "blank"): "first_rehab_success_blank",
          ("REG", "marolinta_new"): "marolinta_new_constructions",
          ("REG", "marolinta_rehab"): "marolinta_rehabilitations"}


def main():
    import populations as P
    src = open(PAGE, encoding="utf8").read()
    changed = []
    for obj in sorted({o for o, _f in FIELDS}):
        m = re.search(r"\bconst %s\s*=\s*" % obj, src)
        if not m:
            sys.exit(f"sync_reg_populations: const {obj} not found")
        i = m.end()
        j = src.index("};", i) + 1
        old = src[i:j]
        val = json.loads(old)
        moved = False
        for (o, field), pid in FIELDS.items():
            if o != obj:
                continue
            n = len(P.get(pid)["members"]())
            if val.get(field) != n:
                changed.append(f"{obj}.{field}: {val.get(field)} -> {n}")
                val[field] = n
                moved = True
        if moved:
            compact = not re.match(r'\{"[^"]+": ', old)
            new = json.dumps(val, ensure_ascii=False,
                             separators=(",", ":") if compact else None)
            src = src[:i] + new + src[j:]
    for c in changed or ["population fields already match"]:
        print(c)
    if "--write" in sys.argv and changed:
        open(PAGE, "w", encoding="utf8").write(src)
    return 0


if __name__ == "__main__":
    sys.exit(main())
