# The Marolinta form split — specification for review

22 September 2026. **For Adriaan to decide. Nothing here has been applied.**

## What is split, and why it matters

Marolinta's works — **rehabilitations and new constructions both** — are recorded on the
borehole-progress form `8764843c94484f5b984078c68f13b2ca`, not on the works form
`86cf66efdd3749dd8a121314bab3675a` that every other point uses. 18 records.

Zero Marolinta points appear among the 773 first-rehabilitation records. Five appear on the works
form at all, and only as work type `3HwlgLk` *"Identification des points d'eau"*, submitted
22 August 2025 — a survey, not works.

**The consequence.** Five of the six managed points with no successful first-rehabilitation
record are the Marolinta points. They are invisible to every query that reads only the works
form. A population that reads rehabilitation and does not read both forms silently omits
Marolinta, which is the same fault as a figure with no source.

Until this is decided, `first_rehabilitated` and `rehabilitated_successfully` in
`tools/populations.py` name both forms in their `reads`, and the chain reports the five
separately rather than counting them as unexplained.

**Why the split happened.** The works form has no *"Nouvelle construction"* option at all. There
was nowhere to record a new borehole, so a second form was made.

## Option A — add construction to the works form, retire the borehole form

**What it costs.** A new choice on *"Type de travaux"*. Migrating 18 records: each needs its
answers mapped onto the works form's questions, and the two forms do not share a question set —
the borehole form carries progress-stage questions the works form has no home for. Those either
get new questions on the works form or are lost.

**What it risks.** Migration is a write to historical records. If the mapping is wrong it is wrong
silently, and the originals are gone. The borehole form also carries the only record of
construction *progress* — a stage model the works form does not have — so "retire" may mean
"discard a dimension of the data".

**What happens to existing records.** 18 records rewritten onto a different form with a different
`_id` for the form. Anything referencing them by form id breaks. The `deployment` split that
distinguishes Marolinta from Moramanga must be preserved or re-encoded.

## Option B — keep both forms, make every query read both

**What it costs.** Every query, tool and population that reads works must read two forms and
union the results. That is already done in `tools/populations.py`; it would have to be done in
`tools/build_call_tables.py`, `tools/marolinta_works.py` and anything written later. The cost is
permanent and falls on every future query, including ones a verifier writes.

**What it risks.** Somebody writes a query that reads one form. That is exactly the fault that
produced "46 unexplained points". The risk does not diminish over time; it recurs with each new
query.

**What happens to existing records.** Nothing. They stay where they are, which is the strongest
argument for this option: no historical write, no migration mapping, nothing lost.

## What is not in question

Either way, **every population that reads rehabilitation must read both forms or state in its
definition that it does not.** That rule stands whichever option is chosen, and is already
enforced.

## Also: the village name is misspelled

**19 records on the works form spell the village "Marolita"**, all submitted 22–23 August 2025.
Flagged for correction by MadAvance, **not corrected from the build** — the build does not write
to mWater, and a name corrected silently at render time hides a data-entry problem rather than
fixing it.
