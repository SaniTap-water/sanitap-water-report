# -*- coding: utf-8 -*-
"""Decide, every build, which actions are still open.

The division of labour this implements: the MACHINE decides whether an item is
open; PEOPLE decide only who owns it and by when. An item with a stored closing
condition is not marked done by hand - the build evaluates the condition, and
the item closes itself when the condition is met and REOPENS when it regresses.

Five kinds of condition:

  data      a count the build recounts (tools/action_metrics.py). Closes when
            the count reaches its threshold - usually zero.
  form      a predicate over the mWater form snapshot the build already takes:
            the question exists, it is required, the condition is set, the
            locale is present.
  artefact  a document, template or plan exists at a stated location, checked
            by path and version in the repo or on SharePoint.
  decision  a person has to answer a question. No data predicate exists. It
            closes only on an entry in data/decisions.json carrying the answer,
            the date and the source. An email is never enough - a candidate
            answer found in the mail thread is surfaced on the row for
            confirmation and closes nothing.
  children  a parent action: closes only when every child listed has closed,
            and reopens with any of them.

Items with no condition are reported as such: that count is the measure of how
much of this list still needs a human to close it.

    python3 tools/eval_conditions.py --write
    python3 tools/eval_conditions.py --show
"""
import datetime, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "action_state.json")
OPS = {"==": lambda a, b: a == b, "<=": lambda a, b: a <= b,
       ">=": lambda a, b: a >= b, "<": lambda a, b: a < b,
       ">": lambda a, b: a > b, "!=": lambda a, b: a != b}


def d(*p):
    return os.path.join(REPO, *p)


def load(name, default=None):
    p = d("data", name)
    return json.load(open(p)) if os.path.isfile(p) else (default or {})


# --------------------------------------------------------------- kinds ----
def eval_data(c, metrics):
    m = metrics.get(c["metric"])
    if not m or m.get("value") is None:
        return None, f'{c["metric"]} could not be counted this build'
    v = m["value"]
    ok = OPS[c["op"]](v, c["target"])
    return ok, f'{c["metric"]} = {v} ({m["says"]}); target {c["op"]} {c["target"]}'


def eval_form(c, snap):
    # an action that asks for the same change on two forms is not done when
    # one of them has it: "all" holds a list of {form, predicate} and every
    # one of them must hold
    if "all" in c:
        evs, res = [], []
        for part in c["all"]:
            ok, ev = eval_form(part, snap)
            res.append(ok)
            evs.append(ev)
        if None in res:
            return None, "; ".join(evs)
        return all(res), "; ".join(evs)
    f = snap.get("forms", {}).get(c["form"])
    if not f:
        return None, f'no snapshot for form {c["form"]}'
    p = c["predicate"]
    if "locale" in p:
        ok = p["locale"] in (f.get("locales") or [])
        return ok, (f'{c["form"]} locales = {", ".join(f.get("locales") or []) or "none"}; '
                    f'needs {p["locale"]}')
    qs = f.get("questions") or []
    if "code" in p:
        hit = [q for q in qs if (q.get("code") or "") == p["code"]]
        what = f'question code {p["code"]}'
    else:
        needle = p["text"].lower()
        hit = [q for q in qs
               if needle in ((q.get("en") or "") + " " + (q.get("fr") or "")).lower()]
        what = f'a question mentioning "{p["text"]}"'
    if not hit:
        return False, f'{what} is not on the {c["form"]} form'
    q = hit[0]
    if p.get("required") and not q.get("required"):
        return False, f'{what} is on the form but is not required'
    if p.get("has_condition") and not q.get("conditions"):
        return False, f'{what} is on the form but carries no condition'
    bits = [what + " is on the form"]
    if p.get("required"):
        bits.append("and required")
    if p.get("has_condition"):
        bits.append("and conditional")
    return True, " ".join(bits)


def eval_artefact(c, sp):
    if c["where"] == "repo":
        p = d(c["path"])
        return os.path.exists(p), (f'{c["path"]} {"exists" if os.path.exists(p) else "does not exist"} '
                                   "in the repository")
    listing = sp.get(c.get("folder") or "", None)
    if listing is None:
        return None, (f'SharePoint folder "{c.get("folder")}" has not been listed '
                      "this build")
    needle = (c.get("name_contains") or "").lower()
    hits = [n for n in listing if needle in n.lower()]
    if not hits:
        return False, f'nothing matching "{c.get("name_contains")}" in {c.get("folder")}'
    if c.get("version"):
        vh = [n for n in hits if c["version"].lower() in n.lower()]
        if not vh:
            return False, (f'{hits[0]} is in {c.get("folder")} but not at '
                           f'{c["version"]}')
        return True, f'{vh[0]} is in {c.get("folder")}'
    return True, f'{hits[0]} is in {c.get("folder")}'


