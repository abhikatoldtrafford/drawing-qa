import pytest

from drawing_qa.parsers.bom import parse_bom
from drawing_qa.parsers.titleblock import parse_title_block
from drawing_qa.parsers.views import part_marks, view_labels

from .conftest import GOLDEN, TITLE

DRGS = sorted(GOLDEN)


@pytest.mark.parametrize("drg", DRGS)
def test_title_block_deterministic_fields(layouts, drg):
    tb = parse_title_block(layouts(drg))
    assert tb.drawing_no == f"TST-SFD-46-01-01-07-000-{drg}"
    assert tb.sheet_size == GOLDEN[drg]["size"]
    assert tb.sheet_no == "1 OF 1"
    assert tb.weight_kg == GOLDEN[drg]["gross"]


@pytest.mark.parametrize("drg", DRGS)
def test_title_block_text_fields_from_bordered_cells(layouts, drg):
    t, tb = TITLE[drg], parse_title_block(layouts(drg))
    assert tb.department == "DESIGN & ENGINEERING-STRUCTURAL"
    assert (tb.equip_area, tb.project, tb.title_lines) == (t["equip"], t["project"], t["lines"])
    assert (tb.drn.name, tb.chd.name, tb.app.name) == ("IRCON", t["persons"][0], "SSA")
    assert tb.drn.date == tb.chd.date == tb.app.date == t["persons"][1]


def test_blank_project_cell_reads_empty_not_the_next_label(layouts):
    from drawing_qa.parsers.titleblock import label_cells, title_block_rect
    L = layouts("16807")
    assert [t for t, _ in label_cells(L, title_block_rect(L), "PROJECT")] == [""]


@pytest.mark.parametrize("drg", DRGS)
def test_every_bom_mark_is_on_the_sheet(layouts, drg):
    L = layouts(drg)
    b = parse_bom(L)
    assert {p.item_no for p in b.parts} <= set(part_marks(L, [b.bbox]))


@pytest.mark.parametrize("drg", DRGS)
def test_view_labels_have_cells_and_section_scales(layouts, drg):
    labels = view_labels(layouts(drg))
    assert len(labels) == GOLDEN[drg]["labels"]
    assert all(v.cell for v in labels)
    assert all(v.scale.startswith("1:") for v in labels if v.kind == "section")
