"""Shared primitives for the gardien-calendar extraction prototype.

The calendar is a printed A3-ish sheet: a 12-column (month) by 31-row (day)
grid, with a title block and a MadAvance / SaniTap logo strip at the top and a
telephone line along the bottom. The pump ID is handwritten in the header.
Photographs of it are taken on maintenance visits in the field, so the sheet
may be held, propped, or laid on the ground, at any of four orientations, flat
or curved, in full sun or dappled shade.

Nothing here writes to the report. Output is a file, by design.
"""
import cv2, numpy as np

CANON_W, CANON_H = 1680, 1170          # canonical rectified sheet, ~1.44:1
MONTHS = 12
DAYS = 31


def load(path, max_dim=1600):
    im = cv2.imread(path, cv2.IMREAD_COLOR)
    if im is None:
        return None, None
    h, w = im.shape[:2]
    s = max_dim / max(h, w)
    small = cv2.resize(im, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else im.copy()
    return im, small


def sheet_quad(small):
    """Find the paper sheet: the dominant bright quadrilateral.

    Paper is the brightest large region in almost every one of these frames, so
    a brightness segmentation is far more robust here than edge detection,
    which drowns in vegetation, bamboo and gravel.
    """
    g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (7, 7), 0)
    # Otsu on the upper half of the histogram isolates paper from soil/shadow
    _, th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None, 0.0
    frame_area = small.shape[0] * small.shape[1]
    best, best_area = None, 0.0
    for c in cnts:
        a = cv2.contourArea(c)
        if a < 0.03 * frame_area or a <= best_area:
            continue
        peri = cv2.arcLength(c, True)
        ap = cv2.approxPolyDP(c, 0.02 * peri, True)
        quad = ap.reshape(-1, 2).astype(np.float32) if len(ap) == 4 else \
               cv2.boxPoints(cv2.minAreaRect(c)).astype(np.float32)
        best, best_area = quad, a
    if best is None:
        return None, 0.0
    return order_quad(best), best_area / frame_area


def order_quad(p):
    """tl, tr, br, bl"""
    p = np.asarray(p, dtype=np.float32)
    s, d = p.sum(1), np.diff(p, axis=1).ravel()
    return np.array([p[np.argmin(s)], p[np.argmin(d)], p[np.argmax(s)], p[np.argmax(d)]], dtype=np.float32)


