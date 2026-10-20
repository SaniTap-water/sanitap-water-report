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
import csv, datetime, io, json, os, re, subprocess, sys, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS = os.path.expanduser("~/mwater-exports")
# A pull is written into STAGE and moved into EXPORTS only when every extract
# came back (20 Oct 2026). The build of 20 Oct pulled 23 of 24 extracts
# straight into EXPORTS, failed on the 24th and rolled the repository back -
# but not the extracts, so the next gate run read today's data beside a page
# built on 17 Oct. The set the swap replaces is kept in PREVIOUS, and
# tools/weekly_build.py puts it back when it rolls back a run that swapped
# (restore_previous), so the extracts always match the page at HEAD.
STAGE = os.path.expanduser("~/mwater-exports.staging")
REFUSED = os.path.expanduser("~/mwater-exports.refused")   # the last refused run's set
PREVIOUS = os.path.expanduser("~/mwater-exports.previous")
SWAP_MARK = os.path.join(PREVIOUS, "_swapped_by_run")
# derived files a build step writes into EXPORTS from this pull; kept and
# restored with the set so a rollback cannot leave one from another pull
DERIVED = ("piped_wq_pairs.json",)
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
    # the annual monitoring survey: SDWS 26 usage, SDWS 25 household size
    "cbn_gender.json": "2eeb86824b4545eca33db9e7cf7dcbd4",
    # the annual hygiene and sanitation survey (JMP core hygiene questions:
    # handwashing place, water and soap observed) - the SDWS 24 impact
    # assessment, read by tools/rebuild_hygiene.py (1 Oct 2026)
    "hygiene_san.json": "209cc5fc24e24463aff702c11b6bd18f",
    # the beneficiary roof count per water point - PUMPS.benef is computed
    # from it every build (tools/rebuild_pump_inputs.py)
    "roof_count.json": "8aa2dd78eb1f460f8f43db7935955846",
    # the piped-scheme SDWS 3 result form (tap, kiosk or system samples); read
    # by tools/rebuild_piped_wq.py for the piped water-quality figures
    "wq_results_piped.json": "0ac68d8274d24f54af0c28b29119b77d",
    # its sampling form: each result is paired with its sample on site and
    # sampling date, and takes the sample's GPS, type and photo from it
    "wq_sampling_piped.json": "ef8cf7353a974cf984d34860dcf2952d",
    # Endur'O onboarding: the system and distribution-point registrations,
    # read by tools/rebuild_piped_wq.py for the onboarding progress counts
    "piped_system_reg.json": "44044e27c0f24cc4a432a38b09886684",
    "piped_point_reg.json": "8a3af50ceec84cda85d454d96079991d",
    # the Moramanga piped-water carbon baseline survey (331 households):
    # the baseline cooking-fuel split for the piped systems in process
    "baseline_moramanga.json": "3ef4385a619244c7ad129169ac1ec71f",
    # the household (point-of-use) water-quality survey, SDWS 18: the 2025
    # round is its final records on the Fort-Dauphin and Maroantsetra
    # deployments (tools/rebuild_sdws18.py, population sdws18_pou_samples)
    "pou_survey.json": "db0bcbf2e7ea44b280aed653a715553e",
}
# Pulled and counted, read by nothing yet. Moving a name out of this set is
# the step that puts it into a figure.
COUNTED_ONLY = set()
# who reads each extract, where it is not populations.py
READ_BY = {"wq_results_piped.json": "rebuild_piped_wq.py",
           "wq_sampling_piped.json": "rebuild_piped_wq.py",
           "enduro_points.csv": "moramanga_dedupe.py, rebuild_enduro_registry.py",
           "piped_systems.csv": "rebuild_piped_wq.py, rebuild_enduro_registry.py",
           "piped_system_reg.json": "rebuild_piped_wq.py",
           "piped_point_reg.json": "rebuild_piped_wq.py",
           "baseline_moramanga.json": "rebuild_piped_wq.py",
           "hygiene_san.json": "rebuild_hygiene.py"}
