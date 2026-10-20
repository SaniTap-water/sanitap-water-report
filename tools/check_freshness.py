# -*- coding: utf-8 -*-
"""Establish how old the data on the page actually is, and record it.

The week caption used to read "Activity logged in mWater in the 7 days to
<date>", where <date> was max(PUMPS.last_visit) computed in the browser. Two
things were wrong with that. last_visit is a PREVENTIVE MAINTENANCE date, so
it is not "activity in mWater" - a repair or a call logged after the last
visit does not move it. And the extract itself lags: on 21 September the page
said 7 September while mWater held records to 21 September.

This tool records both numbers so the page can state its own age instead of
implying it is current:

    latest_in_extract   the newest date anywhere in the data the page carries
    latest_in_mwater    the newest submission in mWater, per form, when this run pulled it

    python3 tools/check_freshness.py --write   # from the pull manifest, rewrite the JSON
    python3 tools/check_freshness.py --show    # print what is on file
"""
import datetime, json, os, re, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "data_freshness.json")
SNAP = os.path.join(REPO, "data", "mwater_form_snapshot.json")

# the forms that constitute "activity" for the week counters
ACTIVITY = ["preventive-maintenance", "repair-after-breakdown", "call-centre",
            "premiere-rehabilitation"]


def extract_dates():
    """Newest date the PAGE carries, per source.

    Per source matters. A single "newest date on the page" hides the case
    where one subsystem is current and another is a fortnight behind, which is
    exactly the state on 21 September: visits and repairs rebuilt to the day
    mWater holds, while the call-centre-derived tables still came from the
    10 September build.
    """
    idx = open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    i = idx.index("\nconst PUMPS=")
    pumps = json.loads(idx[i + len("\nconst PUMPS="):idx.index("];", i) + 1])

    def mx(field, pred=lambda p: True):
        v = [p[field] for p in pumps if p.get(field) and pred(p)]
        return max(v) if v else None

    return {
        "preventive-maintenance": mx("last_pm"),
        "repair-after-breakdown": mx("last_repair"),
        # the call-centre tables' own date: the newest status_date, whatever
        # record set it. Only tools/build_call_tables.py writes status_date,
        # from the call extract with the visits and repairs, so a pull it never
        # rebuilt from still shows. Until 16 Oct 2026 this counted only
        # statuses whose source is a call, and so read "behind" whenever the
        # newest call was overtaken by a later visit (rule 4): the 14 Oct call
        # on 743345808 was followed by a maintenance visit on 15 Oct, the page
        # was correct, and every build failed.
        "call-centre": mx("status_date"),
    }


# the extract file behind each activity form
FILE_OF = {"preventive-maintenance": "pm.csv",
           "repair-after-breakdown": "reparation_apres_panne.csv",
           "call-centre": "appel_signalement_pannes.csv",
           "premiere-rehabilitation": "premiere_rehabilitation.csv"}


def mwater_latest():
    """The newest submission mWater held for each form when this run pulled it,
    from the pull manifest - not a second live read (20 Oct 2026: one mWater
    read per run). The pull reads every response, so its newest IS mWater's
    newest at that moment; the build follows it within the same run."""
    _newest, files = extract_file_dates()
    return {k: files.get(f) for k, f in FILE_OF.items() if k in ACTIVITY}


def extract_file_dates():
    """Newest record in the extract FILES, from the pull manifest.

    The gap between this and the page tells you the extract was pulled and the
    page never rebuilt from it. The gap between this and mWater tells you the
    pull did not happen. They are different failures and they need different
    fixes, so they are measured separately.
    """
    p = os.path.join(REPO, "data", "extract_manifest.json")
    if not os.path.isfile(p):
        return None, {}
    man = json.load(open(p))
    return man.get("newest_in_files"), {
        k: v.get("newest_submitted") for k, v in man.get("files", {}).items()
        if v.get("newest_submitted")}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--show"
    if mode == "--show":
        print(json.dumps(json.load(open(OUT)), indent=1) if os.path.isfile(OUT)
              else "no data/data_freshness.json yet")
        return 0
    if mode != "--write":
        sys.exit("usage: check_freshness.py --write | --show")
    ex = extract_dates()
    mw = mwater_latest()
    files_newest, files = extract_file_dates()
    today = datetime.date.today()
    doc = {
        "checked": today.isoformat(),
        "latest_in_extract": ex,
        "latest_in_mwater": mw,
        "latest_in_extract_files": files,
        "extract_newest": max([v for v in ex.values() if v] or [""]),
        "files_newest": files_newest,
        "mwater_newest": max([v for v in mw.values() if v] or [""]),
    }

    def gap(a, b):
        if not a or not b:
            return None
        return (datetime.date.fromisoformat(a)
                - datetime.date.fromisoformat(b)).days

    # lag_days is the one the build fails on: how far the data ON THE PAGE is
    # behind the day the build ran. Measuring it against mWater instead would
    # have read 0 on a day when mWater itself was quiet.
    doc["lag_days"] = gap(doc["mwater_newest"], doc["extract_newest"])
    doc["page_age_days"] = gap(today.isoformat(), doc["extract_newest"])
    doc["files_age_days"] = gap(today.isoformat(), files_newest)
    doc["page_behind_files_days"] = gap(files_newest, doc["extract_newest"])
    # Per source: how far the page is behind mWater for each form. Comparing
    # the page against TODAY instead would fail the build in a quiet week, when
    # the page is perfectly current and mWater simply has nothing newer.
    per = {}
    for k, page_d in ex.items():
        live = mw.get(k)
        g = gap(live, page_d)
        # a page newer than mWater's newest record of the form is not behind
        # (a call overtaken by a later visit dates the call tables after it)
        per[k] = {"page": page_d, "mwater": live, "behind_days": None if g is None else max(0, g)}
    doc["per_source"] = per
    behind = [v["behind_days"] for v in per.values() if v["behind_days"] is not None]
    doc["worst_source_lag_days"] = max(behind) if behind else None
    doc["worst_source"] = max(
        (v["behind_days"], k) for k, v in per.items()
        if v["behind_days"] is not None)[1] if behind else None

    # A source the build cannot rebuild is named here, with the reason and the
    # action that closes it. It is NOT silently tolerated: the page still shows
    # the gap, the checker still fails if the gap has no action row, and every
    # source that IS rebuildable still fails the build when it falls behind.
    # Leaving an unfixable source in the blocking set would make the gate
    # permanently red, which is the same as having no gate.
    # The call-centre gap is closed: tools/build_call_tables.py rebuilds
    # those tables from the extract and reproduces the published ones exactly,
    # so call-centre is a rebuildable source like the other two and belongs in
    # the blocking set.
    doc["known_gaps"] = {}
    doc["blocking_lag_days"] = max(
        [v["behind_days"] for k, v in per.items()
         if v["behind_days"] is not None and k not in doc["known_gaps"]] or [0])
    json.dump(doc, open(OUT, "w"), indent=1, sort_keys=True)
    print(json.dumps(doc, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
