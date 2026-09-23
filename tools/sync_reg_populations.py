# -*- coding: utf-8 -*-
"""Write the REG counts that ARE populations from the populations themselves.

REG.succ was a stored 730 that nothing wrote. check_consistency asserts it
equals the population rehabilitated_successfully, so on 23 September - the
first pull after a new successful first rehabilitation reached mWater - the
population said 731 and the weekly build failed on a figure it had no way to
move. Only the fields defined as a population are written here; every other
REG field is left exactly as it is.

    python3 tools/sync_reg_populations.py            # show what would change
    python3 tools/sync_reg_populations.py --write
"""
import json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
PAGE = os.path.join(REPO, "index.html")

# REG field -> the population whose size it is. Every other REG field is on
# the dated ungenerated backlog (data/ungenerated_fields.json).
FIELDS = {"succ": "rehabilitated_successfully",
          "succ_records": "successful_first_rehabilitation_records",
          "total_first_rehab": "first_rehabilitation_records",
          "final_records": "first_rehabilitation_records_final",
          "fail": "first_rehab_recorded_unsuccessful",
          "blank": "first_rehab_success_blank",
          "register_total": "register_records",
          "marolinta_new": "marolinta_new_constructions",
          "marolinta_rehab": "marolinta_rehabilitations"}


def main():
    import populations as P
    src = open(PAGE, encoding="utf8").read()
    m = re.search(r"\bconst REG\s*=\s*", src)
    if not m:
        sys.exit("sync_reg_populations: const REG not found")
    i = m.end()
    j = src.index("};", i) + 1
    reg = json.loads(src[i:j])
    changed = []
    for field, pid in FIELDS.items():
        n = len(P.get(pid)["members"]())
        if reg.get(field) != n:
            changed.append(f"REG.{field}: {reg.get(field)} -> {n}")
            reg[field] = n
    for c in changed or ["REG population fields already match"]:
        print(c)
    if "--write" in sys.argv and changed:
        open(PAGE, "w", encoding="utf8").write(
            src[:i] + json.dumps(reg, ensure_ascii=False, separators=(",", ":")) + src[j:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
