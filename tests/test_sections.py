import pytest

from drawing_qa.parsers.bom import parse_bom
from drawing_qa.sections import Plate, decompose, parse_section, weight_matches

from .conftest import GOLDEN


@pytest.mark.parametrize("section,family", [
    ("PL10*150", "plate"), ("PLT8*50", "plate"), ("WH1200X500X40X32", "built_up"), ("T 300X250X25X20", "built_up"),
    ("ISA75X75X8", "angle"), ("ISMC150", "channel"), ("PIPE219.1*5.4", "pipe"), ("ROD20", "round"),
    ("SPD508*508*608*608*8", "unknown"),
])
def test_parse_section_families(section, family):
    assert parse_section(section).family == family


def test_wh_and_tee_recipes():
    wh = decompose(parse_section("WH1200X500X40X32"), 7989.5)
    assert wh == [Plate(40, 500, 7989.5, 2), Plate(32, 1120, 7989.5, 1)]
    tee = decompose(parse_section("T 300X250X25X20"), 1950)
    assert tee == [Plate(25, 250, 1950, 1), Plate(20, 275, 1950, 1)]
    assert sum(p.weight_kg for p in wh) == pytest.approx(4756.50, abs=0.05)      # BOM piece weight of 3C2


@pytest.mark.parametrize("drg", sorted(GOLDEN))
def test_every_built_up_and_plate_matches_its_bom_weight(layouts, drg):
    for p in parse_bom(layouts(drg)).parts:
        ps = parse_section(p.section)
        if ps.family == "built_up":
            assert weight_matches(decompose(ps, p.length_mm), p.pc_wt, p.net_kg / p.qty), p.item_no
        elif ps.family == "plate":
            assert weight_matches([Plate(ps.thickness_mm, ps.width_mm, p.length_mm)], p.pc_wt, p.net_kg / p.qty), \
                p.item_no


def test_weight_matches_rejects_a_wrong_breakdown():
    assert not weight_matches([Plate(8, 200, 506)], 54.93, 54.93)
