import pymupdf

from drawing_qa.context import page_context, page_text, tiles

from .conftest import sample_path


def test_page_text_tags_every_line_with_a_grid_cell(layouts):
    txt = page_text(layouts("14281"))
    lines = txt.splitlines()
    assert len(lines) == len(layouts("14281").lines)
    assert all(ln.startswith("[") for ln in lines)
    assert "37a-39a/LA" in txt and "[A21] BILL OF MATERIALS" in txt


def test_tiles_cover_the_sheet_by_size(layouts):
    for drg, n in (("09970", 4), ("14281", 6)):
        page = pymupdf.open(sample_path(drg))[0]
        t = tiles(page, layouts(drg))
        assert len(t) == n and all(cap.startswith("tile ") and png[:4] == b"\x89PNG" for cap, png in t)


def test_page_context_is_deterministic(layouts):
    page = pymupdf.open(sample_path("09970"))[0]
    a, b = page_context(page, layouts("09970")), page_context(page, layouts("09970"))
    assert a == b                                    # identical prefix -> prompt-cache hits
