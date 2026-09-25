# -*- coding: utf-8 -*-
"""Regenerate the machine-extraction block of index.html from the data files.

THE ONLY PLACE THIS BLOCK IS EDITED. The corresponding region of index.html is
output, not source: it is delimited by the BEGIN/END markers below and is
overwritten wholesale by --write. Editing index.html between those markers
looks like it worked and is silently reverted the next time this runs - that
happened twice before the rule was made a check (see CONTRIBUTING.md).

Every number in the block is read from data/*.json|csv, so the page cannot
drift from the files it cites. The prose is fixed; only the figures move.

    python3 tools/render_block.py --write    # splice into index.html
    python3 tools/render_block.py --check    # exit 1 if index.html has drifted
"""
import csv, json, os, sys, collections, statistics, difflib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# a region that differs only in prerendered figure values is not drift
from prerender_figures import same as _same  # noqa: E402
from table_notes import render as _tablenote  # noqa: E402
from gen_figs import GenFigs  # noqa: E402

# every number this region states is a live figure over GEN.calendar
G = GenFigs("calendar")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEGIN = "<!-- BEGIN GENERATED machine-extraction :: tools/render_block.py :: do not edit between these markers -->"
END = "<!-- END GENERATED machine-extraction -->"

fig = json.load(open(os.path.join(REPO, "data", "calendar_extraction_figures.json")))
nc = list(csv.DictReader(open(os.path.join(REPO, "data", "calendar_not_calendar.csv"))))
nu = list(csv.DictReader(open(os.path.join(REPO, "data", "calendar_no_usable_image.csv"))))
cov = list(csv.DictReader(open(os.path.join(REPO, "data", "calendar_year_coverage.csv"))))
SELP = os.path.join(REPO, "transcription", "validation_selection.csv")
sel = list(csv.DictReader(open(SELP))) if os.path.exists(SELP) else []
in_frame = [r for r in sel if r["in_frame"] == "yes"]
out_frame = [r for r in sel if r["in_frame"] != "yes"]
kept = [r for r in in_frame if r["origin"].startswith("kept")]
drawn = [r for r in in_frame if r["origin"].startswith("drawn")]
SEEDS = sorted({r["seed"] for r in sel if r["seed"]})
sel_sites = collections.Counter(r["site"] for r in in_frame)
sel_q = collections.Counter(r["quality_quartile"] for r in in_frame)
DRAWN_ON = next((r["drawn_on"] for r in drawn if r["drawn_on"]), "")
SEED = sel[0]["seed"] if sel else ""
YRS = os.environ.get("SHEET_YEAR_OCR",
    "/home/bushp/sdws1/calendar_extract/sheet_year_ocr.csv")
yr = [r for r in csv.DictReader(open(YRS)) if r["sheet_year"]]
rel = collections.Counter(
    "same" if r["sheet_year"] == r["photo_date"][:4]
    else ("earlier" if r["sheet_year"] < r["photo_date"][:4] else "later")
    for r in yr)
tot_y = max(1, sum(rel.values()))
PCT_SAME = round(100*rel["same"]/tot_y)
PCT_EARLIER = round(100*rel["earlier"]/tot_y)
PCT_LATER = round(100*rel["later"]/tot_y)

# Emitted plain. Wrapping every number in its own data-artefact span was
# tried: it broke a dozen literal assertions elsewhere in the checker and
# moved the unsourced count by one, because these values are fields of
# data/calendar_extraction_figures.json and the census already matches them
# exactly. Only figures DERIVED from that file need an individual marking.
n = lambda v: f"{v:,}" if isinstance(v, int) and v >= 1000 else str(v)


def wp(code):
    """Link a water point to a RECORD that references it.

    The portal has no route to an individual entity - #/water_point/<uuid>
    lands on "Page not found" and the app's own route table has no entity
    route at all. A response does resolve, and opens the document that says
    something about the point.
    """
    import json as _json
    _p = os.path.join(REPO, "data", "mwater_point_responses.json")
    _m = _json.load(open(_p, encoding="utf8")) if os.path.isfile(_p) else {}
    d = _m.get(code) or {}
    for kind, what in (("works", "first-rehabilitation record"),
                       ("borehole", "borehole-progress record"),
                       ("repair", "repair record"),
                       ("pm", "maintenance visit"),
                       ("call", "call-centre record")):
        rid = d.get(kind)
        if rid:
            return (f'<a class="wp" href="https://portal.mwater.co/#/responses/'
                    f'{rid}" target="_blank" rel="noopener" title="Open the '
                    f'{what} for water point {code} in mWater">'
                    f'<span class="mono">{code}</span></a>')
    return f'<span class="mono">{code}</span>'
