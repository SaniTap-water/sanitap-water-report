# -*- coding: utf-8 -*-
"""The invariants that predict an Excel repair, with no openpyxl dependency.

Kept separate so tools/check_consistency.py - which runs under the system
python3, where openpyxl is not installed - can assert exactly what the
generator asserts. One definition of "well formed", two callers.
"""
import re, zipfile


# A part name is only an OPC part if it is a legal one. SharePoint injects
# [trash]/NNNN.dat filler when it promotes document properties, and names
# containing [ or ] are NOT legal OPC part names, so the packaging layer never
# sees those entries - they are invisible to Excel, which is why almost every
# file in a SharePoint library carries them and opens normally. Skipping them
# is correct by construction, not a tolerance.
OPC_ILLEGAL = set("[]")


def is_opc_part(name):
    if name.startswith("/") or name.endswith("/"):
        return False
    if any(c in OPC_ILLEGAL for c in name):
        return False
    return all(seg and seg not in (".", "..") for seg in name.split("/"))


def col_letter_row(ref):
    m = re.match(r"([A-Z]+)(\d+)$", ref)
    return (m.group(1), int(m.group(2))) if m else (None, None)


def verify(path, expect_ids=None, expect_owners=None):
    """Assert the invariants that actually predict an Excel repair.

    The one fault that made this file open read-only was cells carrying an
    explicit type with an empty body. Everything checked here is a property
    of the CONTENT, so it survives a round-trip through SharePoint - which
    adds parts but changes no cell.
    """
    z = zipfile.ZipFile(path)
    names = [n for n in z.namelist() if is_opc_part(n)]
    faults = []

    # 1. content types: every legal part is typed, by Default or Override
    ct = z.read("[Content_Types].xml").decode("utf8")
    overrides = set(re.findall(r'PartName="/([^"]+)"', ct))
    defaults = {e.lower() for e in re.findall(r'Extension="([^"]+)"', ct)}
    for n in names:
        if n == "[Content_Types].xml":
            continue
        ext = n.rsplit(".", 1)[-1].lower() if "." in n else ""
        if n not in overrides and ext not in defaults:
            faults.append(f"part has no content type: {n}")

    sheets = [n for n in names if n.startswith("xl/worksheets/sheet")]
    for n in sorted(sheets):
        xml = z.read(n).decode("utf8")
        cells = re.findall(r"<c\b[^>]*/>|<c\b[^>]*>.*?</c>", xml, re.S)

        # 2. no cell carries a type with an empty body or no <v>/<is> child
        for c in cells:
            m = re.search(r'\bt="([^"]*)"', c)
            if not m:
                continue
            has_value = ("<v>" in c) or ("<is>" in c) or ("<f>" in c)
            if not has_value:
                ref = re.search(r'r="([A-Z]+\d+)"', c)
                faults.append(f"{n}: cell {ref.group(1) if ref else '?'} has "
                              f't="{m.group(1)}" with no value')

        # 3. the dimension ref matches the real used range
        dim = re.search(r'<dimension ref="([^"]+)"', xml)
        refs = [r for r in re.findall(r'<c\b[^>]*\br="([A-Z]+\d+)"', xml)]
        if dim and refs:
            rows = [col_letter_row(r)[1] for r in refs]
            cols = [col_letter_row(r)[0] for r in refs]
            want = (f"{min(cols, key=lambda c: (len(c), c))}{min(rows)}:"
                    f"{max(cols, key=lambda c: (len(c), c))}{max(rows)}")
            if dim.group(1) != want:
                faults.append(f"{n}: dimension ref is {dim.group(1)}, "
                              f"used range is {want}")

    # the actions sheet carries the validations and the deadline column
    sheet1 = "xl/worksheets/sheet1.xml"
    if sheet1 in names:
        xml = z.read(sheet1).decode("utf8")
        refs = re.findall(r'<c\b[^>]*\br="([A-Z]+\d+)"', xml)
        last = max((col_letter_row(r)[1] for r in refs), default=1)

        # 4. both validations present, over the real row range
        dvs = re.findall(r"<dataValidation\b[^>]*>", xml)
        want_dv = {"list": f"B2:B{last}", "date": f"C2:C{last}"}
        for typ, sqref in want_dv.items():
            hit = [d for d in dvs if f'type="{typ}"' in d]
            if not hit:
                faults.append(f"no {typ} data validation on the actions sheet")
                continue
            got = re.search(r'sqref="([^"]+)"', hit[0])
            if not got or got.group(1) != sqref:
                faults.append(f"{typ} validation covers "
                              f"{got.group(1) if got else '?'}, expected {sqref}")

        # 5. deadlines are absent or numeric with a date format - never text
        styles = z.read("xl/styles.xml").decode("utf8")
        xf = re.search(r"<cellXfs[^>]*>(.*?)</cellXfs>", styles, re.S)
        xfs = re.findall(r"<xf\b[^>]*>", xf.group(1)) if xf else []
        numfmts = dict(re.findall(r'numFmtId="(\d+)"[^>]*formatCode="([^"]+)"',
                                  styles))
        for c in re.findall(r'<c\b[^>]*\br="C\d+"[^>]*(?:/>|>.*?</c>)', xml, re.S):
            ref = re.search(r'r="(C\d+)"', c).group(1)
            if ref == "C1":
                continue
            if re.search(r'\bt="(s|str|inlineStr)"', c):
                faults.append(f"deadline {ref} is a string, not a date")
                continue
            if "<v>" not in c:
                continue                      # genuinely absent: correct
            s = re.search(r'\bs="(\d+)"', c)
            fmt = ""
            if s and int(s.group(1)) < len(xfs):
                nid = re.search(r'numFmtId="(\d+)"', xfs[int(s.group(1))])
                if nid:
                    fmt = numfmts.get(nid.group(1), "")
            if "yy" not in fmt.lower():
                faults.append(f"deadline {ref} carries no date number format "
                              f"(got {fmt!r})")

        # 6. the dropdown vocabulary must be renderable by the action renderer
        lst = [d for d in dvs if 'type="list"' in d]
        f1 = re.search(r"<formula1>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</formula1>",
                       xml, re.S)
        if f1:
            listed = [o.strip() for o in f1.group(1).strip('"').split(",") if o.strip()]
            if expect_owners is not None:
                stray = [o for o in listed if o not in expect_owners]
                if stray:
                    faults.append("dropdown offers owner(s) the report cannot "
                                  f"render: {stray[:3]}")

        # the id column must be exactly what the generator wrote
        if expect_ids is not None:
            shared = []
            if "xl/sharedStrings.xml" in names:
                shared = re.findall(r"<t[^>]*>(.*?)</t>",
                                    z.read("xl/sharedStrings.xml").decode("utf8"), re.S)
            got_ids = []
            for c in re.findall(r'<c\b[^>]*\br="A\d+"[^>]*(?:/>|>.*?</c>)', xml, re.S):
                ref = re.search(r'r="(A\d+)"', c).group(1)
                if ref == "A1":
                    continue
                inline = re.search(r"<is>\s*<t[^>]*>(.*?)</t>\s*</is>", c, re.S)
                if inline:                       # openpyxl writes inlineStr
                    got_ids.append(inline.group(1))
                    continue
                v = re.search(r"<v>(.*?)</v>", c, re.S)
                if not v:
                    got_ids.append(None)
                elif re.search(r'\bt="s"', c):   # shared string index
                    got_ids.append(shared[int(v.group(1))] if shared else None)
                else:
                    got_ids.append(v.group(1))
            if got_ids != list(expect_ids):
                a_, b_ = set(expect_ids), set(x for x in got_ids if x)
                faults.append(f"id column differs: {len(got_ids)} row(s) vs "
                              f"{len(expect_ids)} expected; "
                              f"missing {sorted(a_ - b_)[:3]}, "
                              f"extra {sorted(b_ - a_)[:3]}")

    if faults:
        raise SystemExit(f"{path}:\n  " + "\n  ".join(faults[:8]))
    print(f"  verified: {len(names)} OPC part(s), {len(sheets)} sheet(s), "
          "no typed-empty cells, dimension and validations correct, "
          "deadlines numeric, dropdown renderable")
    return True


