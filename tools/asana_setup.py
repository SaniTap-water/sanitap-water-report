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
     and --section-top moves the section above the project's first section;
  9. --trim-notes strips the bookkeeping lines from every description in the
     project, and --rewrite-task <act-id> sets one task's assignee, due date and
     description (data/asana_notes.json) (7 Oct 2026). New tasks
     get the short format of notes_for(); nothing in the build rewrites a
     description;
  8. --push-owners (7 Oct 2026) sets each open task's assignee to its owner in
     data/action_owners.json, after tools/asana_pull.py has taken in changes
     made in Asana: Asana is the single source for owners;
  7. --approval (7 Oct 2026) creates or updates the week's approval task for
     major mWater changes (tools/change_review.py), assigned to Adriaan with
     Jan following.

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
# Coddy Velonizy and Ntsoa Ranaivoson (Endur'O director) added 2 Oct 2026
# (second pass). Since 7 Oct 2026 Coddy is coddy.velonizy@enduro.mg (guest,
# 1219154315843358): he cannot use the old MadAvance account "IT Assistant"
# (coddy@madavance.org, CODDY_OLD), which keeps only his completed tasks and
# work outside this project; NAME_OF still reads it as Coddy for those. An owner "Endur'O" with a
# person in brackets is that person; "Endur'O" with no person named is assigned
# to Coddy and keeps "Owner: Endur'O" as the first line of the description.
# An owner "MadAvance" (field teams, transcriber to be named) is Angelo, and
# "MadAvance / Cathy" is Cathy (third pass, same day). Ralf van Veenendaal
# (Curtech) and Gold Standard are not users: assigned to Adriaan.
CODDY = "1219154315843358"
CODDY_OLD = "1209012876322233"
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
NAME_OF[CODDY_OLD] = "Coddy Velonizy"
MEMBERS = [ANGELO, CODDY, NTSOA]
ENDURO_LINE = "Owner: Endur'O"


def _first(word):
    return re.sub(r"[^a-zé]", "", word.lower())


_KEEP_OWNER = set(json.load(open(os.path.join(REPO, "data", "assignment_rules.json"), encoding="utf8")).get("keep_owner", [])) \
    if os.path.isfile(os.path.join(REPO, "data", "assignment_rules.json")) else set()


def rule_owner(text):
    """(7 Oct 2026) The assignee data/assignment_rules.json gives this task, or None."""
    p = os.path.join(REPO, "data", "assignment_rules.json")
    if not os.path.isfile(p):
        return None
    for r in json.load(open(p, encoding="utf8"))["rules"]:
        if re.search(r["pattern"], text or "", re.I):
            return PEOPLE[r["owner"]][0]
    return None


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


QUESTIONS = "If you have questions about this task, please contact:"
FOOTER = ("Owner, due date and completion on the weekly report come from this task; ticking it closes the "
          "action only once evidence is posted (an 'Evidence:' comment or a file).")
_INTERNAL = re.compile(r"\b(data/|docs/|tools/|commit\b|[0-9a-f]{7,40}\b|\.json\b|\.csv\b|\.py\b|action record)", re.I)


def notes_for(a, info):
    """A new task's description (format of 7 Oct 2026): no bookkeeping lines."""
    lines = []
    if info.get("first_line"):
        lines += [info["first_line"], ""]
    if info["not_in_asana"]:
        lines += [f"Owner: {info['not_in_asana']} (not in Asana)", ""]
    lines.append(f"Closes when: {info['closes_when']}")
    if info["depends"] and info["depends"] not in ("—", "none"):
        lines.append(f"Depends on: {info['depends']}")
    if info["source"] and not _INTERNAL.search(info["source"]):
        lines.append(f"Source: {info['source']}")
    lines += ["", FOOTER]
    return "\n".join(lines)


def _people_in(text):
    """Asana gids of the people a line names, by first name."""
    return {PEOPLE[w][0] for w in (_first(x) for x in re.split(r"[\s,/;()]+", text)) if w in PEOPLE}


def _two_sentences(block):
    txt = " ".join(l.strip() for l in block if l.strip())
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"(])", txt)
    return [" ".join(parts[:2])] if txt else []


