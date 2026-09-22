# First-rehabilitation records: what the numbers are, and the paging fault beneath them

22 September 2026.

## The counts, from a stable enumeration

| quantity | unit | value |
|---|---|---|
| first-rehabilitation records | **records** | 773 |
| distinct points carrying one | **points** | 773 — one record each |
| successful records | **records** | 731 |
| successful points, in the register | **points** | 730 |

773 records on 773 points: **no point carries more than one first-rehabilitation record.**

## The 48 repeated points do not exist

They were an artefact of mWater's paging. `skip`/`limit` on the responses endpoint has no sort
order, so the row order shifts between requests. A straight paged pull of this 1,688-response
form returned:

* 1,688 rows carrying only **1,586 distinct `_id`s** — 102 records returned twice,
* and **102 records missed entirely**.

The duplicated records appear as a second record on a point that has one. De-duplicated, the same
pull gives 726 records on 726 points with **zero repeats**.

`tools/mwater/pull_form.mjs` enumerates by 30-day windows instead. No window exceeds 221 rows, so
paging never engages and each window is a complete bounded query. That enumeration gives 773/731,
which matches the figure the page has always carried and the figure obtained independently by
direct query.

**There is therefore nothing to classify** into genuine second attempts, duplicates and
misclassifications, and no form guard is proposed: the fault the guard would prevent is not
occurring. If a future stable pull shows a point with two records, that is a real finding and the
four-way classification should be done then.

## 723 is withdrawn

The page carried 723 successful first rehabilitations. The stable enumeration gives **731
successful records** and **730 successful points**, and neither is 723. No filter, date cut or
status restriction reproduces 723 from anything held in this repository.

It is withdrawn, as 727 was, rather than carried with a caveat. `REG.succ` is now the derived
point count, 730, which is exactly what the page's own register-chain note has always claimed.
`REG.succ_withdrawn` records the old value so the change is auditable.

## A coincidence to be careful of

**731 successful first-rehabilitation RECORDS** happens to equal **731 carbon-fleet POINTS**.
They are unrelated quantities that share a number this week. Every population now declares its
unit, every chain step names whether it relates records or points, and
`tools/check_consistency.py` asserts that the two are never set beside each other as a
reconciliation.

That confusion is not hypothetical: it produced 727, it produced the 723/731 gap, and it produced
a "46 managed points with no rehabilitation record" finding that was really the paging fault.
