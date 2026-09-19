"""Tekla 'BILL OF MATERIALS' table.

Layout facts (checked independently on the 5 samples, PyMuPDF 1.28):
- Header frame: the longest horizontal line just under the title that spans it. Sheet 14278 also has a
  stray line off the page (x 5221-8048), so the frame must span the title and lie on the page.
- Rows are separated by full-width rules and the numeric columns have vertical rulings, but the
  MARK | ITEM | SECTION block has no vertical rulings, and page-wide find_tables() merges ABSTRACT into
  the BOM. So numeric column edges come from the header words (snapped to a ruling between two headers
  when present), the left block is split by tokens, and rows come from clustering word y-centres.
- find_tables() clipped to the BOM frame reads the same rows; cross_check_bom() uses it as an
  independent second parse.
- The first row with a value in the ERECTION MARK column is the assembly row.
"""
import re

import pymupdf

from ..geometry import cluster, join_tokens, num, xc, yc
from ..models import Bom, BomRow, BomTotals

HEADER_ANCHORS = ["LENGTH", "Qty./", "PC.", "NET(KG)", "GROSS(KG)", "MATERIAL", "REMARKS", "SURFACE"]
MARK_CELL = re.compile(r"^\d[A-Za-z]{1,4}\d+$")
CROSS_HEADERS = {"item": "ITEM", "section": "SECTION", "length": "LENGTH", "qty": "QTY",
                 "gross": "GROSS", "material": "MATERIAL"}
NUMERIC_COLS = ["length_mm", "qty", "pc_wt", "net_kg", "gross_kg", "material", "remarks", "surface_area_m2"]


def _frame(layout, title):
    best = None
    for x0, y0, x1, y1 in layout.segments:
        if abs(y0 - y1) < 0.5 and 0 < y0 - title.y1 < 15:
            a, b = sorted((x0, x1))
            if a < title.x0 and b > title.x1 and (best is None or b - a > best[1] - best[0]):
                best = (a, b, y0)
    return best


def _to_int(s):
    v = num(s)
    return int(v) if v is not None and v == int(v) else None


