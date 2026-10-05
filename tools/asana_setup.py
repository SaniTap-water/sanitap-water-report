#!/usr/bin/env python3
"""Put the report's open actions into Asana (2 Oct 2026). The ONLY script that
writes to Asana; every build reads it read-only (tools/asana_pull.py).

Project "H2O4CO2 - CLEAN WATER" (1209455787942089):
  1. adds Angelo NAHAVITATSARA, Coddy Velonizy and Ntsoa Ranaivoson as members
     if they are not;
  2. creates the section "Weekly report actions" if it does not exist;
  3. creates one task per OPEN action on the report (state ACT or WATCH, as
     tools/render_actions.py computes it), named "<plain title> [act-id]" (the
     title from data/action_owners.json; first named "<act-id> — <title>", and
     renamed on the next run unless its owner has renamed it), due on the
     deadline, assigned to the owner when the owner is an Asana user in the
     workspace and to Adriaan otherwise, with a description that starts
     "Owner: <name> (not in Asana)" in that case and gives the closes-when, type,
     source, dependencies and a link to the action on the live report;
  4. reassigns tasks held by Adriaan for an owner "not in Asana" who now is
     (Coddy, Ntsoa, Endur'O), removing that first description line;
  5. completes the tasks of actions named with --complete;
  6. --retitle renames named tasks to their title in data/action_owners.json,
     and --section-top moves the section above the project's first section.

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
# Coddy Velonizy ("IT Assistant", coddy@madavance.org) and Ntsoa Ranaivoson
# (Endur'O director) added 2 Oct 2026 (second pass). An owner "Endur'O" with a
# person in brackets is that person; "Endur'O" with no person named is assigned
# to Coddy and keeps "Owner: Endur'O" as the first line of the description.
# An owner "MadAvance" (field teams, transcriber to be named) is Angelo, and
# "MadAvance / Cathy" is Cathy (third pass, same day). Ralf van Veenendaal
# (Curtech) and Gold Standard are not users: assigned to Adriaan.
CODDY = "1209012876322233"
NTSOA = "1211301105253477"
PEOPLE = {"jan": ("1209565438602753", "Jan de Graaf"),
          "angelo": (ANGELO, "Angelo Nahavitatsara"),
          "lanja": ("1206894470435125", "Lanja Randriamanantena"),
          "cathy": ("1208683882004265", "Cathy Andriambololonirina"),
          "james": ("1213895542888866", "James Walker"),
          "amede": ("1210706024318014", "Amédé Rafidimanantsoa"),
          "amédé": ("1210706024318014", "Amédé Rafidimanantsoa"),
          "adriaan": (ADRIAAN, "Adriaan Mol"),
          "coddy": (CODDY, "Coddy Velonizy"),
          "ntsoa": (NTSOA, "Ntsoa Ranaivoson")}
NAME_OF = {gid: name for gid, name in PEOPLE.values()}
MEMBERS = [ANGELO, CODDY, NTSOA]
ENDURO_LINE = "Owner: Endur'O"


def _first(word):
    return re.sub(r"[^a-zé]", "", word.lower())


def match_owner(owner):
    """-> (assignee gid, canonical name or None, owner text when not in Asana,
    first description line or None)."""
    o = (owner or "").strip()
    first = _first(o.split()[0]) if o.split() else ""
    if first in PEOPLE:
        gid, name = PEOPLE[first]
        return gid, name, None, None
    if first == "madavance":
        # (2 Oct 2026, third pass) "MadAvance / Cathy" is Cathy; "MadAvance",
        # "MadAvance field teams" and "MadAvance — transcriber to be named" are Angelo
        if re.search(r"/\s*Cathy\b", o):
            gid, name = PEOPLE["cathy"]
        else:
            gid, name = PEOPLE["angelo"]
        return gid, name, None, None
    if first == "enduro":
        inner = re.match(r"^\S+\s*\(([^)]*)\)", o)
        for w in (re.split(r"[\s,/]+", inner.group(1)) if inner else []):
            if _first(w) in PEOPLE:
                gid, name = PEOPLE[_first(w)]
                return gid, name, None, None
        return CODDY, PEOPLE["coddy"][1], None, ENDURO_LINE
    return ADRIAAN, None, (o if o and o not in ("—", "&mdash;") else "none set"), None


def notes_for(a, info):
    lines = []
    if info.get("first_line"):
        lines.append(info["first_line"])
        lines.append("")
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
                 "Ticking it complete does not close the action on its own: add a comment starting "
                 "\"Evidence:\" saying what shows it is done, or attach the file.")
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
        gid, name, not_in, first_line = match_owner(owner_text)
        c = con.get(a["id"], {})
        cl = clos.get(a["id"], {})
        src = rec.get("source")
        if not src and srcs.get(a["id"]):
            s = srcs[a["id"]][-1]
            src = f"{s['sender']}, \"{s['subject']}\", {s['date']}"
        dep = list(filter(None, [rec.get("depends_on"), parent.get(a["id"]) and f"part of {parent[a['id']]}"]))
        out[a["id"]] = dict(
            act=a, state=a["state"], title=rec.get("title") or a["title"], deadline=rec.get("deadline"),
            assignee=gid, assignee_name=name or NAME_OF[gid], not_in_asana=not_in, owner_text=owner_text,
            first_line=first_line,
            closes_when=cl.get("closes_when") or c.get("closes_when") or c.get("says") or "not stated",
            type=cl.get("type") or c.get("closure") or c.get("kind") or "not stated",
            source=src or "the report's action record (data/action_details.json)",
            depends=", ".join(dep) or "—")
    return out


TAG = re.compile(r"\[(act-[a-z0-9-]+)\]\s*$")
OLD_PREFIX = re.compile(r"^(act-[a-z0-9-]+)\s+\u2014\s")


def task_name(title, aid):
    """The task name: the plain title, then the act-id tag (2 Oct 2026)."""
    return f"{title} [{aid}]"[:1000]


def tag_of(name):
    """The act-id a task name carries: the trailing [act-id] tag, or the
    "<act-id> — <title>" prefix of the first naming. Matching is by task gid
    (data/asana_map.json); the tag is for people reading the list."""
    m = TAG.search(name or "") or OLD_PREFIX.match(name or "")
    return m.group(1) if m else None


def plan_rename(section, amap, info):
    """Tasks still named "<act-id> — <old title>" get "<plain title> [act-id]".
    A task its owner has renamed keeps the owner's wording (the build copies it
    into data/action_owners.json "title"); only a missing tag is added back."""
    if not section:
        return []
    by_gid = {g: k for k, g in amap["tasks"].items()}
    out = []
    for t in A.get(f"/sections/{section}/tasks", {"opt_fields": "name"}):
        aid = by_gid.get(t["gid"])
        if not aid:
            continue
        name = t["name"]
        if OLD_PREFIX.match(name):
            if aid in info:
                out.append((t["gid"], aid, task_name(info[aid]["title"], aid)))
        elif not TAG.search(name):
            out.append((t["gid"], aid, task_name(name.strip(), aid)))
    return out


NOT_IN_LINE = re.compile(r"^\s*Owner:\s*(.+?)\s*\(not in Asana\)\s*$")


def plan_reassign(section):
    """Tasks assigned to Adriaan whose description starts "Owner: <x> (not in
    Asana)" where <x> is now an Asana user (or Endur'O): reassign, drop that
    first line (Endur'O with no person keeps "Owner: Endur'O"), and keep the
    owner as written on the report further down."""
    if not section:
        return []
    out = []
    for t in A.get(f"/sections/{section}/tasks", {"opt_fields": "name,assignee.gid,notes,completed"}):
        if (t.get("assignee") or {}).get("gid") != ADRIAAN:
            continue
        lines = (t.get("notes") or "").split("\n")
        m = NOT_IN_LINE.match(lines[0]) if lines else None
        if not m:
            continue
        gid, name, not_in, first_line = match_owner(m.group(1))
        if gid == ADRIAAN:
            continue
        rest = lines[1:]
        while rest and not rest[0].strip():
            rest = rest[1:]
        written = f"Owner as written on the report: {m.group(1)}"
        if written not in rest:
            i = next((j + 1 for j, l in enumerate(rest) if l.startswith("On the report: ")), len(rest))
            rest = rest[:i] + [written] + rest[i:]
        notes = "\n".join(([first_line, ""] if first_line else []) + rest)
        aid = tag_of(t["name"]) or t["gid"]
        out.append((t["gid"], aid, m.group(1), gid, notes))
    return out


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--write", action="store_true")
    ap.add_argument("--complete", nargs="*", default=[])
    ap.add_argument("--retitle", nargs="*", default=[],
                    help="rename these act-ids' tasks to '<title> [act-id]' from data/action_owners.json")
    ap.add_argument("--section-top", action="store_true",
                    help="move the section 'Weekly report actions' above the project's first section")
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
            k = tag_of(t["name"])
            if k:
                existing.setdefault(k, []).append(t["gid"])
    todo = [k for k in want if k not in amap["tasks"] and k not in existing]
    print(f"open actions {len(open_ids)}; already mapped {sum(1 for k in want if k in amap['tasks'])}; "
          f"adopted from the section {sum(1 for k in want if k in existing and k not in amap['tasks'])}; to create {len(todo)}")
    print("members: " + ", ".join(f"{NAME_OF[g]} {g in members}" for g in MEMBERS)
          + f"; section exists: {A.SECTION_NAME in secs}")
    adriaan = sorted(k for k in want if info.get(k, {}).get("not_in_asana"))
    print(f"assigned to Adriaan because the owner is not in Asana: {len(adriaan)}")
    renames = plan_rename(secs.get(A.SECTION_NAME), amap, info)
    print(f"tasks to rename to '<plain title> [act-id]': {len(renames)}")
    reassign = plan_reassign(secs.get(A.SECTION_NAME))
    for gid, aid, owner, to, _ in reassign:
        print(f"  {'would reassign' if a.dry_run else 'reassign'}: {aid} ({owner}) -> {NAME_OF[to]}")
    if a.dry_run:
        for k in todo[:8]:
            v = info[k]
            print(f"  would create: {k} — {v['title'][:70]} | {v['assignee_name']} | due {v['deadline']}")
        return 0

    for g in MEMBERS:
        if g not in members:
            A.post(f"/projects/{A.PROJECT}/addMembers", {"members": [g]})
            print(f"  added {NAME_OF.get(g, g)} as a project member")
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
        body = {"name": task_name(v["title"], k), "projects": [A.PROJECT],
                "memberships": [{"project": A.PROJECT, "section": amap["section"]}],
                "assignee": v["assignee"], "notes": notes_for(v["act"], v)}
        if v["deadline"]:
            body["due_on"] = v["deadline"]
        t = A.post("/tasks", body)
        amap["tasks"][k] = t["gid"]
        created.append(k)
        json.dump(amap, open(MAP, "w", encoding="utf8"), indent=1, ensure_ascii=False)   # after every task
    for gid, aid, owner, to, notes in reassign:
        A.put(f"/tasks/{gid}", {"assignee": to, "notes": notes})
    for gid, aid, new_name in renames:
        A.put(f"/tasks/{gid}", {"name": new_name})
    if renames:
        print(f"  renamed {len(renames)} task(s)")
    for k in a.retitle:
        A.put(f"/tasks/{amap['tasks'][k]}", {"name": task_name(info[k]["title"], k)})
        print(f"  retitled {k}: {info[k]['title']!r}")
    if a.section_top:
        order = [x["gid"] for x in A.get(f"/projects/{A.PROJECT}/sections", {"opt_fields": "name"})]
        if order[0] != amap["section"]:
            A.post(f"/projects/{A.PROJECT}/sections/insert",
                   {"section": amap["section"], "before_section": order[0]})
        after = A.get(f"/projects/{A.PROJECT}/sections", {"opt_fields": "name"})
        print("  sections now: " + " | ".join(x["name"] for x in after))
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
