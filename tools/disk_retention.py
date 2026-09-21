# -*- coding: utf-8 -*-
"""Report what is filling the disks, and enforce retention on what we control.

WHICH DISK IS ACTUALLY FULL
---------------------------
Measured 21 September 2026:

    /  (WSL ext4)      1007 GB,  147 GB used,  810 GB free   -  16%
    C: (Windows)        952 GB,  931 GB used,   22 GB free   -  98%

**C: is the problem and the Linux disk is not.** That matters because deleting
files inside WSL does not give C: a single byte back on its own: the WSL disk
is one file on C:

    ext4.vhdx    161.8 GB allocated,  147 GB used inside

and a VHDX grows but never shrinks by itself. Freeing 9 GB inside WSL widens
the gap between allocated and used; it takes a compaction to hand that back.
Compaction needs `wsl --shutdown`, which kills whatever is running, so this
script prints the command and never runs it.

The other 770 GB of C: is three sync clients holding local copies:

    AppData        227 GB   (162 GB of it the WSL disk)
    Proton Drive   226 GB
    Dropbox        188 GB
    Downloads      113 GB
    OneDrive       106 GB

**Nothing in a sync folder is deleted by this script**, ever. Deleting from a
sync folder deletes from the cloud, which is the opposite of freeing a cache.
The lever there is dehydration - "free up space" / `attrib +U -P` - which is
reversible and keeps the file. But see tools/require_local.py first: the build
reads about 47 GB of OneDrive directly, and dehydrating that breaks it.

WHAT THIS SCRIPT OWNS
---------------------
Only stores this project creates, where "regenerable" is demonstrable:

  ~/mwater-mcp/backups   form-design snapshots, 3-4 per form edit, unbounded.
                         Keep KEEP_DAYS. Older ones are deleted only when a
                         byte-identical copy exists in SharePoint, or when
                         they are *_proposed.json - a plan artefact that was
                         either applied (so the postwrite is the record) or
                         abandoned. Anything else is reported and kept.
  ~/mwater-exports       CSV exports, regenerable by re-exporting. Age only.
  package caches         pip / uv / go-build. Pure download caches.

It will not touch virtual environments: none of them has a requirements file,
so none can be demonstrably rebuilt.

    python3 tools/disk_retention.py            # report, delete nothing
    python3 tools/disk_retention.py --apply    # enforce retention
    python3 tools/disk_retention.py --caches   # also clear package caches
"""
import hashlib, os, shutil, subprocess, sys, time

HOME = os.path.expanduser("~")
BACKUPS = f"{HOME}/mwater-mcp/backups"
EXPORTS = f"{HOME}/mwater-exports"
MIRROR = ("/mnt/c/Users/bushp/OneDrive - SaniTap/Central Data Hub - "
          "Water Documents/Evidence/mWater backup/form design changes")
CACHES = [f"{HOME}/.cache/pip", f"{HOME}/.cache/uv", f"{HOME}/.cache/go-build"]
VHDX = ("/mnt/c/Users/bushp/AppData/Local/wsl/"
        "{ed3bf82c-f203-4385-8f43-9eea2d70239f}/ext4.vhdx")

KEEP_DAYS = 30          # mWater form-design backups
EXPORT_DAYS = 14        # regenerable CSV exports
VHDX_SLACK_GB = 20      # allocated-minus-used above which compaction is worth it


def gb(n):
    return n / (1024 ** 3)


def mb(n):
    return n / (1024 ** 2)