NO_CHASER_LINE = "Ralf's work; Coddy tracks; no chasers."
NO_CHASERS = set(json.load(open(os.path.join(REPO, "data", "build_config.json"), encoding="utf8"))["actions"].get("no_chasers", []))


def trim_notes(notes, assignee_gid, is_action, own_url=None, closes_when=None, aid_hint=None):
    """Strip the bookkeeping from a description (7 Oct 2026). Kept: everything a
    person wrote. Removed: Type; Source when it is an internal file path;
    'Depends on: none'; an 'On the report' link the Links already carry;
    'Questions to' and 'Owner as written on the report' when they name only the
    assignee; the old footer (replaced by FOOTER on action tasks); glossary
    entries for terms the description does not use."""
    lines = (notes or "").split("\n")
    body_end = next((k for k, l in enumerate(lines) if l.strip() == "Glossary"), len(lines))
    body, gloss = lines[:body_end], lines[body_end + 1:]
    stop = next((k for k, l in enumerate(gloss) if not l.strip()), len(gloss))
    body, gloss = body + gloss[stop:], gloss[:stop]      # the glossary ends at its first blank line
    # (7 Oct 2026, lean) "What and why" keeps two sentences
    if body and body[0].strip() == "What and why":
        end = next((k for k in range(1, len(body)) if not body[k].strip()), len(body))
        body = [body[0]] + _two_sentences(body[1:end]) + body[end:]
    text_wo = "\n".join(body)
    out = []
    for l in body:
        st = l.strip()
        # links that only point back at the report (its own live status, or another anchor)
        if re.match(r"^(https?://sanitap-water\.github\.io/sanitap-water-report/(index\.html)?(#[\w-]*)?)(\s*\(.*\))?\.?$", st):
            continue
        if st.startswith("Owner as written on the report:"):
            continue
        if NOT_IN_LINE.match(st) and assignee_gid and assignee_gid != ADRIAAN:
            continue                                  # stale: the task now has a real assignee
        if closes_when and st.startswith("Closes when:"):
            l = f"Closes when: {closes_when[0].upper() + closes_when[1:]}"
            st = l
        if re.match(r"^Type:", st):
            continue
        if re.match(r"^Source:", st) and (_INTERNAL.search(st) or "action record" in st):
            continue
        if re.match(r"^Depends on:\s*(none|—|-)?\.?\s*$", st, re.I):
            continue
        if st.startswith("On the report:"):
            continue
        if st.startswith("Questions to:") or st.startswith(QUESTIONS):
            # (8 Oct 2026) the wording is "If you have questions about this task, please contact:";
            # kept only where it names someone other than the assignee
            who = st.split(":", 1)[1].strip()
            named = _people_in(who)
            if named and named <= {assignee_gid}:
                continue
            l = f"{QUESTIONS} {who}"
        if st.startswith("Owner, due date and completion are read from this task") or st == FOOTER \
                or st.startswith("Ticking it complete does not close"):
            continue
        out.append(l.rstrip())
    # a "Links" header left with nothing under it goes too
    k = 0
    while k < len(out):
        if out[k].strip() == "Links" and (k + 1 >= len(out) or not out[k + 1].strip()):
            del out[k]
            continue
        k += 1
    used = "\n".join(out)
    def needed(term):
        parts = [x for x in re.split(r"\s*(?:/|,|;| and |\(|\))\s*", term) if len(x.strip()) >= 3]
        codes = re.findall(r"[A-Za-z]*\d[\w.]*", term)
        return any(x.strip().lower() in used.lower() for x in parts or [term]) \
            or any(len(c) >= 3 and c.rstrip(".") in used for c in codes)
    keep = [g for g in gloss if g.strip() and ":" in g and needed(g.split(":", 1)[0].strip())]
    if keep:
        out += ["", "Glossary"] + keep
    # Curtech tasks (7 Oct 2026): one line at the top, so nobody chases Ralf
    if aid_hint in NO_CHASERS:
        out = [l for l in out if l.strip() != NO_CHASER_LINE]
        out = [NO_CHASER_LINE, ""] + out
    if is_action:
        out += ["", FOOTER]
    txt = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    return txt


