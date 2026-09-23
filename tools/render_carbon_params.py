# -*- coding: utf-8 -*-
"""Data the carbon programme needs from us, and whether we are supplying it.

This report tracks what the field operation must measure and whether it is
measuring it. It does NOT run the carbon programme: methodology interpretation,
the design review and the Gold Standard relationship are the Head of Carbon's
remit. Where the two meet there is one question, and this section answers it -
can we supply the data, and if not what is missing and who owns it.

One row per parameter, from data/carbon_parameters.json. Nothing in the table
is a stored figure:

  coverage   the named population over the named relevant population, both
             computed from data/populations.json every build
  freshness  the newest record on the source form, from the extract manifest,
             and whether the build pulls that form at all

Readiness falls out of those two rather than being asserted, so a row cannot
say READY while its evidence says otherwise.

    python3 tools/render_carbon_params.py --write | --check
"""
import datetime, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "index.html")
BEGIN = ("<!-- BEGIN GENERATED carbon-params :: tools/render_carbon_params.py :: "
         "do not edit between these markers -->")
END = "<!-- END GENERATED carbon-params -->"
MW = "https://portal.mwater.co/#/forms/"

# form id -> the extract the build pulls it into, for freshness
FORM_EXTRACT = {
    "de26d89a5c8a4452b42158c622be20d0": "pm.csv",
    "958b4763788348d699e7d8c5821f92ee": "reparation_apres_panne.csv",
    "c08b3fe26d0f42c084074701f29eb75e": "appel_signalement_pannes.csv",
    "63747997e70e478fbb2ebf71581ceeb0": "premiere_rehabilitation.csv",
    "8764843c94484f5b984078c68f13b2ca": "forage_moramanga.csv",
    "7b33c5d7e5074808a94915939a5a0783": "wq_results.json",
    "283c5670de82489d833e986cb76a67d8": "hygiene.json",
    "198b016d72af41baa2608a8c9c35f8cb": "identification.json",
    "86cf66efdd3749dd8a121314bab3675a": "combined_rehab.json",
    "2eeb86824b4545eca33db9e7cf7dcbd4": "cbn_gender.json",
}


def esc(x):
    return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def nice(d):
    if not d:
        return None
    x = datetime.date.fromisoformat(str(d)[:10])
    return f"{x.day} {x.strftime('%b')} {x.year}"


def readiness(p, cov, fresh_days, pulled):
    """READY / PARTIAL / NOT COLLECTED / NO ROUTE, from the evidence only."""
    if not p.get("form") and not p.get("population"):
        return ("none", "Not collected")
    if p.get("population") is None:
        return ("noroute", "No route")
    if cov is None:
        return ("noroute", "No route")
    if cov >= 99.5:
        return ("ready", "Ready")
    if cov >= 50:
        return ("partial", "Partial")
    return ("thin", "Thin")


