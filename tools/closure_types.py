# -*- coding: utf-8 -*-
"""How each action gets closed, and which ones nobody is watching.

Every live action is one of three closure types:

  auto      closes on a condition the build evaluates every run - an mWater
            count, the form snapshot, a repo file, or its child steps
            (kinds data, form, artefact in the repo, children). The date the
            build first saw it closed is recorded.
  evidence  closes when a named document, email reply or file exists: a
            written answer logged in data/decisions.json, or a document in a
            SharePoint folder the build does not list itself.
  manual    closes only when Adriaan (or Claude on his instruction) marks it
            done - field work, standing rules and his own calls, which no
            system we read records.

The type and a plain-words "closes when" come from data/action_conditions.json
(the build's condition for auto; the classified sentence for evidence and
manual). The result is written into data/action_owners.json under "closure",
beside - never inside - the owner and deadline rows the workbook supplies.

first_seen is when the action first appeared in the repository, from git
history the first time it is seen and kept after that; the "Needs a nudge"
line at the top of the action list uses it for undated items.

    python3 tools/closure_types.py --write
    python3 tools/closure_types.py --check
"""
import datetime, json, os, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OWNERS = os.path.join(REPO, "data", "action_owners.json")
AUTO_KINDS = {"data", "form", "children"}
TYPES = ("auto", "evidence", "manual")


def load(name):
    return json.load(open(os.path.join(REPO, "data", name), encoding="utf8"))


def closure_type(c):
    if c["kind"] in AUTO_KINDS or (c["kind"] == "artefact" and c.get("where") == "repo"):
        return "auto"
    return c.get("closure")


def first_seen(aid):
    r = subprocess.run(["git", "log", "--reverse", "--format=%ad", "--date=short",
                        f"-S{aid}", "--", "index.html", "data/action_details.json"],
                       capture_output=True, text=True, cwd=REPO)
    dates = r.stdout.split()
    return dates[0] if dates else datetime.date.today().isoformat()


def build():
    det, conds = load("action_details.json"), load("action_conditions.json")
    state = load("action_state.json").get("state", {})
    doc = load("action_owners.json")
    prev = doc.get("closure", {}).get("actions", {})
    rows, problems = {}, []
    for aid in sorted(det):
        c = conds.get(aid)
        if not c:
            problems.append(f"{aid}: no closing condition"); continue
        t = closure_type(c)
        if t not in TYPES:
            problems.append(f"{aid}: kind {c['kind']} has no closure type"); continue
        s = state.get(aid, {})
        rows[aid] = {"type": t,
                     "closes_when": c.get("says") if t == "auto" else c.get("closes_when"),
                     "closed": bool(s.get("satisfied")),
                     "detected_closed_on": s.get("closed_since") if t == "auto" else None,
                     "first_seen": (prev.get(aid) or {}).get("first_seen") or first_seen(aid)}
        if not rows[aid]["closes_when"]:
            problems.append(f"{aid}: no 'closes when' sentence")
    counts = {t: sum(1 for r in rows.values() if r["type"] == t) for t in TYPES}
    return {"note": "Written by tools/closure_types.py from data/action_conditions.json and "
                    "data/action_state.json. Not part of the workbook: owner and deadline "
                    "stay in 'owners'.",
            "counts": counts, "actions": rows}, problems


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    block, problems = build()
    if problems:
        print("closure_types: REFUSED - " + "; ".join(problems[:6]))
        return 1
    doc = load("action_owners.json")
    same = doc.get("closure") == block
    if same:
        print("data/action_owners.json closure block unchanged")
        return 0
    if mode != "--write":
        print("data/action_owners.json closure block DIFFERS")
        return 1
    doc["closure"] = block
    open(OWNERS, "w", encoding="utf8").write(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    print("closure types: " + ", ".join(f"{k} {v}" for k, v in block["counts"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