def sha(p, buf=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def tree_size(p):
    t = 0
    for dp, _, fns in os.walk(p):
        for fn in fns:
            try:
                t += os.path.getsize(os.path.join(dp, fn))
            except OSError:
                pass
    return t


def disks():
    print("DISKS")
    for label, path in (("/  (WSL ext4)", "/"), ("C: (Windows)", "/mnt/c")):
        try:
            s = os.statvfs(path)
        except OSError:
            continue
        total = s.f_blocks * s.f_frsize
        free = s.f_bavail * s.f_frsize          # what a non-root user may use
        used = (s.f_blocks - s.f_bfree) * s.f_frsize   # f_bfree, not f_bavail:
        # the difference is the root-reserved blocks, and counting those as
        # "used" overstated the WSL disk by 50 GB the first time this ran.
        print(f"  {label:16s} {gb(total):7.0f} GB total  {gb(used):7.0f} used  "
              f"{gb(free):7.0f} free   {100 * used / total:3.0f}%")
    if os.path.exists(VHDX):
        alloc = os.path.getsize(VHDX)
        try:
            s = os.statvfs("/")
            inside = (s.f_blocks - s.f_bfree) * s.f_frsize
        except OSError:
            inside = 0
        slack = gb(alloc) - gb(inside)
        print(f"\n  ext4.vhdx on C:  {gb(alloc):.1f} GB allocated, "
              f"{gb(inside):.1f} GB used inside  ->  {slack:.1f} GB recoverable")
        if slack >= VHDX_SLACK_GB:
            print("  *** COMPACTION IS WORTH RUNNING. It needs WSL shut down, so it is")
            print("      not run from here. In PowerShell as Administrator:")
            print("          wsl --shutdown")
            print("          Optimize-VHD -Path '<vhdx>' -Mode Full")
            print("      (or diskpart: select vdisk file='<vhdx>' / attach readonly /")
            print("       compact vdisk / detach vdisk)")
        else:
            print(f"  compaction would recover under {VHDX_SLACK_GB} GB; not worth the downtime yet")
    print()


def mirror_hashes():
    if not os.path.isdir(MIRROR):
        return None
    out = set()
    for dp, _, fns in os.walk(MIRROR):
        for fn in fns:
            try:
                out.add(sha(os.path.join(dp, fn)))
            except OSError:
                pass
    return out


def prune_backups(apply_):
    if not os.path.isdir(BACKUPS):
        return 0
    remote = mirror_hashes()
    if remote is None:
        print("BACKUPS: the SharePoint mirror is not reachable - nothing pruned.")
        return 0
    cutoff = time.time() - KEEP_DAYS * 86400
    freed = kept_recent = kept_unmirrored = 0
    to_delete = []
    for dp, _, fns in os.walk(BACKUPS):
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                st = os.stat(p)
            except OSError:
                continue
            if st.st_mtime >= cutoff:
                kept_recent += 1
                continue
            regenerable = fn.endswith("_proposed.json")
            try:
                mirrored = sha(p) in remote
            except OSError:
                mirrored = False
            if mirrored or regenerable:
                to_delete.append((p, st.st_size,
                                  "mirrored" if mirrored else "plan artefact"))
            else:
                kept_unmirrored += 1
    print(f"BACKUPS  {BACKUPS}")
    print(f"  keep {KEEP_DAYS} days: {kept_recent} file(s) inside the window, kept")
    print(f"  older and NOT mirrored anywhere: {kept_unmirrored} file(s), KEPT "
          f"(their only copy is local)")
    print(f"  older and safe to remove: {len(to_delete)} file(s), "
          f"{mb(sum(s for _, s, _ in to_delete)):.1f} MB")
    for p, s, why in to_delete[:6]:
        print(f"      {os.path.basename(p)}  ({why})")
    if len(to_delete) > 6:
        print(f"      ... and {len(to_delete) - 6} more")
    if apply_:
        for p, s, _ in to_delete:
            try:
                os.remove(p)
                freed += s
            except OSError:
                pass
        print(f"  deleted: {mb(freed):.1f} MB")
    print()
    return freed


def prune_exports(apply_):
    if not os.path.isdir(EXPORTS):
        return 0
    cutoff = time.time() - EXPORT_DAYS * 86400
    old = []
    for dp, _, fns in os.walk(EXPORTS):
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                st = os.stat(p)
            except OSError:
                continue
            if st.st_mtime < cutoff:
                old.append((p, st.st_size))
    print(f"EXPORTS  {EXPORTS}  (regenerable by re-exporting)")
    print(f"  older than {EXPORT_DAYS} days: {len(old)} file(s), "
          f"{mb(sum(s for _, s in old)):.1f} MB")
    freed = 0
    if apply_:
        for p, s in old:
            try:
                os.remove(p)
                freed += s
            except OSError:
                pass
        print(f"  deleted: {mb(freed):.1f} MB")
    print()
    return freed


def prune_caches(apply_):
    total = 0
    print("PACKAGE CACHES (pure download caches, rebuilt on next install)")
    for c in CACHES:
        if not os.path.isdir(c):
            print(f"  {c}: absent")
            continue
        s = tree_size(c)
        total += s
        print(f"  {c}: {gb(s):.2f} GB")
        if apply_:
            shutil.rmtree(c, ignore_errors=True)
    if apply_:
        print(f"  cleared: {gb(total):.2f} GB")
    else:
        print(f"  total {gb(total):.2f} GB - pass --caches to clear")
    print()
    return total if apply_ else 0


def main():
    apply_ = "--apply" in sys.argv[1:]
    caches = "--caches" in sys.argv[1:]
    print(f"disk retention - {time.strftime('%Y-%m-%d %H:%M')} - "
          f"{'ENFORCING' if apply_ or caches else 'REPORT ONLY'}\n")
    disks()
    freed = prune_backups(apply_) + prune_exports(apply_)
    freed += prune_caches(caches)
    if apply_ or caches:
        print(f"TOTAL FREED INSIDE WSL: {mb(freed):.1f} MB")
        print("Remember: this frees the Linux disk, which has room already.")
        print("C: gets it back only after the VHDX is compacted - see above.")
    else:
        print("Nothing was deleted. Re-run with --apply (and --caches) to enforce.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
