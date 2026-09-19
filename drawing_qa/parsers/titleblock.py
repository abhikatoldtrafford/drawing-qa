"""Title block, fully deterministic.

Each labelled field is the whole bordered cell to the right of its label (cell edges = vertical rules
crossing the label's row). Title lines are the rows of the DRAWING DESCRIPTION cell between the
EQUIP/AREA and PROJECT rows. A cell that starts with another label is an empty field. Verified on the
5 samples (A1 and A0 templates), including the A1 sheets whose PROJECT row is blank."""
import re

from ..geometry import num, xc, yc
from ..models import Person, TitleBlock

DRG_NO = re.compile(r"^[A-Z]{2,5}-[A-Z]{2,5}(?:-\d+){5,}$")
SHEET_NO = re.compile(r"\b(\d+)\s+OF\s+(\d+)\b")
SIZE = re.compile(r"^A[0-4]$")
DATE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
TITLE_LABELS = {"DEPARTMENT", "EQUIP/AREA", "PROJECT", "MATERIAL", "DRN.", "CHD.", "APP.", "DRG.No.", "REV",
                "SHEET", "WEIGHT", "DRAWING", "DESCRIPTION", "SCALE", "TITLE"}


def title_block_rect(layout):
    tb = layout.find("TATA STEEL LIMITED")
    if not tb:
        return None
    tb = tb[0]
    return (tb.x0 - 320, tb.y0 - 10, layout.width, layout.height)


def all_drawing_numbers(layout):
    return sorted({w[4] for w in layout.words if DRG_NO.match(w[4])})


def _walls(layout, y):
    return sorted(s[0] for s in layout.segments if abs(s[0] - s[2]) < 0.5 and min(s[1], s[3]) < y < max(s[1], s[3]))


def _cell_right(layout, rect, x, y):
    return min([w for w in _walls(layout, y) if w > x + 1], default=rect[2])


def label_cells(layout, rect, label, tol=7) -> list[tuple[str, tuple]]:
    """For each occurrence of `label`: (full text of the bordered cell holding the first word to its right on
    the same row, label word). A cell starting with another label counts as empty."""
    words = layout.words_in(rect)
    out = []
    for lab in (w for w in words if w[4] == label):
        y = yc(lab)
        row = sorted((w for w in words if abs(yc(w) - y) <= tol and w[0] > lab[2]), key=lambda w: w[0])
        if not row or row[0][4] in TITLE_LABELS:
            out.append(("", lab))
            continue
        right = _cell_right(layout, rect, row[0][0], y)
        out.append((" ".join(w[4] for w in row if w[2] <= right + 1), lab))
    return out


def _field(layout, rect, label):
    """First non-empty cell for a label ('' if none)."""
    return next((t for t, _ in label_cells(layout, rect, label) if t), "")


def _person(layout, rect, label):
    words = layout.words_in(rect)
    for name, lab in label_cells(layout, rect, label):
        if not name or DATE.match(name):
            continue
        dates = sorted((w for w in words if DATE.match(w[4]) and abs(yc(w) - yc(lab)) <= 7 and w[0] > lab[2]),
                       key=lambda w: w[0])
        return Person(name=name, date=dates[0][4] if dates else "")
    return Person()


def _title_lines(layout, rect):
    words = layout.words_in(rect)
    eq = [w for w in words if w[4] == "EQUIP/AREA"]
    if not eq:
        return []
    eq = eq[0]
    proj = [w for w in words if w[4] == "PROJECT" and w[1] > eq[1]]
    if not proj:
        return []
    proj = min(proj, key=lambda w: w[1])
    mid = (eq[3] + proj[1]) / 2
    left = min([w for w in _walls(layout, mid) if w > eq[2]], default=eq[2])
    band = sorted((w for w in words if eq[3] + 1 < yc(w) < proj[1] - 1 and w[0] > left), key=yc)
    rows = []
    for w in band:
        if rows and abs(yc(w) - rows[-1][0]) <= 3:
            rows[-1][1].append(w)
        else:
            rows.append([yc(w), [w]])
    lines = []
    for y, ws in rows:
        ws.sort(key=lambda w: w[0])
        right = _cell_right(layout, rect, ws[0][0], y)      # drops the sheet-border grid letter
        text = " ".join(w[4] for w in ws if w[2] <= right + 1)
        if text:
            lines.append(text)
    return lines


def parse_title_block(layout) -> TitleBlock:
    rect = title_block_rect(layout)
    if rect is None:
        return TitleBlock()
    words = layout.words_in(rect)
    tb = TitleBlock()
    drg = [w[4] for w in words if DRG_NO.match(w[4])]
    if drg:
        tb.drawing_no = drg[0]
    m = SHEET_NO.search(" ".join(w[4] for w in words))
    if m:
        tb.sheet_no = f"{m.group(1)} OF {m.group(2)}"
    size = [w[4] for w in words if SIZE.match(w[4])]
    if size:
        tb.sheet_size = size[0]
    kg = [w for w in words if w[4] == "KG"]
    if kg:
        k = kg[0]
        wt = [w for w in words if abs(xc(w) - xc(k)) < 60 and 0 < w[1] - k[3] < 25 and re.fullmatch(r"\d+\.\d+", w[4])]
        if wt:
            tb.weight_kg = num(wt[0][4])
    revs = [w for w in words if w[4] == "REV"]
    if revs:
        r = max(revs, key=lambda w: w[1])
        below = [w for w in words if abs(xc(w) - xc(r)) < 15 and 0 < w[1] - r[3] < 25 and re.fullmatch(r"[0-9A-Z]{1,2}", w[4])]
        if below:
            tb.rev = below[0][4]
    tb.department = _field(layout, rect, "DEPARTMENT")
    tb.equip_area = _field(layout, rect, "EQUIP/AREA")
    tb.project = _field(layout, rect, "PROJECT")
    tb.title_lines = _title_lines(layout, rect)
    tb.drn, tb.chd, tb.app = (_person(layout, rect, lab) for lab in ("DRN.", "CHD.", "APP."))
    return tb
