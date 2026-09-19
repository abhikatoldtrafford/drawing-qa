"""Page extraction: 100% PyMuPDF (no model calls), then guardrail checks, then a disk cache.
OpenAI is used later, for Q&A (chat.py) and the inventory (inventory.py), on top of this extract."""
import hashlib
from pathlib import Path

from .config import SCHEMA_VERSION, Settings
from .layout import PageLayout, open_pdf, sha256
from .models import Check, PageExtract
from .parsers.bom import cross_check_bom, parse_bom
from .parsers.tables import parse_abstract, parse_bolts, parse_mark_locations, parse_notes, parse_revisions
from .parsers.titleblock import parse_title_block, title_block_rect
from .parsers.views import part_marks, view_labels
from .validate import run_checks


def _safe(name, fn, errors, default=None):
    try:
        return fn()
    except Exception as e:  # a broken parser must not take down the page
        errors.append(Check(id=f"parse.{name}", level="fail", message=f"{name} parser error: {e}", region=name))
        return default


def _regions(layout, bom):
    out = {}
    if bom:
        out["bom"] = bom.bbox
    tb = title_block_rect(layout)
    if tb:
        out["title_block"] = tb
    hit = lambda s: (layout.find(s) or [None])[0]
    a, e = hit("ABSTRACT"), hit("TOTAL IN KGS.")
    if a and e:
        out["abstract"] = (e.x0 - 40, a.y0 - 5, a.x1 + 150, e.y1 + 5)
    b, t = hit("List of Permanent Bolts"), hit("TATA STEEL LIMITED")
    if b and t:
        out["bolts"] = (b.x0 - 450, b.y0 - 5, b.x1 + 650, t.y0 - 5)
    n = hit("1. ALL DIMENSIONS")
    if n:
        out["notes"] = (n.x0 - 5, n.y0 - 5, n.x0 + 420, n.y0 + 95)
    g = hit("GRID LOCATION")
    if g:
        out["mark_location"] = (max(0, g.x0 - 120), g.y0 - 45, g.x1 + 150, g.y1 + 45)
    r = [h for h in layout.find("REVISION") if h.y0 > layout.height * 0.8 and h.x0 < layout.width * 0.3]
    if r:
        out["revisions"] = (0, r[0].y0 - 200, r[0].x1 + 450, r[0].y1 + 5)
    return {k: tuple(float(v) for v in rect) for k, rect in out.items()}


def deterministic_extract(layout, source_name, file_sha, page_index) -> PageExtract:
    errors: list[Check] = []
    bom = _safe("bom", lambda: parse_bom(layout), errors)
    revisions = _safe("revisions", lambda: parse_revisions(layout), errors, [])
    tb = _safe("title_block", lambda: parse_title_block(layout), errors)
    if tb is not None and not tb.rev and revisions:
        tb.rev = revisions[0].rev                       # top row = latest revision (A1 title block has no REV cell)
    x = PageExtract(
        source_file=source_name, file_sha256=file_sha, page_index=page_index,
        page_size_pt=(layout.width, layout.height), has_text_layer=layout.has_text_layer,
        bom=bom,
        abstract=_safe("abstract", lambda: parse_abstract(layout), errors),
        bolts=_safe("bolts", lambda: parse_bolts(layout), errors, []),
        revisions=revisions,
        notes=_safe("notes", lambda: parse_notes(layout), errors, []),
        mark_locations=_safe("mark_location", lambda: parse_mark_locations(layout), errors, []),
        part_marks=_safe("marks", lambda: part_marks(layout, [bom.bbox] if bom else []), errors, []),
        view_labels=_safe("view_labels", lambda: view_labels(layout), errors, []),
        bom_crosscheck=_safe("bom_crosscheck", lambda: cross_check_bom(layout, bom), errors) if bom else None,
        regions=_regions(layout, bom),
    )
    if tb is not None:
        x.title_block = tb
    x.pipeline_errors = errors
    return x


def _cache_path(settings, file_sha, page_index):
    tag = hashlib.sha256(f"{SCHEMA_VERSION}".encode()).hexdigest()[:10]
    return Path(settings.cache_dir) / f"{file_sha[:20]}_p{page_index}_{tag}.json"


def extract_page(pdf_bytes: bytes, page_index: int, source_name: str, settings: Settings | None = None,
                 use_cache=True) -> PageExtract:
    settings = settings or Settings()
    file_sha = sha256(pdf_bytes)
    cache = _cache_path(settings, file_sha, page_index)
    if use_cache and cache.exists():
        x = PageExtract.model_validate_json(cache.read_text(encoding="utf-8"))
        x.source_file = source_name                    # same bytes may arrive under another name
        x.checks = x.pipeline_errors + run_checks(x)
        return x
    layout = PageLayout.from_page(open_pdf(pdf_bytes)[page_index])
    x = deterministic_extract(layout, source_name, file_sha, page_index)
    x.checks = x.pipeline_errors + run_checks(x)
    if use_cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(x.model_dump_json(indent=1), encoding="utf-8")
    return x