acc = [r for r in nc if r["reader"] == "accepted as a calendar"]
rej = [r for r in nc if r["reader"] == "rejected"]
byreason = collections.Counter(r["reason"] for r in nc)
byreason_acc = collections.Counter(r["reason"] for r in acc)
cat = collections.Counter(r["category"] for r in nu)
never = cat["no calendar was ever photographed"]
mixed = cat["some photographs are of something else"]
unread = cat["calendar photographed, not readable"]
byq = collections.Counter(r["question"] for r in nc)

frac = [float(r["fraction_covered"]) for r in cov]
covyear = collections.defaultdict(list)
for r in cov:
    covyear[r["sheet_year"]].append(float(r["fraction_covered"]))
med_all = statistics.median(frac)
part = sum(1 for x in frac if x < 0.9)
sy = fig.get("sheets_by_year", {})

# The printed-year finding, computed from the reader's outputs (25 September
# 2026: these were typed, and the reader data had moved on under them).
# Sheets printed 2027 and photographed during 2026; the marked rate over
# legible cells (marked / (marked + clear)) in months up to and including the
# photograph month against months after it, from the current day-level file.
s27 = [r for r in yr if r["sheet_year"] == "2027" and r["photo_date"][:4] == "2026"]
_s27 = {r["image_id"]: int(r["photo_date"][5:7]) for r in s27}
_dc = collections.Counter()
_DAYS = os.environ.get("EXTRACTION_DAYS",
    "/home/bushp/sdws1/calendar_extract/extraction_days2.csv")
for r in csv.DictReader(open(_DAYS)):
    pm_ = _s27.get(r["image_id"])
    if pm_ is None or r["call"] not in ("marked", "clear"):
        continue
    _dc[("early" if int(r["month"]) <= pm_ else "late", r["call"])] += 1
def _rate(k):
    m_, c_ = _dc[(k, "marked")], _dc[(k, "clear")]
    return round(100 * m_ / (m_ + c_), 2) if m_ + c_ else None
RATE_EARLY, RATE_LATE = _rate("early"), _rate("late")
STEP = round(RATE_EARLY / RATE_LATE, 1) if RATE_EARLY and RATE_LATE else None
CONF_MIN = round(min(float(r["confidence"]) for r in s27), 2) if s27 else None
CONF_MAX = round(max(float(r["confidence"]) for r in s27), 2) if s27 else None
_p26 = {r["water_point"] for r in cov if r["sheet_year"] == "2026"}
_p27 = {r["water_point"] for r in s27}
PTS_2026, PTS_2026_REATTR, PTS_AFFECTED = len(_p26), len(_p26 | _p27), len(_p27)
COVER_HIGH, COVER_LOW = 0.9, 0.5      # the coverage bands the table below uses

site_n = collections.Counter(r["site"] for r in nu)
portrait = sum(1 for r in nu if r["only_portrait_field"] == "yes")
SITECOUNTS = (", ".join(f"<b>{G.fig('nousable_' + k.lower().replace('-', '_'), v)}</b> in {k}" for k, v in site_n.most_common())
              + f", and only <b>{G.fig('only_portrait', portrait)}</b> where the portrait field is the sole source")

rows = "".join(
    f'<tr><td>{y}</td><td class="num">{len(v)}</td>'
    f'<td class="num">{statistics.median(v):.0%}</td>'
    f'<td class="num">{sum(1 for x in v if x >= .9)}</td>'
    f'<td class="num">{sum(1 for x in v if x < .5)}</td></tr>'
    for y, v in sorted(covyear.items()))

