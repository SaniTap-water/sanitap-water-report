# -*- coding: utf-8 -*-
"""Every field in every embedded data object on the page, and what writes it.

S.wq_tested was a stored 729 that no generator wrote and no assertion read.
It is the fifth figure of that shape, after WPOP_C250, 727, 723 and 628, and
every one of the five was found by a person noticing rather than by a check.
A value nothing can move is a value nobody is checking.

This enumerates the page's embedded objects field by field and resolves each
against GENERATORS, the declared registry in generator_registry.py. A field
with no entry is reported as NO GENERATOR. The registry is deliberately
explicit: a field is covered because someone wrote down what computes it, not
because a heuristic guessed.

    python3 tools/embedded_fields.py            # table
    python3 tools/embedded_fields.py --json     # machine-readable
"""
import json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")

# Objects that are page furniture rather than measured data: copy decks,
# captions, route tables, scope definitions. They are prose and links, not
# figures, and holding them to a generator would be noise.
FURNITURE = {
    "ROUTES", "SCOPES", "SITEMAP", "PHOTO_CAPS", "QUOTES", "WITHDRAWN",
    "ARTEFACTS", "PARAMS", "RWHY", "NA", "SC", "G", "IND", "CAP_T", "SA",
    "W", "MW", "MWR", "TRACE", "RECONSET", "DERIV", "COAST", "FULLMAD",
    "EDITION", "PHOTOS",
}


def objects(src=None):
    """Yield (name, line, parsed) for every `const NAME={...}` / `[...]`."""
    src = src if src is not None else open(PAGE, encoding="utf8").read()
    out = []
    for m in re.finditer(r"^const ([A-Z_][A-Z_0-9]*)\s*=\s*", src, re.M):
        name = m.group(1)
        i = m.end()
        if i >= len(src) or src[i] not in "{[":
            continue
        close = "};" if src[i] == "{" else "];"
        j = src.index(close, i)
        try:
            val = json.loads(src[i:j + 1])
        except Exception:
            continue
        out.append((name, src[:m.start()].count("\n") + 1, val))
    return out


def _id_keyed(val):
    """True when a dict is a lookup keyed by entity id, not a set of fields."""
    ks = list(val)
    return len(ks) > 8 and sum(1 for k in ks if re.fullmatch(r"\d{4,}", k)) > len(ks) * 0.8


def fields(name, val):
    """Top-level fields of one object, as (field, kind, summary)."""
    if isinstance(val, dict):
        if _id_keyed(val):
            # A per-point lookup. Its fields are the inner keys; the outer
            # ones are point ids and carry no separate provenance.
            inner = []
            for v in val.values():
                if isinstance(v, dict):
                    for k in v:
                        if k not in inner:
                            inner.append(k)
            if inner:
                for k in inner:
                    yield f"{{*}}.{k}", "column", f"{len(val)} keys"
            else:
                yield "{*}", "lookup", f"{len(val)} keys"
            return
        for k, v in val.items():
            yield k, type(v).__name__, _brief(v)
    elif isinstance(val, list):
        # A list of records: its fields are the union of its rows' keys.
        keys = []
        for r in val:
            if isinstance(r, dict):
                for k in r:
                    if k not in keys:
                        keys.append(k)
        if keys:
            for k in keys:
                yield f"[].{k}", "column", f"{len(val)} rows"
        else:
            yield "[]", type(val).__name__, f"{len(val)} items"


def _brief(v):
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return v[:40]
    if isinstance(v, list):
        return f"list[{len(v)}]"
    if isinstance(v, dict):
        return "{" + ", ".join(list(v)[:4]) + ("…}" if len(v) > 4 else "}")
    return str(v)[:40]


def main():
    from generator_registry import GENERATORS, resolve
    rows, missing = [], []
    for name, line, val in objects():
        if name in FURNITURE:
            continue
        for f, kind, brief in fields(name, val):
            gen = resolve(name, f)
            rows.append({"object": name, "field": f, "kind": kind,
                         "value": brief, "generator": gen})
            if gen is None:
                missing.append((name, f, brief))
    if "--json" in sys.argv:
        print(json.dumps({"fields": rows, "missing": len(missing)}, indent=1))
        return 0
    w = max(len(r["object"]) + len(r["field"]) for r in rows) + 2
    print(f'{"FIELD".ljust(w)} {"VALUE".ljust(26)} GENERATOR')
    for r in rows:
        key = f'{r["object"]}.{r["field"]}'
        print(f'{key.ljust(w)} {str(r["value"])[:25].ljust(26)} '
              f'{r["generator"] or "** NO GENERATOR **"}')
    print(f"\n{len(rows)} fields, {len(missing)} with no generator")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())