def block():
    reg = json.load(open(os.path.join(REPO, "data", "carbon_parameters.json"),
                        encoding="utf8"))
    pops = json.load(open(os.path.join(REPO, "data", "populations.json"),
                          encoding="utf8"))["populations"]
    man = json.load(open(os.path.join(REPO, "data", "extract_manifest.json"),
                         encoding="utf8"))["files"]

    rows, counts = [], {}
    for p in reg["parameters"]:
        pop = pops.get(p["population"]) if p.get("population") else None
        rel = pops.get(p["relevant"]) if p.get("relevant") else None
        cov = (100.0 * pop["size"] / rel["size"]) if (pop and rel and rel["size"]) else None

        ex = FORM_EXTRACT.get(p.get("form"))
        info = man.get(ex) if ex else None
        newest = info.get("newest_submitted") if info else None
        pulled = ex is not None
        age = None
        if newest:
            age = (datetime.date.today()
                   - datetime.date.fromisoformat(newest)).days

        cls, label = readiness(p, cov, age, pulled)
        counts[label] = counts.get(label, 0) + 1

        src = (f'<a href="{MW}{p["form"]}" target="_blank" rel="noopener">'
               f'{esc(p["source_label"])}</a>' if p.get("form")
               else f'<span class="muted">{esc(p["source_label"])}</span>')

        if cov is None:
            covcell = '<span class="muted">not derivable</span>'
        else:
            covcell = (f'<b><span data-fig="POPS.populations[\'{p["population"]}\'].size">'
                       f'</span></b> of <span data-fig="POPS.populations'
                       f'[\'{p["relevant"]}\'].size"></span>'
                       f'<br><span class="muted">{cov:.0f}%</span>')

        also = p.get("also_from") or []
        alt = [(k, man.get(FORM_EXTRACT.get(k), {}).get("newest_submitted"))
               for k in also]
        alt = [(k, d) for k, d in alt if d]
        if not p.get("form"):
            frcell = (f'<span class="muted">{esc(p.get("freshness_note") or "not collected")}'
                      f'</span>')
        elif not pulled:
            frcell = ('<span class="muted">the build does not pull this form, '
                      'so its freshness is unknown</span>')
        elif newest:
            d = "day" if age == 1 else "days"
            frcell = (f'{esc(nice(newest))}<br><span class="muted">'
                      f'{age} {d} ago</span>')
        else:
            frcell = '<span class="muted">no records on this form yet</span>'
        if alt:
            best = max(d for _k, d in alt)
            frcell += (f'<br><span class="muted" style="font-size:.86em">the evidence '
                       f'behind the coverage is historic, newest {esc(nice(best))}</span>')

        gap = (f'{esc(p["gap"])}' if p.get("gap")
               else '<span class="muted">&mdash;</span>')
        if p.get("action"):
            gap += (f'<br><a href="#{esc(p["action"])}">'
                    f'{esc(p["action"])}</a>')

        rows.append(
            f'<tr data-ready="{cls}">'
            f'<td><b>{esc(p["name"])}</b><br>'
            f'<span class="mono muted" style="font-size:.78em">v1 {esc(p["v1"])}'
            f' &middot; v2 {esc(p["v2"])}</span>'
            f'<div class="muted" style="font-size:.86em;margin-top:3px">'
            f'{esc(p["measure"])}</div></td>'
            f'<td>{src}</td>'
            f'<td class="num">{covcell}</td>'
            f'<td>{frcell}</td>'
            f'<td><span class="pill rd-{cls}">{label}</span></td>'
            f'<td>{gap}<br><span class="muted" style="font-size:.86em">'
            f'{esc(p["owner"])}</span></td></tr>')

    chips = "".join(
        f'<button class="chip cp" data-r="{c}" aria-pressed="false">{l} '
        f'<span class="mono">{counts.get(l, 0)}</span></button>'
        for c, l in (("ready", "Ready"), ("partial", "Partial"),
                     ("thin", "Thin"), ("noroute", "No route"),
                     ("none", "Not collected")) if counts.get(l))

    notready = sum(v for k, v in counts.items() if k != "Ready")
    return f"""{BEGIN}
<section data-scopes="all mad madx mar" id="carbon-params">
  <div class="sechead"><div><h2>Data the carbon programme needs from us</h2>
  <p>One row for every parameter the methodology requires us to evidence. This report does not run
  the carbon programme &mdash; methodology interpretation, the design review and the Gold Standard
  relationship are the Head of Carbon's. Where the two meet there is one question, and this is it:
  <b>can we supply the data, and if not, what is missing and who owns it</b>.
  <span class="muted">Coverage and freshness are computed every build from the populations and the
  extract manifest; nothing in this table is typed. A new requirement is a row in
  <span class="mono">data/carbon_parameters.json</span>, not a rebuild of this section.</span></p>
  </div><span class="count">{notready} of {len(rows)} not ready</span></div>
  <div class="actviews" style="margin:10px 0 12px">{chips}
  <button class="chip cp" data-r="all" aria-pressed="true">Show all</button></div>
  <div class="tablewrap" style="max-height:none"><table class="ind" id="cptbl">
  <thead><tr><th>Parameter &mdash; and what must be measured</th><th>Where it comes from</th>
  <th class="num">Coverage</th><th>Most recent record</th><th>Readiness</th>
  <th>Gap, and who owns it</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table></div>
  <p class="note"><b>Readiness is derived, not asserted.</b> A row reads Ready only when a
  population covers the relevant set; <i>No route</i> means no population reads that form, so
  coverage cannot be computed at all; <i>Not collected</i> means no form captures it.
  <span class="muted">{esc(reg["source"])}</span></p>
</section>
{END}"""


def apply(write):
    page = open(PAGE, encoding="utf8").read()
    new = block()
    if BEGIN in page:
        i, j = page.index(BEGIN), page.index(END) + len(END)
    else:
        sys.exit("render_carbon_params: markers not present; place them first")
    if page[i:j].strip() == new.strip():
        print("index.html carbon-params matches its generator")
        return 0
    if not write:
        print("index.html carbon-params DIFFERS from its generator")
        return 1
    open(PAGE, "w", encoding="utf8").write(page[:i] + new + page[j:])
    print("index.html: carbon-params rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(apply("--write" in sys.argv))