OVERRIDES = {}
_OV = os.path.join(REPO, "data", "asana_notes.json")
if os.path.isfile(_OV):
    OVERRIDES = json.load(open(_OV, encoding="utf8")).get("closes_when", {})


def trim_all(dry):
    """Every task in the project, action or not."""
    ts = A.get(f"/projects/{A.PROJECT}/tasks", {"opt_fields": "name,notes,assignee.gid", "limit": 100})
    changed = 0
    for t in ts:
        old = t.get("notes") or ""
        aid = tag_of(t["name"])
        new = trim_notes(old, (t.get("assignee") or {}).get("gid"), bool(aid), closes_when=OVERRIDES.get(aid), aid_hint=aid)
        norm = lambda x: re.sub(r"\n{3,}", "\n\n", "\n".join(l.rstrip() for l in x.split("\n"))).strip()
        if new != norm(old):                     # whitespace alone is not a change
            changed += 1
            if not dry:
                A.put(f"/tasks/{t['gid']}", {"notes": new})
    print(f"trim-notes: {changed} of {len(ts)} descriptions {'would be ' if dry else ''}trimmed")
    return 0


def close_task(aid, evidence, name=None):
    """Post an "Evidence:" comment and complete the task (7 Oct 2026)."""
    gid = json.load(open(MAP, encoding="utf8"))["tasks"][aid]
    A.post(f"/tasks/{gid}/stories", {"text": "Evidence: " + evidence})
    body = {"completed": True}
    if name:
        body["name"] = f"{name} [{aid}]"
    A.put(f"/tasks/{gid}", body)
    print(f"closed: {aid} ({gid})")
    return 0


def merge_task(src, dst, why):
    """Carry src's comments to dst, then close src as merged (7 Oct 2026)."""
    amap = json.load(open(MAP, encoding="utf8"))["tasks"]
    gs, gd = amap[src], amap[dst]
    st = [x for x in A.get(f"/tasks/{gs}/stories", {"opt_fields": "resource_subtype,text,created_at,created_by.name"})
          if x.get("resource_subtype") == "comment_added"]
    carried = [f"- {x['created_at'][:10]}, {(x.get('created_by') or {}).get('name')}: {x['text']}" for x in st]
    A.post(f"/tasks/{gd}/stories", {"text": f"Merged in from [{src}] (decision of Adriaan Mol, 7 Oct 2026): {why}"
                                    + ("\n\nComments carried over:\n" + "\n".join(carried) if carried else "")})
    A.post(f"/tasks/{gs}/stories", {"text": f"Evidence: Merged into [{dst}] (decision of Adriaan Mol, 7 Oct 2026). {why}"})
    A.put(f"/tasks/{gs}", {"completed": True})
    print(f"merged: {src} -> {dst} ({len(carried)} comment(s) carried)")
    return 0


def rewrite_task(aid):
    """One action's task from the repository: owner, deadline and, where
    data/asana_notes.json carries one, its description."""
    amap = json.load(open(MAP, encoding="utf8"))["tasks"]
    rec = json.load(open(os.path.join(REPO, "data", "action_owners.json"), encoding="utf8"))["owners"].get(aid)
    body = {}
    if rec is not None:                     # an Asana-only task keeps its assignee
        gid, _n, _x, _f = match_owner(rec.get("owner"))
        body["assignee"] = gid
    rec = rec or {}
    if rec.get("deadline"):
        body["due_on"] = rec["deadline"]            # never clears a due date set in Asana
    custom = os.path.join(REPO, "data", "asana_notes.json")
    lines = (json.load(open(custom, encoding="utf8"))["tasks"].get(aid) if os.path.isfile(custom) else None)
    if lines:
        body["notes"] = "\n".join(lines)
    A.put(f"/tasks/{amap[aid]}", body)
    print(f"rewrite-task: {aid} -> {NAME_OF.get(body.get('assignee'), 'assignee unchanged')}, due {rec.get('deadline')}"
          + (", description rewritten" if "notes" in body else ""))
    return 0


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
            # assignment rules (7 Oct 2026): a team, Jan or Adriaan as owner gives way to the rule
            rule_assignee=None if a["id"] in _KEEP_OWNER else (rule_owner((rec.get("title") or a["title"]) + " " + re.sub(r"<[^>]+>", " ", (a.get("detail") or "")[:600]))
                           if gid in (ADRIAAN, PEOPLE["jan"][0]) or re.match(r"^\s*(MadAvance|Endur.?O)\b", owner_text or "", re.I) and not name
                           else None),
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
        if written not in rest and not _people_in(m.group(1)) <= {gid}:
            i = next((j + 1 for j, l in enumerate(rest) if l.startswith("On the report: ")), len(rest))
            rest = rest[:i] + [written] + rest[i:]
        notes = "\n".join(([first_line, ""] if first_line else []) + rest)
        aid = tag_of(t["name"]) or t["gid"]
        out.append((t["gid"], aid, m.group(1), gid, notes))
    return out


