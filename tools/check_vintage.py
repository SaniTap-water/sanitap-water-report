# -*- coding: utf-8 -*-
"""No edition may mix vintages, and none may be fed by an extract older than itself.

Until 2026-09-22 seven JSON extracts - the ones six of the fourteen populations
are built from - were refreshed by no build step at all. tools/mwater/pull_form.mjs
was invoked by nothing, so those files held whatever date someone last ran it by
hand. Nothing failed, because the figures agreed with the populations and the
populations agreed with the files. The whole build passed green while its inputs
aged.

That is what this stops. It asserts:

  0. every extract the build EXPECTS is present in the manifest. A pull that
     fails leaves the old file on disk and drops the extract from the manifest
     entirely - so a check that only walks the manifest walks straight past it.
     That happened on the first real run: identification.json died on an
     ECONNRESET, vanished from the manifest, and every vintage check passed
     while a stale file sat there feeding a population;
  1. every extract the build reads is recorded in the manifest with a pull date;
  2. no extract was pulled BEFORE the build it is feeding - a file left over
     from a previous week fails the build and is named;
  3. the page's single "data to" date is the OLDEST PULL across all extracts,
     never the newest. That is the vintage floor: the earliest moment at which
     some source stopped being observed, and so the last date the page can
     honestly claim to know anything about. A form's own newest record is a
     different quantity - a quiet form has an old last record and is still
     current - so both are reported and neither is passed off as the other.

It writes data/extract_vintage.json for the page to render.

    python3 tools/check_vintage.py                     # against today
    python3 tools/check_vintage.py --as-of 2026-09-28  # against a build date
    python3 tools/check_vintage.py --max-age-days 1
"""
import argparse, datetime, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO, "data", "extract_manifest.json")
OUT = os.path.join(REPO, "data", "extract_vintage.json")
HIST = os.path.join(REPO, "data", "extract_rowcounts.json")

# Every extract is now pulled by the build, including the register: the
# filtered entity query is one bounded request, so the global-table walk that
# kept it outside never applied. Nothing carries a longer allowance; if one
# ever does, it belongs here where it is visible.
SEPARATE = {}