B = f'''<div class="eyebrow" style="margin:18px 0 8px">Machine extraction from the calendar photographs &mdash; internal only</div>
  <div class="panel" style="border-left:3px solid #b45309">
  <p style="margin-top:0"><b>None of the figures in this block is the figure of record.</b> They come from software that reads the photographs of the gardiens&rsquo; calendars and counts the marked days. Every one carries the footnote below, and <b>no published emission-reduction or days-operational figure of record derives from these files</b> &mdash; <span class="mono">DO<sub>p,y</sub></span> stands exactly where it did.</p>

  <div class="stats">
    <div class="stat"><b>{G.fig("pump_periods", fig["pump_periods"])}</b><span>pump-periods with day calls <sup>&dagger;</sup></span></div>
    <div class="stat"><b>{G.fig("water_points", fig["water_points"])}</b><span>water points <sup>&dagger;</sup></span></div>
    <div class="stat"><b>{G.fig("observed_cells", fig["observed_cells"])}</b><span>day cells actually observed <sup>&dagger;</sup></span></div>
    <div class="stat"><b>{G.fig("unobserved_cells", fig["unobserved_cells"])}</b><span>cells the day had not reached <sup>&dagger;</sup></span></div>
    <div class="stat"><b>{G.fig("median_confidence", fig["median_confidence"])}</b><span>median confidence, a score between zero and one <sup>&dagger;</sup></span></div>
  </div>

  <p class="note"><b>Two gates, two questions.</b> Whether a sheet can be read at all is decided by fitting twelve month columns to the printed rules; whether individual days can be called on it is decided separately, by registering the day rows to the same rules. <b>{G.fig("images_readable", fig["images_readable"])}</b> photographs pass the first, <b>{G.fig("images_with_day_calls", fig["images_with_day_calls"])}</b> the second. <b>Coverage figures use the first; every day-level figure uses only the second.</b></p>

  <p class="note"><b>Indicative uptime, backed out.</b> Subtracting the impossible-cell false-positive floor from the marked rate on observed cells gives an <b>implied true marked rate</b> of {G.fig("observed_marked_pct", round(fig["observed_marked_pct"], 2))}% &minus; {G.fig("probe_marked_pct", round(fig["probe_marked_pct"], 2))}% = <b>{G.fig("implied_true_marked_pct", round(fig["implied_true_marked_pct"], 2))}%</b> <sup>&dagger;</sup>, which is <b>{G.fig("implied_days_not_operational", fig["implied_days_not_operational"])} days not operational</b> in a common year and an implied uptime of <b>{G.fig("implied_uptime_days", fig["implied_uptime_days"])} days</b> <sup>&dagger;</sup>. <b>This is not a figure we can apply.</b> It sits above the <b><span data-param="do_cap"></span></b>-day cap, and the calendars are a manual log, so the registered basis holds it at <span data-param="do_cap"></span> regardless. What it does is test the condition for <i>keeping</i> <span data-param="do_cap"></span>: downtime must not exceed <b><span data-fig="365-PARAMS.do_cap.v"></span></b> days per point-year, and <b>{G.fig("implied_days_not_operational", fig["implied_days_not_operational"])}</b> days is well inside that. <b>The test bounds over-counting only</b> &mdash; it says nothing about faint marks the software missed, which would push the other way, and nothing here can measure that until a human has read the same sheets. <span class="muted"><a href="#act-transcription-round">Run the transcription validation round.</a></span></p>

  <details class="expl"><summary>How the cells are classified, how the error floor is measured, and what the implied figure assumes</summary>
  <p class="note"><b>What a calendar photograph can and cannot show.</b> A sheet photographed on a given date carries marks only for the days up to that date. Every later cell is blank because the day had not arrived, not because the pump was working. Each printed cell is therefore classified three ways from <b>the year printed on the sheet itself</b> and the date of the photograph: <b>observed</b>, <b>not yet observed</b>, or <b>not a date at all</b>. Every rate is computed over <b>observed cells only</b>. A {list(sy)[0] if sy else "2025"} sheet photographed in a later year is fully observed, while a 2027 sheet photographed in 2026 shows nothing at all.</p>
  <p class="note"><b>The measured error direction.</b> Every sheet prints a twelve-by-thirty-one grid, so in a common year <b>seven</b> of its cells are days that cannot exist &mdash; 29, 30 and 31 February, and 31 April, June, September and November &mdash; and <b>in a leap year six</b>. Anything the software calls &ldquo;marked&rdquo; in those cells is a false positive that needs no human transcript to detect. The probe only works where the month itself had been reached, so it is restricted to impossible cells in months the photograph had got to: <b>{G.fig("probe_cells", fig["probe_cells"])}</b> of the <b>{G.fig("impossible_cells", fig["impossible_cells"])}</b> impossible cells. Of those probe cells <b>{G.fig("probe_marked_pct", round(fig["probe_marked_pct"], 2))}%</b> are called marked, against <b>{G.fig("observed_marked_pct", round(fig["observed_marked_pct"], 2))}%</b> of <b>{G.fig("observed_cells", fig["observed_cells"])}</b> <b>observed day cells</b> <sup>&dagger;</sup>.</p>
  <p class="note"><b>&ldquo;Could not be read&rdquo; and &ldquo;had not happened yet&rdquo; are different states.</b> On observed cells the software calls <b>{G.fig("days_not_operational", fig["days_not_operational"])}</b> <b>days not operational</b> and <b>{G.fig("days_illegible", fig["days_illegible"])}</b> days illegible <sup>&dagger;</sup>. Separately, <b>{G.fig("days_unobserved", fig["days_unobserved"])}</b> cells lay beyond the photograph date and were never evidence of anything; of those the software called <b>{G.fig("unobserved_called_marked", fig["unobserved_called_marked"])}</b> marked and <b>{G.fig("unobserved_called_illegible", fig["unobserved_called_illegible"])}</b> illegible, which is a floor under its false-positive rate on cells that were blank by construction. The two are <b>counted separately</b> everywhere and are never added together.</p>
  <p class="note"><b>Three assumptions make the implied uptime indicative rather than measured:</b> that the false-positive rate is the same on observed cells as on impossible ones; that days called illegible carry the same marked rate as days that could be read, since they are excluded rather than imputed; and that the accuracy assessment against independent human transcription is still outstanding. <span class="muted">Source files: <span class="mono">data/calendar_extraction_summary.csv</span>, <span class="mono">data/calendar_extraction_figures.json</span>, <span class="mono">data/calendar_not_calendar.csv</span> and <span class="mono">data/calendar_year_coverage.csv</span>, all regenerated by <span class="mono">recompute_figures.py</span> and <span class="mono">coverage.py</span> from the reader output.</span></p>
  </details>

  <p class="note"><b>The year has to be read off the sheet, and on <b>{G.fig("sheets_not_dated", fig["sheets_not_dated"])}</b> readable photographs it cannot be.</b> Of <b>{G.fig("images_readable", fig["images_readable"])}</b> readable photographs the printed year could be read on <b>{G.fig("sheets_dated_from_the_sheet", fig["sheets_dated_from_the_sheet"])}</b>. <b>Sheets whose year could not be read are excluded from every rate rather than assigned a year</b> &mdash; an undated sheet cannot be attached to a monitoring year, so it evidences nothing however well it is read. By year: {", ".join(f"<b>{G.fig(chr(115)+chr(104)+chr(101)+chr(101)+chr(116)+chr(115)+chr(95)+k, v)}</b> for {k}" for k, v in sorted(sy.items()))}. <span class="muted"><a href="#act-undatable">Quantify the water points behind the undatable sheets.</a></span></p>

  <details class="expl"><summary>What the year printed on a sheet denotes, and why the photograph date cannot stand in for it</summary>
  <p class="note">Among the sheets that could be dated, {G.fig("pct_same", PCT_SAME)}% carry the year they were photographed in, {G.fig("pct_earlier", PCT_EARLIER)}% an earlier year and {G.fig("pct_later", PCT_LATER)}% a <i>later</i> one, so the photograph date is not a safe substitute. <b>A printed year later than the photograph does not mean an unused sheet.</b> <b>{G.fig("sheets_2027_in_2026", len(s27))}</b> sheets carry a printed <b>2027</b> and were photographed during 2026. The printed year is real: under magnification a sample of them shows a crisp, unambiguous <b>2027</b>, and none a different year; the OCR string is literally <span class="mono">paompy 2027 ID</span>, and confidence runs <b>{G.fig("sheets_2027_conf_min", CONF_MIN)}</b> to <b>{G.fig("sheets_2027_conf_max", CONF_MAX)}</b>. <b>But the sheets are in service.</b> On a sheet printed 2027, months at or before the photograph month are marked at <b>{G.fig("rate_early_pct", RATE_EARLY)}%</b> of legible cells and months after it at <b>{G.fig("rate_late_pct", RATE_LATE)}%</b> &mdash; a step of <b>{G.fig("rate_step", STEP)}&times;</b>{(", and the later rate is <i>below</i> the impossible-cell floor of " + G.fig("probe_marked_pct", round(fig["probe_marked_pct"], 2)) + "%, so it is noise") if RATE_LATE is not None and RATE_LATE < fig["probe_marked_pct"] else ""}. A blank sheet held in stock shows no such step.</p>
  <p class="note"><b>What the printed year records is the sheet&rsquo;s edition or print run, not reliably the period it covers</b> &mdash; and the template no longer prints one: from <span class="mono">Template-v1.3</span> onward the year is written on the sheet by the technician who hangs it, <span class="mono">Template-v1.4</span> is the current issue, and on older stock <b>a printed year denotes the print run only</b>. The consequence for coverage is bounded and small: attributing those sheets to the photograph&rsquo;s year instead would move water points with 2026 evidence &mdash; the <span class="mono">2026-dated-sheet basis</span> &mdash; from <b>{G.fig("points_2026", PTS_2026)}</b> to <b>{G.fig("points_2026_reattributed", PTS_2026_REATTR)}</b>, because most of the <b>{G.fig("points_2027_in_2026", PTS_AFFECTED)}</b> points affected already hold another 2026 sheet. The figures here stay on the printed-year basis, which is the conservative one. <span class="muted"><a href="#act-printed-year-meaning">Establish what the printed year is meant to denote.</a> {G.fig("sheets_2024", sy.get("2024", 0))} sheets are 2024, a leap year: on those, 29 February is a real day.</span></p>
  </details>

  <p class="note"><b>{G.fig("not_calendar", len(nc))} of the photographs are not calendars.</b> Every calendar photograph on file was inspected by eye. <b>{G.fig("not_calendar_accepted", len(acc))}</b> of them the reader had accepted as calendars and they are excluded from every figure here; <b>{G.fig("not_calendar_rejected", len(rej))}</b> it had already thrown out. A person holding up a calendar is counted as a calendar, however badly framed. They are listed with water point, question and reason in <span class="mono">data/calendar_not_calendar.csv</span>, and are to be moved to the right question, not deleted &mdash; <span class="muted"><a href="#act-photo-misfiled">move the misfiled photographs to the right question</a>.</span></p>

  <details class="expl"><summary>What the {G.fig("not_calendar", len(nc))} non-calendar photographs are, and which question they sit on</summary>
  <p class="note"><b>{G.fig("reason_signboard", byreason["signboard"])}</b> of the blue &ldquo;Point d&rsquo;Eau Potable et P&eacute;renne&rdquo; signboard, <b>{G.fig("reason_document", byreason["document"])}</b> of a printed document other than a calendar, <b>{G.fig("reason_pump", byreason["pump"])}</b> of a standpipe or pump head, <b>{G.fig("reason_other", byreason["other"])}</b> portraits or site views with no sheet in the frame, and <b>{G.fig("reason_bottle_on_pump", byreason["bottle_on_pump"])}</b> of a sample bottle on a pump platform. By question: <b>{G.fig("q_2_15_5", byq["2.15.5"])}</b> on <span class="mono">2.15.5</span>, <b>{G.fig("q_2_15_6", byq["2.15.6"])}</b> on <span class="mono">2.15.6</span>, <b>{G.fig("q_1_3_1_3", byq["1.3.1.3"])}</b> on <span class="mono">1.3.1.3</span>.</p>
  <p class="note"><span class="muted">One pump-period had been lost to the exclusion and is restored: water point {wp("742896406")}, 2025 holds a signboard and a usable calendar, and the signboard had been selected. The selection is now re-run after exclusion rather than rows being deleted. Three pump-periods held a non-calendar alongside a usable image and no other point was affected; five pump-periods whose only day-call image was a non-calendar are correctly gone.</span></p>
  </details>

  <p class="note"><b>What an operation sensor would size, and nothing else.</b> <b>None of this is available on calendar evidence</b> &mdash; the methodology permits a value above <span data-param="do_cap"></span> days only on measured sensor data, so the arithmetic exists to size the instrumentation decision and for no other purpose. Emission reductions are <b><span data-param="er_maro"></span> tCO<sub>2</sub>e per community water supply per year</b> in the VPA-DD at <b><span data-param="do_cap"></span></b> days, and <span class="mono">DO<sub>p,y</sub></span> enters the volume calculation linearly. The span from <span data-param="do_cap"></span> days to a full common year is <b>+<span data-fig="(100*(365/PARAMS.do_cap.v-1)).toFixed(2)"></span>%</b>, or <b>+<span data-fig="(PARAMS.er_maro.v*(365/PARAMS.do_cap.v-1)).toFixed(2)"></span> tCO<sub>2</sub>e per point per year</b> on the Maroantsetra figure. Fort-Dauphin carries the higher baseline emission factor (<b><span data-param="efb_anosy"></span></b> against <b><span data-param="efb_maroantsetra"></span></b> tCO<sub>2</sub>e/L), so that span is wider there. A sensor would not deliver a full year either: it would deliver whatever it measures, and the metering programme is fleet-wide &mdash; a logger on every metered pump &mdash; so the comparison is the whole programme against the whole fleet, not a per-unit trade. <b>Whether it is worth the instrumentation is a decision for the Head of Carbon, not a conclusion of this page.</b></p>

  <div class="eyebrow" style="margin:18px 0 8px">How much of a year the calendars actually evidence</div>
  <p class="note"><b>This is the binding constraint, and it is not about how well the sheets are read.</b> A calendar evidences a year only up to the day it was photographed; where a point has several photographs of the same year, the latest governs and the earlier ones corroborate it. Across <b>{G.fig("point_years", len(cov))}</b> point-years with a readable, dated sheet, the median share of the year carrying photographic evidence is <b>{G.fig("median_covered_pct", round(100*med_all))}%</b>, and <b>{G.fig("point_years_under_high", part)}</b> of them have less than {G.fig("cover_high_pct", round(100*COVER_HIGH))}% of the year covered.</p>
  <div class="tablewrap"><table class="ind" data-table="calyear"><thead><tr><th>Sheet year</th><th class="num">Point-years</th><th class="num">Median covered</th><th class="num">&ge;90% covered</th><th class="num">&lt;50% covered</th></tr></thead><tbody>{rows}</tbody></table></div>
  {_tablenote("calyear")}
  <p class="note" style="margin-top:12px"><b>What that means for <span class="mono">SDWS 27</span>.</b> A year that is already over can be evidenced end to end, because the sheet was photographed after it closed. <b>The year being monitored cannot be</b>, because the photograph is taken during it. So the calendars cannot carry a full-year days-operational figure for the current period however well they are read &mdash; which is the cooking precedent reached from the other direction: technology days are computed for the estate, and the calendars discount recorded downtime within the stretches they actually cover. <span class="muted">Per-point detail: <span class="mono">data/calendar_year_coverage.csv</span>.</span></p>

  <p class="note"><b>Coverage, after recalibrating the reader.</b> Four template generations are in the field &mdash; 2024, 2025, 2026 and 2027 &mdash; and the reader now fits a twelve-column grid to the rules actually printed on the sheet instead of assuming one generation&rsquo;s spacing. Of <b>{G.fig("photographs_held", fig["photographs_held"])}</b> calendar photographs held, <b>{G.fig("not_calendar_accepted", len(acc))}</b> are not calendars and are excluded; of the remainder it reads <b>{G.fig("images_readable", fig["images_readable"])}</b>, against <span data-fig="CALS.first_reader.images_extracted"></span> on the first reader, and can call individual days on <b>{G.fig("images_with_day_calls", fig["images_with_day_calls"])}</b>. At the level that matters &mdash; <b>visits left with no usable image</b> &mdash; of <b>{G.fig("visits_total", fig["visits_total"])}</b> visits that produced a calendar photograph, <b>{G.fig("visits_with_readable", fig["visits_with_readable"])}</b> ({G.fig("visits_with_readable_pct", round(100*fig["visits_with_readable"]/fig["visits_total"], 1))}%) carry at least one readable image and <b>{G.fig("visits_without_readable", fig["visits_without_readable"])}</b> ({G.fig("visits_without_readable_pct", round(100*fig["visits_without_readable"]/fig["visits_total"], 1))}%) carry none, against <span data-retired="first reader run of 18 September 2026" data-was="visits with no readable image on the first reader">217</span> on the first reader. At water-point level, <b>{G.fig("points_without_readable", fig["points_without_readable"])}</b> points have never produced a usable calendar image, against <span data-retired="first reader run of 18 September 2026" data-was="points with no usable image on the first reader">110</span> on the first reader.</p>

  <p class="note"><b>The reissue list needs two different instructions, not one.</b> Of those <b>{G.fig("points_without_readable", fig["points_without_readable"])}</b> points, <b>{G.fig("never_photographed", never)}</b> have <i>never had a calendar photographed at all</i> &mdash; every image on the record is a signboard, a pump, a poster or a portrait &mdash; <b>{G.fig("mixed", mixed)}</b> have a mixture, and only <b>{G.fig("unreadable", unread)}</b> have a calendar photograph the reader genuinely could not read. Telling the first {G.fig("never_photographed", never)} that their photograph was unreadable would send the field team to fix the wrong thing. <span class="mono">data/calendar_no_usable_image.csv</span> carries the cause and the field action for each: {SITECOUNTS}. <span class="muted">These <b>{G.fig("points_without_readable", fig["points_without_readable"])}</b> are not the <b><span data-fig="CALS.custody.by_site[\'All sites\'].none_ever"></span></b> counted above: those have <i>no calendar photograph at all</i>, out of <span data-fig="CALS.custody.by_site[\'All sites\'].points"></span> managed points; the {G.fig("points_without_readable", fig["points_without_readable"])} <i>have</i> photographs of which none is readable, out of the {G.fig("points_total", fig["points_total"])} points that have any. A point can be in both sets. <a href="#act-2026-recovery">Run the 2026 calendar recovery round.</a></span></p>

  <div class="eyebrow" style="margin:18px 0 8px">How the accuracy assessment is being made</div>
  <p class="note"><b>The sample basis.</b> <b>{G.fig("in_frame", len(in_frame))}</b> calendars sit inside the frame and are the set on which a human can be compared with a machine: <b>{G.fig("kept", len(kept))}</b> kept from the original draw and <b>{G.fig("drawn", len(drawn))}</b> drawn since to bring the round up to size. <b>That satisfies the minimum under either methodology version</b> &mdash; the Clean Development Mechanism floor of <b><span data-param="sample_min_v1"></span></b> for a proportion parameter carried into ERSDWS v1.0 &sect;4.2.2, and the <b><span data-param="sample_min_v2"></span></b> per sample group or stratum required by v2.0 &sect;14.5.3 &mdash; so the assessment <b>stands whichever version governs</b>, and will not need repeating at renewal. The draw is stratified by district ({", ".join(f"{G.fig(chr(115)+chr(105)+chr(116)+chr(101)+chr(95)+k.lower().replace(chr(45),chr(95)), v)} {k}" for k, v in sel_sites.most_common())}) and across the full quality range ({", ".join(f"{G.fig(chr(113)+chr(117)+chr(97)+chr(114)+chr(116)+chr(105)+chr(108)+chr(101)+chr(95)+str(k), v)} in quartile {k}" for k, v in sorted(sel_q.items()))}), so it is not a sample of easy sheets. A further <b>{G.fig("out_frame", len(out_frame))}</b> sheets stay in the round outside the frame, where the machine produced nothing: they are scored <b>human against human only</b> and are never folded into the machine figure. <span class="muted"><a href="#act-v2-sample-size">Re-scope every sample against the v2.0 minimum of <span data-param="sample_min_v2"></span>.</a></span></p>
  <p class="note" id="agrcov"><b>What any agreement figure will and will not cover.</b> <span class="agrcov">An agreement figure from this round applies to <b>the photographs the extraction produces output for</b> &mdash; currently <b>{G.fig("images_with_day_calls", fig["images_with_day_calls"])}</b> of <b>{G.fig("images_readable", fig["images_readable"])}</b> <b>readable calendar photographs</b> and <b>{G.fig("photographs_total", fig["photographs_total"])}</b> held. It is not a measure of how well the calendars are read; it is a measure of how well the ones the software can read and date are read.</span> <b>That sentence travels with the number</b> &mdash; it is printed above the comparison table, written into the head of the comparison output file, and asserted on this page, so an agreement figure can never appear here without it.</p>

  <details class="expl"><summary>The frame, the transcriber&rsquo;s prior exposure, and why agreement is reported per calendar</summary>
  <p class="note"><b>The validation frame was corrected on {DRAWN_ON}.</b> The original fifty calendars were drawn from &ldquo;readable calendar photographs&rdquo;, which was the wrong population: a human transcript can only be compared with a machine one where the machine produced something to compare, and on the observed-cell basis that also requires a year, because without a year there is no observable window and no month lengths. <b>The frame is now: photographs the extraction produces day calls for, whose year could be read off the sheet, and which are calendars</b> &mdash; <b>{G.fig("images_with_day_calls", fig["images_with_day_calls"])}</b> images. <span class="muted">Frame, reason, date and seed are recorded per row in <span class="mono">transcription/validation_selection.csv</span>; the draw used seeds <span class="mono">{", ".join(SEEDS)}</span>, and every row records which pass drew it, so the whole selection can be repeated.</span></p>
  <p class="note"><b>The reference transcription is made by Adriaan Mol</b>, from the photographs. That transcriber had already seen the extraction&rsquo;s <b>aggregate error statistics</b> &mdash; the impossible-cell rate, the marked rate, the confidence distribution &mdash; though <b>no per-cell output</b> for any sheet, and the page shows none. Prior knowledge of the aggregates is a weaker exposure than seeing the machine&rsquo;s answers, but it is not zero, and a verifier is entitled to know it before reading the agreement figure. A second transcriber with no such exposure would settle it; the page records who transcribed each sheet so the two can be compared separately.</p>
  <p class="note"><b>The cell is not the unit that carries the variation &mdash; the calendar is.</b> Cells within one sheet share its paper, its light, its handwriting and its template generation, so agreement must be reported per calendar and aggregated across calendars, not pooled cell-by-cell. The transcription grid <b>locks every cell the photograph could not show</b>, so the human and the machine are compared on exactly the same cells and no one spends time on a cell that was blank by construction.</p>
  </details>

  <p class="note"><b>Transcription page:</b> <a href="https://sanitap-water.github.io/sanitap-water-report/transcription/" target="_blank" rel="noopener">sanitap-water.github.io/sanitap-water-report/transcription/</a>. It shows the photographs and nothing else &mdash; no machine output, no aggregate, no hint of either. <span class="muted">Results are not in this report yet. When the transcription round is complete, per-calendar agreement will be added here.</span></p>
  
  {G.script()}
  '''