JAN = PEOPLE["jan"][0]
APPROVALS = os.path.join(REPO, "data", "approvals.json")
CHANGES = os.path.join(REPO, "data", "change_review.json")


PULL = os.path.join(REPO, "data", "asana_pull.json")


def push_owners():
    """(7 Oct 2026) Asana is the single source for owners. Run after
    tools/asana_pull.py has taken in any reassignment made in Asana: what still
    differs is an owner changed in the repository, and it is pushed to the task
    here, in the same run. Open actions only; the pull file is updated to match."""
    info = action_info()
    pull = json.load(open(PULL, encoding="utf8"))
    pushed = 0
    for aid, t in pull["tasks"].items():
        v = info.get(aid)
        if not v or v["state"] not in ("ACT", "WATCH") or t.get("completed"):
            continue
        if v["assignee"] != t.get("assignee_gid"):
            A.put(f"/tasks/{t['gid']}", {"assignee": v["assignee"]})
            print(f"  owner pushed to Asana: {aid}: {t.get('owner')} -> {NAME_OF.get(v['assignee'], v['assignee'])}")
            t.update(assignee_gid=v["assignee"], owner=v.get("not_in_asana") and t["owner"] or NAME_OF.get(v["assignee"], t["owner"]))
            pushed += 1
    if pushed:
        json.dump(pull, open(PULL, "w", encoding="utf8"), indent=1, ensure_ascii=False)
        open(PULL, "a").write("\n")
    print(f"push-owners: {pushed} task(s) reassigned to their repository owner")
    return 0


