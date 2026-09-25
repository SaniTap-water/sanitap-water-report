# -*- coding: utf-8 -*-
"""Write the Endur'O block into index.html from its dated manual file.

WHY THIS EXISTS
---------------
Endur'O is not on mWater, so its figures cannot be derived from an extract.
That is a fact about the programme. What is not acceptable is those figures
ageing silently: fifteen numbers sat inline in index.html with no date, no
owner and no document behind them, indistinguishable from figures that
refresh themselves every build.

They now live in data/enduro_manual.json with an as_at date, the person who
supplied them and the document they came from, and this writes them into the
page. The page states "as at <date>, supplied by <name>" wherever an Endur'O
figure appears, and says so loudly once the block is older than the file's
own max_age_days.

    python3 tools/render_enduro.py --write
    python3 tools/render_enduro.py --check
"""
import datetime, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# a region that differs only in prerendered figure values is not drift
from prerender_figures import same as _same  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
SRC = os.path.join(REPO, "data", "enduro_manual.json")
BEGIN = ("/* BEGIN GENERATED enduro :: tools/render_enduro.py :: "
         "do not edit between these markers */")
END = "/* END GENERATED enduro */"


def load():
    return json.load(open(SRC, encoding="utf8"))


def age_days(m, today=None):
    today = today or datetime.date.today()
    return (today - datetime.date.fromisoformat(m["as_at"])).days


def block(m=None, today=None):
    m = m or load()
    reg = {k: v for k, v in m["register"].items() if not k.startswith("_")
           and isinstance(v, int)}
    con = {k: v for k, v in m["contract"].items() if not k.startswith("_")
           and isinstance(v, int)}
    reg.update(con)
    age = age_days(m, today)
    stale = age > m["max_age_days"]
    body = {
        "systems": m["figures"]["systems"]["v"],
        "people": m["figures"]["people"]["v"],
        "reg": reg,
    }
    js = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    prov = {
        "as_at": m["as_at"],
        "by": m["supplied_by"],
        "doc": m["doc"],
        "age": age,
        "max": m["max_age_days"],
        "stale": stale,
        "people_as_at": m["figures"]["people"]["as_at"],
        "people_by": m["figures"]["people"]["supplied_by"],
        "reg_as_at": m["register"]["as_at"],
    }
    return (
        f"{BEGIN}\n"
        "// Hand-entered. Source, owner and date: data/enduro_manual.json\n"
        f"const ENDURO={js};\n"
        f"const ENDURO_SRC={json.dumps(prov, ensure_ascii=False)};\n"
        "// One line, used wherever an Endur'O figure is shown, so a reader\n"
        "// never meets one of these numbers without its date and its owner.\n"
        "const enduroAsAt=()=>`<span class=\"muted\" data-manual=\"enduro\">"
        "as at ${ENDURO_SRC.as_at}, supplied by ${ENDURO_SRC.by}"
        "${ENDURO_SRC.stale?` &mdash; <b class=\"warn\">${ENDURO_SRC.age} days "
        "old, past the ${ENDURO_SRC.max}-day limit; these figures need "
        "re-confirming</b>`:''}</span>`;\n"
        f"{END}"
    )


def apply(write):
    page = open(PAGE, encoding="utf8").read()
    new = block()
    if BEGIN in page:
        i, j = page.index(BEGIN), page.index(END) + len(END)
        cur = page[i:j]
    else:                                   # first run: replace the inline const
        m = re.search(r"^const ENDURO=\{.*?\};\s*$", page, re.M)
        if not m:
            sys.exit("render_enduro: cannot find the ENDURO block to replace")
        i, j, cur = m.start(), m.end(), m.group(0)
    if _same(cur, new):
        print("index.html Endur'O block matches its generator")
        return 0
    if not write:
        print("index.html Endur'O block DIFFERS from its generator")
        return 1
    open(PAGE, "w", encoding="utf8").write(page[:i] + new + page[j:])
    m = load()
    print(f"index.html Endur'O block rewritten - as at {m['as_at']}, "
          f"{age_days(m)} day(s) old, limit {m['max_age_days']}")
    return 0


if __name__ == "__main__":
    sys.exit(apply("--write" in sys.argv))
