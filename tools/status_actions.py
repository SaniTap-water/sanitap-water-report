# -*- coding: utf-8 -*-
"""Status -> action gate (Adriaan Mol, 30 Sep 2026).

Every status cell in a requirements or evidence table is one of two kinds:

  complete   "applied", "in place", "sourced and evidenced" (data/status_actions.json)
  otherwise  "partial", "not yet evidenced", "sourced, not re-measured ...", ...
             it names an OPEN action (data/status_actions.json, rows) and the
             cell links to that action in the Action list.

The gated tables carry class "statusgate" and a data-gate name. A table that
looks like one (a "Status" or "Evidence status" column after a "Requirement"
or "Input" column) but is not marked fails the check, so a new requirements
table cannot slip past the gate.

    python3 tools/status_actions.py --write   # (re)write the links into the cells
    python3 tools/status_actions.py --check   # the gate; non-zero on any failure

--check fails on:
  * a non-complete status with no mapping row, or mapped to an action that does
    not exist or is not open (state OK in the action list);
  * a non-complete status cell without its link;
  * a mapping row that matches no row on the page;
  * a requirements-shaped table without class statusgate.
Closing an action while its status is still non-complete therefore fails the
build - unless the status text changed in the same commit: then the row's
status differs from HEAD's page and the check says so instead of failing.
"""
import html, json, os, re, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
MAP = os.path.join(REPO, "data", "status_actions.json")
LINK_RX = re.compile(r'\s*<span class="statact">.*?</span><!--/statact-->', re.S)


def text(x):
    x = LINK_RX.sub("", x)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", x))).strip()


def gated_tables(page):
    """(gate, table start, table end) for every table marked statusgate."""
    for m in re.finditer(r'<table\b[^>]*\bclass="[^"]*\bstatusgate\b[^"]*"[^>]*>', page):
        g = re.search(r'data-gate="([^"]+)"', m.group(0))
        yield (g.group(1) if g else "?"), m.start(), page.index("</table>", m.start())


def rows(page, a, b):
    """(row start, row end, first cell html, last cell (start, end)) for body rows."""
    t = page[a:b]
    for m in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", t, re.S):
        cells = list(re.finditer(r"<td\b[^>]*>(.*?)</td>", m.group(1), re.S))
        if len(cells) < 2:
            continue
        base = a + m.start(1)
        last = cells[-1]
        yield cells[0].group(1), (base + last.start(1), base + last.end(1))


def status_of(cell):
    """The status words: the pill's text if the cell has one, else the cell's text."""
    p = re.search(r'<span class="pill[^"]*">(.*?)</span>', LINK_RX.sub("", cell), re.S)
    return text(p.group(1)) if p else text(cell)


def complete(status, spec):
    return status.lower() in [c.lower() for c in spec["complete"]]


def match(spec, gate, req):
    for r in spec["rows"]:
        if r["table"] == gate and req.startswith(r["requirement"]):
            return r
    return None


def action_states(page):
    """action id -> state, from the rendered action list (#act-flat)."""
    a = page.find('id="act-flat"')
    # the flat list ends where the by-owner view starts; a detail can carry a
    # nested table, so the first </tbody></table> is not the list's end
    b = page.find('id="act-owner"', a)
    out = {}
    for m in re.finditer(r'<tr data-state="(\w+)"[^>]*><td>(.*?)</td>', page[a:b], re.S):
        for i in re.findall(r'id="(act-[a-z0-9-]+)"', m.group(2)):
            out.setdefault(i, m.group(1))
    return out


def link(aid):
    return (f' <span class="statact">&rarr; <a href="#{aid}" title="The action that closes this: {aid}">'
            f'open action</a></span><!--/statact-->')


