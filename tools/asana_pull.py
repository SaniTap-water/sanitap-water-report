#!/usr/bin/env python3
"""Read the action tasks from Asana for the build (2 Oct 2026). READ-ONLY.

Reads every task in the section "Weekly report actions" of the project
"H2O4CO2 - CLEAN WATER" and writes data/asana_pull.json, the local copy the
action list renders from (tools/render_actions.py): owner (the assignee, or the
name on an "Owner: <name> (not in Asana)" first line), deadline (the due date)
and completed state. Nothing is written to Asana here - tools/asana_setup.py is
the only writer.

A task is matched to its action by the act-id that starts its name, or by
data/asana_map.json. A task added by hand in the section without an act-id gets
one generated from its name ("act-" + a slug), is added to the map, and is
listed as "new from Asana" in the build log. Two tasks naming the same act-id
are recorded under "duplicates" and fail the gate (tools/check_asana.py).

Offline or without the token, the committed copy stays as it is and the build
says so; tools/check_asana.py still holds the page to that copy.

    python3 tools/asana_pull.py --write
"""
import datetime, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asana_api as A  # noqa: E402
from asana_setup import NAME_OF  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "asana_pull.json")
MAP = os.path.join(REPO, "data", "asana_map.json")
OWNER_LINE = re.compile(r"^\s*Owner:\s*(.+?)\s*\(not in Asana\)\s*$", re.M)


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return "act-" + "-".join(s.split("-")[:6])


def main():
    if "--write" not in sys.argv:
        sys.exit("usage: asana_pull.py --write")
    amap = json.load(open(MAP, encoding="utf8"))
    by_gid = {g: k for k, g in amap["tasks"].items()}
    try:
        tasks = A.get(f"/sections/{amap['section']}/tasks",
                      {"opt_fields": "name,assignee.name,due_on,completed,completed_at,notes,permalink_url,modified_at"})
    except SystemExit as e:
        print(f"asana_pull: Asana not readable ({str(e)[:120]}); the committed data/asana_pull.json stays as it is")
        return 0
    out, dup, new = {}, {}, []
    for t in tasks:
        m = re.match(r"(act-[a-z0-9-]+)\s", t["name"])
        aid = m.group(1) if m else by_gid.get(t["gid"])
        if not aid:
            aid = slug(t["name"])
            new.append({"act_id": aid, "gid": t["gid"], "name": t["name"]})
            amap["tasks"][aid] = t["gid"]
        o = OWNER_LINE.search(t.get("notes") or "")
        a = t.get("assignee") or {}
        owner = (o.group(1) if o else NAME_OF.get(a.get("gid")) or a.get("name") or "Unassigned")
        rec = {"gid": t["gid"], "name": t["name"], "owner": owner, "assignee_gid": a.get("gid"),
               "due_on": t.get("due_on"), "completed": bool(t.get("completed")),
               "completed_at": (t.get("completed_at") or "")[:10] or None,
               "permalink": t.get("permalink_url"), "modified_at": t.get("modified_at")}
        if aid in out:
            dup.setdefault(aid, [out[aid]["gid"]]).append(t["gid"])
            continue
        out[aid] = rec
    doc = {"note": "Read-only copy of the Asana section 'Weekly report actions', written by tools/asana_pull.py "
                   "at each build. The action list renders owner, deadline and completion from it.",
           "pulled_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "project": A.PROJECT, "section": amap["section"],
           "tasks": dict(sorted(out.items())), "duplicates": dup, "new_from_asana": new}
    json.dump(doc, open(OUT, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    open(OUT, "a").write("\n")
    if new:
        amap["tasks"] = dict(sorted(amap["tasks"].items()))
        json.dump(amap, open(MAP, "w", encoding="utf8"), indent=1, ensure_ascii=False)
        open(MAP, "a").write("\n")
    done = sum(1 for r in out.values() if r["completed"])
    print(f"asana_pull: {len(out)} tasks read ({done} completed), {len(dup)} duplicated act-id(s)")
    for n in new:
        print(f"asana_pull: new from Asana: {n['act_id']} <- task {n['gid']} \"{n['name']}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
