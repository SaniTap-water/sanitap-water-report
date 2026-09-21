# -*- coding: utf-8 -*-
"""Pull the mWater extracts the report is built from, and record what was pulled.

This exists because the pull was not code. It was a step somebody did by hand,
so when it stopped happening nothing noticed: the extracts under
~/mwater-exports sat at 7 September for fourteen days and every edition in
between reported the same fortnight-old week.

Canonical filenames matter. A pull that lands on a NEW name - repairs.csv
beside reparation_apres_panne.csv - looks like a success and changes nothing,
which is what happened on 21 September. The names below are the only ones the
build reads, and the manifest records what each one holds.

    python3 tools/pull_extract.py --write   # pull, overwrite, write the manifest
    python3 tools/pull_extract.py --show
"""
import csv, datetime, io, json, os, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.expanduser("~/mwater-mcp/cli_call.mjs")
EXPORTS = os.path.expanduser("~/mwater-exports")
MANIFEST = os.path.join(REPO, "data", "extract_manifest.json")

# canonical name -> snapshot key in data/mwater_form_snapshot.json
FORMS = {
    "pm.csv": "preventive-maintenance",
    "reparation_apres_panne.csv": "repair-after-breakdown",
    "appel_signalement_pannes.csv": "call-centre",
    "premiere_rehabilitation.csv": "premiere-rehabilitation",
    "forage_moramanga.csv": "marolinta-borehole-progress",
}


def call(tool, args):
    r = subprocess.run(["node", CLI, tool, json.dumps(args)],
                       capture_output=True, text=True, cwd=os.path.dirname(CLI))
    s = r.stdout
    return json.loads(s[s.index("["):]) if "[" in s else []


# The MCP server's exporter pages with skip/limit and no sort order. mWater
# returns rows in an order that shifts between requests, so a long export
# duplicates some rows and DROPS others - and stops on a short page, so it
# reports success either way. A 21 September export of the preventive
# maintenance form wrote 755 rows of which only 547 were distinct, and the
# four most recent responses - 3, 4, 10 and 11 September - were not among
# them. That is how a pull can run, report success, and still leave the page
# a fortnight behind.
#
# So this does not page. It walks fixed date windows, which are stable no
# matter what order the server answers in, and de-duplicates on _id. A window
# that comes back full is split, because a full window may have been cut off.
WINDOW_FULL = 190          # the CLI truncates its output at 200 rows


def fetch_windowed(form_id, start, end, depth=0):
    """Every response between two dates, by stable date windows."""
    got = call("mwater_responses",
               {"form_id": form_id, "limit": 500,
                "filter_json": json.dumps(
                    {"submittedOn": {"$gte": start.isoformat(),
                                     "$lt": end.isoformat()}})})
    if len(got) >= WINDOW_FULL and (end - start).days > 1 and depth < 8:
        mid = start + (end - start) / 2
        mid = datetime.date(mid.year, mid.month, mid.day)
        return (fetch_windowed(form_id, start, mid, depth + 1)
                + fetch_windowed(form_id, mid, end, depth + 1))
    return got


def pull_form(form_id, first=datetime.date(2023, 1, 1)):
    end = datetime.date.today() + datetime.timedelta(days=2)
    rows, seen = [], set()
    cur = first
    while cur < end:
        nxt = min(datetime.date(cur.year + (cur.month // 12),
                                (cur.month % 12) + 1, 1), end)
        for r in fetch_windowed(form_id, cur, nxt):
            if r.get("_id") not in seen:
                seen.add(r["_id"])
                rows.append(r)
        cur = nxt
    # responses with no submittedOn never appear in a date window
    for r in call("mwater_responses",
                  {"form_id": form_id, "limit": 500,
                   "filter_json": json.dumps({"submittedOn": {"$exists": False}})}):
        if r.get("_id") not in seen:
            seen.add(r["_id"])
            rows.append(r)
    return rows


def write_csv(rows, path):
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with io.open(path, "w", encoding="utf8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v, ensure_ascii=False)
                            if isinstance(v, (dict, list)) else v)
                        for k, v in r.items()})
    return len(rows)


