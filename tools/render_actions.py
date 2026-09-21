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
import datetime, difflib, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEGIN = ("<!-- BEGIN GENERATED action-list :: tools/render_actions.py "
         ":: do not edit between these markers -->")
END = "<!-- END GENERATED action-list -->"

# old state -> (new state, label kept inside it)
MAP = {"DUE": ("ACT", ""), "OVERDUE": ("ACT", ""), "STANDING": ("WATCH", ""),
       "DONE": ("OK", ""), "DECIDED": ("OK", "DECIDED")}
CLASS = {"ACT": "crit", "WATCH": "warn", "OK": "ok"}
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


def actions(idx):
    out = []
    for m in re.finditer(r'<tr id="(act-[a-z0-9-]+)">(.*?)</tr>', idx, re.S):
        aid, body = m.group(1), m.group(2)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", body, re.S)
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
        out.append(dict(id=aid, title=title, owner=strip(cells[2]) or "—",
                        state=state, label=label, deadline=dl_raw, due=due,
                        criterion=crit))
    return out


def row(a, today):
    overdue = (a["state"] == "ACT" and a["due"] is not None and a["due"] < today)
    badge = ('<span class="pill crit" style="margin-left:6px">OVERDUE</span>'
             if overdue else "")
    label = (f'<span class="muted" style="font-size:.82em;margin-left:6px">'
             f'{a["label"]}</span>' if a["label"] else "")
    dl = a["deadline"] or "&mdash;"
    if overdue:
        dl = f'<b style="color:var(--crit)">{dl}</b>'
    return (f'<tr><td><a href="#{a["id"]}">{a["title"]}</a>'
            f'<div class="muted" style="font-size:.82em">{a["criterion"]}</div></td>'
            f'<td>{a["owner"]}</td>'
            f'<td><span class="pill {CLASS[a["state"]]}">{a["state"]}</span>'
            f'{badge}{label}</td>'
            f'<td class="num">{dl}</td>'
            f'<td><a href="#{a["id"]}">the section</a></td></tr>')


def block(idx, today=None):
    today = today or datetime.date.today()
    acts = actions(idx)
    live = [a for a in acts if a["state"] != "OK"]
    closed = [a for a in acts if a["state"] == "OK"]
    order = {"ACT": 0, "WATCH": 1}
    live.sort(key=lambda a: (order[a["state"]],
                             a["due"] or datetime.date(2099, 1, 1), a["title"]))
    n_over = sum(1 for a in live
                 if a["state"] == "ACT" and a["due"] and a["due"] < today)
    head = ('<thead><tr><th>Item</th><th>Owner</th><th>Status</th>'
            '<th class="num">Deadline</th><th>Explained in</th></tr></thead>')
    out = [
        '<section data-scopes="all mad madx mar enduro" id="actions">',
        '  <div class="sechead"><div><h2>Actions &mdash; the one list</h2>'
        '<p>Every open item in this report, in one place. Each row links to the '
        'section that explains it, and every section links back here. '
        f'<b>{len(live)}</b> open &mdash; '
        f'<b>{sum(1 for a in live if a["state"] == "ACT")}</b> to act on, '
        f'<b>{sum(1 for a in live if a["state"] == "WATCH")}</b> to watch'
        + (f', <b>{n_over}</b> past their proposed date' if n_over else "")
        + f'. <b>{len(closed)}</b> closed this period.</p></div></div>',
        '  <div class="tablewrap"><table class="ind">' + head + '<tbody>',
    ]
    out += ["    " + row(a, today) for a in live]
    out.append("  </tbody></table></div>")
    if closed:
        out.append('  <details style="margin-top:14px"><summary style="cursor:pointer;'
                   'font-weight:600">Closed this period &mdash; '
                   f'{len(closed)} item(s)</summary>')
        out.append('  <div class="tablewrap" style="margin-top:10px">'
                   '<table class="ind">' + head + "<tbody>")
        out += ["    " + row(a, today) for a in closed]
        out.append("  </tbody></table></div></details>")
    out.append("</section>")
    return "\n".join(out)


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
