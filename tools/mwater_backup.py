#!/usr/bin/env python3
"""
SaniTap / MadAvance mWater backup, run weekly by tools/weekly_build.py.

Takes an independent copy of everything mWater holds for the safe-water
programme: every form design, every response (including drafts, so nothing is
silently lost), the water point register, and every photograph referenced by a
response.

Data is re-fetched in full each run (it is small) into data/<YYYY-MM-DD>/.
Photographs are fetched ONCE and then only when new ones appear - the image
store is content-addressed by mWater's own image id and sharded on its first
two characters, so an id that is already on disk is never downloaded again.

Moved into the repository from ~/bin/mwater_backup.py on 10 Oct 2026 (Adriaan
Mol), unchanged in what it fetches and where it writes, so the Monday build can
run it. Added then:

  * READ-ONLY. Every request goes through _send(), which refuses any method
    other than GET before a byte is sent - except the login, POST /v3/clients.
    Same rule as tools/mwater/api.mjs and the MCP server's mwaterFetch.
  * One login per run, with the credentials in ~/mwater-mcp/.env, unless
    MWATER_CLIENT is already set. The token is never written anywhere.
  * Once a week: a run is skipped (exit 0) when a verified backup less than
    --min-days old exists. At least 60 minutes between runs that read mWater.
  * Exit 1 when the server's response count disagrees with what was saved, or
    the run fails; the last line says why, for the build log.

    python3 tools/mwater_backup.py              # the weekly backup
    python3 tools/mwater_backup.py --force      # ignore the once-a-week rule
"""

import argparse, json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, date

API = "https://api.mwater.co/v3"
ENV = os.path.expanduser("~/mwater-mcp/.env")
DEST = ("/mnt/c/Users/bushp/OneDrive - SaniTap/Central Data Hub - Water Documents/"
        "Evidence/mWater backup")
STAMP = os.path.expanduser("~/.local/state/sanitap/mwater_backup_last_started")
LOGDIR = os.path.expanduser("~/logs")

FORMS = {
    "86cf66efdd3749dd8a121314bab3675a": "old-combined-works",
    "de26d89a5c8a4452b42158c622be20d0": "preventive-maintenance",
    "958b4763788348d699e7d8c5821f92ee": "repair-after-breakdown",
    "c08b3fe26d0f42c084074701f29eb75e": "call-centre",
    "7b33c5d7e5074808a94915939a5a0783": "water-quality-result-sdws3",
    "43c96af4bc4240c0b5c4402383b9c539": "water-quality-sampling-sdws3",
    "283c5670de82489d833e986cb76a67d8": "hygiene-promotion",
    "8764843c94484f5b984078c68f13b2ca": "marolinta-borehole-progress",
    "8aa2dd78eb1f460f8f43db7935955846": "beneficiary-roof-count",
    "8be8e0384709433795d2d0197e98275f": "stroke-meter",
    "db0bcbf2e7ea44b280aed653a715553e": "point-of-use-survey",
}

MANAGED_BY = "group:aaaf0a14e4ce44eaa7a2bcfd1c74aa56"


class RefusedWrite(Exception):
    pass


def _send(req, timeout=120):
    """The only way this script talks to mWater. GET anything; POST only to
    /v3/clients (the login). Every other method or target raises before
    anything is sent."""
    method = req.get_method().upper()
    path = urllib.parse.urlsplit(req.full_url).path.rstrip("/")
    if method != "GET" and not (method == "POST" and path == "/v3/clients"):
        raise RefusedWrite(f"tools/mwater_backup.py is read-only: refusing {method} {path}")
    return urllib.request.urlopen(req, timeout=timeout)


