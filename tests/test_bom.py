import pytest

from drawing_qa.parsers.bom import parse_bom

from .conftest import GOLDEN

DRGS = sorted(GOLDEN)


@pytest.mark.parametrize("drg", DRGS)
def test_bom_matches_golden(layouts, drg):
    g, b = GOLDEN[drg], parse_bom(layouts(drg))
    assert b.assembly.erection_mark == g["asm"]
    assert b.assembly.qty == g["asm_qty"]
    assert len(b.parts) == g["parts"]
    assert (b.totals.gross_kg, b.totals.net_kg, b.totals.surface_area_m2) == (g["gross"], g["net"], g["area"])
    assert sum(p.gross_kg for p in b.parts) * g["asm_qty"] == pytest.approx(g["gross"], abs=0.05)
    for p in b.parts:
        assert p.item_no and p.section and p.material and p.qty and p.length_mm, p


def test_bom_row_values_09970(layouts):
    rows = {p.item_no: p for p in parse_bom(layouts("09970")).parts}
    r = rows["4p660"]
    assert (r.section, r.length_mm, r.qty, r.pc_wt, r.net_kg, r.gross_kg, r.material, r.surface_area_m2) == \
        ("PL10*358", 358.3, 2, 10.08, 15.88, 20.15, "E350A", 0.21)
    assert rows["4m706"].section == "PIPE219.1*5.4"


def test_bom_section_with_long_name_16362(layouts):
    rows = {p.item_no: p for p in parse_bom(layouts("16362")).parts}
    assert rows["1m470"].section == "SPD508*508*608*608*8"
    assert rows["1m473"].qty == 22


@pytest.mark.parametrize("drg,cols,rows", [("09970", 16, 12), ("14281", 24, 16)])
def test_sheet_grid_detected(layouts, drg, cols, rows):
    g = layouts(drg).grid
    assert (len(g.col_x), len(g.row_y)) == (cols, rows)


@pytest.mark.parametrize("drg", DRGS)
def test_find_tables_crosscheck_agrees_and_catches_corruption(layouts, drg):
    from drawing_qa.parsers.bom import cross_check_bom
    L = layouts(drg)
    b = parse_bom(L)
    assert cross_check_bom(L, b) == []
    b.parts[1].length_mm *= 10                     # arithmetic checks cannot see length or material errors
    b.parts[2].material = "E250A" if b.parts[2].material != "E250A" else "E350A"
    assert len(cross_check_bom(L, b)) == 2
