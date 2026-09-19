"""Abstract, permanent-bolt list, revision table, notes, mark/grid/level box."""
import re

import pymupdf

from ..geometry import cluster, join_tokens, num, xc, yc
from ..models import Abstract, AbstractRow, BoltRow, MarkLocation, RevisionRow

DATE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
MARK_RE = re.compile(r"^\d[A-Za-z]{1,4}\d+$")
BOLT_COLS = list(BoltRow.model_fields)


def _rows_by_y(words, tol=4):
    rows = {}
    for w in words:
        rows.setdefault(round(yc(w) / tol), []).append(w)
    return [sorted(v, key=lambda w: w[0]) for _, v in sorted(rows.items())]


def parse_abstract(layout):
    head, end = layout.find("ABSTRACT"), layout.find("TOTAL IN KGS.")
    if not head or not end:
        return None
    head, end = head[0], end[0]
    hdr = layout.words_in((head.x0 - 150, head.y1, head.x1 + 150, head.y1 + 20))
    sr = [w for w in hdr if w[4] == "SR."]
    wt = [w for w in hdr if w[4] == "WT."]
    if not sr or not wt:
        return None
    y_body = max(w[3] for w in hdr) + 1                      # below "SR. No. DESCRIPTION TOTAL WT."
    region = (sr[0][0] - 5, y_body, wt[0][2] + 15, end.y1 + 2)
    rows, total = [], None
    for line in _rows_by_y(layout.words_in(region)):
        toks = [t[4] for t in join_tokens(line)]
        if toks[:3] == ["TOTAL", "IN", "KGS."]:
            total = num(toks[-1])
        elif len(toks) >= 3 and toks[0].isdigit() and num(toks[-1]) is not None:
            rows.append(AbstractRow(sr=int(toks[0]), description=" ".join(toks[1:-1]), total_wt=num(toks[-1])))
    return Abstract(rows=rows, total_kg=total)


def parse_bolts(layout):
    t = layout.find("List of Permanent Bolts")
    tb = layout.find("TATA STEEL LIMITED")
    if not t or not tb:
        return []
    t, tb = t[0], tb[0]
    conn = layout.find("CONNECTED", clip=pymupdf.Rect(0, t.y0 - 5, t.x0, t.y1 + 40))
    x0 = conn[0].x0 - 5 if conn else t.x0 - 450
    circ = [r for r in layout.find("TSL INTERNAL CIRCULATION") if r.x0 > t.x1]
    x1 = circ[0].x0 - 5 if circ else layout.width - 20
    words = layout.words_in((x0, t.y1, x1, tb.y0 - 5))
    spec = [w for w in words if w[4] == "Specification"]
    if not spec:
        return []
    y_hdr = min(w[1] for w in spec)
    hdr = sorted([w for w in words if abs(w[1] - y_hdr) < 4 and w[4] not in ("ASSEMBLY", "MARK")], key=lambda w: w[0])
    centers = [x0 + 25] + [xc(w) for w in hdr]
    if len(centers) != len(BOLT_COLS):
        raise ValueError(f"bolt header has {len(centers)} columns, expected {len(BOLT_COLS)}")
    body = [w for w in words if w[1] > y_hdr + 8]
    anchors = sorted(yc(w) for w in body if w[4] == "HEX" and abs(xc(w) - centers[2]) < 25)
    rows = []
    for i, y in enumerate(anchors):
        y0 = (anchors[i - 1] + y) / 2 if i else y_hdr + 8
        y1 = (y + anchors[i + 1]) / 2 if i + 1 < len(anchors) else tb.y0 - 5
        cells = {c: [] for c in BOLT_COLS}
        for w in sorted([w for w in body if y0 <= yc(w) < y1], key=lambda w: (round(w[1]), w[0])):
            j = min(range(len(centers)), key=lambda k: abs(centers[k] - xc(w)))
            cells[BOLT_COLS[j]].append(w[4])
        rows.append(BoltRow(**{k: " ".join(v) for k, v in cells.items()}))
    return rows


