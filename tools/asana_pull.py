#!/usr/bin/env python3
"""Read the action tasks from Asana for the build (2 Oct 2026). READ-ONLY.

Reads every task in the section "Weekly report actions" of the project
"H2O4CO2 - CLEAN WATER" and writes data/asana_pull.json, the local copy the
action list renders from (tools/render_actions.py): owner (the assignee, or the
name on an "Owner: <name> (not in Asana)" first line), deadline (the due date)
and completed state. Nothing is written to Asana here - tools/asana_setup.py is
the only writer.

A task is matched to its action by its gid in data/asana_map.json (since
2 Oct 2026), so people can rename tasks freely; the "[act-id]" tag at the end
of a name is for readers. A task added by hand in the section is placed by its
tag if it carries an unused one, otherwise gets an act-id generated from its
name ("act-" + a slug); either way it is added to the map and listed as "new
from Asana" in the build log. A task whose owner renamed it gives the action
its title: the Asana wording is copied into data/action_owners.json "title". Two tasks naming the same act-id
are recorded under "duplicates" and fail the gate (tools/check_asana.py).

Completion needs evidence (Adriaan Mol, 5 Oct 2026). For every completed task
the pull also reads the task's history, comments and attachments. A task counts
as closed only if it is completed AND carries evidence: a comment starting
"Evidence:" or an attached file. The evidence (its text or file name, author,
date and the task link) is written into data/action_owners.json "evidence"
automatically, marked "from": "asana"; an entry recorded in the repository by
hand is never overwritten. Who ticked the task and when comes from its
history ("ticked_by", "ticked_at"). A tick alone closes nothing: the page shows
"ticked in Asana, no evidence yet". An Asana-sourced entry whose task is
reopened, or whose Evidence comment and attachments are gone, is removed.

Offline or without the token, the committed copy stays as it is and the build
says so; tools/check_asana.py still holds the page to that copy.

    python3 tools/asana_pull.py --write
"""
import datetime, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asana_api as A  # noqa: E402
from asana_setup import NAME_OF, TAG, OLD_PREFIX, tag_of  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "asana_pull.json")
MAP = os.path.join(REPO, "data", "asana_map.json")
OWNER_LINE = re.compile(r"^\s*Owner:\s*(.+?)\s*\(not in Asana\)\s*$", re.M)


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return "act-" + "-".join(s.split("-")[:6])


def plain_title(name):
    """The task name without its act-id: the trailing [act-id] tag, or the
    "<act-id> — " prefix of the first naming."""
    return OLD_PREFIX.sub("", TAG.sub("", name or "")).strip()


EVIDENCE = re.compile(r"^\s*evidence\s*:\s*", re.I)


def completion(gid, permalink):
    """-> (ticked_by, ticked_at, evidence or None) for a completed task, from
    its stories (history and comments) and its attachments."""
    stories = A.get(f"/tasks/{gid}/stories", {"opt_fields": "resource_subtype,text,created_at,created_by.name"})
    ticks = [s for s in stories if s.get("resource_subtype") == "marked_complete"]
    tick = ticks[-1] if ticks else {}
    by = (tick.get("created_by") or {}).get("name")
    at = (tick.get("created_at") or "")[:10] or None
    ev = None
    for s in stories:                                  # the latest Evidence comment wins
        if s.get("resource_subtype") == "comment_added" and EVIDENCE.match(s.get("text") or ""):
            ev = {"kind": "comment", "text": EVIDENCE.sub("", s["text"]).strip(),
                  "author": (s.get("created_by") or {}).get("name"), "date": (s.get("created_at") or "")[:10],
                  "link": permalink}
    if not ev:
        files = A.get("/attachments", {"parent": gid, "opt_fields": "name,created_at,permanent_url"})
        added = {(s.get("text") or ""): s for s in stories if s.get("resource_subtype") == "attachment_added"}
        if files:
            f = files[-1]
            who = next(((s.get("created_by") or {}).get("name") for txt, s in added.items() if f["name"] in txt), None)
            ev = {"kind": "attachment", "text": f["name"], "author": who,
                  "date": (f.get("created_at") or "")[:10], "link": permalink, "file": f.get("permanent_url")}
    return by, at, ev


