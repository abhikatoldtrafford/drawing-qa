import pytest

from drawing_qa.parsers.tables import parse_abstract, parse_bolts, parse_mark_locations, parse_notes, parse_revisions

from .conftest import GOLDEN

DRGS = sorted(GOLDEN)


@pytest.mark.parametrize("drg", DRGS)
def test_abstract_sums_to_total(layouts, drg):
    a = parse_abstract(layouts(drg))
    assert len(a.rows) == GOLDEN[drg]["abstract_rows"]
    assert a.total_kg == GOLDEN[drg]["gross"]
    assert sum(r.total_wt for r in a.rows) == pytest.approx(a.total_kg, abs=0.05)
    assert [r.sr for r in a.rows] == list(range(1, len(a.rows) + 1))


@pytest.mark.parametrize("drg", DRGS)
def test_bolt_row_count(layouts, drg):
    assert len(parse_bolts(layouts(drg))) == GOLDEN[drg]["bolts"]


def test_bolt_row_values_14281(layouts):
    rows = parse_bolts(layouts("14281"))
    assert [(r.assembly_mark, r.bolt_dia, r.bolt_length, r.bolt_qty, r.bolt_grade) for r in rows] == \
        [("3FR3", "20", "105", "8", "8.8XOX"), ("3C1", "24", "150", "88", "10.9XOX")]
    assert rows[1].nut_qty == "176" and rows[1].washer_type == "FLAT-E"
    assert rows[0].bolt_material == "IS:1367 (I) 2014"


@pytest.mark.parametrize("drg", DRGS)
def test_revisions_latest_first(layouts, drg):
    revs = parse_revisions(layouts(drg))
    assert revs[0].rev == GOLDEN[drg]["rev"]
    assert all(r.description == "ISSUED FOR CONSTRUCTION" and r.drn == "IRCON" and r.app == "SSA" for r in revs)


def test_revisions_two_rows_14278(layouts):
    assert [(r.rev, r.date) for r in parse_revisions(layouts("14278"))] == [("1", "14.08.2026"), ("0", "01.06.2026")]


@pytest.mark.parametrize("drg", DRGS)
def test_notes_and_mark_location(layouts, drg):
    notes = parse_notes(layouts(drg))
    assert len(notes) == 5 and notes[0].startswith("1. ALL DIMENSIONS")
    assert notes[4].endswith("FABRICATION SHOP.")
    locs = parse_mark_locations(layouts(drg))
    assert len(locs) == GOLDEN[drg]["asm_qty"]                 # one row per erected instance
    assert all(m.mark_no == GOLDEN[drg]["asm"] for m in locs)
    assert locs[0].level == GOLDEN[drg]["level"]


def test_mark_locations_two_instances_16362(layouts):
    assert [(m.grid_location, m.level) for m in parse_mark_locations(layouts("16362"))] ==         [("19-20/<LEG-1", "EL. +17.065"), ("22-23/<LEG-1", "EL. +17.049")]
