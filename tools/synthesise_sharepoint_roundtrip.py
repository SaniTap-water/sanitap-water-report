# -*- coding: utf-8 -*-
"""Make a copy of the workbook that looks like it came back from SharePoint.

WHY THIS EXISTS
---------------
tools/verify_published_workbook.py is written to be tolerant of SharePoint by
construction: it ignores parts that are not legal OPC part names, and ignores
the parts SharePoint owns. That claim had never been tested against a file
that had actually been through SharePoint - only against the 10-member file
the generator writes, where there is nothing to tolerate. A tolerance nobody
has exercised is a guess.

This injects exactly what a property-promotion round trip adds:

  [trash]/NNNN.dat x4   filler; the names contain [ and ] so they are not
                        legal OPC part names and the packaging layer never
                        sees them. Content is ff ff ff ff then nulls.
  customXml/item{1,2,3}.xml          the promoted property sets
  customXml/itemProps{1,2,3}.xml     their schema references
  customXml/_rels/item{1,2,3}.xml.rels
  docProps/custom.xml                ContentTypeId and friends

[Content_Types].xml and _rels/.rels are rewritten to declare and reference
them, so the result is a genuinely valid package rather than a zip with
extra files in it.

    python3 tools/synthesise_sharepoint_roundtrip.py <src.xlsx> <out.xlsx>
"""
import os, shutil, sys, zipfile

TRASH_SIZES = (183, 247, 301, 354)        # observed range in the live library

ITEM = ('<?xml version="1.0" encoding="utf-8"?>'
        '<{root} xmlns="{ns}"{attrs}/>')
ITEMPROPS = ('<?xml version="1.0" encoding="utf-8"?>'
             '<ds:datastoreItem xmlns:ds="http://schemas.openxmlformats.org/'
             'officeDocument/2006/customXml" ds:itemID="{{{iid}}}">'
             '<ds:schemaRefs><ds:schemaRef ds:uri="{ns}"/></ds:schemaRefs>'
             '</ds:datastoreItem>')
ITEM_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
             '2006/relationships"><Relationship Id="rId1" Type="http://'
             'schemas.openxmlformats.org/officeDocument/2006/relationships/'
             'customXmlProps" Target="itemProps{n}.xml"/></Relationships>')
CUSTOM = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument'
          '/2006/custom-properties" xmlns:vt="http://schemas.openxmlformats'
          '.org/officeDocument/2006/docPropsVTypes">'
          '<property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="2" '
          'name="ContentTypeId"><vt:lpwstr>0x0101008E1B2F4A6C3D4E8FA0'
          '2B7C5D91E3F44</vt:lpwstr></property>'
          '<property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="3" '
          'name="MediaServiceImageTags"><vt:lpwstr/></property></Properties>')

NSS = [("properties", "http://schemas.microsoft.com/office/2006/metadata/properties",
        ' xmlns:pc="http://schemas.microsoft.com/office/infopath/2007/PartnerControls"'),
       ("contentTypeSchema", "http://schemas.microsoft.com/office/2006/metadata/contentType",
        ' xmlns:ma="http://schemas.microsoft.com/office/2006/metadata/properties/metaAttributes"'),
       ("Receivers", "http://schemas.microsoft.com/sharepoint/events", "")]
IIDS = ["5C4F2A19-7B6E-4D83-9E51-C2A8F0B36D74",
        "A1E9D7C3-58B2-4F06-8A9D-31C7E4B5F802",
        "7D30B6A5-9C14-4E2B-B8F7-0A6D5E93C1B8"]


def trash_member(size):
    return b"\xff\xff\xff\xff" + b"\x00" * (size - 4)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__.strip().splitlines()[-1].strip())
    src, out = sys.argv[1], sys.argv[2]
    if not os.path.isfile(src):
        sys.exit(f"no such workbook: {src}")
    zin = zipfile.ZipFile(src)
    ct = zin.read("[Content_Types].xml").decode("utf8")
    rels = zin.read("_rels/.rels").decode("utf8")

    adds = []
    for i, ((root, ns, attrs), iid) in enumerate(zip(NSS, IIDS), start=1):
        adds.append((f"customXml/item{i}.xml",
                     ITEM.format(root=root, ns=ns, attrs=attrs).encode("utf8")))
        adds.append((f"customXml/itemProps{i}.xml",
                     ITEMPROPS.format(iid=iid, ns=ns).encode("utf8")))
        adds.append((f"customXml/_rels/item{i}.xml.rels",
                     ITEM_RELS.format(n=i).encode("utf8")))
    adds.append(("docProps/custom.xml", CUSTOM.encode("utf8")))

    # declare the new parts, as SharePoint does
    ov = ''.join(
        f'<Override PartName="/customXml/itemProps{i}.xml" ContentType='
        '"application/vnd.openxmlformats-officedocument.customXmlProperties+xml"/>'
        for i in (1, 2, 3))
    ov += ('<Override PartName="/docProps/custom.xml" ContentType='
           '"application/vnd.openxmlformats-officedocument.custom-properties+xml"/>')
    ct = ct.replace("</Types>", ov + "</Types>")

    rel_add = ''.join(
        f'<Relationship Id="rIdCx{i}" Type="http://schemas.openxmlformats.org/'
        f'officeDocument/2006/relationships/customXml" '
        f'Target="customXml/item{i}.xml"/>' for i in (1, 2, 3))
    rel_add += ('<Relationship Id="rIdCust" Type="http://schemas.openxmlformats'
                '.org/officeDocument/2006/relationships/custom-properties" '
                'Target="docProps/custom.xml"/>')
    rels = rels.replace("</Relationships>", rel_add + "</Relationships>")

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
        for it in zin.infolist():
            data = zin.read(it.filename)
            if it.filename == "[Content_Types].xml":
                data = ct.encode("utf8")
            elif it.filename == "_rels/.rels":
                data = rels.encode("utf8")
            zo.writestr(it.filename, data)
        for name, data in adds:
            zo.writestr(name, data)
        for i, size in enumerate(TRASH_SIZES, start=1):
            zo.writestr(f"[trash]/{1000 + i * 137}.dat", trash_member(size))

    z = zipfile.ZipFile(out)
    names = z.namelist()
    tr = [n for n in names if n.startswith("[trash]/")]
    print(f"round-tripped copy written: {out}")
    print(f"  {len(zin.namelist())} members in, {len(names)} out "
          f"({len(names) - len(zin.namelist())} added)")
    print(f"  {len(tr)} [trash] member(s), "
          f"{min(z.getinfo(n).file_size for n in tr)}-"
          f"{max(z.getinfo(n).file_size for n in tr)} bytes, "
          f"each starting ff ff ff ff")
    print("  customXml: " + ", ".join(sorted(n for n in names
                                             if n.startswith("customXml/"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
