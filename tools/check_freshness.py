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
    latest_in_mwater    the newest submission in mWater, per form, right now

    python3 tools/check_freshness.py --write   # query mWater, rewrite the JSON
    python3 tools/check_freshness.py --show    # print what is on file
"""
import datetime, json, os, re, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "data_freshness.json")
CLI = os.path.expanduser("~/mwater-mcp/cli_call.mjs")
SNAP = os.path.join(REPO, "data", "mwater_form_snapshot.json")

# the forms that constitute "activity" for the week counters
ACTIVITY = ["preventive-maintenance", "repair-after-breakdown", "call-centre",
            "premiere-rehabilitation"]


def extract_dates():
    """Newest dates in the data index.html actually carries."""
    idx = open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    i = idx.index("\nconst PUMPS=")
    pumps = json.loads(idx[i + len("\nconst PUMPS="):idx.index("];", i) + 1])
    out = {}
    for field in ("last_visit", "last_repair", "last_call"):
        ds = sorted(p[field] for p in pumps if p.get(field))
        if ds:
            out[field] = ds[-1]
    return out


def mwater_latest():
    snap = json.load(open(SNAP))["forms"]
    out = {}
    since = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
    for key in ACTIVITY:
        fid = snap.get(key, {}).get("id")
        if not fid:
            continue
        args = json.dumps({"form_id": fid, "limit": 2000,
                           "filter_json": json.dumps(
                               {"submittedOn": {"$gte": since}})})
        r = subprocess.run(["node", CLI, "mwater_responses", args],
                           capture_output=True, text=True,
                           cwd=os.path.dirname(CLI))
        s = r.stdout
        if "[" not in s:
            out[key] = None
            continue
        rows = json.loads(s[s.index("["):])
        ds = sorted(x["submittedOn"][:10] for x in rows if x.get("submittedOn"))
        out[key] = ds[-1] if ds else None
    return out


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
    doc = {
        "checked": datetime.date.today().isoformat(),
        "latest_in_extract": ex,
        "latest_in_mwater": mw,
        "extract_newest": max([v for v in ex.values() if v] or [""]),
        "mwater_newest": max([v for v in mw.values() if v] or [""]),
    }
    doc["lag_days"] = (
        (datetime.date.fromisoformat(doc["mwater_newest"])
         - datetime.date.fromisoformat(doc["extract_newest"])).days
        if doc["extract_newest"] and doc["mwater_newest"] else None)
    json.dump(doc, open(OUT, "w"), indent=1, sort_keys=True)
    print(json.dumps(doc, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
