"""The whole page as model input: every text line of the PyMuPDF text layer tagged with its sheet grid
cell, plus high-resolution tiles of the full sheet. Built once per page and placed first in every
request, so the identical prefix is served from OpenAI's prompt cache on later calls."""
from .llm import image_part
from .render import render_clip, tile_rects


def page_text(layout) -> str:
    """'[E7] 4p637' lines in reading order (grid row, grid column, then position). Rotated text is kept and
    marked '(vertical)'; dimension figures are often vertical on these sheets."""
    rows = []
    for ln in layout.lines:
        x = (ln.bbox[0] + ln.bbox[2]) / 2
        y = (ln.bbox[1] + ln.bbox[3]) / 2
        cell = layout.grid.cell_of(x, y) or "?"
        rows.append((cell[:1], int(cell[1:] or 0) if cell[1:].isdigit() else 0, round(y), round(x),
                     f"[{cell}] {ln.text}" + ("" if ln.horizontal else " (vertical)")))
    return "\n".join(r[-1] for r in sorted(rows))


def tiles(page, layout, max_px=2000, dpi=150):
    """[(caption, png)] covering the sheet: 3x2 tiles on A0-size sheets, 2x2 otherwise."""
    cols, nrows = (3, 2) if layout.width > 3000 else (2, 2)
    out = []
    for i, r in enumerate(tile_rects(page, cols, nrows)):
        c0 = layout.grid.cell_of(r[0] + 5, r[1] + 5) or "?"
        c1 = layout.grid.cell_of(r[2] - 5, r[3] - 5) or "?"
        out.append((f"tile {i + 1}: grid cells {c0}..{c1}", render_clip(page, r, max_px=max_px, dpi=dpi)))
    return out


def page_context(page, layout) -> list[dict]:
    """Content parts for one user message: the sheet text, then the captioned tiles."""
    t = tiles(page, layout)
    parts = [{"type": "input_text", "text":
              "SHEET TEXT LAYER (from the PDF; authoritative for characters). Format: [grid cell] text.\n"
              + page_text(layout)
              + "\n\nSHEET IMAGES follow in this order: " + "; ".join(c for c, _ in t)}]
    for caption, png in t:
        parts += [{"type": "input_text", "text": caption}, image_part(png, detail="high")]
    return parts
