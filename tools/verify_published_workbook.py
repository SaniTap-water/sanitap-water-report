# -*- coding: utf-8 -*-
"""Read the published workbook back and assert it is still well formed.

Tolerant of SharePoint BY CONSTRUCTION, not by exception. When SharePoint
promotes document properties it injects customXml/item1-3, docProps/custom.xml
carrying a ContentTypeId, and [trash]/NNNN.dat filler. Part names containing
[ or ] are not legal OPC part names, so the packaging layer never sees the
filler at all - it is invisible to Excel, which is why nearly every file in a
SharePoint library carries it and opens perfectly well.

So this ignores anything that is not a legal OPC part, ignores the parts
SharePoint owns, and asserts only invariants of the CONTENT - which an upload
does not touch. It deliberately does NOT assert on part count or byte size:
both legitimately change on upload.

    python3 tools/verify_published_workbook.py            # the OneDrive copy
    python3 tools/verify_published_workbook.py <path>
"""
import os, sys, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xlsx_invariants as M                                  # noqa: E402
import re                                                    # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLISHED = ("/mnt/c/Users/bushp/OneDrive - SaniTap/"
             "Central Data Hub - Water Documents/"
             "Water report - action owners and deadlines.xlsx")
# parts SharePoint adds and owns; they say nothing about the workbook
SHAREPOINT_OWNED = ("customXml/", "docProps/custom.xml")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else PUBLISHED
    if not os.path.isfile(path):
        sys.exit(f"no published workbook at {path}")
    src = os.path.join(REPO, "build", "action_owners.xlsx")
    if not os.path.isfile(src):
        sys.exit("build/action_owners.xlsx is missing - run "
                 "tools/make_owner_workbook.py first")

    z = zipfile.ZipFile(path)
    ignored = [n for n in z.namelist()
               if not M.is_opc_part(n) or n.startswith(SHAREPOINT_OWNED)]
    print(f"published: {path}")
    print(f"  {len(z.namelist())} zip member(s), ignoring {len(ignored)} that "
          "SharePoint owns or that are not legal OPC parts")

    # the ids the generator wrote, read from its own output
    zs = zipfile.ZipFile(src)
    xs = zs.read("xl/worksheets/sheet1.xml").decode("utf8")
    ids = []
    for c in re.findall(r'<c\b[^>]*\br="A\d+"[^>]*(?:/>|>.*?</c>)', xs, re.S):
        if re.search(r'r="A1"', c):
            continue
        t = re.search(r"<is>\s*<t[^>]*>(.*?)</t>\s*</is>", c, re.S)
        if t:
            ids.append(t.group(1))
    owners = set(re.findall(r'"([^"]+)"', re.search(
        r"OWNERS = \[(.*?)\]",
        open(os.path.join(REPO, "tools", "make_owner_workbook.py"),
             encoding="utf8").read(), re.S).group(1)))
    try:
        M.verify(path, expect_ids=ids, expect_owners=owners)
    except SystemExit as e:
        print("\nPUBLISHED WORKBOOK FAILED VERIFICATION:")
        print(str(e))
        return 1
    print(f"  id column matches the generator exactly: {len(ids)} row(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
