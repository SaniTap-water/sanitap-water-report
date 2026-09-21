#!/usr/bin/env python3
"""The retirement rule for the SaniTap water register.

WHY THIS EXISTS, AND WHY IT IS A NAME PREFIX
--------------------------------------------
A record that turns out not to be a water point - a camera test, a duplicate, a
site that was never built - has to be excluded from every published figure and
from the map. The obvious way to do that is a status field on the record. We
cannot: mWater's permission model will not let this account write one.

All 236 properties on the `water_point` entity type carry a `roles` list, and
every status-like property is reserved to another organisation's group:

    wa_non_inventory    group:mWater Staff, group:f9ffe531...   (WaterAid)
    mwa_functionality   group:MWA All Partners - Latin America
    twp_project_status  group:0f29ead6...
    cw_type             group:8f797e9b...

Writing any of them returns HTTP 403 "Cannot update property <name>". This was
confirmed against the live API on 17 September 2026. The only properties open to
us (role "all") are `name`, `desc` and `type` - and `type` is load-bearing for
other reasons, so it cannot double as a status flag.

That leaves the record NAME as the only marker we can actually write. So:

    A record whose name begins with "ZZ TEST" is retired. It is excluded from
    every figure and from the map, and counted nowhere.

The "ZZ " prefix also sorts such records to the bottom of any alphabetical list
in the mWater UI, which is the behaviour we want.

WHERE THIS MUST BE APPLIED
--------------------------
The report build is not in this repository - index.html and portfolio.html
arrive pre-built. This module is therefore the definition of the rule, not its
only enforcement point. It must be applied in the build, at the point where the
mWater register is first read, BEFORE anything is counted, so that:

  * the water point counts (per site, carbon portfolio, in scope)
  * the population model input (water_points.csv)
  * the map markers in portfolio.html
  * the sampling and maintenance denominators

all see the same filtered set. Filtering later, or in only some of those places,
reintroduces exactly the inconsistency tools/check_consistency.py exists to
catch.

tools/check_consistency.py asserts after the fact that no retired record reached
the published pages. That is a backstop, not the rule.

CURRENTLY RETIRED (17 September 2026)
-------------------------------------
    924119262  "ZZ TEST - NOT A WATER POINT AEPG"  Moramanga      photo: a potted plant
    927104201  "ZZ TEST - NOT A WATER POINT AEP"   Antananarivo   photo: a village street

Both are type `kiosk` inside the MadAvance hand-pump register, both created by
account ce2563df... in February 2026. They are retained in mWater for audit -
reclassified, never deleted.
"""

RETIRED_NAME_PREFIX = "ZZ TEST"

# Known retired codes, kept for the assertion in check_consistency.py. The rule
# is the name prefix; this list is a belt-and-braces cross-check, not the rule.
KNOWN_RETIRED_CODES = ("924119262", "927104201")

# The full names as they stand in the register. A retired RECORD reaching a
# published page carries its whole name; the bare prefix does not, and the
# report legitimately discusses the convention in prose - the decommissioning
# action explains that two records are retired this way and why the prefix is
# the only marker mWater permissions leave writable. So the published-page
# assertion is on these, matching the treatment already given to the codes:
# hard on data, permissive on prose.
KNOWN_RETIRED_NAMES = ("ZZ TEST - NOT A WATER POINT AEPG",
                       "ZZ TEST - NOT A WATER POINT AEP")


def is_retired(record):
    """True if this register record must be excluded from every published figure.

    `record` is a mWater water_point document (or any mapping with a "name").
    Matching is case-insensitive and tolerates leading whitespace, because the
    prefix is typed by hand in the mWater UI.
    """
    name = record.get("name") if hasattr(record, "get") else getattr(record, "name", None)
    if not name:
        return False
    return str(name).strip().upper().startswith(RETIRED_NAME_PREFIX)


def exclude_retired(records):
    """Drop retired records. Returns (kept, dropped)."""
    kept, dropped = [], []
    for r in records:
        (dropped if is_retired(r) else kept).append(r)
    return kept, dropped


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) != 2:
        sys.exit("usage: exclude_retired.py <water_point json array>\n"
                 "       prints the retired records it would drop")
    recs = json.load(open(sys.argv[1], encoding="utf8"))
    kept, dropped = exclude_retired(recs)
    print(f"{len(recs)} records: {len(kept)} kept, {len(dropped)} retired")
    for d in dropped:
        print(f"  RETIRED  {d.get('code')}  {d.get('name')!r}")