def sync_evidence(own, out):
    """Asana evidence -> data/action_owners.json "evidence" (from: asana). An
    entry recorded in the repository by hand is never touched. -> changes."""
    evid = own.setdefault("evidence", {}).setdefault("actions", {})
    changes = []
    for aid, r in out.items():
        cur = evid.get(aid)
        if cur and cur.get("from") != "asana":
            continue
        e = r.get("evidence") if r["completed"] else None
        if e:
            what = ("an Evidence comment on the Asana task" if e["kind"] == "comment"
                    else f"a file attached to the Asana task: {e['text']}")
            new = {"recorded_on": e["date"], "recorded_by": "tools/asana_pull.py, from the Asana task",
                   "what": what, "source": f"{e.get('author') or 'not recorded'}, Asana, {e['date']}",
                   "summary": e["text"], "author": e.get("author"), "date": e["date"], "kind": e["kind"],
                   "link": e["link"], "task": r["gid"], "from": "asana"}
            if e.get("file"):
                new["file"] = e["file"]
            if cur != new:
                evid[aid] = new
                changes.append(f"evidence from Asana: {aid} ({e['kind']}, {e.get('author')}, {e['date']})")
        elif cur:
            del evid[aid]
            changes.append(f"evidence from Asana withdrawn: {aid} (task {'reopened' if not r['completed'] else 'has no evidence any more'})")
    if changes:
        own["evidence"]["actions"] = dict(sorted(evid.items()))
    return changes


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
    own_path = os.path.join(REPO, "data", "action_owners.json")
    own = json.load(open(own_path, encoding="utf8"))
    retitled = []
    for t in tasks:
        # matched by task gid (data/asana_map.json), so a task can be renamed
        # freely; the name's [act-id] tag only places a task not yet in the map
        aid = by_gid.get(t["gid"])
        if not aid:
            aid = tag_of(t["name"])
            if not aid or aid in amap["tasks"]:
                aid = slug(TAG.sub("", t["name"]).strip())
            new.append({"act_id": aid, "gid": t["gid"], "name": t["name"]})
            amap["tasks"][aid] = t["gid"]
            by_gid[t["gid"]] = aid
        title = plain_title(t["name"])
        row = own["owners"].get(aid)
        # a task its owner renamed: the Asana wording becomes the action's title
        if title and not OLD_PREFIX.match(t["name"]) and row is not None and row.get("title") != title:
            retitled.append((aid, row.get("title"), title))
            row["title"] = title
        o = OWNER_LINE.search(t.get("notes") or "")
        a = t.get("assignee") or {}
        owner = (o.group(1) if o else NAME_OF.get(a.get("gid")) or a.get("name") or "Unassigned")
        rec = {"gid": t["gid"], "name": t["name"], "title": title, "owner": owner, "assignee_gid": a.get("gid"),
               "due_on": t.get("due_on"), "completed": bool(t.get("completed")),
               "completed_at": (t.get("completed_at") or "")[:10] or None,
               "permalink": t.get("permalink_url"), "modified_at": t.get("modified_at")}
        if rec["completed"]:
            by, at, ev = completion(t["gid"], t.get("permalink_url"))
            rec.update(ticked_by=by or owner, ticked_at=at or rec["completed_at"], evidence=ev)
        if aid in out:
            dup.setdefault(aid, [out[aid]["gid"]]).append(t["gid"])
            continue
        out[aid] = rec
    evchanges = sync_evidence(own, out)
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
    if retitled or evchanges:
        json.dump(own, open(own_path, "w", encoding="utf8"), indent=1, ensure_ascii=False)
        open(own_path, "a").write("\n")
    for aid, was, now in retitled:
        print(f"asana_pull: title from Asana: {aid}: {was!r} -> {now!r}")
    done = sum(1 for r in out.values() if r["completed"])
    print(f"asana_pull: {len(out)} tasks read ({done} completed), {len(dup)} duplicated act-id(s)")
    for c in evchanges:
        print(f"asana_pull: {c}")
    noev = sorted(a for a, r in out.items() if r["completed"] and not r.get("evidence"))
    print(f"asana_pull: completed with evidence {sum(1 for r in out.values() if r.get('evidence'))}, "
          f"completed without evidence {len(noev)}" + (f" ({', '.join(noev)})" if noev else ""))
    for n in new:
        print(f"asana_pull: new from Asana: {n['act_id']} <- task {n['gid']} \"{n['name']}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
