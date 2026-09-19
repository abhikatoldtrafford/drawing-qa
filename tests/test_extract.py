from pathlib import Path

import pytest

from drawing_qa.extract import extract_page
from drawing_qa.validate import run_checks

from .conftest import GOLDEN, det, sample_path


@pytest.mark.parametrize("drg", sorted(GOLDEN))
def test_deterministic_extract_has_no_failures(drg, settings):
    x = det(drg, settings)
    assert [c for c in x.checks if c.level == "fail"] == []
    assert {"bom", "title_block", "abstract", "notes", "mark_location", "revisions"} <= set(x.regions)
    assert x.title_block.rev == GOLDEN[drg]["rev"]                 # A1 sheets: from the revision table


def test_checks_catch_a_corrupted_row(settings):
    x = det("09970", settings)
    x.bom.parts[0].gross_kg += 5
    ids = {c.id for c in run_checks(x) if c.level == "fail"}
    assert {"bom.row_arith", "bom.gross_total"} <= ids


def test_checks_catch_missing_mark(settings):
    x = det("16807", settings)
    x.part_marks = [m for m in x.part_marks if m != "2p205"]
    fails = [c for c in run_checks(x) if c.level == "fail"]
    assert [c.id for c in fails] == ["marks.bom_on_sheet"] and "2p205" in fails[0].message


def test_assembly_qty_multiplies_gross(settings):
    x = det("16362", settings)          # assembly qty 2: Σ parts 175.27 × 2 = 350.54 ≈ 350.52 grand total
    assert next(c for c in x.checks if c.id == "bom.gross_total").level == "pass"


def test_new_checks_pass_on_all_samples(settings):
    for drg in sorted(GOLDEN):
        levels = {c.id: c.level for c in det(drg, settings).checks}
        assert levels["bom.crosscheck"] == "pass" and levels["abstract.by_section"] == "pass", drg
        assert levels["mark_location.count"] == "pass", drg
        assert "title.fields" not in levels, drg                    # department, equip/area, title lines found
    assert {c.id: c.level for c in det("16362", settings).checks}["bom.net_total"] == "pass"   # net not x qty


def test_extract_cache_roundtrip_and_file_name(settings):
    p = sample_path("16807")
    data = p.read_bytes()
    a = extract_page(data, 0, p.name, settings=settings)
    b = extract_page(data, 0, p.name, settings=settings)
    assert a == b
    assert len(list(Path(settings.cache_dir).glob("*.json"))) == 1
    renamed = extract_page(data, 0, "copy.pdf", settings=settings)          # cache hit under a new name
    assert renamed.source_file == "copy.pdf"
    assert next(c for c in renamed.checks if c.id == "title.drawing_no").level == "warn"


def test_settings_read_environment_at_construction(monkeypatch):
    from drawing_qa.config import Settings
    monkeypatch.setenv("DQA_MODEL", "m-x")
    monkeypatch.setenv("DQA_CACHE_DIR", "somewhere")
    s = Settings()
    assert (s.model, s.cache_dir) == ("m-x", "somewhere")


@pytest.mark.parametrize("tables", [[], "odd"], ids=["no_table", "unexpected_columns"])
def test_unavailable_crosscheck_is_a_warning_not_a_failure(settings, monkeypatch, tables):
    import pymupdf
    from types import SimpleNamespace
    if tables == "odd":        # a table whose header matches none of ITEM/SECTION/LENGTH/QTY/GROSS/MATERIAL
        odd = SimpleNamespace(extract=lambda: [["A", "B", "C"], ["1", "2", "3"]])
        monkeypatch.setattr(pymupdf.Page, "find_tables", lambda self, **kw: SimpleNamespace(tables=[odd]))
    else:
        monkeypatch.setattr(pymupdf.Page, "find_tables", lambda self, **kw: SimpleNamespace(tables=[]))
    p = sample_path("16807")
    x = extract_page(p.read_bytes(), 0, p.name, settings=settings, use_cache=False)
    assert x.bom_crosscheck is None
    levels = {c.id: c.level for c in x.checks}
    assert levels["bom.crosscheck"] == "warn" and "fail" not in levels.values()
