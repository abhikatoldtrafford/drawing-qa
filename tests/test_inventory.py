import math
from pathlib import Path

import pymupdf
import pytest

from drawing_qa.inventory import InventoryLLM, allowed_weld_sizes, build_inventory, deterministic_inventory
from drawing_qa.layout import PageLayout
from drawing_qa.llm import LLM

from .conftest import GOLDEN, det, sample_path
from .fakes import FakeClient


@pytest.mark.parametrize("drg", sorted(GOLDEN))
def test_deterministic_inventory_reconciles_with_bom(drg, settings):
    inv = deterministic_inventory(det(drg, settings))
    levels = {c.id: c.level for c in inv.checks}
    assert levels["inventory.weight"] == "pass" and levels["inventory.paint"] == "pass"
    listed = sum(p.weight_kg for p in inv.plates) + sum(s.weight_kg for s in inv.sections)
    assert listed == pytest.approx(GOLDEN[drg]["gross"], abs=0.1)
    assert inv.assembly_qty == GOLDEN[drg]["asm_qty"] and inv.paint_area_m2 == GOLDEN[drg]["area"]


def test_built_ups_become_plates_14281(settings):
    inv = deterministic_inventory(det("14281", settings))
    assert not [s for s in inv.sections if s.family == "built-up"]
    pl40 = next(p for p in inv.plates if p.thickness_mm == 40 and p.grade == "E350BR(UT)")
    assert pl40.pieces == 8                                        # 4 WH1200X500X40X32 members x 2 flanges
    assert pl40.weight_kg == pytest.approx(9265.51, abs=0.05)
    assert any("3m471 (WH 500x40)" == s for s in pl40.sources)


def test_assembly_qty_multiplies_pieces_16362(settings):
    inv = deterministic_inventory(det("16362", settings))
    rod = next(s for s in inv.sections if s.profile == "ROD8")
    assert (rod.pieces, rod.total_length_m) == (44, 26.752)       # 22 per assembly x 2 assemblies
    assert [u.mark for u in inv.unclassified] == ["1m470"]


def test_fasteners_from_bolt_table_09970(settings):
    inv = deterministic_inventory(det("09970", settings))
    got = {(f.item, f.dia_mm, f.length_mm, f.qty) for f in inv.fasteners}
    assert got == {("bolt", "16", "60", 18), ("nut", "16", "", 26), ("plain washer", "18", "", 18)}
    assert {c.id: c.level for c in inv.checks}["inventory.taper_qty"] == "warn"   # qty column blank on sheet


def test_allowed_weld_sizes_come_from_weld_callouts_only(layouts, settings):
    x = det("09970", settings)
    assert allowed_weld_sizes(layouts("09970"), x.notes, x.regions.values()) == {6.0}   # not bolt-table TYPE numbers
    x = det("16362", settings)
    assert {4.0, 6.0} <= allowed_weld_sizes(layouts("16362"), x.notes, x.regions.values())   # '4/4 CONT.' welds


def _llm_answer(unknown=(), welds=()):
    return lambda model, schema: InventoryLLM(unknown_sections=list(unknown), welds=list(welds))


def _weld(attached, base, edge, size=6, sides=1, count=1, tack=False, evidence=""):
    return {"attached": attached, "base": base, "edge": edge, "sides": sides, "size_mm": size, "count": count,
            "tack": tack, "evidence": evidence}


def _run(drg, settings, fn, deep_model=None, cache_dir=None):
    p = sample_path(drg)
    page = pymupdf.open(p)[0]
    client = FakeClient(parse_fn=fn)
    inv = build_inventory(det(drg, settings), page, PageLayout.from_page(page), LLM(client), "mini", deep_model,
                          cache_dir=cache_dir)
    return inv, client