def approval_task():
    """(7 Oct 2026) One Asana approval task per week with major changes, in the
    section, assigned to Adriaan with Jan following. Created once; its
    description is brought up to date on later builds of the same week. The
    approval itself is read back by tools/change_review.py."""
    if not os.path.isfile(APPROVALS):
        print("approval: no data/approvals.json - nothing flagged")
        return 0
    appr = json.load(open(APPROVALS, encoding="utf8"))
    res = json.load(open(CHANGES, encoding="utf8")) if os.path.isfile(CHANGES) else {}
    key = f"{res.get('year')}-W{res.get('week', 0):02d}"
    w = appr["weeks"].get(key)
    if not w or w.get("status") == "approved" or not w.get("flags"):
        print(f"approval: nothing to approve for {key}")
        return 0
    fig = w.get("figures") or {}
    lab = {"tco2e": "Carbon credits (tCO2e a year)", "points": "Water points in scope",
           "people": "People served", "days_operational": "Days operational (applied)"}
    lines = [f"Major changes in the mWater data, week {res.get('week')} (against the edition of "
             f"{(res.get('baseline') or {}).get('published')}). They are on the report as PROVISIONAL until "
             "Adriaan or Jan approves this task. Approve: they become final at the next build. "
             "Reject or request changes, with a comment: they stay provisional and the comment is shown.", "",
             "Headline figures, last week -> this week:"]
    lines += [f"  {lab[k]}: {v.get('before')} -> {v.get('after')}" for k, v in fig.items()]
    fl = w["flags"]
    if fl.get("a"):
        lines += ["", "(a) Existing records edited so that credits or eligibility go up:"]
        lines += [f"  water point {r['wp']}: {', '.join(r['up'])}; record(s) "
                  + ", ".join(f"https://portal.mwater.co/#/responses/{i}" for i in r["records"]) for r in fl["a"]]
    if fl.get("b"):
        lines += ["", "(b) Records deleted:"]
        lines += [f"  {d['count']} from {d['file']}" + (f": {', '.join(d['ids'])}" if d.get("ids") else "") for d in fl["b"]]
    if fl.get("c"):
        lines += ["", "(c) Week-on-week moves above the threshold carried by edited records:"]
        lines += [f"  {lab[c['figure']]}: {c['carried']} ({c['pct']}%)" for c in fl["c"]]
    lines += ["", f"On the report: {A.REPORT_URL}#changes"]
    notes = "\n".join(lines)
    name = f"Approve: major changes [week {res.get('week')}]"
    if w.get("task"):
        A.put(f"/tasks/{w['task']}", {"notes": notes})
        print(f"approval: updated {name} ({w['task']})")
    else:
        secs = {s["name"]: s["gid"] for s in A.get(f"/projects/{A.PROJECT}/sections", {"opt_fields": "name"})}
        # Approval tasks need an Asana Business or Enterprise plan; this workspace answers
        # HTTP 402 (8 Oct 2026). An ordinary task is used: Adriaan or Jan completes it to
        # approve, or comments "Rejected:" / "Changes requested:" (tools/change_review.py).
        notes += ("\n\nTo approve: complete this task (Adriaan or Jan). To reject or ask for changes: "
                  "comment starting \"Rejected:\" or \"Changes requested:\".")
        t = A.post("/tasks", {"name": name, "assignee": ADRIAAN,
                              "followers": [JAN], "notes": notes, "projects": [A.PROJECT],
                              "workspace": A.WORKSPACE})
        if A.SECTION_NAME in secs:
            A.post(f"/sections/{secs[A.SECTION_NAME]}/addTask", {"task": t["gid"]})
        gid = t["gid"]
        w.update(task=gid)
        print(f"approval: created {name} ({gid})")
    json.dump(appr, open(APPROVALS, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return 0


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--write", action="store_true")
    g.add_argument("--push-owners", action="store_true",
                   help="set each open task's assignee to its owner in data/action_owners.json (7 Oct 2026)")
    g.add_argument("--trim-notes", action="store_true",
                   help="strip bookkeeping lines from every task description in the project (7 Oct 2026)")
    g.add_argument("--rewrite-task", metavar="ACT_ID",
                   help="set one task's assignee, due date and (asana_notes) description from the repository")
    g.add_argument("--assign", nargs=2, metavar=("ACT_ID", "PERSON"),
                   help="assign a task that has no row on the report (Asana-only) to a person by first name")
    g.add_argument("--close", nargs=2, metavar=("ACT_ID", "EVIDENCE"),
                   help="post 'Evidence: <text>' on the task and complete it")
    g.add_argument("--merge", nargs=3, metavar=("FROM", "INTO", "WHY"),
                   help="carry FROM's comments to INTO and close FROM as merged")
    ap.add_argument("--rename", help="with --close: the new task name, without the [act-id]")
    g.add_argument("--approval", action="store_true",
                   help="create or update this week's approval task from data/approvals.json (rule of 7 Oct 2026)")
    ap.add_argument("--complete", nargs="*", default=[])
    ap.add_argument("--retitle", nargs="*", default=[],
                    help="rename these act-ids' tasks to '<title> [act-id]' from data/action_owners.json")
    ap.add_argument("--section-top", action="store_true",
                    help="move the section 'Weekly report actions' above the project's first section")
    a = ap.parse_args()
    if a.approval:
        return approval_task()
    if a.push_owners:
        return push_owners()
    if a.assign:
        gid = json.load(open(MAP, encoding="utf8"))["tasks"][a.assign[0]]
        who = PEOPLE[_first(a.assign[1])][0]
        A.put(f"/tasks/{gid}", {"assignee": who})
        print(f"assigned: {a.assign[0]} -> {NAME_OF[who]}")
        return 0
    if a.close:
        return close_task(a.close[0], a.close[1], a.rename)
    if a.merge:
        return merge_task(*a.merge)
    if a.trim_notes:
        return trim_all(dry="--dry" in sys.argv)
    if a.rewrite_task:
        return rewrite_task(a.rewrite_task)
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
                "assignee": v["rule_assignee"] or v["assignee"], "notes": notes_for(v["act"], v)}
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