def newest(path):
    """(rows, unique rows, newest submittedOn) for an exported response CSV."""
    if not os.path.isfile(path):
        return 0, 0, None
    with io.open(path, encoding="utf8", errors="replace") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return 0, 0, None
    uniq = len({r.get("_id") for r in rows})
    col = next((c for c in rows[0] if c and c.lower() == "submittedon"), None)
    if not col:
        return len(rows), uniq, None
    ds = sorted(str(r.get(col) or "")[:10] for r in rows
                if str(r.get(col) or "")[:2] == "20")
    return len(rows), uniq, (ds[-1] if ds else None)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--show"
    if mode == "--show":
        print(json.dumps(json.load(open(MANIFEST)), indent=1, sort_keys=True)
              if os.path.isfile(MANIFEST) else "no data/extract_manifest.json yet")
        return 0
    if mode != "--write":
        sys.exit("usage: pull_extract.py --write | --show")
    snap = json.load(open(os.path.join(REPO, "data",
                                       "mwater_form_snapshot.json")))["forms"]
    files, failed = {}, []
    for name, key in FORMS.items():
        fid = snap.get(key, {}).get("id")
        if not fid:
            failed.append(f"{name}: no form id for {key} in the snapshot")
            continue
        p = os.path.join(EXPORTS, name)
        rows = pull_form(fid)
        write_csv(rows, p)
        n, uniq, new = newest(p)
        if n != uniq:
            failed.append(f"{name}: {n - uniq} duplicate rows after a windowed "
                          "pull - the windows are overlapping")
        files[name] = {"form": key, "form_id": fid, "rows": n, "unique": uniq,
                       "newest_submitted": new,
                       "written": datetime.datetime.fromtimestamp(
                           os.path.getmtime(p)).isoformat(timespec="seconds")
                       if os.path.isfile(p) else None}
    # The register is NOT pulled here. An unfiltered water_point export walks
    # the whole global mWater entity table, not ours, and runs for as long as
    # it is allowed to; the register also is not what goes stale - the
    # activity forms are. It is pulled separately, filtered to the managed
    # group, and its file date is reported here so the gap is still visible.
    p = os.path.join(EXPORTS, "wp_madavance.csv")
    files["wp_madavance.csv"] = {
        "entity_type": "water_point",
        "pulled_by": "separate filtered export, not by this tool",
        "rows": sum(1 for _ in io.open(p, encoding="utf8", errors="replace")) - 1
        if os.path.isfile(p) else 0,
        "written": datetime.datetime.fromtimestamp(
            os.path.getmtime(p)).isoformat(timespec="seconds")
        if os.path.isfile(p) else None}
    # A pull that lands on a name nothing reads is the failure that cost two
    # weeks: repairs.csv, written 21 September, was a correct export of the
    # repair form under a name no build has ever opened. Anything in the
    # exports directory that is not canonical is reported, not ignored.
    known = set(FORMS) | {"wp_madavance.csv"}
    strays = sorted(f for f in os.listdir(EXPORTS)
                    if f.endswith(".csv") and f not in known
                    and os.path.getsize(os.path.join(EXPORTS, f)) > 1)

    dates = [f["newest_submitted"] for f in files.values() if f.get("newest_submitted")]
    doc = {"pulled_at": datetime.datetime.now().isoformat(timespec="seconds"),
           "files": files,
           "newest_in_files": max(dates) if dates else None,
           "failed": failed,
           "strays": strays,
           "note": ("These are the ONLY filenames the build reads. A pull that "
                    "writes anywhere else changes nothing and still looks like a "
                    "success - that is how 21 September's repairs.csv was lost.")}
    json.dump(doc, open(MANIFEST, "w"), indent=1, sort_keys=True)
    for k, v in sorted(files.items()):
        print(f"  {v.get('rows', 0):6d} rows  newest {v.get('newest_submitted') or '-':10s}  {k}")
    if strays:
        print("\nfiles in ~/mwater-exports that no build reads:")
        for s in strays:
            print("  " + s)
    if failed:
        print("\nPROBLEMS:")
        for f in failed:
            print("  " + f)
        return 1
    print(f"\nnewest record across the extract: {doc['newest_in_files']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