def rectify(img, quad, scale):
    """Warp the sheet to a canonical landscape rectangle, at full resolution."""
    q = quad * scale
    dst = np.array([[0, 0], [CANON_W, 0], [CANON_W, CANON_H], [0, CANON_H]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(q.astype(np.float32), dst)
    return cv2.warpPerspective(img, M, (CANON_W, CANON_H))


def quad_aspect(q):
    wa = (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / 2
    ha = (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1])) / 2
    if min(wa, ha) < 1:
        return 0.0
    return max(wa, ha) / min(wa, ha)


def sharpness(gray):
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def exposure(gray):
    f = gray.astype(np.float32) / 255.0
    return dict(mean=float(f.mean()), std=float(f.std()),
                clip_hi=float((gray >= 250).mean()), clip_lo=float((gray <= 5).mean()))


def shade_unevenness(gray):
    """Dappled shade shows up as large-scale luminance variation across the sheet."""
    small = cv2.resize(gray, (32, 22), interpolation=cv2.INTER_AREA).astype(np.float32)
    return float(small.std() / 255.0)


def _profile_period(sig, lo, hi):
    """Dominant period of a 1-D edge profile, by autocorrelation, and its strength.

    A real calendar grid gives a sharp autocorrelation peak at the row or column
    pitch. Vegetation, clothing and corrugated iron do not, which is what makes
    this a usable test of whether the thing we rectified is actually a calendar.
    """
    x = sig - sig.mean()
    if x.std() < 1e-6:
        return 0, 0.0
    x = x / x.std()
    ac = np.correlate(x, x, mode="full")[len(x) - 1:]
    ac = ac / (ac[0] + 1e-9)
    seg = ac[lo:hi]
    if len(seg) == 0:
        return 0, 0.0
    k = int(np.argmax(seg)) + lo
    return k, float(seg[k - lo])


def grid_score(rect_bgr):
    """Does this rectified image actually contain the calendar grid?

    Returns (score 0-1, detected row pitch, detected column pitch). The sheet is
    a 12-month x 31-day grid, so at canonical size the row pitch is ~CANON_H/34
    and the column pitch ~CANON_W/12 (each month is one printed block).
    """
    g = cv2.cvtColor(rect_bgr, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    gx = np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3))
    gy = np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3))
    col = gx.mean(axis=0)          # vertical rules -> peaks along x
    row = gy.mean(axis=1)          # horizontal rules -> peaks along y
    rp, rs = _profile_period(row, max(8, CANON_H // 45), CANON_H // 22)
    cp, cs = _profile_period(col, max(8, CANON_W // 30), CANON_W // 8)
    return float(max(0.0, min(1.0, (rs + cs) / 2))), rp, cp


def green_logo_y(rect_bgr):
    """Vertical position (0 top, 1 bottom) of the MadAvance logo.

    The logo is a saturated green rectangle and is the only large green object
    on the sheet, which makes it a far more decisive orientation cue than
    overall saturation: shadow, soil and vegetation inside a loosely-detected
    quadrilateral can easily out-saturate the header strip.

    Returns None when no green block is found.
    """
    hsv = cv2.cvtColor(rect_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (35, 80, 40), (90, 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(mask, 8)
    if n <= 1:
        return None
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    if stats[i, cv2.CC_STAT_AREA] < 0.001 * mask.size:
        return None
    return float(cent[i][1] / rect_bgr.shape[0])


def logo_band_score(rect_bgr):
    """The header carries the MadAvance (green) and SaniTap (blue) logos and the
    title. It is the most saturated band on an otherwise grey-and-pale sheet, so
    its vertical position tells us which way up the photograph is."""
    hsv = cv2.cvtColor(rect_bgr, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1].astype(np.float32) / 255.0
    prof = sat.mean(axis=1)
    top = prof[: int(0.22 * len(prof))].mean()
    bot = prof[int(0.78 * len(prof)):].mean()
    return float(top - bot)


def geometry_score(rp, cp):
    """Is the measured pitch consistent with a 12-month x 31-day sheet?

    The column pitch should be CANON_W/12; the autocorrelation may instead lock
    onto the day-number/weekday sub-column (half pitch) or a harmonic, so those
    are accepted too. This geometric test is what separates a real calendar from
    corrugated iron, clothing and foliage, which also produce strong but
    wrongly-scaled periodicity.
    """
    def near(v, targets, tol=0.18):
        return max((1.0 - abs(v - t) / (t * tol) for t in targets if t > 0), default=0.0)
    # measured on rectified sheets: the grid occupies ~78% of the canonical
    # height (a title band above, a telephone line below) and nearly the full
    # width, giving a row pitch of ~29 px and a month pitch of ~135 px.
    cs = max(0.0, near(cp, [135.0, 67.5, 45.0]))
    rs = max(0.0, near(rp, [29.0, 14.5, 58.0]))
    return float(min(1.0, (cs + rs) / 2))


def analyse(img, quad, scale):
    """Rectify at the best of the four orientations and score it.

    Returns a dict; `ok` is True only when the rectified sheet both shows grid
    periodicity and shows it at the right scale.
    """
    cands = []
    for k in range(4):
        q = np.roll(quad, -k, axis=0)
        r = rectify(img, q, scale)
        per, rp, cp = grid_score(r)
        gs = geometry_score(rp, cp)
        cands.append(dict(k=k, rect=r, periodicity=per, row_pitch=rp, col_pitch=cp,
                          geometry=gs, logo=logo_band_score(r)))
    # pick on grid evidence first, then use the logo band to settle 0 vs 180
    # 0 and 180 degrees are indistinguishable on grid evidence alone, so decide
    # on grid evidence to within a tolerance and let the logo band settle the
    # flip. Without this the sheet reads upside down and every date is wrong.
    cands.sort(key=lambda c: c["geometry"] * c["periodicity"], reverse=True)
    top = cands[0]["geometry"] * cands[0]["periodicity"]
    near_top = [c for c in cands if c["geometry"] * c["periodicity"] >= top - 0.05]
    # prefer a candidate whose green MadAvance logo sits in the upper half;
    # fall back to the saturation band only when no logo is found at all
    def key(c):
        gy = green_logo_y(c["rect"])
        c["green_y"] = gy
        return (1 if (gy is not None and gy < 0.5) else 0, c["logo"])
    best = max(near_top, key=key)
    best["green_y"] = green_logo_y(best["rect"])
    best["ok"] = best["geometry"] > 0.35 and best["periodicity"] > 0.15
    return best


def grid_bbox(rect_bgr):
    """Bounding box of the day grid inside the rectified sheet.

    Located from the printed pale-blue Sunday shading, which appears in day
    cells and nowhere else on the sheet: not in the header strip, not in the
    telephone line, and not on the ground around a loosely-detected sheet. An
    edge-energy span was tried first and failed - it ran to the full canvas,
    because soil and vegetation carry as much edge energy as printed rules.
    """
    hsv = cv2.cvtColor(rect_bgr, cv2.COLOR_BGR2HSV)
    blue = cv2.inRange(hsv, (80, 18, 80), (145, 190, 255))   # printed row tint across all four generations; the vivid SaniTap logo is excluded by the upper saturation bound
    blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    if blue.mean() < 2.0:                       # almost no shading found
        return None
    ys, xs = np.where(blue > 0)
    # trim the extreme 1% each way so one stray blue object cannot stretch the box
    x0, x1 = int(np.percentile(xs, 0.5)), int(np.percentile(xs, 99.5))
    y0, y1 = int(np.percentile(ys, 0.5)), int(np.percentile(ys, 99.5))
    if (x1 - x0) < 500 or (y1 - y0) < 250:
        return None
    return x0, y0, x1, y1


def cell_marks(rect_bgr, bbox):
    """Per-cell handwritten-ink fraction over the 12 x 31 day grid.

    The printed content of a cell is a small day number, a three-letter weekday
    and, on Sundays, a pale blue fill. A gardien's mark is a pen stroke across
    the cell. So the measure is dark, low-saturation-blue ink as a fraction of
    the cell, with the printed text's own contribution estimated from the
    column's own quietest cells rather than assumed.

    Returns a 12 x 31 float array of ink fractions, and the per-cell pixel area.
    """
    x0, y0, x1, y1 = bbox
    roi = rect_bgr[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2].astype(np.float32)
    s = hsv[:, :, 1].astype(np.float32)
    h = hsv[:, :, 0].astype(np.float32)
    # ink: dark, and not the printed blue fill (hue ~95-130 in OpenCV's 0-179)
    blue = (h > 90) & (h < 135) & (s > 60)
    thr = max(60.0, np.percentile(v, 25) * 0.75)
    ink = ((v < thr) & (~blue)).astype(np.float32)

    H, W = ink.shape
    out = np.zeros((MONTHS, DAYS), dtype=np.float32)
    for m in range(MONTHS):
        cx0, cx1 = int(W * m / MONTHS), int(W * (m + 1) / MONTHS)
        for d in range(DAYS):
            cy0, cy1 = int(H * d / DAYS), int(H * (d + 1) / DAYS)
            cell = ink[cy0:cy1, cx0:cx1]
            out[m, d] = float(cell.mean()) if cell.size else 0.0
    cell_px = (H / DAYS) * (W / MONTHS)
    return out, cell_px


# --------------------------------------------------------------------------
# Generation-aware calibration
#
# There are at least four template generations in the field (2024, 2025, 2026,
# 2027). The first reader gated on the autocorrelation pitch, which is the one
# thing that DOES differ between them: the 2024/25 sheets carry a three-letter
# weekday (LUN, MAR, ...) and no checkbox, the 2026/27 sheets a single letter
# and a printed checkbox. That sub-structure moved the dominant pitch and six
# fully legible sheets were thrown away for it.
#
# What does NOT differ is the grid itself: twelve month columns by thirty-one
# day rows, at a column pitch of roughly 100-140 px and a row pitch of 29-38 px
# on the canonical sheet, in every generation. So the gate now reads the grid
# from the printed tint, which is generation-stable, and the pitch is measured
# rather than assumed.

GEN_CHECKBOX = "2026/27 (checkbox)"
GEN_PLAIN = "2024/25 (no checkbox)"
GEN_UNKNOWN = "undetermined"


def grid_from_bbox(bbox):
    x0, y0, x1, y1 = bbox
    return (x1 - x0) / float(MONTHS), (y1 - y0) / float(DAYS)


def bbox_plausible(bbox):
    """Is this bounding box a 12 x 31 day grid, at any generation's scale?"""
    x0, y0, x1, y1 = bbox
    cw, rh = grid_from_bbox(bbox)
    if not (95.0 <= cw <= 165.0):
        return False, f"month pitch {cw:.0f} px outside 95-165"
    if not (24.0 <= rh <= 42.0):
        return False, f"day pitch {rh:.0f} px outside 24-42"
    if (x1 - x0) < 0.45 * CANON_W:
        return False, "grid spans less than 45% of the sheet width"
    return True, ""


def box_like_count(rect_bgr, bbox):
    """Small filled-outline squares inside the grid: the printed checkbox.

    About two per day cell on a 2026/27 sheet (the checkbox and the day-number
    box), near zero on 2024/25. Only meaningful on a sheet that is imaged well
    enough to resolve them, so the caller must not read a low count as
    'no checkbox' on a poor photograph.
    """
    x0, y0, x1, y1 = bbox
    roi = cv2.cvtColor(rect_bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    cw, rh = grid_from_bbox(bbox)
    cell = cw * rh
    th = cv2.adaptiveThreshold(roi, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, 21, 6)
    cnts, _ = cv2.findContours(th, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    n = 0
    for c in cnts:
        a = cv2.contourArea(c)
        if a < 0.04 * cell or a > 0.55 * cell:
            continue
        x, y, w, h = cv2.boundingRect(c)
        if w < 4 or h < 4 or not (0.55 < w / float(h) < 1.9):
            continue
        if a / float(w * h) < 0.55:
            continue
        n += 1
    return n


def generation(rect_bgr, bbox, rules=None):
    """(label, boxes-per-cell). Undetermined when the image cannot resolve the
    checkbox either way - better than guessing a generation from a blur.

    A low count only means "no checkbox" on a sheet imaged well enough that a
    checkbox would have shown; otherwise it means "cannot tell".
    """
    n = box_like_count(rect_bgr, bbox)
    per = n / float(MONTHS * DAYS)
    if per >= 1.5:
        return GEN_CHECKBOX, per
    if per <= 0.10 and (rules is None or rules >= 0.60):
        return GEN_PLAIN, per
    return GEN_UNKNOWN, per


def cell_window(gen):
    """Where in a day cell the gardien's mark lives, as a fraction of cell width.

    2024/25: day number and three-letter weekday on the left, the mark goes in
    the open area to their right. 2026/27: number, single letter, then a printed
    checkbox occupying the right-hand third.
    """
    if gen == GEN_CHECKBOX:
        return 0.58, 1.00
    if gen == GEN_PLAIN:
        return 0.45, 1.00
    return 0.45, 1.00


def cell_marks_gen(rect_bgr, bbox, gen):
    """Per-cell ink fraction, sampling only the marking area for the generation."""
    x0, y0, x1, y1 = bbox
    roi = rect_bgr[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2].astype(np.float32)
    s = hsv[:, :, 1].astype(np.float32)
    h = hsv[:, :, 0].astype(np.float32)
    tint = (h > 85) & (h < 140) & (s > 45)
    thr = max(60.0, np.percentile(v, 25) * 0.75)
    ink = ((v < thr) & (~tint)).astype(np.float32)
    H, W = ink.shape
    f0, f1 = cell_window(gen)
    out = np.zeros((MONTHS, DAYS), dtype=np.float32)
    for m in range(MONTHS):
        cx0 = W * m / MONTHS
        a = int(cx0 + (W / MONTHS) * f0)
        b = int(cx0 + (W / MONTHS) * f1)
        for d in range(DAYS):
            cy0, cy1 = int(H * d / DAYS), int(H * (d + 1) / DAYS)
            cellpx = ink[cy0:cy1, a:b]
            out[m, d] = float(cellpx.mean()) if cellpx.size else 0.0
    return out, (H / DAYS) * ((b - a) if W else 0)


def month_rule_fraction(rect_bgr, bbox):
    """How many of the eleven interior month boundaries carry a printed rule.

    This is the test that separates a calendar from a shirt. The sheet detector
    can latch onto clothing or foliage and hand back a region whose tint and
    proportions pass every other check; what it cannot produce is eleven
    vertical rules at exactly one-twelfth spacing. Measured on hand-read
    photographs, every legible sheet scored 0.55 or better and every illegible
    one 0.36 or worse.
    """
    x0, y0, x1, y1 = bbox
    g = cv2.cvtColor(rect_bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    gx = np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)).mean(axis=0)
    sd = gx.std()
    if sd < 1e-9:
        return 0.0
    gx = (gx - gx.mean()) / sd
    W = len(gx)
    cw = W / float(MONTHS)
    tol = max(3, int(cw * 0.12))
    hits = 0
    for i in range(1, MONTHS):
        c = int(i * cw)
        a, b = max(0, c - tol), min(W, c + tol + 1)
        if gx[a:b].max() > 1.2:
            hits += 1
    return hits / float(MONTHS - 1)


def fit_month_grid(rect_bgr, bbox):
    """Fit a twelve-column grid to the vertical rules actually present.

    Checking for rules at exact twelfths of the bounding box assumes the box
    edges ARE the grid edges. They are not: the tint-derived box overshoots or
    undershoots by a margin that varies with the photograph, so the expected
    boundaries land between rules and a perfectly legible sheet scores badly.
    Here the rules are found first and a uniform twelve-column grid is fitted to
    them, which both tests for a calendar and registers the grid for sampling.

    Returns (score 0-1, x_left, pitch) in bbox coordinates.
    """
    x0, y0, x1, y1 = bbox
    g = cv2.cvtColor(rect_bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    gx = np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)).mean(axis=0)
    sd = gx.std()
    if sd < 1e-9:
        return 0.0, 0.0, 0.0
    gx = (gx - gx.mean()) / sd
    W = len(gx)
    # candidate rule positions: local maxima above a modest threshold
    peaks = []
    for i in range(2, W - 2):
        if gx[i] > 0.8 and gx[i] >= gx[i - 1] and gx[i] >= gx[i + 1]:
            peaks.append(i)
    if len(peaks) < 6:
        return 0.0, 0.0, 0.0
    peaks = np.array(peaks, dtype=np.float32)

    best = (0.0, 0.0, 0.0)
    # the grid spans most of the box; search plausible pitches and offsets
    for pitch in np.arange(W / 14.0, W / 10.0, max(0.5, W / 900.0)):
        span = pitch * MONTHS
        if span > W * 1.06:
            continue
        for x_left in np.arange(0, max(1.0, W - span) + 1, max(1.0, W / 120.0)):
            hits = 0
            tol = max(3.0, pitch * 0.10)
            for i in range(MONTHS + 1):
                xc = x_left + i * pitch
                if np.min(np.abs(peaks - xc)) <= tol:
                    hits += 1
            sc = hits / float(MONTHS + 1)
            if sc > best[0]:
                best = (sc, float(x_left), float(pitch))
    return best


def cell_marks_fitted(rect_bgr, bbox, gen, x_left, pitch):
    """Per-cell ink fraction using the fitted column grid."""
    x0, y0, x1, y1 = bbox
    roi = rect_bgr[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2].astype(np.float32)
    s = hsv[:, :, 1].astype(np.float32)
    h = hsv[:, :, 0].astype(np.float32)
    tint = (h > 85) & (h < 140) & (s > 45)
    thr = max(60.0, np.percentile(v, 25) * 0.75)
    ink = ((v < thr) & (~tint)).astype(np.float32)
    H, W = ink.shape
    f0, f1 = cell_window(gen)
    out = np.zeros((MONTHS, DAYS), dtype=np.float32)
    for m in range(MONTHS):
        a = int(round(x_left + (m + f0) * pitch))
        b = int(round(x_left + (m + f1) * pitch))
        a, b = max(0, a), min(W, b)
        if b <= a:
            continue
        for d in range(DAYS):
            cy0, cy1 = int(H * d / DAYS), int(H * (d + 1) / DAYS)
            cell = ink[cy0:cy1, a:b]
            out[m, d] = float(cell.mean()) if cell.size else 0.0
    return out


def fit_day_grid(rect_bgr, bbox):
    """Fit a thirty-one-row grid to the horizontal rules actually present.

    The column fit fixed half the registration problem; the rows were still
    divided evenly across the tint-derived bounding box, which overshoots by a
    variable margin. That misalignment let printed text from a neighbouring row
    leak into a cell's ink measurement, and the false-positive rate on cells
    that cannot be marked rose to meet the rate on real days.

    Returns (score 0-1, y_top, pitch) in bbox coordinates.
    """
    x0, y0, x1, y1 = bbox
    g = cv2.cvtColor(rect_bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    gy = np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)).mean(axis=1)
    sd = gy.std()
    if sd < 1e-9:
        return 0.0, 0.0, 0.0
    gy = (gy - gy.mean()) / sd
    H = len(gy)
    peaks = [i for i in range(2, H - 2)
             if gy[i] > 0.6 and gy[i] >= gy[i - 1] and gy[i] >= gy[i + 1]]
    if len(peaks) < 10:
        return 0.0, 0.0, 0.0
    peaks = np.array(peaks, dtype=np.float32)

    best = (0.0, 0.0, 0.0)
    for pitch in np.arange(H / 36.0, H / 26.0, max(0.25, H / 1400.0)):
        span = pitch * DAYS
        if span > H * 1.06:
            continue
        for y_top in np.arange(0, max(1.0, H - span) + 1, max(1.0, H / 200.0)):
            tol = max(2.0, pitch * 0.14)
            hits = sum(1 for i in range(DAYS + 1)
                       if np.min(np.abs(peaks - (y_top + i * pitch))) <= tol)
            sc = hits / float(DAYS + 1)
            if sc > best[0]:
                best = (sc, float(y_top), float(pitch))
    return best


def cell_marks_registered(rect_bgr, bbox, gen, x_left, x_pitch, y_top, y_pitch):
    """Per-cell ink fraction on a grid registered in both axes.

    The sampled window is inset from the fitted cell on all four sides, so a
    printed rule sitting exactly on a boundary is not counted as a gardien's
    mark.
    """
    x0, y0, x1, y1 = bbox
    roi = rect_bgr[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2].astype(np.float32)
    s = hsv[:, :, 1].astype(np.float32)
    h = hsv[:, :, 0].astype(np.float32)
    tint = (h > 85) & (h < 140) & (s > 45)
    thr = max(60.0, np.percentile(v, 25) * 0.75)
    ink = ((v < thr) & (~tint)).astype(np.float32)
    H, W = ink.shape
    f0, f1 = cell_window(gen)
    inset_y = max(1.0, y_pitch * 0.18)
    out = np.zeros((MONTHS, DAYS), dtype=np.float32)
    for m in range(MONTHS):
        a = int(round(x_left + (m + f0) * x_pitch))
        b = int(round(x_left + (m + f1) * x_pitch))
        a, b = max(0, a + 1), min(W, b - 1)
        if b <= a:
            continue
        for d in range(DAYS):
            c0 = int(round(y_top + d * y_pitch + inset_y))
            c1 = int(round(y_top + (d + 1) * y_pitch - inset_y))
            c0, c1 = max(0, c0), min(H, c1)
            if c1 <= c0:
                continue
            cell = ink[c0:c1, a:b]
            out[m, d] = float(cell.mean()) if cell.size else 0.0
    return out


# --------------------------------------------------------------------------
# Row registration from the printed shading (29 Sep 2026)
#
# fit_day_grid searched row pitches between 1/36 and 1/26 of the tint bounding
# box. That box is taken from every blue pixel on the sheet, so on most
# photographs it runs up through the header photographs, the title and the
# MadAvance / SaniTap logos. The true pitch then lay outside the search range,
# the fit settled on the range's edge, and the 31 rows were stretched over the
# header as well as the grid: "days 1-5" were read off the photographs and
# lettering, and every lower row was shifted too. Against Adriaan Mol's
# transcription of 28 Sep 2026 that was 366 of the 394 false X, all on days
# 1-5. The rows are now registered on things only the day grid carries:
#
#   * the shaded weekend cells (blue on the 2024/25 sheets). They recur every
#     seven rows in every column; the pitch comes from the horizontal rules
#     between them, and the 31-row window that holds the most shaded cells
#     fixes which row is day 1. Every year 2024-2027 has a month that starts
#     on a Sunday and one whose 31st is a Sunday, so a window one row too high
#     or too low always loses a shaded cell;
#   * on the 2026/27 sheets, whose shading is grey, the saturated month-name
#     band printed directly above day 1.
#
# Each month column gets its own vertical offset, because a folded or curled
# sheet does not keep a row line straight across. When neither anchor is
# found the old fit_day_grid is used, and the reader records which was used.

def shading_mask(rect_bgr):
    """Printed weekend shading: bluer than the paper around it.

    Relative, not absolute: a photograph with a blue cast turns the whole
    sheet 'blue' under a fixed HSV range, which is why the tint box so often
    covered the full canvas.
    """
    im = rect_bgr.astype(np.float32)
    bl = im[..., 0] - (im[..., 1] + im[..., 2]) / 2
    d = bl - cv2.GaussianBlur(bl, (0, 0), 40)
    th, _ = cv2.threshold(np.clip(d * 4 + 128, 0, 255).astype(np.uint8), 0, 255,
                          cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    m = (d > max(5.0, (th - 128) / 4.0)).astype(np.uint8) * 255
    return cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))


def shading_patches(rect_bgr, x0, x1):
    """(x, y, w, h) of the shaded day cells between x0 and x1, or [].

    A shaded cell (or a shaded weekend pair) is a solid bar about a month
    column's width wide and one or two rows high. Photographs, logos and the
    title are not that shape; a stray patch far above or below the rest is
    dropped.
    """
    blue = shading_mask(rect_bgr)
    n, _, st, _ = cv2.connectedComponentsWithStats(blue, 8)
    Hs, Ws = blue.shape
    out = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if not (0.012 * Hs <= h <= 0.075 * Hs):
            continue
        if not (0.035 * Ws <= w <= 0.10 * Ws):
            continue
        if w < 1.2 * h or a < 0.55 * w * h:
            continue
        if x + w / 2 < x0 or x + w / 2 > x1:
            continue
        out.append((x, y, w, h))
    if len(out) < 15:
        return []
    b = np.array(out, float)
    mw = np.median(b[:, 2])
    b = b[np.abs(b[:, 2] - mw) <= 0.30 * mw]
    b = b[np.argsort(b[:, 1])]
    while len(b) > 15 and b[1, 1] - b[0, 1] > 0.10 * Hs:
        b = b[1:]
    bot = b[:, 1] + b[:, 3]
    o = np.argsort(bot)
    b, bot = b[o], bot[o]
    while len(b) > 15 and bot[-1] - bot[-2] > 0.10 * Hs:
        b, bot = b[:-1], bot[:-1]
    return b if len(b) >= 15 else []


def _rule_phase(prof, ys, p):
    """Strength and phase of a period-p comb in a rule-energy profile."""
    z = np.sum(prof * np.exp(2j * np.pi * ys / p))
    return abs(z), (np.angle(z) / (2 * np.pi) * p) % p


def _rule_pitch(gy, ya, yb, xa, xb):
    prof = gy[ya:yb, xa:xb].mean(axis=1)
    prof = np.clip(prof - np.median(prof), 0, None)
    ys = np.arange(ya, yb, dtype=float)
    best = (0.0, 0.0, 0.0)
    for p in np.arange(20.0, 46.0, 0.02):
        s, ph = _rule_phase(prof, ys, p)
        if s > best[0]:
            best = (s, p, ph)
    s, p, ph = best
    s2, ph2 = _rule_phase(prof, ys, p / 2)
    if p / 2 >= 20 and s2 > 0.8 * s:          # a double pitch must not win
        p, ph = p / 2, ph2
    return p, ph


def header_band_bottom(rect_bgr, x0, x1):
    """Lower edge of the saturated month-name band (2026/27 sheets), or None."""
    hsv = cv2.cvtColor(rect_bgr, cv2.COLOR_BGR2HSV)
    xa, xb = int(max(0, x0)), int(min(rect_bgr.shape[1], x1))
    if xb - xa < 10:
        return None
    band = ((hsv[:, xa:xb, 1] > 110) & (hsv[:, xa:xb, 0] > 75)
            & (hsv[:, xa:xb, 0] < 105) & (hsv[:, xa:xb, 2] > 90))
    on = band.mean(axis=1) > 0.55
    Hs = len(on)
    runs, y = [], 0
    while y < Hs:
        if on[y]:
            s = y
            while y < Hs and on[y]:
                y += 1
            runs.append((s, y))
        y += 1
    runs = [r for r in runs if 12 <= r[1] - r[0] <= 70 and r[0] < 0.5 * Hs]
    if not runs:
        return None
    return max(runs, key=lambda r: r[1] - r[0])[1]


def fit_day_rows(rect_bgr, bbox, x_left, x_pitch):
    """Register the 31 day rows. -> (method, y_top, pitch, offsets) in rectified
    sheet coordinates, offsets one per month column; or None."""
    x0 = bbox[0] + x_left
    x1 = x0 + MONTHS * x_pitch
    g = cv2.cvtColor(rect_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gy = np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3))
    Hs, Ws = g.shape
    xa, xb = int(max(0, x0)), int(min(Ws, x1))

    P = shading_patches(rect_bgr, x0, x1)
    if len(P):
        ya, yb = int(P[:, 1].min()), int((P[:, 1] + P[:, 3]).max())
        p, ph = _rule_pitch(gy, ya, yb, xa, xb)
        # a shaded cell's top edge sits just below its row's upper rule
        idx = np.floor((P[:, 1] - ph + 0.35 * p) / p).astype(int)
        cands = []
        for k0 in range(idx.min() - DAYS + 1, idx.max() + 1):
            inside = int(np.sum((idx >= k0) & (idx <= k0 + DAYS - 1)))
            cands.append((inside, bool(np.any(idx == k0)),
                          bool(np.any(idx == k0 + DAYS - 1)), k0))
        cands.sort(reverse=True)
        y_top = ph + cands[0][3] * p
        method = "shading"
        # per column: the phase of that column's own rules
        offs = np.zeros(MONTHS)
        yA, yB = int(max(0, y_top)), int(min(Hs, y_top + DAYS * p))
        yy = np.arange(yA, yB, dtype=float)
        for m in range(MONTHS):
            a = int(max(0, x0 + m * x_pitch))
            b = int(min(Ws, x0 + (m + 1) * x_pitch))
            if b - a < 10 or yB - yA < 10:
                continue
            pr = gy[yA:yB, a:b].mean(axis=1)
            pr = np.clip(pr - np.median(pr), 0, None)
            _, phm = _rule_phase(pr, yy, p)
            offs[m] = ((phm - ph + p / 2) % p) - p / 2
        return method, float(y_top), float(p), offs

    hb = header_band_bottom(rect_bgr, x0, x1)
    if hb is None:
        return None
    yb = int(min(Hs, hb + 0.75 * (Hs - hb)))
    p, _ = _rule_pitch(gy, hb, yb, xa, xb)
    # the band's lower edge is day 1's upper rule; measured per column,
    # since a curled sheet does not keep one row line straight across
    offs = np.zeros(MONTHS)
    for m in range(MONTHS):
        a, b = x0 + m * x_pitch, x0 + (m + 1) * x_pitch
        hm = header_band_bottom(rect_bgr, a + 0.1 * x_pitch, b - 0.1 * x_pitch)
        if hm is not None and abs(hm - hb) < 0.6 * p:
            offs[m] = hm - hb
    return "header band", float(hb), float(p), offs


def cell_marks_rows(rect_bgr, bbox, gen, x_left, x_pitch, y_top, y_pitch, offs):
    """Per-cell ink fraction on rows from fit_day_rows (sheet coordinates).

    Same ink measure, marking window and inset as cell_marks_registered; only
    the row positions differ, and they may lie outside the tint box.
    """
    x0, y0, x1, y1 = bbox
    hsv = cv2.cvtColor(rect_bgr, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2].astype(np.float32)
    s = hsv[:, :, 1].astype(np.float32)
    h = hsv[:, :, 0].astype(np.float32)
    tint = (h > 85) & (h < 140) & (s > 45)
    thr = max(60.0, np.percentile(v[y0:y1, x0:x1], 25) * 0.75)
    ink = ((v < thr) & (~tint)).astype(np.float32)
    H, W = ink.shape
    f0, f1 = cell_window(gen)
    inset_y = max(1.0, y_pitch * 0.18)
    out = np.zeros((MONTHS, DAYS), dtype=np.float32)
    for m in range(MONTHS):
        a = int(round(x0 + x_left + (m + f0) * x_pitch))
        b = int(round(x0 + x_left + (m + f1) * x_pitch))
        a, b = max(0, a + 1), min(W, b - 1)
        if b <= a:
            continue
        yt = y_top + offs[m]
        for d in range(DAYS):
            c0 = int(round(yt + d * y_pitch + inset_y))
            c1 = int(round(yt + (d + 1) * y_pitch - inset_y))
            c0, c1 = max(0, c0), min(H, c1)
            if c1 <= c0:
                continue
            out[m, d] = float(ink[c0:c1, a:b].mean())
    return out


# --------------------------------------------------------------------------
# Reader v3 (1 Oct 2026): registration on the printed day text, ink against
# the local background. Diagnosis on transcription round 1 (40 days both human
# readers marked X, 40 both read blank; data/reader_diagnosis/): the v2 reader
# found none of the 40. Its month columns started at the printed weekday
# rather than the day-number rule, and on some sheets a whole column or row
# out; its ink test masked every blue pixel as printed shading, which removes
# blue and purple ballpoint; and its 0.20 ink threshold sits above a pencil or
# ballpoint X, which covers 0.03-0.10 of the window.
#
#   * registration: OCR of the printed month names fixes each column, and of
#     the day numbers each column's left edge and row line, fitted per column
#     so a leaning or curled column is followed; orientation is the
#     rectification whose month names read left to right;
#   * ink: darker than the local paper by a fixed margin, in grey, so blue,
#     purple, red and pencil all count, with the printed rules removed;
#   * a cell's score is what exceeds what the sheet prints there (its day
#     number, the same in every month, and its weekday, the same in every cell
#     of that weekday), over the right of the cell.
# Result on round 1 (data/reader_validation.json): better than v2 but far
# from the publication gate.
# Nothing in production calls this until the validation gate passes.
# --------------------------------------------------------------------------

V3_DARK = 32            # grey levels darker than the local paper


def v3_dark(rect_bgr, pitch, col_pitch=None):
    """Ink darker than the local paper, with the printed rules taken out.

    Long straight runs - the grid rules and the edges of the shaded cells -
    are removed by opening with a long horizontal and a long vertical line;
    a hand-drawn X, tick or bar is shorter than either and survives."""
    g = cv2.cvtColor(rect_bgr, cv2.COLOR_BGR2GRAY)
    k = int(max(15, pitch * 1.2)) | 1
    k = min(k, 99)
    bg = cv2.medianBlur(g, k)
    dark = ((bg.astype(np.int16) - g.astype(np.int16)) > V3_DARK).astype(np.uint8)
    if col_pitch:
        hl = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((1, max(9, int(col_pitch * 0.45))), np.uint8))
        vl = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((max(9, int(pitch * 1.6)), 1), np.uint8))
        lines = cv2.dilate(hl | vl, np.ones((3, 3), np.uint8))
        dark = dark & (1 - lines)
    return dark.astype(bool)


MONTH_NAMES = ["JANVIER", "FEVRIER", "MARS", "AVRIL", "MAI", "JUIN", "JUILLET", "AOUT",
               "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DECEMBRE"]
_OCR = None


def _ocr():
    global _OCR
    if _OCR is None:
        from rapidocr_onnxruntime import RapidOCR
        _OCR = RapidOCR()
    return _OCR


def _month_of(text):
    import difflib, unicodedata
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().upper()
    t = "".join(ch for ch in t if ch.isalpha())
    if len(t) < 3:
        return None
    best = max(range(MONTHS), key=lambda m: difflib.SequenceMatcher(None, t, MONTH_NAMES[m]).ratio())
    r = difflib.SequenceMatcher(None, t, MONTH_NAMES[best]).ratio()
    return best if r >= 0.75 and (len(t) >= 4 or t == "MAI") else None


def _robust_line(xs, ys):
    """y = a + b x by repeated median (Siegel), tolerant of misread tokens."""
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    n = len(xs)
    if n < 2:
        return None
    slopes = []
    for i in range(n):
        dx = xs - xs[i]
        ok = dx != 0
        if ok.any():
            slopes.append(np.median((ys[ok] - ys[i]) / dx[ok]))
    b = float(np.median(slopes))
    a = float(np.median(ys - b * xs))
    return a, b


def register_ocr(rect):
    """Register the day grid on the printed text. -> dict or None.

    Month names give each column's centre (a straight line in the month
    index: centre = x0 + m * pitch). Day numbers give the rows: in each
    column, a number n is centred on y = top_m + (n - 0.5) * row_pitch, fitted
    per column so a curled sheet keeps its own row line in each column."""
    # the day numbers are about 12 px tall on the rectified sheet; read at
    # twice the size they are found three to five times as often
    big = cv2.resize(rect, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    res, _ = _ocr()(big)
    res = res or []
    months, nums = [], []
    for box, text, conf in res:
        b = np.asarray(box, float) / 2.0
        xc, yc = b[:, 0].mean(), b[:, 1].mean()
        xL, h = b[:, 0].min(), b[:, 1].max() - b[:, 1].min()
        m = _month_of(text)
        if m is not None:
            months.append((m, xc, yc))
            continue
        import re as _re
        mt = _re.match(r"^\s*(\d{1,2})", text)
        if mt and 1 <= int(mt.group(1)) <= DAYS and h > 4:
            # the number's own box: a fused "01JEU" box keeps the number at its left
            nums.append((int(mt.group(1)), xL, yc, float(conf)))
    if len({m for m, _, _ in months}) < 4:
        return {"month_names": len({m for m, _, _ in months}), "numbers": len(nums)}
    line = _robust_line([m for m, _, _ in months], [x for _, x, _ in months])
    x0, xp = line
    if xp <= 20:
        return {"month_names": len(months), "numbers": len(nums)}
    header_y = float(np.median([y for _, _, y in months]))
    # assign numbers to columns: a day number sits at the left of its column
    cols = {m: [] for m in range(MONTHS)}
    for n, xL, yc, cf in nums:
        if yc < header_y:
            continue
        m = int(np.floor((xL - (x0 - xp / 2)) / xp + 0.05))
        if 0 <= m < MONTHS:
            cols[m].append((n, yc))
    pooled = [(n, y) for m in cols for n, y in cols[m]]
    if len(pooled) < 30:
        return {"month_names": len(months), "numbers": len(nums)}
    # each column on its own numbers: the left edge and the row line as
    # straight lines in the day number, so a leaning or curled column and a
    # pitch that changes with perspective are followed column by column
    colx = {m: [] for m in range(MONTHS)}
    for n, xL, yc, cf in nums:
        if yc < header_y:
            continue
        m = int(np.floor((xL - (x0 - xp / 2)) / xp + 0.05))
        if 0 <= m < MONTHS:
            colx[m].append((n, xL, yc))
    dd = np.arange(DAYS) + 0.5                    # the centre of day d+1, in rows
    Lc = np.full((MONTHS, DAYS), np.nan)
    Yc = np.full((MONTHS, DAYS), np.nan)
    pitches = []
    for m, t in colx.items():
        if len(t) < 5:
            continue
        n_ = np.array([n - 0.5 for n, _, _ in t])
        ly = _robust_line(n_, [y for _, _, y in t])
        lx = _robust_line(n_, [x for _, x, _ in t])
        if ly is None or lx is None or ly[1] <= 3:
            continue
        # drop misread numbers (a "91" for "01") and refit
        res = np.abs(np.array([y for _, _, y in t]) - (ly[0] + ly[1] * n_))
        keep = res < 0.5 * ly[1]
        if keep.sum() >= 5 and keep.sum() < len(t):
            ly = _robust_line(n_[keep], np.array([y for _, _, y in t])[keep])
            lx = _robust_line(n_[keep], np.array([x for _, x, _ in t])[keep])
        Yc[m] = ly[0] + ly[1] * dd
        Lc[m] = lx[0] + lx[1] * dd
        pitches.append(ly[1])
    ok = ~np.isnan(Lc[:, 0])
    # a column whose fit disagrees with both neighbours by more than a third
    # of a row (or of the left-edge spacing) was fitted on misread numbers
    for _ in range(2):
        for m in range(MONTHS):
            if not ok[m]:
                continue
            nb = [k for k in (m - 1, m + 1) if 0 <= k < MONTHS and ok[k]]
            if len(nb) < 1:
                continue
            ey = np.mean([Yc[k] for k in nb], axis=0)
            dev = np.abs(Yc[m] - ey)
            pm = np.median([np.median(np.diff(Yc[k])) for k in nb])
            if np.median(dev) > 0.35 * pm or dev.max() > 0.8 * pm:
                if len(nb) == 2:
                    ok[m] = False
    if ok.sum() < 6:
        return {"month_names": len(months), "numbers": len(nums)}
    idx = np.arange(MONTHS)
    for d in range(DAYS):                     # a column with too few numbers takes its neighbours'
        Lc[~ok, d] = np.interp(idx[~ok], idx[ok], Lc[ok, d])
        Yc[~ok, d] = np.interp(idx[~ok], idx[ok], Yc[ok, d])
    yp = float(np.median(pitches))
    pad = 0.04 * xp                           # the column rule sits just left of the number
    left = Lc - pad
    right = np.empty_like(left)
    right[:-1] = left[1:]
    right[-1] = left[-1] + np.median(np.diff(left, axis=0), axis=0)
    rp = np.empty_like(Yc)                    # local row pitch, from the row line itself
    rp[:, 1:-1] = (Yc[:, 2:] - Yc[:, :-2]) / 2
    rp[:, 0], rp[:, -1] = rp[:, 1], rp[:, -2]
    return {"x0": x0 - xp / 2, "xp": xp, "yp": yp, "left": left, "right": right,
            "top": Yc - rp / 2, "bottom": Yc + rp / 2,
            "month_names": len({m for m, _, _ in months}), "numbers": len(nums),
            "numbers_used": int(sum(len(t) for t in colx.values())), "columns_fitted": int(ok.sum())}


def read_v3(im, small, year=None, prefer=None):
    """The v3 reading of one photograph -> dict with 'scores' (12 x 31), or
    {'why': ...}. Orientation: the reader's own choice first, then the other
    three rectifications, keeping the one whose month names read."""
    if im is None:
        return {"why": "file unreadable"}
    q, frac = sheet_quad(small)
    if q is None:
        return {"why": "no sheet found"}
    scale = im.shape[1] / small.shape[1]
    first = analyse(im, q, scale)["k"] if prefer is None else prefer
    best = None
    for k in [first] + [k for k in range(4) if k != first]:
        r = rectify(im, np.roll(q, -k, axis=0), scale)
        g = register_ocr(r)
        g["k"], g["rect"] = k, r
        # a registered grid beats an unregistered one: month names stacked
        # down the page (a sheet read turned 90 degrees) do not register
        rank = lambda h: ("xp" in h, h.get("columns_fitted", 0), h.get("month_names", 0), h.get("numbers", 0))
        if best is None or rank(g) > rank(best):
            best = g
        if "xp" in g and g["month_names"] >= 8 and g["numbers_used"] >= 100:
            break
    if "xp" not in best:
        return {"why": f"grid not registered from the printed text (month names {best.get('month_names', 0)}, "
                       f"numbers {best.get('numbers', 0)})"}
    bb = grid_bbox(best["rect"])
    best["gen"] = generation(best["rect"], bb)[0] if bb is not None else GEN_UNKNOWN
    dark = v3_dark(best["rect"], best["yp"], best["xp"])
    best["dark"] = dark
    best["scores"] = v3_cells(dark, best, year)
    return best


V3_CELL = (16, 48)          # a day cell resampled to rows x columns
V3_NUMBER_ZONE = 0.22       # the day number fills the left of the cell; the weekday follows


def v3_box(g, m, d, inset=(0.02, 0.08)):
    """(x0, y0, x1, y1) of day cell (m, d) on the registered grid."""
    L, R, T, B = g["left"][m, d], g["right"][m, d], g["top"][m, d], g["bottom"][m, d]
    ix, iy = inset[0] * (R - L), inset[1] * (B - T)
    return L + ix, T + iy, R - ix, B - iy


def v3_cell_stack(dark, g):
    """Every day cell's ink, resampled to one size. -> (12, 31, h, w)."""
    h, w = V3_CELL
    f = dark.astype(np.float32)
    H, W = f.shape
    out = np.zeros((MONTHS, DAYS, h, w), np.float32)
    for m in range(MONTHS):
        for d in range(DAYS):
            a, c0, b, c1 = (int(round(v)) for v in v3_box(g, m, d))
            a, b, c0, c1 = max(0, a), min(W, b), max(0, c0), min(H, c1)
            if b - a > 4 and c1 - c0 > 2:
                out[m, d] = cv2.resize(f[c0:c1, a:b], (w, h), interpolation=cv2.INTER_AREA)
    return out


def v3_cells(dark, g, year=None):
    """Hand-added ink per day cell: the cell less what the sheet prints there.

    The printed content of a cell is its day number (the same in every month
    column) and its weekday (the same in every cell of that weekday, shading
    included). The template for a cell is therefore the median, over the
    twelve months, of cells with the same day number in the number zone, and
    the median of cells with the same weekday elsewhere. What exceeds it is
    what someone wrote. Without a sheet year the weekday cannot be known and
    the whole-sheet median stands in for it."""
    import datetime as _dt
    S = v3_cell_stack(dark, g)
    h, w = V3_CELL
    nz = int(round(V3_NUMBER_ZONE * w))
    by_day = np.median(S, axis=0)                       # (31, h, w)
    wd = np.full((MONTHS, DAYS), -1)
    if year:
        for m in range(MONTHS):
            for d in range(DAYS):
                try:
                    wd[m, d] = _dt.date(int(year), m + 1, d + 1).weekday()
                except ValueError:
                    pass
    by_wd = {k: np.median(S[wd == k], axis=0) for k in range(7) if (wd == k).sum() >= 5}
    whole = np.median(S.reshape(-1, h, w), axis=0)
    out = np.zeros((MONTHS, DAYS))
    for m in range(MONTHS):
        for d in range(DAYS):
            t = by_wd.get(wd[m, d], whole).copy()
            t[:, :nz] = np.maximum(t[:, :nz], by_day[d][:, :nz])
            # printing jitters by a pixel or two from cell to cell: dilate the
            # template and let the cell shift a little before what is left over
            # is counted as written
            t = cv2.dilate(t, np.ones((3, 3), np.uint8))
            c = S[m, d]
            best = None
            for dy in (-1, 0, 1):
                for dx in (-2, -1, 0, 1, 2):
                    sh = np.roll(np.roll(c, dy, axis=0), dx, axis=1)
                    # the right of the cell, past the day number: where a mark is
                    # written and the printing varies least (chosen on the
                    # odd-numbered round-1 calendars: AUC 0.957 against 0.939
                    # for the whole cell)
                    r = float(np.clip(sh - t, 0, None)[2:-2, int(0.3 * (w - 6)) + 3:-3].mean())
                    best = r if best is None or r < best else best
            out[m, d] = best
    return out
