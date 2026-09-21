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
import collections, datetime, difflib, json, os, re, sys

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


def actions(idx):
    out = []
    for aid, body in row_bodies(idx):
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
        title = strip(title.group(1)) if title else strip(cells[0])[:90]
        pill = re.search(r'pill\s+[a-z]+">([^<]*)<', cells[1])
        old = (pill.group(1).strip().upper() if pill else "DUE")
        state, label = MAP.get(old, ("ACT", ""))
        dl_raw = re.search(r"<b>([^<]*)</b>", cells[1])
        dl_raw = strip(dl_raw.group(1)) if dl_raw else ""
        due = parse_deadline(dl_raw)
        crit = re.findall(r'<span class="muted"[^>]*>(.*?)</span>', cells[1], re.S)
        crit = strip(crit[-1]) if crit else ""
        owner = strip(cells[2]) or "—"
        out.append(dict(id=aid, title=title, owner=owner,
                        lead=lead_owner(owner),
                        state=state, label=label, deadline=dl_raw, due=due,
                        # an item to act on with no date is a date still
                        # to be set; a closed or standing item needs none
                        nodate=(not dl_raw) and state == "ACT",
                        criterion=crit))
    st = load_state()
    wb, _wb_problem = load_owners()
    WB_PROBLEM.append(_wb_problem)
    for a in out:
        w = wb.get(a["id"])
        if w:
            if w.get("owner"):
                a["owner"] = w["owner"]
                a["from_workbook"] = True
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
    for a in out:
        # a date is only outstanding on something still to act on, so this is
        # recomputed after the conditions have had their say
        a["nodate"] = a["nodate"] and a["state"] == "ACT"
    declared = len(re.findall(r'<tr id="act-[a-z0-9-]+">', idx))
    if len(out) != declared:
        got = {a["id"] for a in out}
        missed = [m.group(1) for m in re.finditer(r'<tr id="(act-[a-z0-9-]+)">', idx)
                  if m.group(1) not in got]
        sys.exit(f"render_actions: {declared} action rows in index.html but only "
                 f"{len(out)} parsed - dropped: {', '.join(missed)}")
    return out


WB_PROBLEM = []


def load_state():
    """What the build worked out about each action this run.

    data/action_state.json is written by tools/eval_conditions.py. A row with
    a satisfied condition is CLOSED here regardless of the pill on its detail
    row, and a row whose condition has regressed is reopened - the pill in the
    body is the author's opinion, the condition is the measurement.
    """
    p = os.path.join(REPO, "data", "action_state.json")
    return (json.load(open(p)) if os.path.isfile(p) else {}).get("state", {})


MAX_WORKBOOK_AGE_DAYS = 10
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
    """Owner and deadline, as people set them, from the SharePoint workbook.

    The page is static and rebuilt weekly, so an owner or a date typed into
    the browser would be one person's private copy and gone by Tuesday. Those
    two fields therefore live in one workbook on SharePoint, read into
    data/action_owners.json through the Microsoft 365 connector each build.

    Status and closure are deliberately NOT in that workbook: if a person
    could set status there, an item could be marked done that the data says
    is not. Those stay computed.

    Returns (rows, problem) - problem is None when the cache is fresh, and a
    sentence to print on the page when it is not.
    """
    p = os.path.join(REPO, "data", "action_owners.json")
    if not os.path.isfile(p):
        return {}, ("The owner and deadline workbook could not be read, so the "
                    "owners and dates below are the ones written into the page.")
    doc = json.load(open(p))
    read = doc.get("read_on")
    try:
        age = (datetime.date.today() - datetime.date.fromisoformat(read)).days
    except (TypeError, ValueError):
        age = None
    if age is None or age > MAX_WORKBOOK_AGE_DAYS:
        return doc.get("owners", {}), (
            f"The owner and deadline workbook was last read {read or 'never'}, "
            f"which is {'unknown' if age is None else str(age) + ' days'} ago. "
            "Owners and dates below may be behind what is in the workbook.")
    return doc.get("owners", {}), None


def slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def row(a, today, owner_cell=True):
    overdue = (a["state"] == "ACT" and a["due"] is not None and a["due"] < today)
    badge = ('<span class="pill crit" style="margin-left:6px">OVERDUE</span>'
             if overdue else "")
    label = (f'<span class="muted" style="font-size:.82em;margin-left:6px">'
             f'{a["label"]}</span>' if a["label"] else "")
    dl = a["deadline"] or '<span class="muted">no date set</span>'
    if overdue:
        dl = f'<b style="color:var(--crit)">{dl}</b>'
    own = (f'<td><span class="ownercell">{face(a["lead"])}'
           f'<span>{a["owner"]}</span></span></td>') if owner_cell else ""
    c = a.get("cond") or {}
    kind = c.get("kind", "none")
    if not c:
        closes = ('<span class="muted">no closing condition &mdash; a person has '
                  'to close this one</span>')
    elif kind == "none":
        closes = f'<span class="muted">{c["says"]}</span>'
    else:
        ev = c.get("evidence", "")
        mark = ("&#10003; " if c.get("satisfied") else
                "&mdash; " if c.get("satisfied") is None else "")
        closes = (f'<span class="ckind ck-{kind}">{kind}</span> {c["says"]}'
                  f'<div class="muted" style="font-size:.82em">{mark}{ev}</div>')
        if c.get("reopened_on"):
            closes += ('<div class="muted" style="font-size:.82em">'
                       f'<b>reopened {c["reopened_on"]}</b> &mdash; it had been '
                       f'closed since {c.get("was_closed_since") or "an earlier build"}'
                       '</div>')
    return (f'<tr data-state="{a["state"]}" data-own="{slug(a["lead"])}"'
            f'{" data-nodate=\"1\"" if a["nodate"] else ""}>'
            f'<td><a href="#{a["id"]}">{a["title"]}</a>'
            f'<div class="muted" style="font-size:.82em">{a["criterion"]}</div></td>'
            + own
            + f'<td><span class="pill {CLASS[a["state"]]}">{a["state"]}</span>'
              f'{badge}{label}</td>'
              f'<td class="num">{dl}</td>'
              f'<td class="closes">{closes}</td>'
              f'<td><a href="#{a["id"]}">the section</a></td></tr>')


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

    head = ('<thead><tr><th>Item</th><th>Owner</th><th>Status</th>'
            '<th class="num">Deadline</th><th>What would close it</th>'
            '<th>Explained in</th></tr></thead>')
    head_no_owner = ('<thead><tr><th>Item</th><th>Status</th>'
                     '<th class="num">Deadline</th><th>What would close it</th>'
                     '<th>Explained in</th></tr></thead>')

    out = [
        '<section data-scopes="all mad madx mar enduro" id="actions">',
        '  <div class="sechead"><div><h2>Actions &mdash; the one list</h2>'
        '<p>Every open item in this report, in one place. Each row links to the '
        'section that explains it, and every section links back here. '
        f'<b>{n_act + n_watch}</b> open &mdash; <b>{n_act}</b> to act on, '
        f'<b>{n_watch}</b> to watch'
        + (f', <b>{n_over}</b> past their proposed date' if n_over else "")
        + f'. <b>{n_ok}</b> closed this period.</p></div>'
        f'<span class="count">{len(acts)} rows</span></div>',
        # --- the shape of the work, before anything is opened ------------
        '  <div class="actstats">',
        f'    <div class="stat"><b>{n_act}</b><span>'
        f'<span class="pill crit">ACT</span> to act on'
        + (f' &middot; {n_over} past their date' if n_over else "")
        + '</span></div>',
        f'    <div class="stat"><b>{n_watch}</b><span>'
        f'<span class="pill warn">WATCH</span> standing items</span></div>',
        f'    <div class="stat"><b>{n_ok}</b><span>'
        f'<span class="pill ok">OK</span> closed this period</span></div>',
        f'    <div class="stat" id="act-nodate-tile"><b>{n_nodate}</b><span>'
        f'<b>of the {n_act} carry no proposed date.</b> Setting them is one '
        f'decision for Jan, not {n_nodate}</span></div>',
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
        f'To act on &mdash; {n_act}</button>',
        '    <button class="tg" id="av-nodate" data-view="nodate" '
        f'aria-pressed="false">No date set &mdash; {n_nodate}</button>',
        '    <button class="tg" id="av-all" data-view="all" aria-pressed="false">'
        f'Full list &mdash; {len(acts)}</button>',
        '    <button class="tg" id="av-owner" data-view="owner" '
        'aria-pressed="false">By owner</button>',
        '  </div>',
        '  <p class="note" id="act-count" style="margin:8px 0 0"></p>',
        ('  <p class="note" style="margin:8px 0 0"><span class="pill warn">'
         'WATCH</span> ' + WB_PROBLEM[0] + '</p>') if WB_PROBLEM and WB_PROBLEM[0]
        else ('  <p class="note" style="margin:8px 0 0"><span class="muted">'
              'Owner and deadline are read from the '
              '<a href="' + (json.load(open(os.path.join(REPO, "data",
                                                         "action_owners.json")))
                             ["source"]["webUrl"]
                             if os.path.isfile(os.path.join(REPO, "data",
                                                            "action_owners.json"))
                             else "#") + '" target="_blank" rel="noopener">owner '
              'and deadline workbook</a> on SharePoint, which Adriaan and Jan edit '
              'in Excel Online. Status and closure are computed here and are not in '
              'that workbook.</span></p>'),
        # --- the rows, once ----------------------------------------------
        '  <div id="act-flat" class="tablewrap" style="margin-top:10px">'
        '<table class="ind">' + head + '<tbody>',
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
                   '<table class="ind">' + head_no_owner + '<tbody>')
        out += ["    " + row(a, today, owner_cell=False) for a in rows]
        out.append("  </tbody></table></div></details>")
    out += ['  </div>', ACT_JS, "</section>"]
    return "\n".join(out)


ACT_JS = r"""  <script>
  (function(){
    var sec = document.getElementById('actions');
    if (!sec) return;
    var flat = document.getElementById('act-flat');
    var own  = document.getElementById('act-owner');
    var note = document.getElementById('act-count');
    var rows = Array.prototype.slice.call(
                 flat.querySelectorAll('tbody tr'));
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
      note.textContent =
        (view === 'owner'
          ? 'Grouped by lead owner. Every row also appears in the full list.'
          : 'Showing ' + shown + ' of ' + rows.length + ' rows.')
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
              % ("unchanged" if cur == want else "rewritten", len(actions(idx))))
        return 0
    if mode == "--check":
        if cur == want:
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
