# -*- coding: utf-8 -*-
"""Refuse to run when a required OneDrive document is cloud-only.

WHY THIS EXISTS
---------------
Windows Storage Sense is switching synced OneDrive files to cloud-only on this
machine, and C: is the drive under pressure: 931 GB used of 952 GB, 22 GB free.
The build reads several documents straight from a OneDrive path - the calendar
generator, the SOPs, the methodologies, the mWater evidence store - and a
cloud-only file does not announce itself. It has a normal size in a directory
listing. Opening it either blocks while Windows downloads it, or fails with an
I/O error that says nothing about the cause.

Either way the failure lands a long way from the reason, which is what this
module exists to prevent: it fails early, names the file, and says what to do.

HOW CLOUD-ONLY IS DETECTED
--------------------------
A dehydrated OneDrive file is a sparse reparse point. Windows reports its full
logical size while allocating no blocks for it, and drvfs passes that through
to `stat`. So on a /mnt/ path:

    st_size > 0 and st_blocks == 0   ->   cloud-only

Verified on this machine on 21 September 2026 by dehydrating a disposable file
that had a checksummed local copy:

    before  attrib +U -P :  size=183695  blocks=360
    after   attrib +U -P :  size=183695  blocks=0     (attributes 0x501620:
                                                       RECALL_ON_DATA_ACCESS
                                                       | UNPINNED | OFFLINE
                                                       | REPARSE | SPARSE)
    after   attrib -U +P :  size=183695  blocks=360

The check is deliberately cheap - one stat per file, no PowerShell, no network
- so it can run on every build.

    python3 tools/require_local.py            # check the required set
    python3 tools/require_local.py --hydrate  # print the command to fix it
"""
import os, sys

ONEDRIVE = ("/mnt/c/Users/bushp/OneDrive - SaniTap/"
            "Central Data Hub - Water Documents")

# What the build and the tools actually open. Directories are sampled rather
# than walked: the image store alone is 68,058 files and 45.9 GB, and Storage
# Sense dehydrates a folder wholesale rather than a file at a time.
REQUIRED_FILES = [
    f"{ONEDRIVE}/SOPs/SOP-MAD-SDWS27-CalendrierGardien-Generator-v1.4.py",
    f"{ONEDRIVE}/SOPs/SOP-MAD-SDWS27-CalendrierGardien-v1.5-2026.docx",
    f"{ONEDRIVE}/SOPs/SOP-MAD-SDWS27-CalendrierGardien-Template-v1.4-2026.svg",
    f"{ONEDRIVE}/SOPs/SOP-MAD-SDWS27-CalendrierGardien-Template-v1.4-2027.svg",
    f"{ONEDRIVE}/Methodology of record/"
    f"429_V1.0_ERSDWS_Emission-reductions-from-Safe-Drinking-Water-Supply.pdf",
    f"{ONEDRIVE}/Methodology of record/"
    f"429_V2.0_PAA-M400-12_Emission-reductions-from-Safe-Drinking-Water-Supply.pdf",
]
SAMPLED_DIRS = [
    (f"{ONEDRIVE}/Evidence/mWater backup/images", 24),
    (f"{ONEDRIVE}/Evidence/mWater backup/data", 8),
]


def state(path):
    """'missing' | 'cloudonly' | 'local' | 'empty'."""
    try:
        st = os.stat(path)
    except OSError:
        return "missing"
    if st.st_size == 0:
        return "empty"
    return "cloudonly" if st.st_blocks == 0 else "local"


def sample(directory, n):
    """First n files found, breadth-first enough to catch a dehydrated folder."""
    out = []
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames.sort()
        for fn in sorted(filenames):
            out.append(os.path.join(dirpath, fn))
            if len(out) >= n:
                return out
    return out


def audit():
    """Return (cloudonly, missing) as lists of paths."""
    cloud, missing = [], []
    for p in REQUIRED_FILES:
        s = state(p)
        if s == "cloudonly":
            cloud.append(p)
        elif s == "missing":
            missing.append(p)
    for d, n in SAMPLED_DIRS:
        if not os.path.isdir(d):
            missing.append(d)
            continue
        files = sample(d, n)
        bad = [p for p in files if state(p) == "cloudonly"]
        if bad:
            cloud.append(f"{d}  ({len(bad)} of {len(files)} sampled are cloud-only)")
    return cloud, missing


def message(cloud, missing):
    lines = []
    if missing:
        lines.append("REQUIRED DOCUMENTS ARE MISSING FROM ONEDRIVE:")
        lines += [f"    {p}" for p in missing]
    if cloud:
        lines.append("REQUIRED DOCUMENTS ARE CLOUD-ONLY, NOT PRESENT ON THIS MACHINE:")
        lines += [f"    {p}" for p in cloud]
        lines.append("")
        lines.append("Windows Storage Sense has freed their local copies. They still exist")
        lines.append("in OneDrive; nothing has been lost. Reading one from here would either")
        lines.append("stall while Windows downloads it or fail with an unexplained I/O error,")
        lines.append("so the build stops here instead.")
        lines.append("")
        lines.append("To restore them, in PowerShell:")
        lines.append('    attrib -U +P "<path>" /s')
        lines.append("or right-click the folder in Explorer and choose")
        lines.append('    "Always keep on this device".')
        lines.append("")
        lines.append("C: is the drive under pressure, not the Linux disk. Pinning these")
        lines.append("costs about 47 GB; tools/disk_retention.py reports what can be freed")
        lines.append("elsewhere to make room.")
    return "\n".join(lines)


def main():
    cloud, missing = audit()
    if not cloud and not missing:
        n = len(REQUIRED_FILES) + sum(k for _, k in SAMPLED_DIRS)
        print(f"all required OneDrive documents are present locally "
              f"({len(REQUIRED_FILES)} files + {len(SAMPLED_DIRS)} sampled folders)")
        return 0
    print(message(cloud, missing), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
