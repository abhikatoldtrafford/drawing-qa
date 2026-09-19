"""Opt-in end-to-end run against the real OpenAI API (costs tokens).

    python scripts/live_smoke.py <pdf> ["question" ...]
"""
import sys
import time
from pathlib import Path

import pymupdf

from drawing_qa.chat import ChatSession
from drawing_qa.config import Settings
from drawing_qa.extract import extract_page
from drawing_qa.inventory import build_inventory
from drawing_qa.layout import PageLayout
from drawing_qa.llm import LLM


def main(pdf, questions):
    data = Path(pdf).read_bytes()
    settings = Settings()
    llm = LLM(timeout=settings.api_timeout_s, max_retries=settings.api_max_retries)
    t = time.time()
    x = extract_page(data, 0, Path(pdf).name, settings=settings, use_cache=False)
    print(f"extract (PyMuPDF only): {time.time() - t:.1f}s")
    for c in x.checks:
        if c.level != "pass":
            print(f"  [{c.level}] {c.id}: {c.message}")
    print(f"title: {x.title_block.title_lines}  project={x.title_block.project!r}")
    page = pymupdf.open(stream=data, filetype="pdf")[0]
    layout = PageLayout.from_page(page)
    t = time.time()
    inv = build_inventory(x, page, layout, llm, settings.model, settings.deep_model)
    print(f"\ninventory: {time.time() - t:.0f}s  model={inv.model}  usage={inv.usage}")
    for p in inv.plates:
        print(f"  PL{p.thickness_mm:g} {p.grade}: {p.pieces} pcs, {p.area_m2} m2, {p.weight_kg} kg")
    for s in inv.sections:
        print(f"  {s.profile} {s.grade}: {s.pieces} pcs, {s.total_length_m} m, {s.weight_kg} kg")
    print(f"  welds accepted {len(inv.welds)}, rejected {len(inv.rejected_welds)}; weld metal {inv.weld_metal_kg} kg")
    for c in inv.checks:
        print(f"  [{c.level}] {c.id}: {c.message[:160]}")
    chat = ChatSession(x, page, layout, llm, settings.model, settings, inventory=inv)
    for q in questions:
        turn = chat.ask(q)
        print(f"\nQ: {q}\n  tools: {turn.tool_log}\n  A: {turn.answer}")
    print(f"\nsession usage: {llm.usage_summary()}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:] or ["What is the total gross weight and which part is heaviest?"])
