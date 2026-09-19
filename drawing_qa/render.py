"""Rasterise regions of a sheet at a resolution the vision model can read."""
import pymupdf


def render_clip(page, rect, max_px=2400, dpi=200) -> bytes:
    """PNG of `rect` (PDF points) at `dpi`, downscaled so the long side <= max_px."""
    r = pymupdf.Rect(rect) & page.rect
    if r.is_empty:
        raise ValueError(f"empty clip {rect}")
    zoom = min(dpi / 72, max_px / max(r.width, r.height))
    return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=r, alpha=False).tobytes("png")


def render_overview(page, max_px=1600) -> bytes:
    return render_clip(page, page.rect, max_px=max_px, dpi=72)


def tile_rects(page, cols, rows, overlap=0.04):
    """Split the sheet into cols x rows tiles with a small overlap so labels on a seam survive."""
    W, H = page.rect.width, page.rect.height
    tw, th = W / cols, H / rows
    ox, oy = tw * overlap, th * overlap
    return [(max(0, c * tw - ox), max(0, r * th - oy), min(W, (c + 1) * tw + ox), min(H, (r + 1) * th + oy))
            for r in range(rows) for c in range(cols)]
