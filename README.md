# Drawing Q&A

Streamlit app for Tekla structural-steel fabrication drawings (vector PDF, TATA STEEL template). Upload a sheet to:
- get a validated extract (title block, BOM, abstract, bolts, revisions, notes, erection locations, view labels);
- build a material inventory;
- ask questions about the drawing;
- export everything to Excel, CSV or JSON.

- **Extract: PyMuPDF only.** No model calls. Checks guard every number: qty × piece weight = gross, Σ gross × assembly
  qty = grand total, abstract = BOM by section, a second independent BOM parse, and every BOM mark appears on the drawing.
- **Q&A: OpenAI** (`gpt-5.4-mini`; deep mode `gpt-5.5`). The model sees the whole sheet on every call: the full text
  layer tagged with grid cells, high-resolution tiles, and the validated extract. It can zoom and search, and it cites
  marks, grid cells and BOM rows.
- **Inventory:** plates by thickness and grade (welded WH/T members decomposed into plates), sections by profile,
  fasteners from the bolt list, and paint area. All of these are deterministic and reconcile to the BOM weight.
  OpenAI reads the welds from the views and interprets unknown sections. Guardrails reject:
  - weld sizes that are not on the sheet;
  - welds citing unknown parts;
  - impossible weld lengths;
  - joint counts over budget;
  - plate breakdowns whose weight doesn't match the BOM.

  Weld metal and electrode figures are estimates.

## Run

    pip install -r requirements.txt
    $env:OPENAI_API_KEY="..."        # bash: export OPENAI_API_KEY=...
    streamlit run app.py

Environment: `DQA_MODEL` (default gpt-5.4-mini), `DQA_DEEP_MODEL` (default gpt-5.5), `DQA_CACHE_DIR` (default .dqa_cache).

## Test

    python -m pytest                                  # offline; sample PDFs in the repo root (or DQA_SAMPLES)
    python scripts/live_smoke.py <pdf> "question"     # real API, costs tokens