PULL_FORM = os.path.join(REPO, "tools", "mwater", "pull_form.mjs")
PULL_ENTITIES = os.path.join(REPO, "tools", "mwater", "pull_entities.mjs")
# Entity extracts: name -> (entity type, managed-by group). The register is
# MadAvance's; the piped systems are Endur'O's, which the piped water-quality
# samples name as their site (tools/rebuild_piped_wq.py places each one).
ENTITIES = {
    "wp_madavance.csv": ("water_point", "group:aaaf0a14e4ce44eaa7a2bcfd1c74aa56"),
    "piped_systems.csv": ("water_system", "group:c305b9b85f41417387b553d9a33c795b"),
    # Endur'O's water points, with name, description and GPS: the Moramanga
    # crosswalk reads the old mWater ID quoted in a new point's description
    "enduro_points.csv": ("water_point", "group:c305b9b85f41417387b553d9a33c795b"),
}


def pull_json(name, form_id, tries=2, out=None):
    """Pull one form to JSON through the stable windowed enumerator.

    Retried: a single ECONNRESET part-way through ninety windows killed the
    identification.json pull on the first real run, and a failed pull leaves
    the previous file sitting on disk looking fine. The window walk is
    idempotent - it rebuilds the whole set from scratch and de-duplicates on
    _id - so retrying is safe. Each request inside it is retried with backoff
    as well (tools/mwater/enumerate.mjs), so two runs of the walk are enough.
    """
    out = out or os.path.join(STAGE, name)
    err = ""
    for attempt in range(tries):
        r = subprocess.run(["node", PULL_FORM, form_id, out],
                           capture_output=True, text=True, cwd=REPO)
        if r.returncode == 0:
            break
        # the error's own line, cause included, not a truncated tail
        lines = (r.stderr or r.stdout or "").splitlines()
        err = next((l.strip() for l in reversed(lines) if "tries failed" in l or "Error" in l),
                   " ".join(" ".join(lines).split())[-300:])[:400]
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


def pull_csv_form(name, form_id):
    """One response form to a CSV extract in STAGE, through the same windowed
    enumerator as the JSON extracts. Until 20 Oct 2026 these five went through
    the MCP CLI (~/mwater-mcp/cli_call.mjs), one process and one login per date
    window, and the CLI prints at most 200 rows: a one-day window cannot be
    split by date, so 4 Feb 2026 came back as 200 of its 522 call-centre
    responses with no error. Returns (rows, error)."""
    tmp = os.path.join(STAGE, name + ".json")
    rows, err = pull_json(name, form_id, out=tmp)
    if err is None:
        os.remove(tmp)
    return rows, err


def swap_in(names):
    """Move a complete pull from STAGE into EXPORTS, keeping the set it
    replaces in PREVIOUS, marked with this run (SANITAP_RUN_STARTED)."""
    import shutil
    if os.path.isdir(PREVIOUS):
        shutil.rmtree(PREVIOUS)
    os.makedirs(PREVIOUS)
    for n in sorted(set(names) | set(DERIVED)):
        cur = os.path.join(EXPORTS, n)
        if os.path.isfile(cur):
            shutil.copy2(cur, os.path.join(PREVIOUS, n))
    with open(SWAP_MARK, "w") as fh:
        fh.write(os.environ.get("SANITAP_RUN_STARTED") or datetime.datetime.now().isoformat(timespec="seconds"))
    for n in names:
        os.replace(os.path.join(STAGE, n), os.path.join(EXPORTS, n))


def clear_swap():
    """After a publish the swapped-in set is the page's own: forget the swap."""
    if os.path.isfile(SWAP_MARK):
        os.remove(SWAP_MARK)


def restore_previous(run=None):
    """Put back the extract set a swap replaced. With `run`, only if that run
    made the swap. Returns the files restored, or None if nothing to do."""
    import shutil
    if not os.path.isfile(SWAP_MARK):
        return None
    if run is not None and open(SWAP_MARK).read().strip() != run:
        return None
    back = sorted(n for n in os.listdir(PREVIOUS) if n != os.path.basename(SWAP_MARK))
    # the refused set is kept for diagnosis, replaced by the next refusal
    # (20 Oct 2026: a refused build's fresh pull was overwritten and lost)
    shutil.rmtree(REFUSED, ignore_errors=True)
    os.makedirs(REFUSED)
    for n in back:
        if os.path.exists(os.path.join(EXPORTS, n)):
            shutil.copy2(os.path.join(EXPORTS, n), os.path.join(REFUSED, n))
        shutil.copy2(os.path.join(PREVIOUS, n), os.path.join(EXPORTS, n))
    os.remove(SWAP_MARK)
    return back


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


def expected_names():
    return sorted(set(FORMS) | set(JSON_FORMS) | set(ENTITIES))