def test_weld_lengths_come_from_bom_geometry_not_the_model(settings):
    welds = [_weld("4p639", "4DC3", "width", count=4),              # PL8*94 x 150: short edge 94
             _weld("4p660", "4m706", "circumference", sides=2),     # all round the 219.1 pipe, both sides
             _weld("4p641", "4DC3", "length", count=4)]             # PL8*83 x 150: long edge 150
    inv, _ = _run("09970", settings, _llm_answer(welds=welds))
    got = {tuple(w.parts): (w.edge, w.length_mm) for w in inv.welds}
    assert got[("4p639", "4DC3")] == ("width", 94)
    assert got[("4p660", "4m706")] == ("circumference", round(2 * math.pi * 219.1, 1))
    assert got[("4p641", "4DC3")] == ("length", 150)
    w = next(w for w in inv.welds if w.parts == ["4p641", "4DC3"])
    assert w.total_length_m == 0.6 and w.weld_metal_kg == pytest.approx(0.6 * 18e-6 * 7850, abs=1e-3)


def test_weld_guardrails_reject_what_the_sheet_cannot_support(settings):
    welds = [
        _weld("4p639", "4DC3", "width", count=8),                   # ok: 2 per piece (qty 4)
        _weld("4p639", "4DC3", "width", count=1),                   # over the per-pair budget
        _weld("4p639", "4m666", "width", count=4),                  # ok: different base part, own budget
        _weld("4p999", "4DC3", "length"),                           # unknown part
        _weld("4p660", "4m706", "circumference", size=10),          # 10 is not a weld size on this sheet
        _weld("4m706", "4m665", "perimeter"),                       # perimeter does not apply to a pipe
        _weld("4p637", "4p637", "length"),                          # welded to itself
        _weld("4p638", "4DC3", "length", sides=3),                  # sides must be 1 or 2
    ]
    inv, _ = _run("09970", settings, _llm_answer(welds=welds))
    assert [w.parts for w in inv.welds] == [["4p639", "4DC3"], ["4p639", "4m666"]]
    reasons = " | ".join(inv.rejected_welds)
    for needle in ("max 8", "unknown part(s) ['4p999']", "size 10 not on sheet", "does not apply to 4m706",
                   "welded to itself", "sides 3"):
        assert needle in reasons, needle


def test_tack_welds_carry_no_weld_metal(settings):
    inv, _ = _run("16362", settings, _llm_answer(welds=[_weld("1m473", "1DC1", "length", count=22, tack=True)]))
    assert inv.welds[0].tack and inv.welds[0].weld_metal_kg == 0 and inv.weld_metal_kg == 0


def test_unknown_section_breakdown_needs_matching_weight_and_thickness(settings):
    good = {"mark": "1m470", "description": "cone developed plate", "plates": [
        {"thickness_mm": 8, "width_mm": 1729, "length_mm": 506, "count": 1}]}             # 54.94 kg vs 54.93
    inv, _ = _run("16362", settings, _llm_answer(unknown=[good]))
    assert inv.unclassified[0].accepted and "SPD508*508*608*608*8" not in {s.profile for s in inv.sections}
    assert {c.id: c.level for c in inv.checks}["inventory.weight"] == "pass"
    thick = {**good, "plates": [{"thickness_mm": 12, "width_mm": 1153, "length_mm": 506, "count": 1}]}   # same kg
    inv, _ = _run("16362", settings, _llm_answer(unknown=[thick]))
    assert not inv.unclassified[0].accepted and "not in the section name" in inv.unclassified[0].note
    light = {**good, "plates": [{"thickness_mm": 8, "width_mm": 600, "length_mm": 506, "count": 1}]}
    inv, _ = _run("16362", settings, _llm_answer(unknown=[light]))
    assert not inv.unclassified[0].accepted and "SPD508*508*608*608*8" in {s.profile for s in inv.sections}


