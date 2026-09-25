# -*- coding: utf-8 -*-
"""Render the week caption from data/data_freshness.json.

The caption states the age of the data rather than implying it is current.
It used to be written in the browser from max(PUMPS.last_visit), which is a
maintenance-visit date dressed up as "activity logged in mWater".

    python3 tools/render_freshness.py --write | --check
"""
import datetime, difflib, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# a region that differs only in prerendered figure values is not drift
from prerender_figures import same as _same  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEGIN = ("<!-- BEGIN GENERATED week-caption :: tools/render_freshness.py "
         ":: do not edit between these markers -->")
END = "<!-- END GENERATED week-caption -->"
NAMES = {"preventive-maintenance": "preventive maintenance",
         "repair-after-breakdown": "repairs",
         "call-centre": "call-centre contacts",
         "premiere-rehabilitation": "first rehabilitations"}


def nice(d):
    x = datetime.date.fromisoformat(d)
    return f"{x.day} {x.strftime('%B')} {x.year}"


def vintage():
    """The vintage floor: the OLDEST pull across every extract the build reads.

    The caption used to lead with extract_newest, which is the newest source.
    That states a currency no single source has - one extract pulled today and
    another left over from last week read as "data to today". The floor is the
    only date true of all of them.
    """
    p = os.path.join(REPO, "data", "extract_vintage.json")
    return json.load(open(p, encoding="utf8")) if os.path.isfile(p) else None


def caption():
    f = json.load(open(os.path.join(REPO, "data", "data_freshness.json")))
    vin = vintage()
    per = f.get("per_source") or {}
    gaps = f.get("known_gaps") or {}
    ex = f["extract_newest"]
    fresh = [k for k, v in per.items() if v.get("behind_days") == 0]
    late = sorted(((v.get("behind_days") or 0), k) for k, v in per.items()
                  if v.get("behind_days"))
    bits = []
    for k, v in sorted(per.items()):
        if not v.get("page"):
            continue
        tag = (f' &mdash; <b><span data-fig="FRESH.per_source[\'{k}\'].behind_days">{v["behind_days"]}</span> days behind</b>'
               if v.get("behind_days") else " &mdash; current")
        bits.append(f'{NAMES.get(k, k)} to {nice(v["page"])}{tag}')
    body = "; ".join(bits)
    import build_config as _bc
    act = _bc.load()["activity"]
    wk = f'<span data-fig="BUILDCFG.activity.week_days">{act["week_days"]}</span>'
    head = ('<p id="weekcap">Activity in the <b>' + wk + ' days to ' + nice(ex) + '</b>, '
            'against the previous ' + wk + ' days and the last '
            f'<span data-fig="BUILDCFG.activity.window_days">{act["window_days"]}</span>. ')
    if vin and vin.get("data_to"):
        n_ex = len(vin.get("per_extract") or {})
        spread = vin.get("spread_days")
        head += ('<b>Data to ' + nice(vin["data_to"]) + '.</b> '
                 + (f'That is the oldest of the <span data-fig="Object.keys(PULLS).length">{n_ex}</span> extracts this edition is '
                    f'built from, not the newest: '
                    + ", ".join(vin.get("oldest_sources") or [])
                    + f' was pulled <span data-fig="VINTAGE.spread_days">{spread}</span> day(s) before the most recent one, '
                      'so nothing here is claimed to be more current than that. '
                    if spread else
                    f'All <span data-fig="Object.keys(PULLS).length">{n_ex}</span> extracts were pulled the same day, so every '
                    'source is of one vintage. '))
    if not late:
        return (head + '<span class="muted">Every source is level with mWater as '
                'of ' + nice(f["checked"]) + ': ' + body + '.</span></p>')
    worst, wname = late[-1]
    known = wname in gaps
    return (head + f'<b>{NAMES.get(wname, wname)} is <span data-fig="FRESH.per_source[\'{wname}\'].behind_days">{worst}</span> days behind mWater</b> '
            + ('and cannot be rebuilt by any code in this repository yet &mdash; '
               f'<a href="#{gaps[wname]["action"]}">write the builder</a>. '
               if known else
               'and should have been rebuilt &mdash; run the pull and rebuild. ')
            + '<span class="muted">By source: ' + body
            + f'. Checked against mWater on {nice(f["checked"])}; '
            f'<span data-fig="Object.values(FRESH.per_source).filter(v=>v.behind_days===0).length">{len(fresh)}</span> of <span data-fig="Object.keys(FRESH.per_source).length">{len(per)}</span> sources level.</span></p>')


def splice(b):
    p = os.path.join(REPO, "index.html")
    idx = open(p, encoding="utf8").read()
    if BEGIN not in idx:
        sys.exit("index.html has no week-caption markers")
    a = idx.index(BEGIN) + len(BEGIN)
    z = idx.index(END)
    return idx[a:z], idx[:a] + b + idx[z:]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    b = caption()
    cur, whole = splice(b)
    if mode == "--write":
        open(os.path.join(REPO, "index.html"), "w", encoding="utf8").write(whole)
        print("index.html: week caption %s"
              % ("unchanged" if _same(cur, b) else "rewritten"))
        return 0
    if mode == "--check":
        if _same(cur, b):
            print("index.html week caption matches its generator")
            return 0
        print("\n".join(list(difflib.unified_diff(
            cur.splitlines(), b.splitlines(), "index.html",
            "render_freshness.py", lineterm="", n=1))[:20]))
        return 1
    sys.exit("usage: render_freshness.py --write | --check")


if __name__ == "__main__":
    sys.exit(main())
