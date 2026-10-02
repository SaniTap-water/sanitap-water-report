#!/usr/bin/env python3
"""Put the report's open actions into Asana (2 Oct 2026). The ONLY script that
writes to Asana; every build reads it read-only (tools/asana_pull.py).

Project "H2O4CO2 - CLEAN WATER" (1209455787942089):
  1. adds Angelo NAHAVITATSARA (1207774235226712) as a member if he is not one;
  2. creates the section "Weekly report actions" if it does not exist;
  3. creates one task per OPEN action on the report (state ACT or WATCH, as
     tools/render_actions.py computes it), named "<act-id> — <title>", due on the
     deadline, assigned to the owner when the owner is an Asana user in the
     workspace and to Adriaan otherwise, with a description that starts
     "Owner: <name> (not in Asana)" in that case and gives the closes-when, type,
     source, dependencies and a link to the action on the live report;
  4. completes the tasks of actions named with --complete.

Idempotent: data/asana_map.json maps act-id to task gid, and a task already in
the section whose name starts with the act-id is adopted rather than
duplicated. Re-running creates nothing twice.

    python3 tools/asana_setup.py --dry-run
    python3 tools/asana_setup.py --write [--complete act-a act-b ...]
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asana_api as A  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(REPO, "data", "asana_map.json")
ANGELO = "1207774235226712"
ADRIAAN = "1132514258683237"
# owner (first name on the report) -> Asana user gid, workspace sanitap.org.
# Coddy and Ntsoa have workspace accounts but are treated as not in Asana, as
# instructed on 2 Oct 2026; Ralf, Endur'O, MadAvance and Gold Standard are not users.
PEOPLE = {"jan": ("1209565438602753", "Jan de Graaf"),
          "angelo": (ANGELO, "Angelo Nahavitatsara"),
          "lanja": ("1206894470435125", "Lanja Randriamanantena"),
          "cathy": ("1208683882004265", "Cathy Andriambololonirina"),
          "james": ("1213895542888866", "James Walker"),
          "amede": ("1210706024318014", "Amédé Rafidimanantsoa"),
          "amédé": ("1210706024318014", "Amédé Rafidimanantsoa"),
          "adriaan": (ADRIAAN, "Adriaan Mol")}
NAME_OF = {gid: name for gid, name in PEOPLE.values()}


def match_owner(owner):
    """-> (assignee gid, canonical name or None, owner text when not in Asana)."""
    o = (owner or "").strip()
    first = re.sub(r"[^a-zé]", "", o.split()[0].lower()) if o.split() else ""
    if first in PEOPLE:
        gid, name = PEOPLE[first]
        return gid, name, None
    return ADRIAAN, None, (o if o and o not in ("—", "&mdash;") else "none set")


def notes_for(a, info):
    lines = []
    if info["not_in_asana"]:
        lines.append(f"Owner: {info['not_in_asana']} (not in Asana)")
        lines.append("")
    lines.append(f"Closes when: {info['closes_when']}")
    lines.append(f"Type: {info['type']}")
    lines.append(f"Source: {info['source']}")
    lines.append(f"Depends on: {info['depends']}")
    lines.append(f"On the report: {A.REPORT_URL}#{a['id']}")
    if info["owner_text"] and not info["not_in_asana"] and info["owner_text"] != info["assignee_name"]:
        lines.append(f"Owner as written on the report: {info['owner_text']}")
    lines.append("")
    lines.append("Owner, due date and completion are read from this task by the weekly report build. "
                 "Completing it closes the action on the report only once its evidence is recorded.")
    return "\n".join(lines)


def action_info():
    import render_actions as R
    idx = open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    acts = R.actions(idx, use_asana=False)
    own = json.load(open(os.path.join(REPO, "data", "action_owners.json"), encoding="utf8"))
    con = json.load(open(os.path.join(REPO, "data", "action_conditions.json"), encoding="utf8"))
    clos = own.get("closure", {}).get("actions", {})
    srcs = own.get("sources", {}).get("actions", {})
    parent = {k: p for p, c in con.items() for k in (c.get("children") or [])}
    out = {}
    for a in acts:
        rec = own["owners"].get(a["id"], {})
        owner_text = rec.get("owner") or a["owner"]
        gid, name, not_in = match_owner(owner_text)
        c = con.get(a["id"], {})
        cl = clos.get(a["id"], {})
        src = rec.get("source")
        if not src and srcs.get(a["id"]):
            s = srcs[a["id"]][-1]
            src = f"{s['sender']}, \"{s['subject']}\", {s['date']}"
        dep = list(filter(None, [rec.get("depends_on"), parent.get(a["id"]) and f"part of {parent[a['id']]}"]))
        out[a["id"]] = dict(
            act=a, state=a["state"], title=a["title"], deadline=rec.get("deadline"),
            assignee=gid, assignee_name=name or NAME_OF[gid], not_in_asana=not_in, owner_text=owner_text,
            closes_when=cl.get("closes_when") or c.get("closes_when") or c.get("says") or "not stated",
            type=cl.get("type") or c.get("closure") or c.get("kind") or "not stated",
            source=src or "the report's action record (data/action_details.json)",
            depends=", ".join(dep) or "—")
    return out


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--write", action="store_true")
    ap.add_argument("--complete", nargs="*", default=[])
    a = ap.parse_args()
    info = action_info()
    open_ids = [k for k, v in info.items() if v["state"] in ("ACT", "WATCH")]
    want = sorted(set(open_ids) | set(a.complete))
    amap = json.load(open(MAP, encoding="utf8")) if os.path.isfile(MAP) else {
        "note": "act-id -> Asana task gid in the section 'Weekly report actions' of the project "
                "'H2O4CO2 - CLEAN WATER'. Written by tools/asana_setup.py (creation) and "
                "tools/asana_pull.py (tasks added by hand in Asana).",
        "project": A.PROJECT, "section": None, "tasks": {}}

    proj = A.get(f"/projects/{A.PROJECT}", {"opt_fields": "members.gid"})
    members = {m["gid"] for m in proj["members"]}
    secs = {s["name"]: s["gid"] for s in A.get(f"/projects/{A.PROJECT}/sections", {"opt_fields": "name"})}
    existing = {}
    if A.SECTION_NAME in secs:
        for t in A.get(f"/sections/{secs[A.SECTION_NAME]}/tasks", {"opt_fields": "name,completed"}):
            m = re.match(r"(act-[a-z0-9-]+)\s", t["name"])
            if m:
                existing.setdefault(m.group(1), []).append(t["gid"])
    todo = [k for k in want if k not in amap["tasks"] and k not in existing]
    print(f"open actions {len(open_ids)}; already mapped {sum(1 for k in want if k in amap['tasks'])}; "
          f"adopted from the section {sum(1 for k in want if k in existing and k not in amap['tasks'])}; to create {len(todo)}")
    print(f"Angelo a member: {ANGELO in members}; section exists: {A.SECTION_NAME in secs}")
    adriaan = sorted(k for k in want if info.get(k, {}).get("not_in_asana"))
    print(f"assigned to Adriaan because the owner is not in Asana: {len(adriaan)}")
    if a.dry_run:
        for k in todo[:8]:
            v = info[k]
            print(f"  would create: {k} — {v['title'][:70]} | {v['assignee_name']} | due {v['deadline']}")
        return 0

    if ANGELO not in members:
        A.post(f"/projects/{A.PROJECT}/addMembers", {"members": [ANGELO]})
        print("  added Angelo NAHAVITATSARA as a project member")
    if A.SECTION_NAME not in secs:
        s = A.post(f"/projects/{A.PROJECT}/sections", {"name": A.SECTION_NAME})
        secs[A.SECTION_NAME] = s["gid"]
        print(f"  created section {A.SECTION_NAME!r} ({s['gid']})")
    amap["section"] = secs[A.SECTION_NAME]
    for k, gids in existing.items():
        if k in want and k not in amap["tasks"]:
            amap["tasks"][k] = gids[0]
    created = []
    for k in todo:
        v = info[k]
        body = {"name": f"{k} — {v['title']}"[:1000], "projects": [A.PROJECT],
                "memberships": [{"project": A.PROJECT, "section": amap["section"]}],
                "assignee": v["assignee"], "notes": notes_for(v["act"], v)}
        if v["deadline"]:
            body["due_on"] = v["deadline"]
        t = A.post("/tasks", body)
        amap["tasks"][k] = t["gid"]
        created.append(k)
        json.dump(amap, open(MAP, "w", encoding="utf8"), indent=1, ensure_ascii=False)   # after every task
    for k in a.complete:
        A.put(f"/tasks/{amap['tasks'][k]}", {"completed": True})
        print(f"  completed {k}")
    amap["tasks"] = dict(sorted(amap["tasks"].items()))
    json.dump(amap, open(MAP, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    open(MAP, "a").write("\n")
    print(f"  created {len(created)} task(s); map -> {os.path.relpath(MAP, REPO)}")
    print("  assigned to Adriaan (owner not in Asana): " + ", ".join(adriaan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
