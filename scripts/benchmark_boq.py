"""Benchmark the app's BOQ against a reference BOQ workbook.

    python scripts/benchmark_boq.py <drawing.pdf> <reference.xlsx> [--openai]

Without --openai the BOQ is fully deterministic (PyMuPDF + handbook table); with it, the OpenAI inventory step
runs first (unit weights for sections missing from the table, unknown-section breakdowns)."""
import sys
from pathlib import Path

import pymupdf

from drawing_qa.benchmark import compare_boq
from drawing_qa.config import Settings
from drawing_qa.extract import extract_page
from drawing_qa.inventory import build_inventory, deterministic_inventory
from drawing_qa.layout import PageLayout
from drawing_qa.llm import LLM


def main(pdf, gt, use_openai=False):
    data = Path(pdf).read_bytes()
    x = extract_page(data, 0, Path(pdf).name, use_cache=False)
    if use_openai:
        s = Settings()
        page = pymupdf.open(stream=data, filetype="pdf")[0]
        inv = build_inventory(x, page, PageLayout.from_page(page), LLM(), s.model, s.deep_model)
    else:
        inv = deterministic_inventory(x)
    res = compare_boq(inv, gt)
    print(f"rows: ours {res['our_rows']}  reference {res['gt_rows']}  missing {res['missing']}  extra {res['extra']}")
    ok = res["fields_checked"] - len(res["field_diffs"])
    print(f"fields: {ok}/{res['fields_checked']} identical")
    for d in res["field_diffs"]:
        print(f"  DIFF {d['item']:10} {d['field']:14} ours={d['ours']!r}  reference={d['gt']!r}")
    print(f"formulas: {len(res['formula_diffs'])} structural differences")
    for d in res["formula_diffs"]:
        print(f"  FORMULA {d['item']:10} col {d['col']}: ours={d['ours']!r} reference={d['gt']!r}")
    print("subtotals (row 1):")
    for k, v in res["totals"].items():
        print(f"  {k:14} ours {v['ours']:12.4f}  reference {v['gt']:12.4f}  {'OK' if v['match'] else 'DIFF'}")
    return res


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], "--openai" in sys.argv)
