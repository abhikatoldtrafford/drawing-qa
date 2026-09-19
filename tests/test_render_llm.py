import pymupdf
from pydantic import BaseModel

import pytest

from drawing_qa.llm import LLM, LLMError
from drawing_qa.render import render_clip, render_overview, tile_rects

from .conftest import sample_path
from .fakes import FakeClient


def _png_size(png):
    pix = pymupdf.Pixmap(png)
    return pix.width, pix.height


def test_render_clip_caps_long_side():
    page = pymupdf.open(sample_path("14281"))[0]
    w, h = _png_size(render_clip(page, page.rect, max_px=1200))
    assert max(w, h) == 1200
    w, h = _png_size(render_clip(page, (0, 0, 72, 36), max_px=5000, dpi=144))
    assert (w, h) == (144, 72)                                 # small clips render at the requested dpi
    assert max(_png_size(render_overview(page, 800))) == 800


def test_tile_rects_cover_sheet_with_overlap():
    page = pymupdf.open(sample_path("09970"))[0]
    tiles = tile_rects(page, 2, 2)
    assert len(tiles) == 4
    assert tiles[0][0] == 0 and tiles[0][1] == 0
    assert tiles[-1][2] == page.rect.width and tiles[-1][3] == page.rect.height
    assert tiles[0][2] > tiles[1][0]                           # neighbours overlap


class Echo(BaseModel):
    value: str


def test_llm_parse_records_usage_per_model():
    client = FakeClient(parse_fn=lambda model, schema: schema(value=model))
    llm = LLM(client)
    assert llm.parse("m1", "sys", "hello", [b"png"], Echo).value == "m1"
    llm.parse("m1", "sys", "again", [], Echo)
    assert llm.usage_summary() == {"m1": {"input": 200, "output": 20, "cached": 0, "calls": 2}}
    content = client.responses.parse_calls[0][2][0]["content"]
    assert content[0] == {"type": "input_text", "text": "hello"}
    assert content[1]["type"] == "input_image" and content[1]["image_url"].startswith("data:image/png;base64,")


def test_llm_parse_raises_on_empty_output():
    llm = LLM(FakeClient(parse_fn=lambda model, schema: None))
    with pytest.raises(LLMError, match="returned no parsed Echo"):
        llm.parse("m1", "sys", "hi", [], Echo)
    assert llm.usage_summary()["m1"]["calls"] == 1           # tokens were still spent and are counted