def login():
    creds = {}
    for line in open(ENV, encoding="utf8"):
        k, _, v = line.strip().partition("=")
        if k in ("MWATER_USERNAME", "MWATER_PASSWORD"):
            creds[k] = v.strip().strip('"').strip("'")
    if len(creds) != 2:
        raise RuntimeError(f"no mWater credentials in {ENV}")
    body = json.dumps({"username": creds["MWATER_USERNAME"],
                       "password": creds["MWATER_PASSWORD"]}).encode()
    req = urllib.request.Request(f"{API}/clients", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with _send(req, timeout=60) as r:
        b = json.load(r)
    cid = b if isinstance(b, str) else (b or {}).get("client") or (b or {}).get("id") or (b or {}).get("_id")
    if not cid:
        raise RuntimeError("login: no client id in response")
    return cid


def get(path, client, **params):
    params["client"] = client
    url = f"{API}/{path}?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with _send(urllib.request.Request(url)) as r:
                return json.load(r)
        except RefusedWrite:
            raise
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def fetch_all(path, client, selector, page=5000):
    """Fetch a whole collection.

    mWater's limit/skip paging returns OVERLAPPING pages: successive requests
    repeat rows already seen and silently drop others. A 500-row paged fetch of
    the call-centre form missed 462 of 3,141 responses. So: ask for everything
    in one request, and de-duplicate on _id regardless. If the server ever caps
    the page below what we asked for, fall back to paging but keep de-duplicating
    and stop only when a page adds nothing new.
    """
    seen, out, skip = set(), [], 0
    while True:
        batch = get(path, client, selector=json.dumps(selector),
                    limit=page, skip=skip)
        if not batch:
            break
        added = 0
        for row in batch:
            rid = row.get("_id")
            if rid in seen:
                continue
            seen.add(rid)
            out.append(row)
            added += 1
        if len(batch) < page or added == 0:
            break
        skip += len(batch)
    return out


def find_image_ids(node, acc):
    """mWater stores image answers as {id, caption} objects, possibly in lists."""
    if isinstance(node, dict):
        v = node.get("id")
        if isinstance(v, str) and len(v) == 32 and all(c in "0123456789abcdef" for c in v):
            acc.add(v)
        for x in node.values():
            find_image_ids(x, acc)
    elif isinstance(node, list):
        for x in node:
            find_image_ids(x, acc)
    return acc


def human(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:,.1f} {u}"
        n /= 1024


def last_verified(root):
    """Date of the newest data/<date>/ whose manifest says verified_complete."""
    best = None
    d = os.path.join(root, "data")
    for name in os.listdir(d) if os.path.isdir(d) else []:
        try:
            day = date.fromisoformat(name)
            m = json.load(open(os.path.join(d, name, "manifest.json"), encoding="utf8"))
        except (ValueError, OSError, json.JSONDecodeError):
            continue
        if m.get("verified_complete") is True and (best is None or day > best):
            best = day
    return best


class Tee:
    def __init__(self, *s):
        self.s = s

    def write(self, x):
        for s in self.s:
            s.write(x)
            s.flush()

    def flush(self):
        for s in self.s:
            s.flush()


def backup(a):
    root = os.path.abspath(a.dest)
    if not os.path.isdir(root):
        raise RuntimeError(f"backup folder not found: {root}")

    if not a.force:
        prev = last_verified(root)
        if prev and (date.today() - prev).days < a.min_days:
            print(f"mWater backup skipped: the last verified backup is {prev}, "
                  f"less than {a.min_days} days ago (runs once a week)")
            return 0

    # at least 60 minutes between runs that read mWater (as the build itself)
    now = time.time()
    try:
        last = float(open(STAMP).read().strip())
    except (OSError, ValueError):
        last = 0
    if 0 <= now - last < 3600:
        print(f"mWater backup skipped: the last run started {int((now - last) // 60)} "
              "minute(s) ago, and runs are at least 60 minutes apart")
        return 0
    os.makedirs(os.path.dirname(STAMP), exist_ok=True)
    open(STAMP, "w").write(str(int(now)))

    client = os.environ.get("MWATER_CLIENT") or login()

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data_dir = os.path.join(root, "data", stamp)
    img_dir = os.path.abspath(a.images_dest) if a.images_dest else os.path.join(root, "images")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(img_dir, exist_ok=True)

    manifest = {"run_utc": datetime.now(timezone.utc).isoformat(), "forms": {}}
    image_ids = set()

    # --- form designs and responses -------------------------------------
    for form_id, name in FORMS.items():
        print(f"  {name} ...", end="", flush=True)
        try:
            design = get(f"forms/{form_id}", client)
            with open(os.path.join(data_dir, f"form_{name}.json"), "w") as f:
                json.dump(design, f, indent=1, ensure_ascii=False)
        except RefusedWrite:
            raise
        except Exception as e:
            print(f" design failed: {e}")

        responses = fetch_all("responses", client, {"form": form_id})
        with open(os.path.join(data_dir, f"responses_{name}.json"), "w") as f:
            json.dump(responses, f, indent=1, ensure_ascii=False)
        find_image_ids(responses, image_ids)

        states = {}
        for r in responses:
            states[r.get("status", "?")] = states.get(r.get("status", "?"), 0) + 1
        manifest["forms"][name] = {"id": form_id, "responses": len(responses), "by_status": states}
        print(f" {len(responses)} responses {states}")

    # --- water point register -------------------------------------------
    print("  water point register ...", end="", flush=True)
    wps = fetch_all("entities/water_point", client, {"_managed_by": MANAGED_BY})
    with open(os.path.join(data_dir, "entities_water_point.json"), "w") as f:
        json.dump(wps, f, indent=1, ensure_ascii=False)
    find_image_ids(wps, image_ids)
    manifest["water_points"] = len(wps)
    print(f" {len(wps)}")

    # data is safe at this point - record it before the long image loop, so an
    # interrupted run still leaves a usable manifest
    with open(os.path.join(data_dir, "manifest_data_only.json"), "w") as f:
        json.dump(manifest, f, indent=1)

    # --- images: fetch once, then only what is new ------------------------
    # SharePoint (and the sync client) copes badly with tens of thousands of
    # files in one folder, so the store is sharded on the first two characters
    # of the image id: 256 folders of a few hundred files each.
    def shard(iid):
        return os.path.join(img_dir, iid[:2])

    have = set()
    for sub in os.listdir(img_dir):
        subp = os.path.join(img_dir, sub)
        if os.path.isdir(subp):
            have |= {n.split(".")[0] for n in os.listdir(subp)}
        elif sub.endswith(".jpg"):
            have.add(sub.split(".")[0])
    todo = sorted(image_ids - have)
    manifest["images_referenced"] = len(image_ids)
    manifest["images_already_held"] = len(image_ids & have)
    manifest["images_downloaded"] = 0
    manifest["images_failed"] = []

    with open(os.path.join(data_dir, "image_ids.txt"), "w") as f:
        f.write("\n".join(sorted(image_ids)))

    if a.skip_images:
        print(f"  images: {len(image_ids)} referenced, {len(todo)} new (skipped)")
    else:
        print(f"  images: {len(image_ids)} referenced, {len(have & image_ids)} already held, {len(todo)} to fetch")
        got = 0
        for i, iid in enumerate(todo, 1):
            try:
                with _send(urllib.request.Request(f"{API}/images/{iid}")) as r:
                    blob = r.read()
                d = shard(iid)
                os.makedirs(d, exist_ok=True)
                with open(os.path.join(d, f"{iid}.jpg"), "wb") as f:
                    f.write(blob)
                got += 1
            except RefusedWrite:
                raise
            except Exception as e:
                manifest["images_failed"].append({"id": iid, "error": str(e)})
            if i % 100 == 0:
                print(f"    {i}/{len(todo)}")
        manifest["images_downloaded"] = got

    total_img, n_img = 0, 0
    for root_dir, _, files in os.walk(img_dir):
        for n in files:
            total_img += os.path.getsize(os.path.join(root_dir, n))
            n_img += 1
    total_data = sum(os.path.getsize(os.path.join(data_dir, n)) for n in os.listdir(data_dir))
    manifest["bytes_images_total"] = total_img
    manifest["images_held"] = n_img
    manifest["bytes_data_this_run"] = total_data

    with open(os.path.join(data_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)

    # independent check: ask the server how many responses each form has and
    # compare against what we saved, so an incomplete run is loud, not silent.
    print()
    print("  verification (server count vs saved):")
    bad = []
    for form_id, name in FORMS.items():
        server = len(fetch_all("responses", client, {"form": form_id}))
        saved = manifest["forms"][name]["responses"]
        flag = "" if server == saved else "   <-- MISMATCH"
        if server != saved:
            bad.append(name)
        print(f"    {name:34s} server {server:6d}  saved {saved:6d}{flag}")
    manifest["verified_complete"] = not bad
    with open(os.path.join(data_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)

    total = sum(f["responses"] for f in manifest["forms"].values())
    print()
    print(f"  data this run : {human(total_data)}  -> {data_dir}")
    print(f"  image store   : {human(total_img)} over {n_img} files  -> {img_dir}")
    print(f"  manifest      : {os.path.join(data_dir, 'manifest.json')}")
    failed = len(manifest["images_failed"])
    if bad:
        print(f"BACKUP INCOMPLETE {stamp}: server and saved counts differ for "
              f"{', '.join(bad)}; manifest says verified_complete false")
        return 1
    print(f"mWater backup {stamp}: {total} responses, verified complete, "
          f"{manifest['images_downloaded']} new image(s)"
          + (f", {failed} image(s) could not be fetched" if failed else ""))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=DEST, help="backup root directory")
    ap.add_argument("--skip-images", action="store_true",
                    help="do not download photographs; still record which ones exist")
    ap.add_argument("--images-dest", default=None,
                    help="where the photo store lives (default: <dest>/images)")
    ap.add_argument("--min-days", type=int, default=6,
                    help="skip when a verified backup this recent exists (default 6)")
    ap.add_argument("--force", action="store_true", help="ignore the once-a-week rule")
    a = ap.parse_args()

    os.makedirs(LOGDIR, exist_ok=True)
    logf = open(os.path.join(LOGDIR, f"mwater_backup_{date.today()}.log"), "a", encoding="utf8")
    sys.stdout = Tee(sys.__stdout__, logf)
    print("mWater backup")
    try:
        return backup(a)
    except Exception as e:                                     # noqa: BLE001
        print(f"BACKUP FAILED: {type(e).__name__}: {str(e)[:200]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