def test_escalation_prefers_resolved_unknowns_not_more_welds(settings):
    good = {"mark": "1m470", "description": "cone", "plates": [
        {"thickness_mm": 8, "width_mm": 1729, "length_mm": 506, "count": 1}]}
    many = [_weld("1p375", "1DC1", "length", count=2), _weld("1m471", "1DC1", "length")]
    fn = lambda model, schema: (InventoryLLM(unknown_sections=[good], welds=[]) if model == "deep"
                                else InventoryLLM(unknown_sections=[], welds=many))
    inv, client = _run("16362", settings, fn, deep_model="deep")
    assert [m for m, _, _ in client.responses.parse_calls] == ["mini", "deep"]
    assert inv.unclassified[0].accepted                                # sections from the run that resolved them
    assert [w.parts for w in inv.welds] == [["1p375", "1DC1"], ["1m471", "1DC1"]]   # welds kept from mini
    assert inv.model == "deep (sections) + mini (welds)"


def test_descriptive_part_names_are_reduced_to_marks(settings):
    good = {"mark": "1m470 conical reducer", "description": "cone", "plates": [
        {"thickness_mm": 8, "width_mm": 1729, "length_mm": 506, "count": 1}]}
    welds = [_weld("1DC1 pipe", "1m470 conical reducer", "circumference")]
    inv, _ = _run("16362", settings, _llm_answer(unknown=[good], welds=welds))
    assert inv.unclassified[0].accepted
    assert inv.welds and inv.welds[0].parts == ["1DC1", "1m470"] and inv.rejected_welds == []
    assert inv.welds[0].length_mm == round(math.pi * 508, 1)          # smaller circular diameter of the joint


def test_escalates_when_the_mini_call_fails(settings):
    def fn(model, schema):
        if model == "mini":
            raise RuntimeError("timeout")
        return InventoryLLM(unknown_sections=[], welds=[])
    inv, client = _run("09970", settings, fn, deep_model="deep")
    assert [m for m, _, _ in client.responses.parse_calls] == ["mini", "deep"] and inv.model == "deep"
    assert not any(c.id == "inventory.llm" for c in inv.checks)


def test_openai_failure_keeps_deterministic_inventory(settings):
    def boom(model, schema):
        raise RuntimeError("connection reset")
    inv, _ = _run("14281", settings, boom, deep_model="deep")
    assert {c.id: c.level for c in inv.checks}["inventory.llm"] == "warn"
    assert inv.plates and inv.welds == []


def test_checks_are_not_duplicated_and_estimate_is_labelled(settings):
    inv, _ = _run("09970", settings, _llm_answer(welds=[_weld("4p641", "4DC3", "length", count=4)]))
    ids = [c.id for c in inv.checks]
    assert len(ids) == len(set(ids))                                   # taper_qty etc. appear once
    est = next(c for c in inv.checks if c.id == "inventory.weld_estimate")
    assert est.level == "warn" and "unverified" in est.message
    inv, _ = _run("14281", settings, _llm_answer())
    assert "flange-to-web seams" in next(c for c in inv.checks if c.id == "inventory.weld_estimate").message


def test_openai_inventory_is_cached_on_disk(settings, tmp_path):
    inv1, c1 = _run("09970", settings, _llm_answer(welds=[_weld("4p641", "4DC3", "length")]), cache_dir=tmp_path)
    inv2, c2 = _run("09970", settings, _llm_answer(), cache_dir=tmp_path)
    assert len(c2.responses.parse_calls) == 0 and inv2 == inv1
    assert len(list(Path(tmp_path).glob("*_inventory_*.json"))) == 1


def test_request_carries_full_page_context(settings):
    inv, client = _run("09970", settings, _llm_answer())
    content = client.responses.parse_calls[0][2][0]["content"]
    assert content[0]["text"].startswith("SHEET TEXT LAYER") and "[D8] A - A" in content[0]["text"]
    assert sum(c["type"] == "input_image" for c in content) == 4      # 2x2 tiles on an A1 sheet
    assert "UNKNOWN sections: none" in content[-1]["text"]