def splice(block):
    """Put `block` between the markers in index.html; return (old, new)."""
    p = os.path.join(REPO, "index.html")
    idx = open(p, encoding="utf8").read()
    if BEGIN not in idx or END not in idx:
        sys.exit("index.html has no generated-region markers - "
                 "add them around the machine-extraction block first")
    a = idx.index(BEGIN) + len(BEGIN)
    b = idx.index(END)
    if b < a:
        sys.exit("index.html markers are in the wrong order")
    return idx[a:b], idx[:a] + "\n" + block.strip() + "\n  " + idx[b:]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--check"
    cur, whole = splice(B)
    want = "\n" + B.strip() + "\n  "
    if mode == "--write":
        open(os.path.join(REPO, "index.html"), "w", encoding="utf8").write(whole)
        print("index.html: generated region %s (%d bytes)"
              % ("unchanged" if _same(cur, want) else "rewritten", len(B.strip())))
        return 0
    if mode == "--check":
        if _same(cur, want):
            print("index.html generated region matches tools/render_block.py")
            return 0
        d = list(difflib.unified_diff(cur.splitlines(), want.splitlines(),
                                      "index.html (published)", "render_block.py (generator)",
                                      lineterm="", n=1))
        print("\n".join(d[:40]))
        print("\nThe generated region of index.html does not match its generator.")
        print("Edit tools/render_block.py, then run: python3 tools/render_block.py --write")
        return 1
    sys.exit("usage: render_block.py --write | --check")


if __name__ == "__main__":
    sys.exit(main())