def expected():
    """Every extract the build must have, from the puller's own declarations."""
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import pull_extract as PE
    return set(PE.FORMS) | set(PE.JSON_FORMS) | set(PE.ENTITIES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default=datetime.date.today().isoformat())
    ap.add_argument("--max-age-days", type=int, default=1)
    ap.add_argument("--manifest", default=MANIFEST,
                    help="a manifest copy, for the negative test")
    ap.add_argument("--no-write", action="store_true",
                    help="do not write data/extract_vintage.json")
    # The day rule above cannot see a file left over from yesterday or from an
    # earlier run the same day. A build that pulls sets SANITAP_RUN_STARTED
    # (tools/weekly_build.py), and then every extract must have been written
    # by THIS run. A publish that does not pull leaves it unset.
    ap.add_argument("--since", default=os.environ.get("SANITAP_RUN_STARTED"),
                    help="local ISO time the run started; any extract written "
                         "before it fails")
    a = ap.parse_args()
    asof = datetime.date.fromisoformat(a.as_of)

    if not os.path.isfile(a.manifest):
        print(f"check_vintage: no {a.manifest}")
        return 2
    man = json.load(open(a.manifest, encoding="utf8"))
    files = man.get("files") or {}
    if not files:
        print("check_vintage: the manifest lists no extracts")
        return 2

    rows, fails = [], []

    # 0. a failed pull must fail the build, not disappear from it.
    want = expected()
    missing = sorted(want - set(files))
    for m_ in missing:
        fails.append(f"{m_}: EXPECTED but absent from the manifest - its pull "
                     f"failed, so the file on disk is whatever was there before")
    for err in (man.get("failed") or []):
        fails.append("pull reported a failure: "
                     + " ".join(str(err).split())[:140])

    # 0b. an extract may not shrink. Response forms only gain records; a drop
    # means the pull came back short. Two pulls of the call-centre form minutes
    # apart gave 2,747 and 2,826 because a failed window returned [] and looked
    # like an empty month. Records CAN be deleted in mWater, so a drop is
    # reported for a person to accept rather than treated as impossible - but
    # it never passes silently.
    hist = json.load(open(HIST, encoding="utf8")) if os.path.isfile(HIST) else {}
    counts = {k: v.get("rows") for k, v in files.items() if v.get("rows") is not None}
    for k, now in sorted(counts.items()):
        was = (hist.get("counts") or {}).get(k)
        if was is not None and now < was:
            fails.append(f"{k}: {was} rows last build, {now} now - {was - now} "
                         f"fewer. A response form does not shrink on its own: "
                         f"either a window came back empty, or records were "
                         f"deleted in mWater and this needs accepting by hand")
    for name, info in sorted(files.items()):
        written = (info.get("written") or "")[:10]
        limit = SEPARATE.get(name, a.max_age_days)
        if not written:
            fails.append(f"{name}: no pull date in the manifest")
            rows.append((name, None, info.get("newest_submitted"), None, limit))
            continue
        age = (asof - datetime.date.fromisoformat(written)).days
        rows.append((name, written, info.get("newest_submitted"), age, limit))
        if age > limit:
            fails.append(f"{name}: pulled {written}, {age} days before this "
                         f"build ({a.as_of}); limit is {limit}")
        elif a.since and info["written"][:19] < a.since[:19]:
            fails.append(f"{name}: written {info['written'][:19]}, before this "
                         f"run started at {a.since[:19]} - left over from an "
                         f"earlier pull, not pulled by this run")

    pulls = [(n, w) for n, w, _v, _a, _l in rows if w]
    oldest = min(w for _n, w in pulls) if pulls else None
    newest = max(w for _n, w in pulls) if pulls else None
    behind = [n for n, w in pulls if w == oldest]
    records = {n: v for n, _w, v, _a, _l in rows if v}

    print(f'{"EXTRACT":30} {"PULLED":11} {"AGE":>4}  {"DATA TO":11} LIMIT')
    for name, written, vintage, age, limit in rows:
        flag = "  ** STALE **" if age is not None and age > limit else ""
        print(f"{name:30} {(written or '—'):11} {('—' if age is None else age):>4}  "
              f"{(vintage or '—'):11} {limit}d{flag}")

    spread = None
    if oldest and newest:
        spread = (datetime.date.fromisoformat(newest)
                  - datetime.date.fromisoformat(oldest)).days
    print(f"\ndata to (OLDEST pull)      : {oldest}   [{', '.join(behind[:3])}]")
    print(f"newest pull                : {newest}")
    print(f"spread between pulls       : {spread} day(s)")
    if records:
        lr = min(records.values())
        print(f"oldest last-record date    : {lr}   "
              f"[{', '.join(n for n, v in records.items() if v == lr)[:60]}]"
              "  (a quiet form, not a stale pull)")

    json.dump({"note": "data_to is the OLDEST pull across every extract - the "
                       "vintage floor. Stating the newest would claim a currency "
                       "no single source has. last_record_by_source is a "
                       "different quantity: a quiet form has an old last record "
                       "and is still perfectly current.",
               "checked": a.as_of,
               "data_to": oldest, "newest_pull": newest,
               "last_record_by_source": records,
               "spread_days": spread,
               "oldest_sources": behind,
               "per_extract": {n: {"pulled": w, "data_to": v, "age_days": ag}
                               for n, w, v, ag, _l in rows}},
              open(os.devnull if a.no_write else OUT, "w", encoding="utf8"),
              indent=1, ensure_ascii=False, sort_keys=True)

    if not fails:
        json.dump({"note": "Row count per extract at the last build that passed. "
                           "check_vintage.py fails if any extract shrinks.",
                   "recorded": a.as_of, "counts": counts},
                  open(os.devnull if a.no_write else HIST, "w", encoding="utf8"),
                  indent=1, sort_keys=True)

    if fails:
        print("\nFAILED:")
        for f in fails:
            print("  " + f)
        print("\nAn edition fed by a stale extract looks current and is not. "
              "Re-run tools/pull_extract.py --write.")
        return 1
    print("\nevery extract was pulled for this build; the page states the oldest.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
