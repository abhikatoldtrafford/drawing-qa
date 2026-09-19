"""Part marks and view labels found in the drawing area."""
import re

from ..models import ViewLabel

# Tekla marks: parts '3p307' / '4m665', assemblies '3C2' / '4DC3' / '4PSB2' / '2GU1'
MARK = re.compile(r"^\d[a-z]\d+$|^\d[A-Z]{1,4}\d+$")
SECTION = re.compile(r"^([A-Z0-9]{1,2}) - \1$")
SCALE = re.compile(r"^1:\d+$")
DETAIL = re.compile(r"^MARK\. NO:-\s*(\S+)$")


def part_marks(layout, exclude_rects=()):
    def outside(w):
        cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        return not any(r[0] <= cx <= r[2] and r[1] <= cy <= r[3] for r in exclude_rects)
    return sorted({w[4] for w in layout.words if MARK.match(w[4]) and outside(w)})


def view_labels(layout):
    out = []
    lines = [ln for ln in layout.lines if ln.horizontal]
    for ln in lines:
        m = SECTION.match(ln.text)
        d = DETAIL.match(ln.text)
        if not (m or d):
            continue
        cx = (ln.bbox[0] + ln.bbox[2]) / 2
        scale = ""
        if m:
            below = [s for s in lines if SCALE.match(s.text) and abs((s.bbox[0] + s.bbox[2]) / 2 - cx) < 40
                     and -5 < s.bbox[1] - ln.bbox[3] < 25]
            scale = below[0].text if below else ""
        out.append(ViewLabel(
            label=ln.text, kind="section" if m else "detail", ref=m.group(1) if m else d.group(1),
            scale=scale, bbox=ln.bbox, cell=layout.grid.cell_of(cx, (ln.bbox[1] + ln.bbox[3]) / 2),
        ))
    return out