def _sha(p):
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def reuse(src):
    """Install a complete extract set already pulled - a run's kept set in
    ~/mwater-exports.refused, or any directory holding all of them - instead of
    pulling (20 Oct 2026: a fix to a check must never need a new mWater read).
    No network. The files keep their own write times, so the manifest and
    check_vintage.py see when they were really pulled; the manifest records
    where they came from. Same staged, all-or-nothing swap as a pull."""
    import shutil
    src = os.path.realpath(os.path.expanduser(src or ""))
    if not os.path.isdir(src):
        print(f"--reuse: {src or '(none given)'} is not a directory")
        return 2
    if src in (os.path.realpath(EXPORTS), os.path.realpath(STAGE), os.path.realpath(PREVIOUS)):
        print(f"--reuse: {src} is one of the build's own directories; copy it elsewhere first")
        return 2
    missing = [n for n in expected_names() if not os.path.isfile(os.path.join(src, n))]
    if missing:
        print(f"--reuse: {src} is not a complete set; missing {', '.join(missing)}")
        return 1
    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE)
    os.makedirs(STAGE)
    files = {}
    names = expected_names() + [d for d in DERIVED if os.path.isfile(os.path.join(src, d))]
    for n in names:
        p = os.path.join(STAGE, n)
        shutil.copy2(os.path.join(src, n), p)
        if n in DERIVED:
            continue
        if n.endswith(".json"):
            rows = json.load(open(p, encoding="utf8"))
            cnt, uniq, new = json_stats(rows)
        elif n in ENTITIES:
            cnt = sum(1 for _ in io.open(p, encoding="utf8", errors="replace")) - 1
            with io.open(p, encoding="utf8", errors="replace") as fh:
                uniq = len({r["code"] for r in csv.DictReader(fh) if r.get("code")})
            new = None
        else:
            cnt, uniq, new = newest(p)
        if cnt != uniq:
            print(f"--reuse: {n}: {cnt - uniq} duplicate rows; refusing the set")
            return 1
        files[n] = {"rows": cnt, "unique": uniq, "newest_submitted": new,
                    "sha256": _sha(p),
                    "written": datetime.datetime.fromtimestamp(
                        os.path.getmtime(p)).isoformat(timespec="seconds")}
        if n in FORMS:
            files[n]["form"] = FORMS[n]
        elif n in JSON_FORMS:
            files[n]["form_id"] = JSON_FORMS[n]
        else:
            files[n].update({"entity_type": ENTITIES[n][0], "group": ENTITIES[n][1]})
    swap_in(names)
    written = sorted(f["written"] for f in files.values())
    dates = [f["newest_submitted"] for f in files.values() if f.get("newest_submitted")]
    doc = {"pulled_at": written[0], "pull_finished": written[-1],
           "reused_from": src,
           "reused_at": datetime.datetime.now().isoformat(timespec="seconds"),
           "files": files, "newest_in_files": max(dates) if dates else None,
           "failed": [], "strays": [],
           "note": ("Reused, not pulled: the set a run pulled at pulled_at, installed "
                    "unchanged by tools/pull_extract.py --reuse. No mWater read.")}
    json.dump(doc, open(MANIFEST, "w"), indent=1, sort_keys=True)
    print(f"reused {len(files)} extracts from {src}, pulled {written[0]} .. {written[-1]}")
    return 0