def parse_revisions(layout):
    hdrs = [h for h in layout.find("REVISION") if h.y0 > layout.height * 0.8 and h.x0 < layout.width * 0.3]
    if not hdrs:
        return []
    h = hdrs[0]
    hw = layout.words_in((0, h.y0 - 3, h.x1 + 700, h.y1 + 3))
    cols = {}
    for w in sorted(hw, key=lambda w: w[0]):                  # leftmost wins ("REF. DRG. NO." also has NO.)
        if w[4] in ("NO.", "DATE", "REVISION", "DRN.", "CHD.", "APP.") and w[4] not in cols:
            cols[w[4]] = xc(w)
    if not {"DATE", "DRN.", "CHD.", "APP."} <= cols.keys():
        return []
    x_max = cols["APP."] + 30
    words = layout.words_in((0, h.y0 - 200, x_max, h.y0 - 1))
    rows = []
    for d in sorted((w for w in words if DATE.match(w[4])), key=lambda w: w[1]):
        line = [w for w in words if abs(yc(w) - yc(d)) < 5]
        def col(name, lo, hi):
            return " ".join(w[4] for w in line if lo <= xc(w) < hi)
        mid = lambda a, b: (cols[a] + cols[b]) / 2
        rev_lo = cols.get("NO.", cols["DATE"]) - 15            # border grid letter sits ~20pt left
        rows.append(RevisionRow(
            rev=col("rev", rev_lo, mid("NO.", "DATE") if "NO." in cols else cols["DATE"] - 20),
            date=d[4],
            description=col("desc", d[2] + 1, mid("REVISION", "DRN.") if "REVISION" in cols else cols["DRN."] - 30),
            drn=col("drn", mid("REVISION", "DRN.") if "REVISION" in cols else cols["DRN."] - 30, mid("DRN.", "CHD.")),
            chd=col("chd", mid("DRN.", "CHD."), mid("CHD.", "APP.")),
            app=col("app", mid("CHD.", "APP."), x_max),
        ))
    return rows


def parse_notes(layout):
    first = layout.find("1. ALL DIMENSIONS")
    if not first:
        return []
    f = first[0]
    stop = [r for r in layout.find("NOTES") if r.y0 > f.y0]
    y1 = min(r.y0 for r in stop) - 1 if stop else f.y0 + 90
    notes = []
    for line in _rows_by_y(layout.words_in((f.x0 - 5, f.y0 - 2, f.x0 + 420, y1)), tol=3):
        s = " ".join(w[4] for w in line)
        if re.match(r"^\d+\.\s", s):
            notes.append(s)
        elif notes:
            notes[-1] += " " + s
    return notes


def parse_mark_locations(layout):
    """MARK NO. / GRID LOCATION / LEVEL box: one row per erected instance (16362 has two),
    rows separated by horizontal rules spanning the box."""
    g = layout.find("GRID LOCATION")
    if not g:
        return []
    g = g[0]
    hdr = layout.words_in((0, g.y0 - 3, g.x1 + 200, g.y1 + 3))
    cols = {w[4]: xc(w) for w in hdr if w[4] in ("MARK", "GRID", "LEVEL")}
    if len(cols) < 3:
        return []
    spans = lambda s: (min(s[0], s[2]), max(s[0], s[2]))
    rules = [s for s in layout.segments if abs(s[1] - s[3]) < 0.5 and g.y1 - 2 <= s[1] <= g.y1 + 120
             and spans(s)[0] < cols["MARK"] and spans(s)[1] > cols["LEVEL"]]
    head = [s for s in rules if s[1] <= g.y1 + 3]
    if head:   # row rules span exactly the header rule's width; drawing lines below the box do not
        hx0, hx1 = spans(head[0])
        rules = [s for s in rules if abs(spans(s)[0] - hx0) < 3 and abs(spans(s)[1] - hx1) < 3]
    x0 = min(spans(s)[0] for s in rules) if rules else cols["MARK"] - 40
    x1 = max(spans(s)[1] for s in rules) if rules else cols["LEVEL"] + 60
    ys = [sum(c) / len(c) for c in cluster([s[1] for s in rules], 1.5)]
    bands = [(a, b) for a, b in zip(ys, ys[1:]) if b - a < 25] or [(g.y1 + 1, g.y1 + 16)]
    mid_mg, mid_gl = (cols["MARK"] + cols["GRID"]) / 2, (cols["GRID"] + cols["LEVEL"]) / 2
    rows = []
    for y0, y1 in bands:
        ws = sorted(layout.words_in((x0, y0, x1, y1)), key=lambda w: w[0])
        mark = " ".join(w[4] for w in ws if xc(w) < mid_mg)
        grid = " ".join(w[4] for w in ws if mid_mg <= xc(w) < mid_gl)
        level = " ".join(w[4] for w in ws if xc(w) >= mid_gl)
        if MARK_RE.match(mark):
            rows.append(MarkLocation(mark_no=mark, grid_location=grid, level=level))
    return rows
