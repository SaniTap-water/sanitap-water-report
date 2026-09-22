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
import csv, datetime, io, json, os, subprocess, sys, time

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

# The seven JSON extracts the SEMANTIC LAYER reads. Six of the fourteen
# populations are built from these files, and until 2026-09-22 no build step
# refreshed any of them: tools/mwater/pull_form.mjs was invoked by nothing, so
# they held whatever date someone last ran it by hand. That is the frozen-value
# fault one level up - the figure gate cannot see it, because the figures agree
# with the populations and the populations agree with the files, so everything
# passes green while the inputs age.
#
# canonical name -> mWater form id. Pulled by pull_form.mjs, which walks 30-day
# windows and de-duplicates on _id, exactly as the CSV pull does.
JSON_FORMS = {
    "combined_rehab.json": "86cf66efdd3749dd8a121314bab3675a",
    "repair.json": "958b4763788348d699e7d8c5821f92ee",
    "wq_results.json": "7b33c5d7e5074808a94915939a5a0783",
    "hygiene.json": "283c5670de82489d833e986cb76a67d8",
    "identification.json": "198b016d72af41baa2608a8c9c35f8cb",
    "marolinta_borehole.json": "8764843c94484f5b984078c68f13b2ca",
    "first_rehab_current.json": "63747997e70e478fbb2ebf71581ceeb0",
}
PULL_FORM = os.path.join(REPO, "tools", "mwater", "pull_form.mjs")


def pull_json(name, form_id, tries=3):
    """Pull one form to JSON through the stable windowed enumerator.

    Retried: a single ECONNRESET part-way through ninety windows killed the
    identification.json pull on the first real run, and a failed pull leaves
    the previous file sitting on disk looking fine. The window walk is
    idempotent - it rebuilds the whole set from scratch and de-duplicates on
    _id - so retrying is safe.
    """
    out = os.path.join(EXPORTS, name)
    err = ""
    for attempt in range(tries):
        r = subprocess.run(["node", PULL_FORM, form_id, out],
                           capture_output=True, text=True, cwd=REPO)
        if r.returncode == 0:
            break
        err = (r.stderr or r.stdout or "")[-200:]
        print(f"  {name}: attempt {attempt + 1} failed, retrying")
        time.sleep(5)
    if r.returncode != 0:
        return None, f"{tries} attempts failed; last: {err}"
    try:
        rows = json.load(open(out, encoding="utf8"))
    except Exception as e:
        return None, f"unreadable after pull: {e}"
    return rows, None


def json_stats(rows):
    ids = [r.get("_id") for r in rows if isinstance(r, dict) and r.get("_id")]
    ds = sorted(str(r.get("submittedOn") or "")[:10] for r in rows
                if isinstance(r, dict) and str(r.get("submittedOn") or "")[:2] == "20")
    return len(rows), len(set(ids)), (ds[-1] if ds else None)


class PullFailed(Exception):
    """A window that did not come back. Never silently an empty window."""


def call(tool, args, tries=3):
    """One bounded query. Raises rather than returning [] on failure.

    This returned [] for ANY failure - a non-zero exit, a network reset, an
    unparseable reply - with no check on the return code. A transient error on
    one monthly window therefore dropped that window's rows and the pull still
    reported success. Two pulls of the call-centre form minutes apart returned
    2,747 and 2,826 rows because of it: 79 records short, silently, and the
    edition built on whichever pull happened to run.

    An empty window is a real answer and must look different from a window
    that failed. That is the whole difference between the two.
    """
    last = ""
    for attempt in range(tries):
        r = subprocess.run(["node", CLI, tool, json.dumps(args)],
                           capture_output=True, text=True,
                           cwd=os.path.dirname(CLI))
        if r.returncode == 0 and "[" in r.stdout:
            try:
                return json.loads(r.stdout[r.stdout.index("["):])
            except json.JSONDecodeError as e:
                last = f"unparseable reply: {e}"
        else:
            last = (f"exit {r.returncode}: "
                    + " ".join((r.stderr or r.stdout or "").split())[-160:])
        if attempt + 1 < tries:
            time.sleep(5)
    raise PullFailed(f"{tool} {json.dumps(args)[:90]}: {last}")


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
        try:
            rows = pull_form(fid)
        except PullFailed as e:
            failed.append(f"{name}: {e}")
            continue
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
    # The seven JSON extracts the populations read, through the same windowed
    # enumerator. Before this they were refreshed by hand or not at all.
    for name, fid in JSON_FORMS.items():
        rows, err = pull_json(name, fid)
        if err is not None:
            failed.append(f"{name}: {err}")
            continue
        n, uniq, new_ = json_stats(rows)
        if n != uniq:
            failed.append(f"{name}: {n - uniq} duplicate rows after a windowed "
                          "pull - the windows are overlapping")
        p = os.path.join(EXPORTS, name)
        files[name] = {"form_id": fid, "rows": n, "unique": uniq,
                       "newest_submitted": new_, "read_by": "populations.py",
                       "written": datetime.datetime.fromtimestamp(
                           os.path.getmtime(p)).isoformat(timespec="seconds")}

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