def verify_reuse(src):
    """publish.sh --reuse-extracts: the gates are about to run on the set in
    `src` - the manifest says so and every file on disk is byte-identical."""
    src = os.path.realpath(os.path.expanduser(src or ""))
    man = json.load(open(MANIFEST, encoding="utf8")) if os.path.isfile(MANIFEST) else {}
    bad = []
    if man.get("reused_from") != src:
        bad.append(f"the manifest's extracts came from {man.get('reused_from') or 'a pull'}, not {src}")
    for n, f in sorted((man.get("files") or {}).items()):
        here, there = os.path.join(EXPORTS, n), os.path.join(src, n)
        if not (os.path.isfile(here) and os.path.isfile(there)):
            bad.append(f"{n}: missing")
        elif not (_sha(here) == _sha(there) == f.get("sha256")):
            bad.append(f"{n}: differs from {src}")
    for b in bad:
        print("  " + b)
    print(f"  reuse verified: {len(man.get('files') or {})} extracts identical to {src}"
          if not bad else f"  reuse NOT verified ({len(bad)} problem(s))")
    return 1 if bad else 0


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--show"
    if mode == "--show":
        print(json.dumps(json.load(open(MANIFEST)), indent=1, sort_keys=True)
              if os.path.isfile(MANIFEST) else "no data/extract_manifest.json yet")
        return 0
    if mode == "--reuse":
        return reuse(sys.argv[2] if len(sys.argv) > 2 else "")
    if mode == "--verify-reuse":
        return verify_reuse(sys.argv[2] if len(sys.argv) > 2 else "")
    if mode != "--write":
        sys.exit("usage: pull_extract.py --write | --show | --reuse DIR | --verify-reuse DIR")
    import shutil
    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE)
    os.makedirs(STAGE)
    os.makedirs(EXPORTS, exist_ok=True)
    snap = json.load(open(os.path.join(REPO, "data",
                                       "mwater_form_snapshot.json")))["forms"]
    files, failed = {}, []
    for name, key in FORMS.items():
        fid = snap.get(key, {}).get("id")
        if not fid:
            failed.append(f"{name}: no form id for {key} in the snapshot")
            continue
        p = os.path.join(STAGE, name)
        rows, err = pull_csv_form(name, fid)
        if err is not None:
            failed.append(f"{name}: {err}")
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
        p = os.path.join(STAGE, name)
        files[name] = {"form_id": fid, "rows": n, "unique": uniq,
                       "newest_submitted": new_,
                       "read_by": ("nothing yet: pulled and counted only"
                                   if name in COUNTED_ONLY
                                   else READ_BY.get(name, "populations.py")),
                       "written": datetime.datetime.fromtimestamp(
                           os.path.getmtime(p)).isoformat(timespec="seconds")}

    # The register, filtered to the managed group. It used to sit outside this
    # tool because an UNFILTERED water_point export walks the whole global
    # mWater entity table. Filtered to the group it is one bounded query
    # (the row count is live - see the manifest - and returns in about two
    # seconds), so the reason it was excluded
    # never applied to the filtered form of the query. While it was excluded it
    # set the page's vintage floor: every population sits on the register, so
    # an eleven-day-old register meant a pump rehabilitated last week was not
    # in the fleet and the page still said 736 with confidence.
    for name, (etype, group) in ENTITIES.items():
        p = os.path.join(STAGE, name)
        # Retried like the form pulls: the real build of 25 September died on
        # one read ETIMEDOUT in the register pull, the only pull that had no
        # retry. The walk writes nothing unless it completes and agrees with
        # the single query, so a retry cannot leave a half-written file.
        for attempt in range(3):
            r = subprocess.run(["node", PULL_ENTITIES, p, etype, group],
                               capture_output=True, text=True, cwd=REPO)
            if r.returncode == 0:
                break
            print(f"  {name}: attempt {attempt + 1} failed, retrying")
            time.sleep(5)
        if r.returncode != 0:
            # the error's own message line, not the tail of a stack trace
            out = (r.stderr or r.stdout or "").splitlines()
            msg = next((l.strip() for l in out if re.match(r"\s*(\w*Error|MISMATCH)", l)),
                       " ".join(" ".join(out).split())[-200:])
            failed.append(f"{name}: 3 attempts failed; last: {msg[:200]}")
            continue
        n = sum(1 for _ in io.open(p, encoding="utf8", errors="replace")) - 1
        codes = set()
        with io.open(p, encoding="utf8", errors="replace") as fh:
            for row in csv.DictReader(fh):
                if row.get("code"):
                    codes.add(row["code"])
        files[name] = {
            "entity_type": etype, "group": group,
            "read_by": READ_BY.get(name, "populations.py"),
            "pulled_by": "tools/mwater/pull_entities.mjs, filtered to the "
                         "managed group and walked in 90-day windows",
            "rows": n, "unique": len(codes),
            "written": datetime.datetime.fromtimestamp(
                os.path.getmtime(p)).isoformat(timespec="seconds")}

    # A pull that lands on a name nothing reads is the failure that cost two
    # weeks: repairs.csv, written 21 September, was a correct export of the
    # repair form under a name no build has ever opened. Anything in the
    # exports directory that is not canonical is reported, not ignored.
    # ALL OR NOTHING: a pull with any failure leaves EXPORTS as it was, and
    # writes no manifest, so nothing downstream can read a mixed set
    if failed:
        print("\nPROBLEMS (nothing moved into ~/mwater-exports; it holds the last complete pull):")
        for f in failed:
            print("  " + f)
        return 1
    swap_in(list(files))
    known = set(FORMS) | set(ENTITIES)
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
