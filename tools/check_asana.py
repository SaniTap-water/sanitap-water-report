#!/usr/bin/env python3
"""The action list agrees with Asana and with the evidence record (2 Oct 2026).

Reads the rendered action list in index.html (each main-list row carries
data-act, data-owner, data-due, data-asana, data-evidence, data-auto), the
local copy of the Asana read (data/asana_pull.json), the map
(data/asana_map.json) and the build's condition state. Fails when:

  1. an open action (ACT or WATCH) does not have exactly one Asana task:
     none in the pull, or two tasks naming the same act-id;
  2. the owner or the deadline on the page differs from the task's;
  3. an action is closed (OK) on the page without recorded evidence: neither a
     build condition that is satisfied this run nor an entry in
     data/action_owners.json "evidence";
  4. the map and the pull name different tasks for the same act-id.

Shown failing on 2 Oct 2026 by changing one task's due date in the local copy
of the pull (not in Asana): see docs/decision_log.md.

    python3 tools/check_asana.py
"""
import json, os, re, sys, html

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    idx = open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    pull = json.load(open(os.path.join(REPO, "data", "asana_pull.json"), encoding="utf8"))
    amap = json.load(open(os.path.join(REPO, "data", "asana_map.json"), encoding="utf8"))["tasks"]
    state = json.load(open(os.path.join(REPO, "data", "action_state.json"), encoding="utf8")).get("state", {})
    evid = (json.load(open(os.path.join(REPO, "data", "action_owners.json"), encoding="utf8"))
            .get("evidence") or {}).get("actions", {})
    tasks, dups = pull.get("tasks", {}), pull.get("duplicates", {})
    rows = {}
    for m in re.finditer(r'<tr data-state="(\w+)"[^>]*?data-act="([^"]+)"([^>]*)>', idx):
        attrs = m.group(3)
        get = lambda k: (re.search(k + r'="([^"]*)"', m.group(0)) or [None, None])[1]
        rows.setdefault(m.group(2), dict(state=m.group(1), owner=html.unescape(get("data-owner") or ""),
                                         due=get("data-due") or "", asana=get("data-asana"),
                                         evidence="data-evidence" in attrs, auto="data-auto" in attrs))
    fails = []
    for aid, r in sorted(rows.items()):
        t = tasks.get(aid)
        if r["state"] in ("ACT", "WATCH"):
            if not t:
                fails.append(f"{aid}: open on the page, no Asana task")
                continue
            if aid in dups:
                fails.append(f"{aid}: {len(dups[aid])} Asana tasks name it")
        if t:
            if r["owner"] != t["owner"]:
                fails.append(f"{aid}: owner on the page {r['owner']!r}, in Asana {t['owner']!r}")
            if r["due"] != (t.get("due_on") or ""):
                fails.append(f"{aid}: deadline on the page {r['due'] or 'none'}, in Asana {t.get('due_on') or 'none'}")
            if amap.get(aid) and amap[aid] != t["gid"]:
                fails.append(f"{aid}: map names task {amap[aid]}, the pull {t['gid']}")
        if r["state"] == "OK":
            built = r["auto"] and (state.get(aid) or {}).get("satisfied") is True
            if not (built or (r["evidence"] and aid in evid)):
                fails.append(f"{aid}: closed on the page without recorded evidence")
    n_open = sum(1 for r in rows.values() if r["state"] in ("ACT", "WATCH"))
    print(f"  asana: {len(rows)} actions on the page, {n_open} open, {len(tasks)} Asana tasks; {len(fails)} failure(s)")
    for f in fails[:30]:
        print("   ", f)
    for n in pull.get("new_from_asana", []):
        print(f"    new from Asana (no detail on the page yet): {n['act_id']} \"{n['name']}\"")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