def eval_decision(aid, c, decisions, candidates):
    got = decisions.get("decisions", {}).get(aid)
    if got:
        return True, (f'decided {got["decided_on"]} by {got["decided_by"]}: '
                      f'{got["answer"]}')
    cand = candidates.get(aid)
    if cand:
        return False, (f'possible answer received &mdash; confirm to close: '
                       f'{cand["summary"]}')
    return False, "no answer logged"


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--show"
    if mode == "--show":
        print(json.dumps(load("action_state.json"), indent=1, sort_keys=True))
        return 0
    if mode != "--write":
        sys.exit("usage: eval_conditions.py --write | --show")
    conds = load("action_conditions.json")
    metrics = load("action_metrics.json").get("metrics", {})
    snap = load("mwater_form_snapshot.json")
    sp = load("sharepoint_listing.json")
    decisions = load("decisions.json")
    cands = load("decision_candidates.json").get("candidates", {})
    prev = load("action_state.json").get("state", {})
    today = datetime.date.today().isoformat()

    state, counts = {}, {"data": 0, "form": 0, "artefact": 0, "decision": 0,
                         "none": 0,
                         "children": 0}
    for aid, c in sorted(conds.items()):
        kind = c["kind"]
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "data":
            ok, ev = eval_data(c, metrics)
        elif kind == "form":
            ok, ev = eval_form(c, snap)
        elif kind == "artefact":
            ok, ev = eval_artefact(c, sp)
        elif kind == "decision":
            ok, ev = eval_decision(aid, c, decisions, cands)
        elif kind == "children":
            continue                  # needs its children's verdicts: below
        else:
            ok, ev = None, c.get("says", "")
        was = prev.get(aid, {})
        rec = {"kind": kind, "says": c.get("says", ""), "satisfied": ok,
               "evidence": ev, "evaluated": today,
               "when_satisfied": c.get("when_satisfied", "OK")}
        if ok:
            rec["closed_since"] = (was.get("closed_since")
                                   if was.get("satisfied") else today)
        elif was.get("satisfied"):
            rec["reopened_on"] = today
            rec["was_closed_since"] = was.get("closed_since")
        state[aid] = rec
    # A parent closes only when every one of its children has closed, and
    # reopens with any of them. Its children are ordinary actions with their
    # own conditions; the parent adds no predicate of its own.
    for aid, c in sorted(conds.items()):
        if c["kind"] != "children":
            continue
        kids = [(k, state.get(k, {}).get("satisfied")) for k in c["children"]]
        missing = [k for k in c["children"] if k not in state]
        done = sum(1 for _k, s in kids if s)
        ok = False if missing else all(s for _k, s in kids)
        ev = (f"{done} of {len(kids)} steps closed"
              + (f"; no condition for {', '.join(missing)}" if missing else ""))
        was = prev.get(aid, {})
        rec = {"kind": "children", "says": c.get("says", ""), "satisfied": ok,
               "evidence": ev, "evaluated": today, "children": c["children"],
               "children_closed": done,
               "when_satisfied": c.get("when_satisfied", "OK")}
        if ok:
            rec["closed_since"] = (was.get("closed_since")
                                   if was.get("satisfied") else today)
        elif was.get("satisfied"):
            rec["reopened_on"] = today
            rec["was_closed_since"] = was.get("closed_since")
        state[aid] = rec
    doc = {"evaluated": today, "state": state, "kinds": counts}
    json.dump(doc, open(OUT, "w"), indent=1, sort_keys=True)
    sat = sum(1 for v in state.values() if v["satisfied"])
    unk = sum(1 for v in state.values() if v["satisfied"] is None)
    reop = [a for a, v in state.items() if "reopened_on" in v]
    print(f"{len(state)} conditions: {sat} satisfied, "
          f"{len(state) - sat - unk} not met, {unk} not evaluable")
    print("kinds:", {k: v for k, v in counts.items() if v})
    if reop:
        print("REOPENED:", ", ".join(reop))
    for a, v in sorted(state.items()):
        if v["satisfied"]:
            print(f"  CLOSED  {a:44s} {v['evidence'][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
