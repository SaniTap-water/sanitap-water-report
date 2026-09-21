# The owner/deadline workbook opened read-only — what it was, and what it was not

**Date:** 21 September 2026
**File:** `Water report - action owners and deadlines.xlsx`, Central Data Hub →
`Water Documents`
**Generator:** `tools/make_owner_workbook.py`

## The cause

Excel Online showed *"WORKBOOK REPAIRED — we temporarily repaired this workbook
so that you can open it in Reading View"*, and **a repaired workbook is always
read-only**.

The cause was **malformed cells**: every row with no deadline carried
`<c r="C106" s="3" t="n"></c>` — an explicit numeric type with no value. There
were **40** of them. `ws.append([...])` with `None` produces this.

The fix: write cells explicitly, leave a blank deadline **genuinely absent**,
and write real deadlines as `datetime.date` with a `yyyy-mm-dd` number format
so they are dates rather than text and the date validation on column C guards
something. Verified in the browser: opens editable, no repair banner, the owner
dropdown works, `C2` is a real date serial with `numFmt yyyy-mm-dd`, `C3` and
`C106` are genuinely absent, both data validations intact.

## What it was NOT — two wrong theories, not to be revisited

**1. `[trash]/NNNN.dat` members are not a fault.** They are SharePoint's
document-property promotion filler, appearing because SharePoint injects
`customXml/item1-3` and `docProps/custom.xml` carrying a `ContentTypeId`. Part
names containing `[` or `]` are **not legal OPC part names**, so the packaging
layer never sees those entries — they are invisible to Excel. Almost every
Office file in a SharePoint library has them and opens normally.

**2. Nothing is rewriting or corrupting the file.** No Excel Online session is
holding it, and the OneDrive sync client is not corrupting it. An earlier
observation that a clean copy "came back with `[trash]` restored 45 seconds
later" was simply SharePoint promoting properties on the uploaded file — normal,
harmless, and not a rewrite of any cell. Both theories were wrong.

## Consequences for the checks

Two assertions were **deleted** as wrong, not relaxed: that no zip member starts
with `[trash]`, and that every zip member is declared in `[Content_Types].xml`.
Both fail on any file that has round-tripped through SharePoint — which is every
published copy.

What is asserted instead are the invariants that actually predict a repair, in
`tools/make_owner_workbook.py::verify`:

1. no `<c>` carries a `t` attribute with an empty body or no value child
2. every member whose name **is** a legal OPC part name has a content type,
   by `Default` extension or `Override`
3. the worksheet `dimension ref` matches the real used range
4. both validations exist — `list` on `B2:B<last>`, `date` on `C2:C<last>`,
   `<last>` equal to the row count
5. every deadline cell is absent, or numeric with a date number format —
   never an inline string
6. the dropdown vocabulary matches the owners the action renderer can render

All six are negative-tested. `tools/verify_published_workbook.py` re-asserts
them against the published copy, ignoring anything that is not a legal OPC part
and anything SharePoint owns (`customXml/*`, `docProps/custom.xml`) — tolerant
**by construction**, not by exception. It deliberately does not assert on part
count or byte size: both legitimately change on upload.

## The supported publishing path

**Copy into the synced OneDrive folder.** That path is proven and the pipeline
owns the live artefact:

```
python3 tools/make_owner_workbook.py        # builds and self-verifies
cp build/action_owners.xlsx "/mnt/c/Users/bushp/OneDrive - SaniTap/Central Data Hub - Water Documents/Water report - action owners and deadlines.xlsx"
python3 tools/verify_published_workbook.py  # reads the published copy back
```

Do **not** upload this file through Microsoft Graph or the Microsoft 365
connector. Neither is necessary.