def write():
    spec = json.load(open(MAP, encoding="utf8"))
    page = open(PAGE, encoding="utf8").read()
    edits = []
    for gate, a, b in gated_tables(page):
        for first, (c0, c1) in rows(page, a, b):
            cell = page[c0:c1]
            st = status_of(cell)
            clean = LINK_RX.sub("", cell)
            r = match(spec, gate, text(first))
            new = clean if complete(st, spec) or not r else clean + link(r["action"])
            if new != cell:
                edits.append((c0, c1, new))
    for c0, c1, new in sorted(edits, reverse=True):
        page = page[:c0] + new + page[c1:]
    open(PAGE, "w", encoding="utf8").write(page)
    print(f"status_actions: {len(edits)} status cell(s) rewritten")


def head_statuses():
    """(gate, requirement) -> status on HEAD's page, for the same-commit exemption."""
    try:
        old = subprocess.run(["git", "-C", REPO, "show", "HEAD:index.html"], capture_output=True,
                             text=True, check=True).stdout
    except Exception:
        return {}
    out = {}
    for gate, a, b in gated_tables(old):
        for first, (c0, c1) in rows(old, a, b):
            out[(gate, text(first))] = status_of(old[c0:c1])
    return out


def check():
    spec = json.load(open(MAP, encoding="utf8"))
    page = open(PAGE, encoding="utf8").read()
    states = action_states(page)
    details = json.load(open(os.path.join(REPO, "data", "action_details.json"), encoding="utf8"))
    before = None
    fails, notes, used = [], [], set()
    n_ok = n_open = 0
    for gate, a, b in gated_tables(page):
        for first, (c0, c1) in rows(page, a, b):
            req, cell = text(first), page[c0:c1]
            st = status_of(cell)
            if complete(st, spec):
                n_ok += 1
                continue
            r = match(spec, gate, req)
            if not r:
                fails.append(f'{gate}: "{req[:60]}" is "{st[:50]}" and names no action (data/status_actions.json)')
                continue
            used.add(id(r))
            aid = r["action"]
            if aid not in details:
                fails.append(f'{gate}: "{req[:60]}" maps to {aid}, which does not exist')
                continue
            state = states.get(aid)
            if state is None:
                fails.append(f'{gate}: {aid} is not in the action list')
            elif state == "OK":
                if before is None:
                    before = head_statuses()
                if before.get((gate, req)) not in (None, st):
                    notes.append(f'{gate}: {aid} closed and "{req[:40]}" changed in this commit '
                                 f'("{before.get((gate, req))}" -> "{st}")')
                else:
                    fails.append(f'{gate}: {aid} is closed but "{req[:60]}" is still "{st[:50]}"')
            if f'href="#{aid}"' not in cell:
                fails.append(f'{gate}: the status cell of "{req[:60]}" does not link to {aid} '
                             "(run tools/status_actions.py --write)")
            n_open += 1
    for r in spec["rows"]:
        if id(r) not in used:
            fails.append(f'mapping row {r["table"]} / "{r["requirement"]}" matches no non-complete row on the page')
    # a requirements-shaped table that is not gated
    for m in re.finditer(r"<table\b[^>]*>\s*(?:<colgroup>.*?</colgroup>)?\s*<thead><tr>(.*?)</tr>", page, re.S):
        heads = [text(h).lower() for h in re.findall(r"<th\b[^>]*>(.*?)</th>", m.group(1), re.S)]
        if heads and heads[0] in ("requirement", "input") and (
                "status" in heads or "evidence status" in heads) and "statusgate" not in m.group(0)[:300]:
            fails.append(f"a requirements table ({', '.join(heads)}) is not marked statusgate")
    print(f"status_actions: {n_ok} complete, {n_open} mapped to an open action, {len(fails)} failure(s)")
    for n in notes:
        print("  note:", n)
    for f in fails:
        print("  FAIL:", f)
    return 1 if fails else 0


if __name__ == "__main__":
    if "--write" in sys.argv:
        write()
    sys.exit(check() if "--check" in sys.argv or "--write" not in sys.argv else 0)