def parse_bom(layout):
    titles, totals = layout.find("BILL OF MATERIALS"), layout.find("GRAND TOTAL")
    if not titles or not totals:
        return None
    title, total = titles[0], totals[0]
    frame = _frame(layout, title)
    if frame is None:
        return None
    x_left, x_right, y_top = frame
    region = (x_left - 1, y_top - 1, x_right + 1, total.y1 + 2)
    words = layout.words_in(region)
    hdr = {}
    for w in words:
        if w[1] < y_top + 45 and w[4] not in hdr:
            hdr[w[4]] = w
    missing = [k for k in HEADER_ANCHORS + ["ITEM"] if k not in hdr]
    if missing:
        raise ValueError(f"BOM header words not found: {missing}")
    y_hdr_bottom = max(hdr[k][3] for k in ("MARK.", "NO.", "mm.") if k in hdr)
    xs = [s[0] for s in layout.segments
          if abs(s[0] - s[2]) < 0.5 and x_left + 5 < s[0] < x_right - 5 and region[1] <= min(s[1], s[3]) <= region[3]]
    rulings = sorted(sum(g) / len(g) for g in cluster(xs, 1.5) if len(g) >= 3)
    anchors = [hdr[k] for k in HEADER_ANCHORS]
    lefts = [x for x in rulings if x < anchors[0][0]]
    edges = [max(lefts) if lefts else anchors[0][0] - 5]
    for a, b in zip(anchors, anchors[1:]):
        between = [x for x in rulings if a[2] - 2 <= x <= b[0] + 2]
        edges.append(between[0] if between else (a[2] + b[0]) / 2)
    edges.append(x_right)
    body = [w for w in words if y_hdr_bottom + 1 < yc(w) < total.y0 - 1]
    row_ys = [sum(g) / len(g) for g in cluster([yc(w) for w in body if w[0] >= edges[0]], 4)]
    item_hdr_x0 = hdr["ITEM"][0]
    assembly, parts = None, []
    for i, y in enumerate(row_ys):
        y0 = (row_ys[i - 1] + y) / 2 if i else y_hdr_bottom + 1
        y1 = (y + row_ys[i + 1]) / 2 if i + 1 < len(row_ys) else total.y0 - 1
        rw = [w for w in body if y0 <= yc(w) < y1]
        cells = {"erection_mark": "", "item_no": "", "section": ""}
        rest = []
        for t in join_tokens([w for w in rw if w[2] <= edges[0] + 1]):
            if t[0] < item_hdr_x0 - 25 and not cells["erection_mark"]:
                cells["erection_mark"] = t[4]
            else:
                rest.append(t[4])
        if rest:
            cells["item_no"], cells["section"] = rest[0], " ".join(rest[1:])
        for name, cx0, cx1 in zip(NUMERIC_COLS, edges, edges[1:]):
            cells[name] = " ".join(t[4] for t in join_tokens([w for w in rw if cx0 <= xc(w) < cx1]))
        row = BomRow(
            erection_mark=cells["erection_mark"], item_no=cells["item_no"], section=cells["section"],
            length_mm=num(cells["length_mm"]), qty=_to_int(cells["qty"]), pc_wt=num(cells["pc_wt"]),
            net_kg=num(cells["net_kg"]), gross_kg=num(cells["gross_kg"]), material=cells["material"],
            remarks=cells["remarks"], surface_area_m2=num(cells["surface_area_m2"]),
            bbox=(x_left, y0, x_right, y1),
        )
        if row.erection_mark and assembly is None:
            assembly = row
        else:
            parts.append(row)
    # grand total line: "<net> GRAND TOTAL WEIGHT IN KGS = <gross> ... <area> M 2"
    line = join_tokens(layout.words_in((x_left, total.y0 - 3, layout.width, total.y1 + 3)))
    vals = [num(t[4]) for t in line if num(t[4]) is not None]
    totals_ = BomTotals()
    if len(vals) >= 3:
        totals_ = BomTotals(net_kg=vals[0], gross_kg=vals[1], surface_area_m2=vals[2])
    return Bom(assembly=assembly, parts=parts, totals=totals_, bbox=(x_left, y_top, x_right, total.y1))


def cross_check_bom(layout, bom):
    """Second, independent parse: PyMuPDF find_tables() clipped to the BOM frame (exact on the samples when
    clipped; unusable on the whole page). Returns mismatch descriptions, or None if no table was found."""
    try:
        tables = layout.page.find_tables(clip=pymupdf.Rect(bom.bbox)).tables
    except Exception:
        return None
    if not tables:
        return None
    data = [[" ".join((c or "").split()) for c in r] for r in tables[0].extract()]
    col = {}
    for key, needle in CROSS_HEADERS.items():                 # locate columns by header text, not position
        hits = [j for r in data[:6] for j, c in enumerate(r) if needle in c.upper()]
        if not hits:
            return None                                       # unknown layout: cross-check unavailable
        col[key] = hits[0]
    rows = {}
    for cells in data:
        if len(cells) > max(col.values()) and MARK_CELL.match(cells[col["item"]]):
            rows[cells[col["item"]]] = cells
    if not rows:
        return None
    issues = []
    for p in bom.parts:
        c = rows.pop(p.item_no, None)
        if c is None:
            issues.append(f"{p.item_no}: not found by find_tables")
            continue
        theirs = (c[col["section"]], num(c[col["length"]]), num(c[col["qty"]]), num(c[col["gross"]]),
                  c[col["material"]])
        ours = (p.section, p.length_mm, p.qty, p.gross_kg, p.material)
        if theirs != ours:
            issues.append(f"{p.item_no}: parser {ours} vs find_tables {theirs}")
    issues += [f"{m}: only found by find_tables" for m in rows]
    return issues
