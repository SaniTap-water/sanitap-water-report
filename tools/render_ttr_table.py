# -*- coding: utf-8 -*-
"""The time-to-repair table, from the live repair form.

WHY THIS EXISTS
---------------
The "Time to repair" table was typed into the page: seven rows of n, median,
p90, mean and max, none of it recomputed by anything, so it could only go
stale. It is now generated from the extract on every build, and the figures
are written to data/ttr_table.json as well so the page can reach them.

THE SET: every final response on the live repair form (Réparation après
panne) carrying both a breakdown notification date and a completion date, the
completion not before the notification. Rows by site, and by the calendar
quarter of the completion date. p90 is the lower-rank percentile,
v[floor(0.9 * (n - 1))] of the sorted days, so it is always a day that
occurred.

This is a different set from TTR's (repairs_time_measured, both repair
sources since August 2024): this table reads the live form only, because the
quarter rows are about the current process.

    python3 tools/render_ttr_table.py --write
    python3 tools/render_ttr_table.py --check
"""
import difflib, json, math, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# a region that differs only in prerendered figure values is not drift
from prerender_figures import same as _same  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
PAGE = os.path.join(REPO, "index.html")
DATA = os.path.join(REPO, "data", "ttr_table.json")
BEGIN = ("<!-- BEGIN GENERATED ttr-table :: tools/render_ttr_table.py "
         ":: do not edit between these markers -->")
END = "<!-- END GENERATED ttr-table -->"


def stats(v):
    v = sorted(v)
    med = statistics.median(v)
    return {"n": len(v),
            "median": int(med) if float(med).is_integer() else round(med, 1),
            "p90": v[math.floor(0.9 * (len(v) - 1))],
            "mean": round(statistics.mean(v), 1),
            "max": v[-1]}


def compute():
    import populations as P
    site = {p["wp"]: p["site"] for p in P._page_pumps()}
    rows = []
    for src, r in P._repair_records():
        if src != "live" or r.get("status") != "final":
            continue
        d = P._repair_interval(src, r)
        if d is None:
            continue
        done = str(P._answer(r, P._Q_DONE["live"]) or "")[:10]
        q = f"{done[:4]} Q{(int(done[5:7]) - 1) // 3 + 1}"
        rows.append((d, site.get(P._point_of(r)), q))
    out = {"note": "Time to repair on the live repair form, final responses "
                   "with both dates; written by tools/render_ttr_table.py.",
           "all": stats([d for d, _s, _q in rows]),
           "by_site": {s: stats([d for d, ss, _q in rows if ss == s])
                       for s in ("Maroantsetra", "Fort-Dauphin")
                       if any(ss == s for _d, ss, _q in rows)},
           "by_quarter": {q: stats([d for d, _s, qq in rows if qq == q])
                          for q in sorted({q for *_x, q in rows})}}
    return out


def block(t):
    def row(label, s, cls=""):
        c = f' class="num{(" " + cls) if cls else ""}"'
        lab = f'<td class="{cls}">{label}</td>' if cls else f"<td>{label}</td>"
        return (f"      <tr>{lab}<td{c}>{s['n']}</td><td{c}>{s['median']}</td>"
                f"<td{c}>{s['p90']}</td><td{c}>{s['mean']}</td><td{c}>{s['max']}</td></tr>")
    a = t["all"]
    lines = [f"      <tr><td><b>All recorded repairs</b></td><td class=\"num\"><b>{a['n']}</b></td>"
             f"<td class=\"num\"><b>{a['median']}</b></td><td class=\"num\"><b>{a['p90']}</b></td>"
             f"<td class=\"num\">{a['mean']}</td><td class=\"num\">{a['max']}</td></tr>"]
    lines += [row(s, v) for s, v in t["by_site"].items()]
    lines += [row(q, v, "muted") for q, v in t["by_quarter"].items()]
    return "\n" + "\n".join(lines) + "\n      "


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    t = compute()
    want = block(t)
    idx = open(PAGE, encoding="utf8").read()
    if BEGIN not in idx or END not in idx:
        sys.exit("index.html has no ttr-table markers")
    a = idx.index(BEGIN) + len(BEGIN)
    z = idx.index(END)
    data = json.dumps(t, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    if mode == "--write":
        open(PAGE, "w", encoding="utf8").write(idx[:a] + want + idx[z:])
        open(DATA, "w", encoding="utf8").write(data)
        print("index.html: ttr-table "
              + ("unchanged" if _same(idx[a:z], want) else "rewritten"))
        return 0
    ok = _same(idx[a:z], want) and os.path.isfile(DATA) \
        and open(DATA, encoding="utf8").read() == data
    if ok:
        print("index.html ttr-table matches its generator")
        return 0
    print("\n".join(list(difflib.unified_diff(
        idx[a:z].splitlines(), want.splitlines(), "index.html",
        "render_ttr_table.py", lineterm="", n=0))[:20]) or "data/ttr_table.json differs")
    return 1


if __name__ == "__main__":
    sys.exit(main())
