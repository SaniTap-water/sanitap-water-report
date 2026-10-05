# -*- coding: utf-8 -*-
"""Regenerate the consolidated action list at the top of index.html.

THE ONE LIST. Every action in the report has a detailed row somewhere in the
body, in the section that explains it. This builds the single summary table
that sits under the fleet summary, from those rows, so the two can never
disagree: the summary is output, the detailed row is the source.

Status vocabulary is three states and no more:

    ACT    bright red    work outstanding      (was DUE, OVERDUE)
    WATCH  orange        standing / monitored  (was STANDING)
    OK     green         done or decided       (was DONE, DECIDED)

OVERDUE is deliberately NOT a stored state. It is a badge rendered beside ACT
and computed here from the deadline against today, so it can never go stale
the way a hand-typed OVERDUE does - which is what happened before: two rows
carried OVERDUE from a date that had long since been superseded.

DECIDED survives as a label inside OK, because a decision taken is not the
same as work completed and a reader should be able to tell them apart.

Closed items drop out of the live table into a collapsed "closed this period"
block, and the section that raised them must stop describing them as open -
tools/check_consistency.py asserts that.

    python3 tools/render_actions.py --write
    python3 tools/render_actions.py --check
"""
import collections, datetime, difflib, html, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# a region that differs only in prerendered figure values is not drift
from prerender_figures import same as _same  # noqa: E402
from table_notes import render as _tablenote  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEGIN = ("<!-- BEGIN GENERATED action-list :: tools/render_actions.py "
         ":: do not edit between these markers -->")
END = "<!-- END GENERATED action-list -->"

# old state -> (new state, label kept inside it). The three new names map to
# themselves: the detailed rows were converted to ACT/WATCH/OK but this table
# was not extended, so every row fell through to the ACT default and the list
# reported 93 to act on, 0 to watch and 0 closed when 8 of them were not ACT.
MAP = {"DUE": ("ACT", ""), "OVERDUE": ("ACT", ""), "STANDING": ("WATCH", ""),
       "DONE": ("OK", ""), "DECIDED": ("OK", "DECIDED"),
       "ACT": ("ACT", ""), "WATCH": ("WATCH", ""), "OK": ("OK", "")}
CLASS = {"ACT": "crit", "WATCH": "warn", "OK": "ok"}

# Owners are written as they are spoken in the rows - "Jan", "Jan de Graaf",
# "Jan / Endur'O team", "Jan, with Coddy" - so grouping on the raw string
# scatters one person across four headings. The group is the LEAD owner,
# matched on the first word; the row still shows the owner exactly as written,
# so nothing is lost and no row is reassigned.
LEADS = {"adriaan": "Adriaan Mol", "james": "James Walker",
         "jan": "Jan de Graaf", "angelo": "Angelo Nahavitatsara",
         "lanja": "Lanja Randriamanantena", "madavance": "MadAvance",
         "coddy": "Coddy", "cathy": "Cathy"}


def lead_owner(owner):
    w = re.sub(r"[^A-Za-z]", "", owner.split()[0].lower()) if owner.split() else ""
    return LEADS.get(w) or (owner if owner not in ("—", "&mdash;", "") else "Unassigned")
MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def strip(html):
    s = re.sub(r"<[^>]+>", "", html)
    for a, b in (("&mdash;", "—"), ("&nbsp;", " "), ("&rsquo;", "’"),
                 ("&ldquo;", "“"), ("&rdquo;", "”"), ("&amp;", "&"),
                 ("&eacute;", "é"), ("&egrave;", "è"), ("&hellip;", "…"),
                 ("&minus;", "−"), ("&times;", "×"), ("&sect;", "§"),
                 ("&Eacute;", "É"), ("&ndash;", "–"), ("&deg;", "°")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def parse_deadline(text):
    m = re.search(r"\b(\d{1,2})\s+([A-Z][a-z]{2})\s+(\d{4})\b", text)
    if not m:
        return None
    try:
        return datetime.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
    except (KeyError, ValueError):
        return None


def _rows_from(det):
    """(id, a synthetic row body) so the parser below is unchanged."""
    for aid, d in sorted(det.items()):
        yield aid, (f'<td>{d["detail"]}</td><td>{d["schedule"]}</td>'
                    f'<td>{d["owner"]}</td>')


def row_bodies(idx):
    """(id, inner html) for each action row, nesting-aware.

    A detail cell may itself contain a table - the approvals row carries a
    per-form breakdown - so a non-greedy match to the first </tr> silently
    truncates the row and drops it from the list. That happened once; the
    count assertion at the end of actions() is what stops it happening again.
    """
    for m in re.finditer(r'<tr id="(act-[a-z0-9-]+)">', idx):
        i = m.end()
        depth = 1
        for tok in re.finditer(r"<tr\b|</tr>", idx[i:]):
            depth += 1 if tok.group(0).startswith("<tr") else -1
            if depth == 0:
                yield m.group(1), idx[i:i + tok.start()]
                break


def details():
    """Every action's explanatory detail, from data/action_details.json.

    It used to live in two tables in the body - "Open actions" and the
    Moramanga field-visit list - each row carrying a link back up to the
    consolidated list. That was the same content twice: a summary row here
    and a detail row there. The detail is now data, rendered once, collapsed
    inside the row it belongs to, and there is one list on the page.
    """
    p = os.path.join(REPO, "data", "action_details.json")
    return json.load(open(p)) if os.path.isfile(p) else {}


def actions(idx, use_asana=True):
    out = []
    det = details()
    for aid, body in _rows_from(det):
        # top-level cells only: a nested table's <td>s must not be mistaken
        # for this row's own
        cells, depth, start = [], 0, None
        for tok in re.finditer(r"<table\b|</table>|<td\b[^>]*>|</td>", body):
            s = tok.group(0)
            if s.startswith("<table"):
                depth += 1
            elif s == "</table>":
                depth -= 1
            elif depth == 0 and s.startswith("<td"):
                start = tok.end()
            elif depth == 0 and s == "</td>" and start is not None:
                cells.append(body[start:tok.start()])
                start = None
        if len(cells) < 3:
            continue
        title = re.search(r"<b>(.*?)</b>", cells[0], re.S)
        # the summary keeps a live figure's markup, so a number in a title
        # stays a figure rather than becoming typed text; a water point id
        # loses its unlinked mono wrapper - the linked id follows in the body
        title_html = (re.sub(r"<(?!/?span\b)[^>]+>", "",
                             re.sub(r'<span class="mono">([^<]*)</span>', r"\1", title.group(1))).strip()
                      if title else None)
        title = strip(title.group(1)) if title else strip(cells[0])[:90]
        pill = re.search(r'pill\s+[a-z]+">([^<]*)<', cells[1])
        old = (pill.group(1).strip().upper() if pill else "DUE")
        state, label = MAP.get(old, ("ACT", ""))
        dl_raw = re.search(r"<b>([^<]*)</b>", cells[1])
        dl_raw = strip(dl_raw.group(1)) if dl_raw else ""
        due = parse_deadline(dl_raw)
        crit = re.findall(r'<span class="muted"[^>]*>(.*?)</span>(?=(?:<br>)?\s*$)', cells[1], re.S) \
            or re.findall(r'<span class="muted"[^>]*>(.*?)</span>', cells[1], re.S)
        # the criterion keeps its markup, so a figure in it stays a figure
        crit = crit[-1].strip() if crit else ""
        owner = strip(cells[2]) or "—"
        out.append(dict(id=aid, title=title, title_html=title_html or title, owner=owner,
                        # a data table inside a detail carries its footnote
                        detail=re.sub(r"<!--tablenote:([\w-]+)-->",
                                      lambda m: _tablenote(m.group(1)),
                                      det.get(aid, {}).get("detail", "")),
                        lead=lead_owner(owner),
                        state=state, label=label, deadline=dl_raw, due=due,
                        # an item to act on with no date is a date still
                        # to be set; a closed or standing item needs none
                        nodate=(not dl_raw) and state == "ACT",
                        criterion=crit))
    st = load_state()
    # Owner and deadline, from the record (data/action_owners.json). A row for
    # an action that no longer exists renders nothing; check_consistency holds
    # such rows to a dated, shrink-only list ("orphan_rows" in the same file).
    wb = load_owners()
    for a in out:
        w = wb.get(a["id"])
        if w:
            if w.get("owner"):
                a["owner"] = w["owner"]
                a["from_record"] = True
            if w.get("deadline"):
                try:
                    a["due"] = datetime.date.fromisoformat(w["deadline"])
                    a["deadline"] = a["due"].strftime("%-d %b %Y")
                except ValueError:
                    pass
            else:
                a["due"], a["deadline"] = None, ""
        s = st.get(a["id"])
        a["cond"] = s
        if not s or s.get("satisfied") is None:
            continue
        if s["satisfied"]:
            a["state"] = s.get("when_satisfied", "OK")
            a["label"] = "" if a["state"] != "OK" else a.get("label", "")
        elif a["state"] == "OK":
            # the condition says it is not done, whatever the row claims
            a["state"] = "ACT"
    # Evidence and Asana (2 Oct 2026). An action that no build condition can
    # close (decision, none, a document outside the repository) is closed only
    # when the evidence its closes-when names is recorded in
    # data/action_owners.json ("evidence"). Asana is the source for owner,
    # deadline and completion of every action that has a task
    # (data/asana_pull.json, read-only at build by tools/asana_pull.py); a task
    # completed in Asana without evidence stays open and shows in amber as
    # "ticked in Asana, no evidence yet" (5 Oct 2026). Evidence on the task (a
    # comment starting "Evidence:" or a file) reaches "evidence" through
    # tools/asana_pull.py.
    rec = json.load(open(os.path.join(REPO, "data", "action_owners.json"), encoding="utf8"))
    evid = (rec.get("evidence") or {}).get("actions", {})
    conds_all = json.load(open(os.path.join(REPO, "data", "action_conditions.json"), encoding="utf8"))
    pull = load_asana() if use_asana else {}
    for a in out:
        c = conds_all.get(a["id"]) or {}
        # a condition the build itself verifies is recorded evidence: an mWater
        # count, the form snapshot, the child steps, or a named file the build
        # finds in the repository or the Central Data Hub listing
        a["auto"] = c.get("kind") in ("data", "form", "children", "artefact")
        a["evidence"] = evid.get(a["id"])
        if not a["auto"]:
            if a["evidence"]:
                a["state"], a["label"] = "OK", ""
            elif a["state"] == "OK":
                a["state"], a["label"] = "ACT", "closed without recorded evidence: reopened"
        # the plain title (2 Oct 2026): the Asana task's wording where the
        # action has a task, else data/action_owners.json "title". The old
        # descriptive heading stays as the first sentence of the detail.
        t = pull.get(a["id"])
        plain = (t or {}).get("title") or (rec["owners"].get(a["id"]) or {}).get("title")
        if plain:
            a["title"], a["title_html"] = plain, html.escape(plain, quote=False)
            a["plain_title"] = True
        if t:
            a["asana"], a["asana_gid"] = t.get("permalink"), t.get("gid")
            a["owner"], a["lead"] = t["owner"], lead_owner(t["owner"])
            a["from_asana"] = True
            if t.get("due_on"):
                a["due"] = datetime.date.fromisoformat(t["due_on"])
                a["deadline"] = a["due"].strftime("%-d %b %Y")
            else:
                a["due"], a["deadline"] = None, ""
            # a tick alone closes nothing (Adriaan Mol, 5 Oct 2026): a task
            # completed with no evidence stays open, in amber, naming who
            # ticked it and when (from the task's history)
            if t.get("completed") and a["state"] != "OK":
                a["asana_done"] = True
                a["ticked"] = {"by": t.get("ticked_by") or t.get("owner"),
                               "at": t.get("ticked_at") or t.get("completed_at")}
    for a in out:
        # a date is only outstanding on something still to act on, so this is
        # recomputed after the conditions have had their say
        a["nodate"] = a["nodate"] and a["state"] == "ACT"
    # A parent action lists its steps, in order, each with its own state, owner
    # and date. The steps are ordinary rows elsewhere in the list (so the owner
    # filter still finds them); the parent closes only when all of them have
    # (kind "children" in data/action_conditions.json).
    conds = json.load(open(os.path.join(REPO, "data", "action_conditions.json"),
                           encoding="utf8"))
    by_id = {a["id"]: a for a in out}
    for a in out:
        kids = (conds.get(a["id"]) or {}).get("children")
        if not kids or "<!--children-->" not in a["detail"]:
            continue
        items = []
        for k in kids:
            c = by_id.get(k)
            if not c:
                continue
            pill = {"ACT": "crit", "WATCH": "warn", "OK": "ok"}.get(c["state"], "crit")
            items.append(
                f'<li><span class="pill {pill}">{c["state"]}</span> '
                f'<a href="#{k}">{c["title_html"]}</a> '
                f'<span class="muted">&mdash; {c["owner"]}'
                f'{", " + c["deadline"] if c.get("deadline") else ""}</span></li>')
        a["detail"] = a["detail"].replace(
            "<!--children-->", '<ol class="act-steps">' + "".join(items) + "</ol>")
    declared = len(det)
    if len(out) != declared:
        got = {a["id"] for a in out}
        missed = [k for k in det if k not in got]
        sys.exit(f"render_actions: {declared} actions in data/action_details.json "
                 f"but only {len(out)} parsed - dropped: {', '.join(missed)}")
    return out




def load_asana():
    """act-id -> the task as last read from Asana (data/asana_pull.json)."""
    p = os.path.join(REPO, "data", "asana_pull.json")
    return (json.load(open(p, encoding="utf8")) if os.path.isfile(p) else {}).get("tasks", {})


def load_state():
    """What the build worked out about each action this run.

    data/action_state.json is written by tools/eval_conditions.py. A row with
    a satisfied condition is CLOSED here regardless of the pill on its detail
    row, and a row whose condition has regressed is reopened - the pill in the
    body is the author's opinion, the condition is the measurement.
    """
    p = os.path.join(REPO, "data", "action_state.json")
    return (json.load(open(p)) if os.path.isfile(p) else {}).get("state", {})


HEADSHOTS = os.path.join(REPO, "assets", "headshots")


def initials(name):
    ws = [w for w in re.split(r"[^A-Za-z]+", name) if w]
    if not ws:
        return "?"
    return (ws[0][0] + (ws[-1][0] if len(ws) > 1 else "")).upper()


def face(lead, size=20):
    """A headshot if one has been dropped into assets/headshots, else initials.

    Never hot-linked: assets/ is the only source, the same rule the partner
    logos follow. See assets/headshots/README.md for why there are no photos
    yet - the connector has no user-photo scope.
    """
    s = slug(lead)
    for ext in ("jpg", "jpeg", "png", "webp"):
        if os.path.isfile(os.path.join(HEADSHOTS, f"{s}.{ext}")):
            return (f'<img class="face" src="assets/headshots/{s}.{ext}" '
                    f'alt="" width="{size}" height="{size}" loading="lazy">')
    return (f'<span class="face ini" aria-hidden="true" '
            f'style="width:{size}px;height:{size}px;line-height:{size}px">'
            f'{initials(lead)}</span>')


def load_owners():
    """Owner and deadline for each action, from data/action_owners.json.

    That file's "owners" block is the source of record for the two fields a
    person sets, edited only in this repository (decision of 28 September
    2026, confirming 26 September; docs/decision_log.md). Until then they were
    read from a SharePoint workbook, which is retired: nothing here reads it,
    and nothing reports it as a to-do.

    Status and closure are deliberately NOT in this file: if a person could set
    status by hand, an item could be marked done that the data says is not.
    Those stay computed.

    A missing file stops the build. The old fallback - the owners typed into
    the body rows, with a notice - is gone with the workbook: the record is in
    the repository, so its absence is a fault, not a stale read.
    """
    p = os.path.join(REPO, "data", "action_owners.json")
    if not os.path.isfile(p):
        sys.exit("render_actions: data/action_owners.json is missing - it is the "
                 "source of record for owner and deadline; refusing to render")
    return json.load(open(p, encoding="utf8")).get("owners", {})


def slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


CONDS = json.load(open(os.path.join(REPO, "data", "action_conditions.json"), encoding="utf8"))
# how each action closes: auto / evidence / manual (tools/closure_types.py)
# retired id -> the action it was merged into (data/action_redirects.json)
_RP = os.path.join(REPO, "data", "action_redirects.json")
REDIRECTS = json.load(open(_RP, encoding="utf8")).get("redirects", {}) if os.path.isfile(_RP) else {}


CLOSURE = (json.load(open(os.path.join(REPO, "data", "action_owners.json"), encoding="utf8"))
           .get("closure", {}).get("actions", {}))
SOURCES = (json.load(open(os.path.join(REPO, "data", "action_owners.json"), encoding="utf8"))
           .get("sources", {}).get("actions", {}))
TICKED_DAYS = json.load(open(os.path.join(REPO, "data", "build_config.json"), encoding="utf8"))["actions"]["ticked_no_evidence_days"]
NUDGE_UNDATED_DAYS = json.load(open(os.path.join(REPO, "data", "build_config.json"), encoding="utf8"))["actions"]["nudge_undated_days"]
CLOSURE_LABEL = {"auto": "auto &mdash; the build closes it",
                 "evidence": "evidence &mdash; closes when this exists",
                 "manual": "manual &mdash; Adriaan marks it done"}
DECISIONS = json.load(open(os.path.join(REPO, "data", "decisions.json"), encoding="utf8"))
_cp = os.path.join(REPO, "data", "decision_candidates.json")
CANDIDATES = json.load(open(_cp, encoding="utf8")) if os.path.isfile(_cp) else {}
# quotations this list renders: decided answers and candidate answers from mail
QUOTES_EXTRA = {}
METRIC_DEFS = (json.load(open(os.path.join(REPO, "data", "action_metrics.json"), encoding="utf8"))
               .get("metrics", {}))


def _num(v):
    return f"{v:,}" if isinstance(v, int) else str(v)


# numbers a closing condition's own words carry that are declared elsewhere:
# the Type 3 cap and the approvals window render from where they are declared
_LIVE = [(r"(?<![\d.,])60,000(?![\d.,])", '<span data-param="cap_t">60,000</span>'),
         (r"(?<![\d.,])180(?= days)", '<span data-fig="BUILDCFG.approvals.window_days">180</span>'),
         (r"at least 8 clusters", 'at least <span data-param="sdws26_min_clusters">8</span> clusters')]


def _live(text):
    for pat, rep in _LIVE:
        text = re.sub(pat, rep, text)
    return text


def evidence_line(a):
    """The one line under a closed action saying what closed it, linked to the
    Asana task (5 Oct 2026): an Evidence comment or file on the task, an entry
    recorded in the repository, or the build's own condition. The evidence
    text is a quotation, never re-typed."""
    e, link = a.get("evidence"), a.get("asana")
    tl = (f' &middot; <a href="{link}" target="_blank" rel="noopener">Asana task</a>' if link else "")
    if e:
        key = f"evidence:{a['id']}"
        if e.get("from") == "asana":
            QUOTES_EXTRA[key] = {"doc": f"Asana task, {'Evidence comment' if e.get('kind') == 'comment' else 'attached file'} by {e.get('author') or 'not recorded'}",
                                 "version": e.get("date", ""), "dated": e.get("date", ""), "says": strip(e.get("summary", "")),
                                 "note": "Read from the Asana task by tools/asana_pull.py and recorded in data/action_owners.json (evidence)."}
            what = "Evidence comment" if e.get("kind") == "comment" else "File attached"
            body = (f'{what} by {html.escape(e.get("author") or "not recorded")}, {e.get("date")}: '
                    f'<span class="quoted" data-quote="{key}">{html.escape(strip(e.get("summary", "")))}</span>')
            src = "asana"
        else:
            QUOTES_EXTRA[key] = {"doc": "Evidence recorded in the repository (data/action_owners.json)",
                                 "version": e.get("recorded_on", ""), "dated": e.get("recorded_on", ""),
                                 "says": strip(f'{e.get("what", "")}. {e.get("source", "")}'),
                                 "note": f"Recorded by {e.get('recorded_by') or 'not recorded'}."}
            body = (f'recorded in the repository {e.get("recorded_on") or ""}: '
                    f'<span class="quoted" data-quote="{key}">{html.escape(strip(e.get("what", "")))}</span>')
            src = "repo"
    elif a.get("auto") and (a.get("cond") or {}).get("satisfied"):
        c = a["cond"]
        body = ("the build&rsquo;s own condition is met"
                + (f', closed by the build on {c["closed_since"]}' if c.get("closed_since") else ""))
        src = "build"
    else:
        return ""
    return (f'<div class="evline muted" data-evsrc="{src}" style="font-size:.82em;margin-top:4px">'
            f'<b>Evidence</b>: {body}{tl}</div>')


def row(a, today, owner_cell=True):
    overdue = (a["state"] == "ACT" and a["due"] is not None and a["due"] < today)
    badge = ('<span class="pill crit" style="margin-left:6px">OVERDUE</span>'
             if overdue else "")
    label = (f'<span class="muted" style="font-size:.82em;margin-left:6px">'
             f'{a["label"]}</span>' if a["label"] else "")
    if a.get("ticked"):
        tk = a["ticked"]
        when = datetime.date.fromisoformat(tk["at"]).strftime("%-d %b %Y") if tk.get("at") else "date not recorded"
        tickline = (f'<div class="ticked">ticked in Asana, no evidence yet'
                    f'<span class="tickwho"> &mdash; by {html.escape(tk.get("by") or "not recorded")}, {when}'
                    + (f' &middot; <a href="{a["asana"]}" target="_blank" rel="noopener">Asana task</a>' if a.get("asana") else "")
                    + '</span></div>')
    else:
        tickline = ""
    dl = a["deadline"] or '<span class="muted">no date set</span>'
    if overdue:
        dl = f'<b style="color:var(--crit)">{dl}</b>'
    own = (f'<td><span class="ownercell">{face(a["lead"])}'
           f'<span>{a["owner"]}</span></span></td>') if owner_cell else ""
    c = a.get("cond") or {}
    kind = c.get("kind", "none")
    live_says = None
    if not c:
        closes = ('<span class="muted">no closing condition &mdash; a person has '
                  'to close this one</span>')
    elif kind == "none":
        closes = f'<span class="muted">{_live(c["says"])}</span>'
    else:
        ev = c.get("evidence", "")
        says = c["says"]
        cc = CONDS.get(a["id"]) or {}
        if kind == "data" and cc.get("metric") in METRIC_DEFS:
            # the readout is built from the data, so the value and the target
            # are live figures that open their derivation, not typed text
            mk, tgt = cc["metric"], cc["target"]
            val = METRIC_DEFS[mk].get("value")
            tspan = (f'<span data-fig="ACTCOND[\'{a["id"]}\'].target">'
                     f'{_num(tgt)}</span>')
            ev = (f'<span class="mono">{mk}</span> = '
                  + (f'<span data-fig="METRICS.{mk}">{_num(val)}</span>'
                     if val is not None else "could not be counted this build")
                  + f' ({_live(METRIC_DEFS[mk].get("says", ""))}); target '
                  + f'{cc["op"].replace("<", "&lt;").replace(">", "&gt;")} {tspan}')
            says = re.sub(r"(?<![\d.,])" + re.escape(_num(tgt)) + r"(?![\d.,])",
                          lambda _m: tspan, _live(says), count=1)
        elif kind == "children":
            # closed / total come from the evaluator's state, inlined as ACTKIDS
            aid = a["id"]
            ev = (f'<span data-fig="ACTKIDS[\'{aid}\'].closed">{c.get("children_closed", 0)}</span> '
                  f'of <span data-fig="ACTKIDS[\'{aid}\'].of">{len(c.get("children") or [])}</span> '
                  f'steps closed')
            says = _live(says)
        else:
            says = _live(says)
        live_says = says
        if kind == "decision":
            dec = (DECISIONS.get("decisions") or {}).get(a["id"])
            cand = (CANDIDATES.get("candidates") or {}).get(a["id"])
            if dec:
                key = f"decision:{a['id']}"
                QUOTES_EXTRA[key] = {"doc": f"Decision recorded in data/decisions.json, from {dec.get('source', 'the decision log')}",
                                     "version": dec.get("decided_on", ""), "dated": dec.get("decided_on", ""),
                                     "says": strip(dec.get("answer", "")),
                                     "note": f"Decided by {dec.get('decided_by', 'not recorded')}. The answer is quoted as recorded."}
                ev = (f'decided {dec.get("decided_on")} by {dec.get("decided_by")}: '
                      f'<span class="quoted" data-quote="{key}">{dec.get("answer", "")}</span>')
            elif cand:
                key = f"candidate:{a['id']}"
                QUOTES_EXTRA[key] = {"doc": f"email \u201c{cand.get('subject', '')}\u201d from {cand.get('from', '')}",
                                     "version": cand.get("on", ""), "dated": cand.get("on", ""),
                                     "says": strip(cand.get("summary", "")),
                                     "note": "A possible answer found in the mail thread. It closes nothing until it is confirmed and logged in data/decisions.json."}
                ev = ('possible answer received &mdash; confirm to close: '
                      f'<span class="quoted" data-quote="{key}">{cand.get("summary", "")}</span>')
        mark = ("&#10003; " if c.get("satisfied") else
                "&mdash; " if c.get("satisfied") is None else "")
        closes = (f'<span class="ckind ck-{kind}">{kind}</span> {says}'
                  f'<div class="muted" style="font-size:.82em">{mark}{ev}</div>')
        if c.get("reopened_on"):
            closes += ('<div class="muted" style="font-size:.82em">'
                       f'<b>reopened {c["reopened_on"]}</b> &mdash; it had been '
                       f'closed since {c.get("was_closed_since") or "an earlier build"}'
                       '</div>')
    det = a.get("detail") or ""
    # where the answer came from: sender, date, subject, one-line answer
    # (data/action_owners.json "sources"); the answer is a quotation
    srcs = SOURCES.get(a["id"]) or []
    if srcs and det:
        lines = []
        for i, sr in enumerate(srcs):
            key = f"source:{a['id']}:{i}"
            QUOTES_EXTRA[key] = {"doc": f"{sr['sender']}, \u201c{sr['subject']}\u201d",
                                 "version": sr["date"], "dated": sr["date"],
                                 "says": strip(sr["answer"]),
                                 "note": "Recorded in data/action_owners.json (sources)."}
            lines.append(f'{sr["sender"]}, &ldquo;{sr["subject"]}&rdquo;, {sr["date"]}: '
                         f'<span class="quoted" data-quote="{key}">{sr["answer"]}</span>')
        det += ('<p class="sources muted" style="font-size:.85em;margin:8px 0 0"><b>Source</b>: '
                + "; ".join(lines) + '</p>')
    cl = CLOSURE.get(a["id"])
    if cl and det:
        det += (f'<p class="closes-when muted" style="font-size:.85em;margin:8px 0 0">'
                f'<b>Closes when</b> <span class="ckind">{CLOSURE_LABEL[cl["type"]]}</span>: '
                f'{live_says if cl["type"] == "auto" and live_says else _live(cl["closes_when"])}'
                + (f'; closed by the build on {cl["detected_closed_on"]}'
                   if cl["type"] == "auto" and cl.get("detected_closed_on") else "")
                + '.</p>')
    if a.get("asana") and det:
        det += (f'<p class="asana muted" style="font-size:.85em;margin:8px 0 0"><b>Asana</b>: '
                f'<a href="{a["asana"]}" target="_blank" rel="noopener">the task for this action</a> '
                f'&mdash; owner, due date and completion are read from it at each build.</p>')
    if a.get("evidence") and det:
        e = a["evidence"]
        det += (f'<p class="evidence muted" style="font-size:.85em;margin:8px 0 0"><b>Evidence recorded</b> '
                f'{e.get("recorded_on") or ""}: {e.get("source") or ""}.</p>')
    evline = evidence_line(a) if a["state"] == "OK" else tickline
    actid = (f' <span class="act-id muted mono" style="font-size:.75em">{a["id"]}</span>'
             if a.get("plain_title") else "")
    body = (f'<details class="act-detail" id="{a["id"]}">'
            f'<summary>{a["title_html"]}{actid}</summary>{det}</details>'
            if det else f'<b>{a["title_html"]}</b>{actid}')
    # a retired id lands here: one anchor per redirect, in the main list only
    alias = "".join(f'<span id="{old}" class="act-alias"></span>'
                    for old, new in REDIRECTS.items() if new == a["id"]) if owner_cell else ""
    gate = (f' data-act="{a["id"]}" data-owner="{html.escape(a["owner"], quote=True)}"'
            f' data-due="{a["due"].isoformat() if a.get("due") else ""}"'
            + (f' data-asana="{a["asana_gid"]}"' if a.get("asana_gid") else "")
            + (' data-evidence="1"' if a.get("evidence") else "")
            + (' data-auto="1"' if a.get("auto") else "")
            + (f' data-ticked="{(a["ticked"].get("at") or "")}"' if a.get("ticked") else "")
            + f' data-title="{html.escape(a["title"], quote=True)}"') if owner_cell else ""
    return (f'<tr data-state="{a["state"]}" data-own="{slug(a["lead"])}"{gate}'
            f'{" data-nodate=\"1\"" if a["nodate"] else ""}>'
            f'<td>{alias}{body}'
            f'<div class="muted" style="font-size:.82em">{a["criterion"]}</div>{evline}</td>'
            + own
            + f'<td class="st"><span class="pill {CLASS[a["state"]]}">{a["state"]}</span>'
              f'{badge}{label}</td>'
              # a date is a number and never wraps; a deadline written as words
              # ("before the piped VPA-DD is submitted") is text and wraps
              + (f'<td class="num">{dl}</td>' if a.get("due") or not a.get("deadline")
                 else f'<td class="dltext">{dl}</td>')
              + f'<td class="closes">{closes}</td></tr>')


def block(idx, today=None):
    """The list, grouped and filtered.

    93 rows in one flat table is a wall, and a wall is not a list. So the
    rows are rendered once, carrying data-state / data-own / data-nodate,
    and three controls decide what is on screen: ACT only (the default),
    everything, or the same rows grouped under their lead owner. The header
    carries the counts, so the shape of the work is legible without opening
    anything - including the count of rows with no proposed date, which is
    one decision for Jan rather than twenty-five separate ones.
    """
    today = today or datetime.date.today()
    acts = actions(idx)
    order = {"ACT": 0, "WATCH": 1, "OK": 2}
    acts.sort(key=lambda a: (order[a["state"]],
                             a["due"] or datetime.date(2099, 1, 1), a["title"]))
    n_act = sum(1 for a in acts if a["state"] == "ACT")
    n_watch = sum(1 for a in acts if a["state"] == "WATCH")
    n_ok = sum(1 for a in acts if a["state"] == "OK")
    n_over = sum(1 for a in acts
                 if a["state"] == "ACT" and a["due"] and a["due"] < today)
    n_nodate = sum(1 for a in acts if a["nodate"])
    by_lead = collections.OrderedDict()
    for a in sorted(acts, key=lambda a: (-sum(1 for x in acts
                                              if x["lead"] == a["lead"]),
                                         a["lead"], order[a["state"]],
                                         a["due"] or datetime.date(2099, 1, 1))):
        by_lead.setdefault(a["lead"], []).append(a)

    # Column widths are set, not measured (29 Sep 2026): measured widths gave
    # the Item column a sliver and Status a wide empty band. Item carries the
    # text, so it is widest; data-cols="set" keeps layoutTables() from
    # re-measuring. Percentages, so print keeps the proportions.
    # 30 Sep 2026: Item 50 / Owner 12 / Status 6 / Deadline 8 / What would close it 24.
    head = ('<colgroup><col style="width:50%"><col style="width:12%"><col style="width:6%">'
            '<col style="width:8%"><col style="width:24%"></colgroup>'
            '<thead><tr><th>Item</th><th>Owner</th><th>Status</th>'
            '<th class="num">Deadline</th><th>What would close it</th>'
            '</tr></thead>')
    # the same proportions without the Owner column (50:6:8:24 of 88)
    head_no_owner = ('<colgroup><col style="width:56.8%"><col style="width:6.8%">'
                     '<col style="width:9.1%"><col style="width:27.3%"></colgroup>'
                     '<thead><tr><th>Item</th><th>Status</th>'
                     '<th class="num">Deadline</th><th>What would close it</th>'
                     '</tr></thead>')

    # The counts are live: they move whenever an item opens or closes. Write
    # them to data/ so they are inlined as ACTN and rendered through data-fig
    # spans, instead of being typed into the generated markup - which is what
    # the prose figure gate objects to, correctly.
    # Needs a nudge: evidence and manual items nobody's data will close -
    # past their date, or undated and in the repository for over 30 days
    nudge = []
    for a in acts:
        cl = CLOSURE.get(a["id"]) or {}
        if cl.get("type") not in ("evidence", "manual") or a["state"] == "OK":
            continue
        seen = datetime.date.fromisoformat(cl["first_seen"]) if cl.get("first_seen") else today
        if a["due"] and a["due"] < today:
            nudge.append((a, f'past its date, {a["deadline"]}'))
        elif not a["due"] and (today - seen).days > NUDGE_UNDATED_DAYS:
            nudge.append((a, f'no date set, on the list since {seen.strftime("%-d %b %Y")}'))
    # ticked in Asana without evidence: open in every count; listed for
    # Adriaan once a tick has gone TICKED_DAYS days with no evidence
    ticked = [a for a in acts if a.get("ticked")]
    late = [a for a in ticked if a["ticked"].get("at")
            and (today - datetime.date.fromisoformat(a["ticked"]["at"])).days >= TICKED_DAYS]
    json.dump({"act": n_act, "watch": n_watch, "open": n_act + n_watch,
               "overdue": n_over, "closed": n_ok, "rows": len(acts),
               "nodate": n_nodate, "nudge": len(nudge), "ticked": len(ticked), "ticked_late": len(late)},
              open(os.path.join(REPO, "data", "action_counts.json"), "w",
                   encoding="utf8"), indent=1, sort_keys=True)
    F = lambda k: f'<span data-fig="ACTN.{k}"></span>'   # noqa: E731

    out = [
        '<section data-scopes="all mad madx mar enduro" id="actions" data-programme-wide="1">',
        '  <div class="sechead"><div><h2>Actions &mdash; the one list</h2>'
        '<p>Every open item in this report, in one place. Open a row for the '
        'detail; there is no second list to keep in step with this one. '
        f'<b>{F("open")}</b> open &mdash; <b>{F("act")}</b> to act on, '
        f'<b>{F("watch")}</b> to watch'
        + (f', <b>{F("overdue")}</b> past their proposed date' if n_over else "")
        + f'. <b>{F("closed")}</b> closed this period.</p></div>'
        f'<span class="count">{F("rows")} rows</span></div>',
        # --- evidence / manual items nobody's data will close ------------
        '  <div class="nudge" style="margin:6px 0 10px;font-size:.9em">'
        f'<b>Needs a nudge</b> ({F("nudge")}) '
        '<span class="muted">&mdash; evidence and manual items past their date, '
        f'or undated and on the list for more than <span data-fig="BUILDCFG.actions.nudge_undated_days">{NUDGE_UNDATED_DAYS}</span> days</span>'
        + ('<ul style="margin:4px 0 0 18px;padding:0">' + "".join(
            f'<li><a href="#{a["id"]}">{a["title_html"]}</a> &mdash; {a["owner"]} '
            f'<span class="muted">&mdash; {why}</span></li>' for a, why in nudge) + '</ul>'
           if nudge else ': <span class="muted">none today.</span>')
        + '</div>',
        # --- ticked in Asana with no evidence, for Adriaan ---------------
        '  <div class="nudge" id="act-ticked" style="margin:0 0 10px;font-size:.9em">'
        f'<b>Ticked without evidence</b> ({F("ticked_late")}) '
        '<span class="muted">&mdash; for Adriaan: Asana tasks ticked complete for '
        f'<span data-fig="BUILDCFG.actions.ticked_no_evidence_days">{TICKED_DAYS}</span> days or more with no '
        'Evidence comment or attached file; a tick alone closes nothing, so these stay open '
        f'({F("ticked")} ticked without evidence in all)</span>'
        + ('<ul style="margin:4px 0 0 18px;padding:0">' + "".join(
            f'<li><a href="#{a["id"]}">{a["title_html"]}</a> &mdash; ticked by '
            f'{html.escape(a["ticked"].get("by") or "not recorded")}, '
            f'{datetime.date.fromisoformat(a["ticked"]["at"]).strftime("%-d %b %Y")}'
            + (f' &middot; <a href="{a["asana"]}" target="_blank" rel="noopener">Asana task</a>' if a.get("asana") else "")
            + '</li>' for a in late) + '</ul>'
           if late else ': <span class="muted">none today.</span>')
        + '</div>',
        # --- the shape of the work, before anything is opened ------------
        '  <div class="actstats">',
        f'    <div class="stat"><b>{F("act")}</b><span>'
        f'<span class="pill crit">ACT</span> to act on'
        + (f' &middot; {F("overdue")} past their date' if n_over else "")
        + '</span></div>',
        f'    <div class="stat"><b>{F("watch")}</b><span>'
        f'<span class="pill warn">WATCH</span> standing items</span></div>',
        f'    <div class="stat"><b>{F("closed")}</b><span>'
        f'<span class="pill ok">OK</span> closed this period</span></div>',
        f'    <div class="stat" id="act-nodate-tile"><b>{F("nodate")}</b><span>'
        f'<b>of the {F("act")} carry no proposed date.</b> Setting them is one '
        f'decision for Jan, not {F("nodate")}</span></div>',
        '  </div>',
        # --- counts per owner, in the header -----------------------------
        '  <div class="eyebrow" style="margin:16px 0 6px">Per owner</div>',
        '  <div class="ownerbar">',
        '    <button class="tg ownchip" data-own="" id="own-all" '
        f'aria-pressed="true">All owners <b>{len(acts)}</b></button>',
    ]
    for lead, rows in by_lead.items():
        na = sum(1 for a in rows if a["state"] == "ACT")
        out.append(f'    <button class="tg ownchip" data-own="{slug(lead)}" '
                   f'aria-pressed="false">{face(lead, 16)}{lead} <b>{len(rows)}</b>'
                   + (f'<span class="muted" style="font-weight:400"> &middot; '
                      f'{na} ACT</span>' if na != len(rows) else "")
                   + '</button>')
    out += [
        '  </div>',
        # --- what is on screen -------------------------------------------
        '  <div class="eyebrow" style="margin:16px 0 6px">Show</div>',
        '  <div class="actviews">',
        '    <button class="tg" id="av-act" data-view="act" aria-pressed="true">'
        f'To act on &mdash; {F("act")}</button>',
        '    <button class="tg" id="av-nodate" data-view="nodate" '
        f'aria-pressed="false">No date set &mdash; {F("nodate")}</button>',
        '    <button class="tg" id="av-all" data-view="all" aria-pressed="false">'
        f'Full list &mdash; {F("rows")}</button>',
        '    <button class="tg" id="av-owner" data-view="owner" '
        'aria-pressed="false">By owner</button>',
        '  </div>',
        '  <p class="note" id="act-count" style="margin:8px 0 0"></p>',
        ('  <p class="note" style="margin:8px 0 0"><span class="muted">'
         'Owner and deadline are kept in the report&rsquo;s own record of actions, '
         'edited only where the report is built. Status and closure are computed '
         'here and are never set by hand.</span></p>'),
        # --- the rows, once ----------------------------------------------
        '  <div id="act-flat" class="tablewrap" style="margin-top:10px">'
        '<table class="ind tfix acttbl" data-prose-table data-cols="set">' + head + '<tbody>',
    ]
    out += ["    " + row(a, today) for a in acts]
    out += ['  </tbody></table></div>',
            '  <div id="act-owner" hidden style="margin-top:10px">']
    for lead, rows in by_lead.items():
        na = sum(1 for a in rows if a["state"] == "ACT")
        nw = sum(1 for a in rows if a["state"] == "WATCH")
        no = sum(1 for a in rows if a["state"] == "OK")
        bits = ", ".join(f"{n} {s}" for n, s in
                         ((na, "ACT"), (nw, "WATCH"), (no, "OK")) if n)
        out.append(f'  <details class="expl" id="own-{slug(lead)}">'
                   f'<summary>{face(lead, 22)}{lead} &mdash; {len(rows)} item(s) '
                   f'<span class="muted">({bits})</span></summary>'
                   '<div class="tablewrap" style="margin-top:8px">'
                   '<table class="ind tfix acttbl acttbl-own" data-prose-table data-cols="set">' + head_no_owner + '<tbody>')
        out += ["    " + row(a, today, owner_cell=False) for a in rows]
        out.append("  </tbody></table></div></details>")
    out += ['  </div>',
            '  <script>window.QUOTES_EXTRA=Object.assign(window.QUOTES_EXTRA||{},'
            + json.dumps(QUOTES_EXTRA, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
            + ');</script>', ACT_JS, "</section>"]
    return "\n".join(out)


ACT_JS = r"""  <script>
  (function(){
    var sec = document.getElementById('actions');
    if (!sec) return;
    var flat = document.getElementById('act-flat');
    var own  = document.getElementById('act-owner');
    var note = document.getElementById('act-count');
    // only the generated rows carry data-state; a row inside a collapsed
    // detail's own table must never be caught by the filters
    var rows = Array.prototype.slice.call(
                 flat.querySelectorAll('tr[data-state]'));
    var views = Array.prototype.slice.call(
                  sec.querySelectorAll('.actviews button'));
    var chips = Array.prototype.slice.call(
                  sec.querySelectorAll('.ownchip'));
    var view = 'act';
    var owner = '';

    function ownerName(o){
      var b = chips.filter(function(c){ return c.dataset.own === o; })[0];
      return b ? b.textContent.replace(/\s*\d+.*$/, '').trim() : o;
    }

    function apply(){
      var shown = 0;
      if (view === 'owner') {
        flat.hidden = true; own.hidden = false;
        Array.prototype.forEach.call(own.children, function(d){
          d.hidden = !!owner && d.id !== 'own-' + owner;
        });
        shown = rows.length;
      } else {
        own.hidden = true; flat.hidden = false;
        rows.forEach(function(tr){
          var keep = view === 'all'
            || (view === 'act'    && tr.dataset.state === 'ACT')
            || (view === 'nodate' && tr.dataset.nodate === '1');
          if (keep && owner && tr.dataset.own !== owner) keep = false;
          tr.hidden = !keep;
          if (keep) shown++;
        });
      }
      views.forEach(function(b){
        b.setAttribute('aria-pressed', String(b.dataset.view === view));
      });
      var who = owner ? ownerName(owner) : null;
      note.innerHTML =
        (view === 'owner'
          ? 'Grouped by lead owner. Every row also appears in the full list.'
          : 'Showing <span data-fig="document.querySelectorAll(\'#act-flat tbody tr:not([hidden])\').length">' + shown
            + '</span> of <span data-fig="document.querySelectorAll(\'#act-flat tbody tr\').length">'
            + rows.length + '</span> rows.')
        + (who ? '  Filtered to ' + who + ' \u2014 press "All owners" to clear.'
               : '');
      sec.classList.toggle('filtered', !!owner);
    }

    views.forEach(function(b){
      b.addEventListener('click', function(){ view = b.dataset.view; apply(); });
    });
    chips.forEach(function(b){
      b.addEventListener('click', function(){
        owner = b.dataset.own;                 // '' on the All owners chip
        if (owner) {
          view = 'owner';
          apply();
          var d = document.getElementById('own-' + owner);
          if (d) { d.open = true; d.scrollIntoView({block:'nearest'}); }
        } else {
          apply();
        }
        chips.forEach(function(c){
          c.setAttribute('aria-pressed', String(c === b));
        });
      });
    });
    apply();
  })();
  </script>"""


def splice(b):
    p = os.path.join(REPO, "index.html")
    idx = open(p, encoding="utf8").read()
    if BEGIN not in idx or END not in idx:
        sys.exit("index.html has no action-list markers")
    a = idx.index(BEGIN) + len(BEGIN)
    z = idx.index(END)
    return idx[a:z], idx[:a] + "\n" + b.strip() + "\n" + idx[z:]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    idx = open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    b = block(idx)
    cur, whole = splice(b)
    want = "\n" + b.strip() + "\n"
    if mode == "--write":
        open(os.path.join(REPO, "index.html"), "w", encoding="utf8").write(whole)
        print("index.html: action list %s (%d rows)"
              % ("unchanged" if _same(cur, want) else "rewritten", len(actions(idx))))
        return 0
    if mode == "--check":
        if _same(cur, want):
            print("index.html action list matches its generator")
            return 0
        print("\n".join(list(difflib.unified_diff(
            cur.splitlines(), want.splitlines(), "index.html", "render_actions.py",
            lineterm="", n=1))[:30]))
        print("\nRun: python3 tools/render_actions.py --write")
        return 1
    sys.exit("usage: render_actions.py --write | --check")


if __name__ == "__main__":
    sys.exit(main())
