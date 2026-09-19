import json

import pymupdf
import pytest

from drawing_qa.chat import ChatSession
from drawing_qa.layout import PageLayout
from drawing_qa.llm import LLM

from .conftest import det, sample_path
from .fakes import FakeClient, call_response, text_response


def test_chat_runs_tools_and_keeps_history(settings):
    p = sample_path("09970")
    x = det("09970", settings)
    page = pymupdf.open(p)[0]
    script = [call_response("zoom", json.dumps({"target": "bom"})),
              text_response("12 plates, 13.40 kg (4p639, 4p640, 4p641)."),
              call_response("query_bom", json.dumps({"contains": "4p660"}), call_id="call_2"),
              text_response("E350A.")]
    client = FakeClient(script=script)
    chat = ChatSession(x, page, PageLayout.from_page(page), LLM(client), "mini", settings)
    t1 = chat.ask("How many 8 mm plates?")
    assert t1.tool_log == ["zoom(bom)"] and len(t1.images) == 1 and "13.40" in t1.answer
    t2 = chat.ask("Material of 4p660?")
    assert t2.tool_log == ["query_bom(4p660)"] and t2.answer == "E350A."
    second_input = client.responses.create_calls[2][1]
    assert any(isinstance(i, dict) and i.get("content") == "How many 8 mm plates?" for i in second_input)
    old_zoom = [i for i in second_input if isinstance(i, dict) and i.get("type") == "function_call_output"]
    assert old_zoom and isinstance(old_zoom[0]["output"], str)   # earlier image stripped from history
    assert all(not isinstance(i.get("output"), list) for i in chat.history if isinstance(i, dict))


def test_chat_survives_malformed_tool_arguments(settings):
    p = sample_path("09970")
    x = det("09970", settings)
    page = pymupdf.open(p)[0]
    client = FakeClient(script=[call_response("zoom", "{not json"), text_response("Could not zoom.")])
    chat = ChatSession(x, page, PageLayout.from_page(page), LLM(client), "mini", settings)
    turn = chat.ask("Zoom somewhere")
    assert turn.tool_log == ["zoom: error"] and turn.answer == "Could not zoom."
    sent = client.responses.create_calls[1][1]
    assert any(isinstance(i, dict) and str(i.get("output", "")).startswith("error:") for i in sent)


def test_chat_zoom_targets(settings):
    p = sample_path("14281")
    x = det("14281", settings)
    page = pymupdf.open(p)[0]
    chat = ChatSession(x, page, PageLayout.from_page(page), LLM(FakeClient()), "mini", settings)
    for target in ["E7", "E7:G9", "bom", "B - B", "title_block"]:
        r = chat._rect_for(target)
        assert r[2] > r[0] and r[3] > r[1], target
    with pytest.raises(ValueError):
        chat._rect_for("nowhere")
    with pytest.raises(ValueError, match="occurs 2 times"):   # 'M - M' is drawn at N13 and P18
        chat._rect_for("M - M")


def test_compact_extract_keeps_bolt_rows_without_assembly(settings):
    from drawing_qa.chat import compact_extract
    x = det("09970", settings)
    bolts = compact_extract(x)["bolts"]
    assert len(bolts) == len(x.bolts)
    assert sum(b["assembly_mark"] == "(blank on sheet)" for b in bolts) == sum(not b.assembly_mark for b in x.bolts)
