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
PCT_SAME = f"{100*rel['same']/tot_y:.0f}%"
PCT_EARLIER = f"{100*rel['earlier']/tot_y:.0f}%"
PCT_LATER = f"{100*rel['later']/tot_y:.0f}%"

n = lambda v: f"{v:,}" if isinstance(v, int) and v >= 1000 else str(v)
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

site_n = collections.Counter(r["site"] for r in nu)
portrait = sum(1 for r in nu if r["only_portrait_field"] == "yes")
SITECOUNTS = (", ".join(f"<b>{v}</b> in {k}" for k, v in site_n.most_common())
              + f", and only <b>{portrait}</b> where the portrait field is the sole source")

rows = "".join(
    f'<tr><td>{y}</td><td class="num">{len(v)}</td>'
    f'<td class="num">{statistics.median(v):.0%}</td>'
    f'<td class="num">{sum(1 for x in v if x >= .9)}</td>'
    f'<td class="num">{sum(1 for x in v if x < .5)}</td></tr>'
    for y, v in sorted(covyear.items()))

B = f'''<div class="eyebrow" style="margin:18px 0 8px">Machine extraction from the calendar photographs &mdash; internal only</div>
  <div class="panel" style="border-left:3px solid #b45309">
  <p style="margin-top:0"><b>None of the figures in this block is the figure of record.</b> They come from software that reads the photographs of the gardiens&rsquo; calendars and counts the marked days. Every one carries the footnote below, and <b>no published emission-reduction or days-operational figure of record derives from these files</b> &mdash; <span class="mono">DO<sub>p,y</sub></span> stands exactly where it did.</p>

  <p class="note"><b>What a calendar photograph can and cannot show.</b> A sheet photographed on a given date carries marks only for the days up to that date. Every later cell is blank because the day had not arrived, not because the pump was working. Each printed cell is therefore classified three ways from <b>the year printed on the sheet itself</b> and the date of the photograph: <b>observed</b>, <b>not yet observed</b>, or <b>not a date at all</b>. <b>Every rate below is computed over observed cells only.</b> <span class="muted">The year has to be read off the sheet: a {list(sy)[0] if sy else "2025"} sheet photographed in a later year is fully observed, while a 2027 sheet photographed in 2026 shows nothing at all.</span></p>

  <div class="stats">
    <div class="stat"><b>{n(fig["pump_periods"])}</b><span>pump-periods with day calls <sup>&dagger;</sup></span></div>
    <div class="stat"><b>{n(fig["water_points"])}</b><span>water points <sup>&dagger;</sup></span></div>
    <div class="stat"><b>{n(fig["observed_cells"])}</b><span>day cells actually observed <sup>&dagger;</sup></span></div>
    <div class="stat"><b>{n(fig["unobserved_cells"])}</b><span>cells the day had not reached <sup>&dagger;</sup></span></div>
    <div class="stat"><b>{fig["median_confidence"]}</b><span>median confidence, 0 to 1 <sup>&dagger;</sup></span></div>
  </div>

  <p class="note"><b>Two gates, two questions.</b> Whether a sheet can be read at all is decided by fitting twelve month columns to the printed rules; whether individual days can be called on it is decided separately, by registering the day rows to the same rules. <b>{n(fig["images_readable"])}</b> photographs pass the first, <b>{n(fig["images_with_day_calls"])}</b> the second. Coverage figures use the first; every day-level figure uses only the second. Source files in the repository: <span class="mono">data/calendar_extraction_summary.csv</span>, <span class="mono">data/calendar_extraction_figures.json</span>, <span class="mono">data/calendar_not_calendar.csv</span> and <span class="mono">data/calendar_year_coverage.csv</span>, all regenerated by <span class="mono">recompute_figures.py</span> and <span class="mono">coverage.py</span> from the reader output.</p>

  <p class="note"><b>Reading the year off the sheet.</b> Of <b>{n(fig["images_readable"])}</b> readable photographs the printed year could be read on <b>{n(fig["sheets_dated_from_the_sheet"])}</b> and not on <b>{n(fig["sheets_not_dated"])}</b>. <b>Sheets whose year could not be read are excluded from every rate rather than assigned a year</b>, because the date of the photograph is not a safe substitute: among the sheets that could be dated, {PCT_SAME} carry the year they were photographed in, {PCT_EARLIER} an earlier year and {PCT_LATER} a <i>later</i> one. <b>A printed year later than the photograph does not mean an unused sheet</b> &mdash; see the note below. By year: {", ".join(f"<b>{v}</b> for {k}" for k, v in sorted(sy.items()))}. <span class="muted">{n(sy.get("2024", 0))} sheets are 2024, which is a leap year: on those, 29 February is a real day and six printed cells cannot exist rather than seven.</span></p>

  <p class="note"><b>A printed year ahead of the photograph does not mean an unused sheet &mdash; tested, because the first reading of it was wrong.</b> <b>152</b> sheets carry a printed <b>2027</b> and were photographed during 2026. The obvious inference &mdash; calendars distributed three quarters of a year early &mdash; was checked rather than repeated. <b>The printed year is real:</b> 21 of 24 sampled sheets show a crisp, unambiguous <b>2027</b> under magnification, the OCR string is literally <span class="mono">paompy 2027 ID</span>, and confidence runs <b>0.80</b> to <b>1.00</b>; the remaining three showed a footer crop, and none showed a different year. <b>But the sheets are in service.</b> On a sheet printed 2027, months at or before the photograph month are marked at <b>4.94%</b> and months after it at <b>1.48%</b> &mdash; a step of <b>3.3&times;</b>, the sharpest of any year, and the 1.48% is <i>below</i> the impossible-cell false-positive floor of 1.84%, so it is noise. A blank sheet held in stock shows no such step. <b>The gardiens are filling these sheets in for the current year.</b> <span class="muted">What the printed year records is therefore the sheet&rsquo;s edition or print run, not reliably the period it covers &mdash; and the template no longer prints one: from <span class="mono">Template-v1.3</span> onward the year is written on the sheet by the technician who hangs it &mdash; <span class="mono">Template-v1.4</span> is the current issue, and on older stock a printed year denotes the print run only. The consequence for coverage is bounded and small: attributing those sheets to the photograph&rsquo;s year instead would move water points with 2026 evidence &mdash; the <span class="mono">2026-dated-sheet basis</span> &mdash; from <b>295</b> to <b>309</b>, because most of the <b>143</b> points affected already hold another 2026 sheet. The figures here stay on the printed-year basis, which is the conservative one.</span></p>

  <p class="note"><b>Two hundred and six of the photographs are not calendars.</b> Every calendar photograph on file was inspected by eye. <b>{len(nc)}</b> are not calendars at all: <b>{byreason["signboard"]}</b> of the blue &ldquo;Point d&rsquo;Eau Potable et P&eacute;renne&rdquo; signboard, <b>{byreason["document"]}</b> of a printed document other than a calendar, <b>{byreason["pump"]}</b> of a standpipe or pump head, <b>{byreason["other"]}</b> portraits or site views with no sheet in the frame, and <b>{byreason["bottle_on_pump"]}</b> of a sample bottle on a pump platform. <b>{len(acc)}</b> of them the reader had accepted as calendars and they are excluded from every figure here; <b>{len(rej)}</b> it had already thrown out. A person holding up a calendar is counted as a calendar, however badly framed. By question: <b>{byq["2.15.5"]}</b> on <span class="mono">2.15.5</span>, <b>{byq["2.15.6"]}</b> on <span class="mono">2.15.6</span>, <b>{byq["1.3.1.3"]}</b> on <span class="mono">1.3.1.3</span>. They are listed with water point, question and reason in <span class="mono">data/calendar_not_calendar.csv</span>, and go to the data-correction action below to be moved to the right question, not deleted.</p>

  <p class="note"><b>The measured error direction.</b> Every sheet prints a twelve-by-thirty-one grid, so in a common year <b>seven</b> of its cells are days that cannot exist &mdash; 29, 30 and 31 February, and 31 April, June, September and November &mdash; and in a leap year six. Anything the software calls &ldquo;marked&rdquo; in those cells is a false positive that needs no human transcript to detect. <b>The probe only works where the month itself had been reached</b>, so it is restricted to impossible cells in months the photograph had got to: <b>{n(fig["probe_cells"])}</b> of the <b>{n(fig["impossible_cells"])}</b> impossible cells. Of those probe cells <b>{fig["probe_marked_pct"]:.2f}%</b> are called marked, against <b>{fig["observed_marked_pct"]:.2f}%</b> of <b>{n(fig["observed_cells"])}</b> observed day cells <sup>&dagger;</sup>.</p>

  <p class="note"><b>&ldquo;Could not be read&rdquo; and &ldquo;had not happened yet&rdquo; are different states.</b> On observed cells the software calls <b>{n(fig["days_not_operational"])}</b> days not operational and <b>{n(fig["days_illegible"])}</b> days illegible <sup>&dagger;</sup>. Separately, <b>{n(fig["days_unobserved"])}</b> cells lay beyond the photograph date and were never evidence of anything; of those the software called <b>{n(fig["unobserved_called_marked"])}</b> marked and <b>{n(fig["unobserved_called_illegible"])}</b> illegible, which is a floor under its false-positive rate on cells that were blank by construction. The two are counted separately everywhere and are never added together.</p>

  <p class="note"><b>Indicative uptime, backed out.</b> Subtracting the impossible-cell floor from the marked rate on observed cells gives an implied true marked rate of {fig["observed_marked_pct"]:.2f}% &minus; {fig["probe_marked_pct"]:.2f}% = <b>{fig["implied_true_marked_pct"]:.2f}%</b> <sup>&dagger;</sup>, which is <b>{fig["implied_days_not_operational"]} days not operational</b> in a 365-day year and an implied uptime of <b>{fig["implied_uptime_days"]} days</b> <sup>&dagger;</sup>. <b>The observed-cell basis is the basis of record for this block, and the correction is large: it more than doubled implied downtime, from 4.1 days to {fig["implied_days_not_operational"]}.</b> <b>This reading is not a figure we can apply.</b> It sits above the <b>347</b>-day cap, and the calendars are a manual log, so the registered basis holds it at 347 regardless &mdash; see the <span class="mono">SDWS 27</span> block above. What the reading does is test the condition for <i>keeping</i> 347: downtime must not exceed <b>18</b> days per point-year, and <b>{fig["implied_days_not_operational"]}</b> days is well inside that. <b>Three assumptions make that indicative rather than measured:</b> that the false-positive rate is the same on observed cells as on impossible ones; that days called illegible carry the same marked rate as days that could be read, since they are excluded rather than imputed; and that the accuracy assessment against independent human transcription is still outstanding.</p>

  <p class="note"><b>What an operation sensor would size, and nothing else.</b> <b>None of this is available on calendar evidence</b> &mdash; the methodology permits a value above 347 days only on measured sensor data, so the arithmetic below exists to size the instrumentation decision and for no other purpose. Emission reductions are <b>27.9 tCO<sub>2</sub>e per community water supply per year</b> in the VPA-DD at <b>347</b> days, and <span class="mono">DO<sub>p,y</sub></span> enters the volume calculation linearly. The span from 347 to 365 days is <b>+5.19%</b>, or <b>+1.45 tCO<sub>2</sub>e per point per year</b> &mdash; <b>USD 29 per point per year</b> at <b>USD 20</b> per tonne, <b>USD 21,200 a year across the 731 carbon points</b>. Fort-Dauphin carries the higher baseline emission factor (<b>0.00027</b> against <b>0.00018</b> tCO<sub>2</sub>e/L), so that span is wider there. And a sensor would not deliver 365 either: it would deliver whatever it measures. Against that, the metering programme sized above is fleet-wide &mdash; <b>~770</b> loggers for <b>723</b> pumps &mdash; so the comparison is the whole programme against the whole fleet, not a per-unit trade. Whether it is worth the instrumentation is a decision for the Head of Carbon, not a conclusion of this page.</p>

  <p class="note"><b>That test bounds over-counting only.</b> It says nothing about faint marks the software missed, which would be under-counting and would push the other way. Nothing here measures that, and nothing can until the human transcription round is done. <b>On the present evidence the extraction is not usable for anything, in either direction</b>, and the figures above are published to show where the work stands, not because they carry information about availability.</p>

  <p class="note"><b>One pump-period was wrongly deleted and is restored.</b> When the non-calendar images were first excluded, a pump-period lost its whole row if the image that happened to be its best was one of them, instead of falling back to the next usable image of the same pump and year. <b>Water point <span class="mono">742896406</span>, 2025</b> was affected: it has two accepted images, a signboard and a usable calendar, and the signboard had been selected. The selection is now re-run after exclusion rather than rows being deleted. <b>Three</b> pump-periods held a non-calendar alongside a usable image; in the other two the usable image was already the one selected, so nothing was lost. <b>No other point was affected.</b> <span class="muted">Five further pump-periods whose only day-call image was a non-calendar are correctly gone.</span></p>

  <div class="eyebrow" style="margin:18px 0 8px">How much of a year the calendars actually evidence</div>
  <p class="note"><b>This is the binding constraint, and it is not about how well the sheets are read.</b> A calendar evidences a year only up to the day it was photographed. Where a point has several photographs of the same year, the latest one governs and the earlier ones corroborate it. Across <b>{n(len(cov))}</b> point-years with a readable, dated sheet, the median share of the year carrying photographic evidence is <b>{med_all:.0%}</b>, and <b>{n(part)}</b> of them have less than 90% of the year covered.</p>
  <div class="tablewrap"><table class="ind"><thead><tr><th>Sheet year</th><th class="num">Point-years</th><th class="num">Median covered</th><th class="num">&ge;90% covered</th><th class="num">&lt;50% covered</th></tr></thead><tbody>{rows}</tbody></table></div>
  <p class="note" style="margin-top:12px"><b>What that means for <span class="mono">SDWS 27</span>.</b> A year that is already over can be evidenced end to end, because the sheet was photographed after it closed. <b>The year being monitored cannot be</b>, because the photograph is taken during it. So the calendars cannot carry a full-year days-operational figure for the current period however well they are read. <b>That is the cooking precedent, arrived at from the other direction:</b> technology days are computed for the estate from the register and the maintenance history, and the calendars are used to discount recorded downtime within the stretches they actually cover. Per-point detail: <span class="mono">data/calendar_year_coverage.csv</span>.</p>

  <p class="note"><b>Coverage, after recalibrating the reader.</b> Four template generations are in the field &mdash; 2024, 2025, 2026 and 2027 &mdash; and the first reader was calibrated on the 2024/25 pitch, so it discarded legible sheets printed to a later design. The reader now fits a twelve-column grid to the rules actually printed on the sheet instead of assuming one generation&rsquo;s spacing. Of <b>{n(fig["photographs_held"])}</b> calendar photographs held, <b>{len(acc)}</b> are not calendars and are excluded; of the remainder it reads <b>{n(fig["images_readable"])}</b>, against 1,156 on the first reader, and can call individual days on <b>{n(fig["images_with_day_calls"])}</b> of those. At the level that matters &mdash; <b>visits left with no usable image</b> &mdash; of <b>{n(fig["visits_total"])}</b> visits that produced a calendar photograph, <b>{n(fig["visits_with_readable"])}</b> ({100*fig["visits_with_readable"]/fig["visits_total"]:.1f}%) carry at least one readable image and <b>{n(fig["visits_without_readable"])}</b> ({100*fig["visits_without_readable"]/fig["visits_total"]:.1f}%) carry none, against 217 on the first reader. At water-point level, <b>{n(fig["points_without_readable"])}</b> points have never produced a usable calendar image, against 110 on the first reader.</p>

  <p class="note"><b>The reissue list needs two different instructions, not one.</b> Of those <b>{n(fig["points_without_readable"])}</b> points, <b>{never}</b> have <i>never had a calendar photographed at all</i> &mdash; every image on the record is a signboard, a pump, a poster or a portrait &mdash; <b>{mixed}</b> have a mixture, and only <b>{unread}</b> have a calendar photograph the reader genuinely could not read. Telling the first {never} that their photograph was unreadable would send the field team to fix the wrong thing. <span class="mono">data/calendar_no_usable_image.csv</span> now carries the cause and the field action for each: {SITECOUNTS}. <span class="muted">These <b>{n(fig["points_without_readable"])}</b> are not the <b>62</b> counted above: the 62 have <i>no calendar photograph at all</i>, out of 736 managed points; the {n(fig["points_without_readable"])} <i>have</i> photographs of which none is readable, out of the {n(fig["points_total"])} points that have any. A point can be in both sets.</span></p>

  <div class="eyebrow" style="margin:18px 0 8px">How the accuracy assessment is being made</div>
  <p class="note"><b>The reference transcription is made by Adriaan Mol</b>, from the photographs, on the transcription page linked below. <b>That transcriber had already seen the extraction&rsquo;s aggregate error statistics &mdash; the impossible-cell rate, the marked rate, the confidence distribution &mdash; though no per-cell output for any sheet, and the page shows none.</b> Prior knowledge of the aggregates is a weaker exposure than seeing the machine&rsquo;s answers, but it is not zero, and a verifier is entitled to know it before reading the agreement figure. A second transcriber with no such exposure would settle it; the page records who transcribed each sheet so the two can be compared separately.</p>
  <p class="note"><b>The validation frame was corrected on {DRAWN_ON}, and this records why.</b> The original fifty calendars were drawn from &ldquo;readable calendar photographs&rdquo;. That was the wrong population. A human transcript can only be compared with a machine one where the machine produced something to compare, and on the observed-cell basis that also requires a year, because without a year there is no observable window and no month lengths. <b>The frame is now: photographs the extraction produces day calls for, whose year could be read off the sheet, and which are calendars</b> &mdash; <b>{n(len(in_frame) + len(out_frame) and fig["images_with_day_calls"])}</b> images. That is the population the extraction makes claims about, so an agreement figure computed on it describes exactly that population and no more. <span class="muted">Frame, reason, date and seed are recorded per row in <span class="mono">transcription/validation_selection.csv</span>; the draw used seeds <span class="mono">{", ".join(SEEDS)}</span> &mdash; the original correction, the extension to the v2.0 minimum, and a replacement pass &mdash; and every row records which pass drew it, so the whole selection can be repeated.</span></p>
  <p class="note"><b>The sample basis.</b> <b>{len(in_frame)}</b> calendars sit inside the frame and are the set on which a human can be compared with a machine: <b>{len(kept)}</b> kept from the original draw and <b>{len(drawn)}</b> drawn since to bring the round up to size. <b>That satisfies the minimum under either methodology version</b> &mdash; the Clean Development Mechanism floor of <b>30</b> for a proportion parameter carried into ERSDWS v1.0 &sect;4.2.2, and the <b>50</b> per sample group or stratum required by v2.0 &sect;14.5.3. <b>The assessment therefore stands whichever version governs, and will not need repeating at renewal.</b> The draw is stratified by district ({", ".join(f"{v} {k}" for k, v in sel_sites.most_common())}) and across the full quality range ({", ".join(f"{v} in quartile {k}" for k, v in sorted(sel_q.items()))}), so it is not a sample of easy sheets. <b>A further <b>{len(out_frame)}</b> sheets stay in the round outside the frame</b> &mdash; the machine produced nothing for them. They are transcribed and scored <b>human against human only</b>, under their own heading, and are never folded into the machine figure: they answer the different question of whether a person can read what the software could not, which is the evidence for choosing between the extraction and manual transcription. <b>The cell is not the unit that carries the variation &mdash; the calendar is.</b> Cells within one sheet share its paper, its light, its handwriting and its template generation, so agreement must be reported per calendar and aggregated across calendars, not pooled cell-by-cell. <b>The transcription grid locks every cell the photograph could not show</b>, so the human and the machine are compared on exactly the same cells and no one spends time on a cell that was blank by construction.</p>
  <p class="note" id="agrcov"><b>What any agreement figure will and will not cover.</b> <span class="agrcov">An agreement figure from this round applies to <b>the photographs the extraction produces output for</b> &mdash; currently <b>{n(fig["images_with_day_calls"])}</b> of <b>{n(fig["images_readable"])}</b> readable calendar photographs and <b>{n(fig["photographs_total"])}</b> held. It is not a measure of how well the calendars are read; it is a measure of how well the ones the software can read and date are read.</span> <b>That sentence travels with the number</b> &mdash; it is printed above the comparison table, written into the head of the comparison output file, and asserted on this page, so an agreement figure can never appear here without it.</p>
  <p class="note"><b>Transcription page:</b> <a href="https://sanitap-water.github.io/sanitap-water-report/transcription/" target="_blank" rel="noopener">sanitap-water.github.io/sanitap-water-report/transcription/</a>. It shows the photographs and nothing else &mdash; no machine output, no aggregate, no hint of either. <span class="muted">Results are not in this report yet. When the transcription round is complete, per-calendar agreement will be added here.</span></p>
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
              % ("unchanged" if cur == want else "rewritten", len(B.strip())))
        return 0
    if mode == "--check":
        if cur == want:
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
