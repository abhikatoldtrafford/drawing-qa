# Drawing Q&A

Material take-off and visual Q&A for Tekla structural-steel fabrication drawings.

## About

Estimators price fabrication drawings by hand: read the bill of materials off the sheet, work out each part's
weight, group the plates by thickness, count the bolts, and type it all into a BOQ spreadsheet. This does that
from the PDF, in a Streamlit app, and lets you ask the drawing questions.

The sheets are Tekla exports on the TATA STEEL title-block template — vector PDFs, one drawing per page, where
every number is real text rather than a scan.

**What it produces from one sheet:**

| Output | Contents |
|---|---|
| **Fabrication BOQ** | One row per BOM part, in the estimator's reference layout, downloadable as Excel with live formulas and subtotals |
| **Validated extract** | Title block, BOM, abstract, bolt list, revisions, notes, erection locations, part marks, view labels — with arithmetic checks on every number |
| **Material inventory** | Plates by thickness and grade, sections by profile, fasteners, paint area, and a weld estimate |
| **Answers** | Chat over the sheet with conversation context, citing part marks, BOM rows and grid cells |

**The design rule:** PyMuPDF reads and checks; OpenAI adds only what text parsing can't. Every number the model
touches is either computed by code from the BOM or reconciled against it. What can't be verified is labelled
unverified and kept out of the BOQ.

**Status:** working on five client drawings, with the BOQ benchmarked against an estimator's own workbook
(135/136 fields identical — the one difference is a typo in the reference). 155 tests. Weld estimates are the
known weak spot; see [Limitations](#limitations).

**Contents:** [Quick start](#quick-start) · [How it works](#how-it-works) · [Extraction](#extraction-pymupdf) ·
[Checks](#checks) · [OpenAI](#openai-page-context-chat-and-inventory) · [BOQ](#fabrication-boq) ·
[Inventory](#inventory) · [App](#streamlit-app) · [Batch runs](#batch-runs-and-the-results-folder) ·
[Results](#results-on-the-sample-drawings) · [Benchmark](#benchmark-against-the-reference-boq) ·
[Config](#configuration) · [Tests](#tests) · [Code map](#code-map) · [Limitations](#limitations) ·
[Data](#data-handling)

## Quick start

```powershell
pip install -r requirements.txt
$env:OPENAI_API_KEY = "..."          # bash: export OPENAI_API_KEY=...
streamlit run app.py                 # the app
python -m pytest                     # 155 offline tests, ~1 min
python scripts/run_all.py            # every PDF in the folder -> results/
python scripts/benchmark_boq.py <drawing.pdf> <reference.xlsx>
```

Python 3.10+ (developed on 3.13). The drawings are not in the repo — put your own sheets in the repo root, or
point `DQA_SAMPLES` at them. Tests whose sample PDF is missing are skipped.

Without `OPENAI_API_KEY` you still get the extract, the checks, the inventory, the BOQ and every export. Only the
chat and the weld/unknown-section step need the key.

## How it works

A Tekla sheet is a vector PDF, so the bill of materials, the title block and the dimensions are all real text that
can be read exactly. What *isn't* text is the drawing itself: which plate is welded to which, what a view shows,
how a rolled cone unrolls. So the work is split:

- **PyMuPDF reads and checks.** It recovers the tables exactly, and arithmetic proves the result: rows multiply
  out, totals add up, a second independent parse agrees with the first. Free, and identical every run.
- **OpenAI reads the drawing.** It sees the sheet as images *and* as text, answers questions, and in the inventory
  supplies only what parsing cannot: weld topology, breakdowns of unrecognised sections, handbook weights missing
  from the table.
- **Code has the last word.** The model gives weld topology, not lengths — lengths come from BOM geometry. A plate
  breakdown is accepted only if it reconciles with the BOM weight.

Sending the text layer alongside the images is also what keeps the bill down: the model never has to squint at a
raster for a number PyMuPDF already has.

### Stages

1. **Open the page.** `PageLayout` wraps one PyMuPDF page: words, text lines, drawn segments, and the sheet grid
   recovered from the border labels. The grid is how everything afterwards says *where* — `[E7]` — in the
   drawing's own language.
2. **Read the sheet.** Parsers locate each region by its printed title and drawn cell borders, then read the BOM,
   abstract, bolt list, title block, revisions, notes, erection locations, part marks and view labels into one
   `PageExtract`, cached on disk by file hash.
3. **Check it.** `run_checks` re-does the sheet's own arithmetic (see [Checks](#checks)). A **fail** means sheet
   and extract disagree; a **warn** is worth a look.
4. **Build the inventory and BOQ, with no model.** Each BOM section string is parsed into a shape — `PL6*800` a
   plate, `ISMC150` a channel, `PIPE508*6` a pipe, `WH1200X500X50X32` a built-up that splits into flange and web
   plates, `SPD508*508*608*608*8` a cone that unrolls flat — and each shape gets a unit weight.
5. **Ask OpenAI for the rest.** One structured call sends the whole sheet plus the BOM *without its weights*, so
   the model can't echo them back. It returns weld topology, unknown-section breakdowns and missing unit weights;
   the guardrails then reject anything that doesn't hold up. On failure or heavy rejection the step escalates once
   to the deeper model and keeps the better result per part.
6. **Ask questions.** Every turn starts from the same page context plus the extract and inventory, so the model
   always has the whole sheet. It zooms into a grid cell or view label when a detail is too small to read.
7. **Export.** BOQ as Excel with live formulas; full workbook, CSV and JSON alongside.

```
 PDF page
   │
   ├─► PageLayout (PyMuPDF: words, lines, drawing segments, sheet grid from border labels)
   │        │
   │        ├─► parsers ──► PageExtract ──► validate.run_checks ──► pass / warn / fail
   │        │
   │        └─► page_context: grid-tagged text layer + hi-res tiles
   │                          (identical prefix every call → OpenAI prompt cache)
   │
   ├─► deterministic_inventory ──► plates, sections, fasteners, paint, BOQ (IS 808 / 7.85 × t)
   │        │
   │        └─► OpenAI step (one structured call, escalates once if needed)
   │               ├─ welds: topology only → lengths computed from BOM, guardrails filter
   │               ├─ unknown sections: plate breakdown → thickness and ±2% weight must match
   │               └─ missing unit weights → used, always flagged unverified
   │
   ├─► ChatSession (page context + extract + inventory; query_bom, search_text, zoom)
   │
   └─► exports: BOQ .xlsx (live formulas), full workbook, BOM CSV, JSON
```

### One part, end to end

`1m470` on drawing 16362 — BOM row `SPD508*508*608*608*8`, length 506, qty 1, 54.93 kg:

1. PyMuPDF reads the row and confirms 1 × 54.93 = 54.93 against a total that matches the title block.
2. `sections.py` recognises `SPD` as a rolled cone, 508 to 608 diameter, 8 mm thick.
3. The cone is developed flat on its mean diameters: a PL8 plate, 1727.9 × 508.5 mm.
4. 7.85 × 8 = 62.8 kg/m² gives 55.17 kg — within 0.5% of the drawing's 54.93 kg, which is the cross-check that
   the development is right.
5. It reaches the BOQ as `1m470 cone plate` with the fabrication quantity of 2 applied, and the inventory as 8 mm
   plate area rather than an unknown section.

No model involved. When the model *did* propose a weld around that cone, the guardrail rejected it — a
"circumference" edge doesn't fit a cone — and recorded the reason in the report.

## Extraction (PyMuPDF)

Deterministic, no API key. Cached under `.dqa_cache/`, keyed by file SHA-256, page and `SCHEMA_VERSION`.

| Element | How it is read |
|---|---|
| **Sheet grid** | Border column numbers and row letters give every text item a cell like `E7`. Letters are matched by alignment, since they sit inset from the border (`geometry.GridMap`). |
| **BOM** | The frame is found from the `BILL OF MATERIALS` title (it must span the title and lie on the page); columns are mapped from the header words, rows grouped by y. First row is the assembly, the rest parts, totals from the footer. Touching fragments are joined without inserting characters. |
| **BOM cross-check** | A second, independent parse with `page.find_tables()` clipped to the same frame, compared field by field. |
| **Abstract** | The `ABSTRACT` table (SR. / description / WT.), bounded by its header. |
| **Bolts** | `List of Permanent Bolts`: bolt, nut, plain washer and taper washer columns per connected assembly. |
| **Title block** | Labelled cells found from the drawn borders: drawing no., rev, sheet, size, weight, department, equipment/area, project, title lines, and drawn/checked/approved names and dates. |
| **Revisions, notes, mark locations** | Row-grouped tables; mark locations give one row per erected instance (mark, grid location, level). |
| **Part marks, view labels** | Marks on the views, plus section/detail labels (`A - A`, `MARK. NO:- 4p637`) with scale and grid cell. |

Measured against PyMuPDF 1.28 (`requirements.txt` pins `>=1.28,<2`).

## Checks

`validate.py` checks the extract; the inventory adds its own.

| Check | What it verifies |
|---|---|
| `text_layer` | The page has a usable text layer (scans fail here) |
| `bom.found`, `bom.assembly_row` | The BOM exists and has an assembly row |
| `bom.row_arith` | Every row: qty × piece weight = gross (± rounding) |
| `bom.gross_total`, `bom.net_total` | Σ part weight × assembly qty = the stated total. Net is informational: Tekla net totals often differ |
| `bom.crosscheck` | The `find_tables` parse agrees with the header-mapped parse |
| `abstract.by_section`, `abstract.total` | The abstract equals the BOM grouped by section, and its total equals the BOM total |
| `title.drawing_no`, `title.fields`, `title.weight` | Drawing no. matches elsewhere on the sheet; required fields present; title-block weight equals the BOM total |
| `marks.bom_on_sheet`, `marks.extra` | Every BOM mark appears on a view; marks on views that aren't in the BOM |
| `mark_location.assembly`, `mark_location.count` | The erection table names the assembly, and its row count matches the assembly qty |
| `bolt`, `nut` | Bolt-list rows are complete |
| `inventory.weight`, `inventory.bom` | Plates + sections add up to the BOM weight |
| `inventory.paint` | Paint area comes from the BOM surface area |
| `inventory.taper_qty` | Taper washers listed without a quantity (not counted) |
| `inventory.unclassified` | Sections the code couldn't classify |
| `inventory.welds`, `inventory.weld_estimate` | Guardrail results; the weld figures are an estimate |
| `inventory.llm` | The OpenAI step failed; inventory is deterministic only |
| `boq.drawing_weight` | BOQ drawing weights add up to the BOM total |
| `boq.calculated` | Calculated vs drawing weight, listing rows off by more than 5% |
| `boq.unit_weights` | Unit weights supplied by OpenAI (always a warning, shown beside the drawing's value) |

## OpenAI: page context, chat and inventory

`gpt-5.4-mini` by default; `gpt-5.5` for deep mode and for escalation. Calls use the Responses API with strict
Pydantic schemas or function tools.

**Page context.** Every request opens with the same prefix, built once per page: the full text layer tagged with
grid cells (`[E7] 4p637`, rotated text marked `(vertical)`), plus tiles of the whole sheet — 3 × 2 on A0, 2 × 2 on
A1. About 17k tokens on A1 and 36k on A0, of which 94–98% is served from OpenAI's prompt cache on later calls. The
model always sees the whole sheet, never just a crop.

**Chat.** `ChatSession` adds the validated extract and, once built, the inventory. Three tools:

| Tool | Returns |
|---|---|
| `query_bom(contains)` | BOM rows matching mark, section or grade |
| `search_text(query)` | Hits on the sheet, each with its grid cell |
| `zoom(target)` | A high-resolution crop as an image: a grid cell (`E7`), a range (`E7:G9`), a region (`bom`, `abstract`, `bolts`, `title_block`, `notes`, `mark_location`, `revisions`) or a view label (`B - B`, `4p637`) |

The instructions require it to treat the extract's numbers as authoritative, cite marks / BOM rows / grid cells /
view labels, copy text exactly as written, zoom before quoting a dimension, say plainly when the sheet doesn't
answer the question, and — when listing or totalling a table — include every contributing row, with stated totals
equal to the rows listed. The session keeps 8 turns, strips images from history, and allows 6 tool rounds a turn.

**Inventory step.** One structured call, with the BOM but not its weights. Returns:

1. **Welds** — topology only: attached part, base part, welded edge (length / width / perimeter / circumference),
   sides, fillet size, joint count, tack or not, and the evidence read. Code computes the lengths. A weld is
   rejected when its size isn't a callout on the sheet, it cites a part not in the BOM, its length is
   geometrically impossible, or it exceeds the joint budget for that pair and edge.
2. **Unknown sections** — a plate breakdown, accepted only if every thickness appears in the section name and the
   total weight is within ±2% of the BOM.
3. **Unit weights** for rolled designations missing from the IS 808 table, always labelled
   "OpenAI handbook value (unverified)".

It escalates once to the deep model if the call fails, a section stays unresolved, or more than 30% of more than
2 proposed welds are rejected; then it takes sections from the run that resolved more and welds from the run with
the lower rejection rate. Successful runs are cached.

## Fabrication BOQ

One row per BOM part, in the reference workbook's layout, column spelling and formulas:

| Col | Header | Content |
|---|---|---|
| A–E | DRAWING NO, ITEM TYPE, MARK NO, ITEMNO, SECTION | Item type from "DETAIL OF *GUTTER* MKD AS"; plates as `PL<t>` |
| F, G | WIDTH, LENGTH | mm (width for plates only) |
| H, I, J | QTY, FAB QTY, TOTAL QTY | `J = H*I`; FAB QTY is the assembly qty |
| K | UNIT WT | plates `=7.85*t` (kg/m²); rolled sections kg/m |
| L | CALCULATED WT | plates `=(F/1000)*(G/1000)*H*K`, else `=(G/1000)*H*K` |
| M | TOTAL CALCULATED WT | `=L*I` |
| N, O | WT, TOTAL DRG WT | Tekla gross weight of the row; `O = N*I` |
| P | DIFFRENCE | `=M-O` |
| Q | GRADE | |
| R, S | UNIT WT SOURCE, NOTE | added columns: where K came from, and remarks |

Row 1 holds `=SUBTOTAL(9, X3:X105848)` for J, L, M, N, O and P — an open range, so rows added by hand count. Row 2
holds the headers.

**Unit weights** (`steel_tables.py`):

| Profile | Rule |
|---|---|
| Plate `PL`/`PLT` | 7.85 × t kg/m² |
| ISA (equal and unequal), ISMC, ISMB, rounds | IS 808 handbook table, transcribed from the Amardeep Steel chart and spot-checked against other published charts. ISA 150×150×15 corrected to 33.8 (the source cell is truncated). |
| Pipe `PIPE od*t` | π (OD − t) t × 7850 |
| Rod `ROD d` | table, else π d²/4 × 7850 |
| Built-up `WH`/`T` | split into flange and web plate rows (`3m471 flange`, `3m471 web`) |
| Cone `SPD d1*d1*d2*d2*t` | developed flat on mean diameters: width π(r1 + r2), length the slant height; becomes one `PL<t>` row |
| Rolled designations missing from the table | OpenAI handbook value, flagged unverified |
| Anything else | OpenAI plate breakdown (thickness- and weight-checked), or the drawing's own weight with no difference computed |

No wastage is added. Where one BOM part becomes several plates, its drawing weight is shared among them by plate
weight.

## Inventory

Deterministic, no API:

- **plates** by thickness and grade — pieces, area, weight, and the source marks of each line (built-ups and cones
  decomposed);
- **sections** by profile and grade — pieces, total length, weight;
- **fasteners** from the bolt list — bolts, nuts, plain and taper washers by diameter, length, grade and spec,
  with the assemblies they connect;
- **paint area** from the BOM surface area;
- **total steel** = Σ BOM gross × assembly qty, reconciled against plates + sections.

The OpenAI step adds welds and the electrode estimate. Both are labelled **model-read estimate, unverified** and
stay out of the BOQ.

## Streamlit app

`streamlit run app.py`. The sidebar uploads a PDF, picks a page, and toggles **Use OpenAI** (on when the key is
set) and **Deep mode**; it also shows check counts and session token usage.

| Tab | Shows |
|---|---|
| Drawing | The sheet, plus a zoom box for a grid cell or range |
| Extract | Title block, BOM, abstract, bolts, revisions, notes, locations, view labels |
| Checks | Every check, grouped by level |
| Inventory | BOQ first with an Excel download; plates, sections, fasteners, items for review; welds. **Run OpenAI step** runs the model pass. |
| Chat | Q&A with context; each answer shows the tools used and the crops the model looked at |
| Export | Full workbook, BOM CSV, extract JSON, inventory JSON |

## Batch runs and the results folder

```powershell
python scripts/run_all.py [pdf_dir] [out_dir] [--offline] [--no-qa]     # defaults: .  results
```

Runs the full pipeline over every PDF in a folder, skipping byte-identical duplicates. Per drawing it writes
`results/<drawing no>/`:

| File | Content |
|---|---|
| `report.md` | Title block, checks, BOM, BOQ, inventory, welds, token usage |
| `qa.md` | Four standard questions answered in one conversation |
| `boq.xlsx` / `workbook.xlsx` | The BOQ with live formulas / everything, all sheets |
| `extract.json`, `inventory.json`, `bom.csv` | Machine-readable outputs |
| `sheet.png` | Overview render |

Plus `results/README.md` (index), `index.json`, `usage.json`, and `benchmark_<drawing>.md/.json` where a reference
BOQ matches. `--offline` skips OpenAI entirely.

## Results on the sample drawings

Full run, `gpt-5.4-mini` with escalation. Outputs are in [`results/`](results/).

| Drawing | Item | Assembly | BOM rows | BOM gross kg | BOQ rows | Calculated kg | Drawing kg | Welds kept (rejected) | Checks P/W/F |
|---|---|---|---|---|---|---|---|---|---|
| 09970 | Down comer | 4DC3 × 1 | 11 | 432.62 | 11 | 473.49 | 432.62 | 9 (0) | 18 / 3 / 0 |
| 14278 | Column | 3C1 × 1 | 43 | 33,496.76 | 48 | 33,497.51 | 33,496.76 | 18 (0) | 18 / 1 / 0 |
| 14281 | Column | 3C2 × 1 | 71 | 26,121.53 | 77 | 26,122.18 | 26,121.52 | 45 (0) | 18 / 2 / 0 |
| 16362 | Down comer | 1DC1 × 2 | 7 | 350.52 | 7 | 352.84 | 350.54 | 4 (1) | 16 / 3 / 0 |
| 16807 | Gutter | 2GU1 × 1 | 8 | 976.84 | 8 | 979.60 | 976.84 | 6 (0) | 17 / 2 / 0 |

Zero failed checks anywhere. On every drawing the BOQ's drawing weights add up to the BOM total (0.01–0.02 kg
from Tekla rounding), and plates + sections equal BOM gross. Every section was classified and every unit weight
came from the table or a formula — no OpenAI unit weights were needed.

The warnings:

| Drawing | Warning | Why |
|---|---|---|
| 09970 | `boq.calculated` +40.87 kg | The three PIPE508*6 rows use BOM lengths, which are before the mitre cut-offs (+7–15%) |
| 09970 | `inventory.taper_qty` | Taper washers are named for 4PSB2/5/6 with no quantity printed, so none are counted |
| 14281, 16807 | `bom.net_total` | Tekla's net total differs from the sum of part net weights; gross totals match |
| 16362 | `boq.calculated` +2.30 kg | The ROD8 cage is +1.07 kg (computed π d²/4 vs Tekla's rounded piece weight) |
| 16362 | `inventory.welds` | One weld rejected: a circumferential weld proposed on cone 1m470, an edge that doesn't fit its geometry |
| all | `inventory.weld_estimate` | Weld metal is 0.01–1.0% of steel against a typical 1–2%; the built-up columns' flange-to-web seams aren't drawn, so they aren't counted |

Cost of the full run — 5 inventory calls, 3 escalations, 20 chat questions: ~1.1 M input tokens on `gpt-5.4-mini`
(90% cached) and 11.5k output, plus 59k/16k on `gpt-5.5`.

## Benchmark against the reference BOQ

```powershell
python scripts/benchmark_boq.py <drawing.pdf> <reference.xlsx> [--openai]
```

It matches rows on ITEMNO and compares every value column; compares the formula structure of J, L, M, O and P
with row numbers normalised; and **evaluates the exported workbook itself** with a small formula evaluator,
comparing every computed cell and SUBTOTAL against the reference. That last step proves the downloaded file
computes the same numbers, not just that the Python rows match.

Drawing 16807 against the estimator's `2GU1 BOQ.xlsx`, both with and without `--openai`:

| Measure | Result |
|---|---|
| Rows | 8 / 8; none missing, none extra |
| Fields | 135 / 136 identical |
| Formula structure | 0 differences |
| Evaluated workbook | 0 cell differences |
| Subtotals | Total qty 66 · calculated 979.5946 kg · drawing 976.84 kg · difference +2.7546 kg, all equal |

The one differing field is the reference's grade for 2GU1, `E2350A`, where the BOM says `E350A` — a typo in the
reference.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | — | Required for chat and the OpenAI inventory step |
| `DQA_MODEL` | `gpt-5.4-mini` | Default model |
| `DQA_DEEP_MODEL` | `gpt-5.5` | Deep mode and escalation |
| `DQA_CACHE_DIR` | `.dqa_cache` | Extract and inventory cache |
| `DQA_SAMPLES` | repo root | Folder of sample PDFs for the tests |

Fixed in `config.Settings`: zoom crops at 200 dpi / 2400 px max, 6 tool rounds per turn, 8 turns kept, 120 s API
timeout, 2 retries.

## Tests

```powershell
python -m pytest        # 155 tests, offline, ~1 min
```

Tests run against real sample PDFs (skipped when absent) with a fake OpenAI client, so no tokens are spent.

| File | Covers |
|---|---|
| `test_geometry.py` | Clustering, number parsing, token joining, grid map |
| `test_bom.py`, `test_tables.py`, `test_titleblock_views.py` | Every parser against golden values from five drawings |
| `test_extract.py` | Full extract, checks, cache |
| `test_context.py`, `test_render_llm.py` | Page context, tiles, rendering, LLM wrapper |
| `test_sections.py` | Section parsing, decomposition, cone development, angle geometry screen |
| `test_inventory.py` | Deterministic inventory, weld guardrails, unknown sections, unit weights, escalation, cache |
| `test_boq.py` | BOQ rows against golden values, benchmark vs the reference xlsx, evaluated workbook |
| `test_chat.py`, `test_app.py`, `test_export.py` | Chat tool loop, Streamlit AppTest, exports |

Live checks that cost tokens: `scripts/live_smoke.py`, `scripts/benchmark_boq.py --openai`, `scripts/run_all.py`.

## Code map

```
app.py                      Streamlit UI
drawing_qa/
  config.py                 Settings (env), SCHEMA_VERSION
  geometry.py               cluster / num / join_tokens / GridMap
  layout.py                 PageLayout over a PyMuPDF page
  parsers/bom.py            BOM parse + find_tables cross-check
  parsers/tables.py         abstract, bolts, revisions, notes, mark locations
  parsers/titleblock.py     bordered-cell title block
  parsers/views.py          part marks, view labels
  extract.py                PageExtract assembly + disk cache
  validate.py               checks
  models.py                 Pydantic records (extract, inventory, BoqRow)
  render.py                 PNG crops, overview, tiles
  context.py                page context sent to OpenAI
  llm.py                    OpenAI wrapper (parse / create / usage)
  chat.py                   ChatSession + tools
  sections.py               section parsing, built-up and cone decomposition
  steel_tables.py           IS 808 unit weights
  boq.py                    BOQ rows
  inventory.py              deterministic inventory + OpenAI step + guardrails
  export.py                 JSON / CSV / Excel with live formulas
  benchmark.py              BOQ comparison and formula evaluator
scripts/run_all.py          batch run → results/
scripts/benchmark_boq.py    BOQ vs a reference workbook
scripts/live_smoke.py       real-API smoke test
docs/superpowers/           design spec and implementation plan
```

## Limitations

- **Welds are the weak spot.** Topology read from the views varies between runs; one run marked the wrong joint as
  tack-welded. Guardrails reject impossible welds but can't prove a plausible one right. Weld and electrode
  figures are estimates and never enter the BOQ.
- **One reference BOQ.** Only 16807 has ground truth, and it holds only plates, channels and angles. The rules for
  built-ups, cones, pipes and fabrication quantities above 1 are covered by tests and reconcile to BOM weights,
  but no estimator's BOQ has confirmed them.
- **Pipes and rods calculate heavier than the drawing**, because BOM lengths precede mitre and hole cut-offs. Such
  rows are flagged, not corrected.
- **Text layer required.** Scanned or raster-only PDFs fail `text_layer`; there is no OCR.
- **Template-specific.** The parsers target the TATA STEEL Tekla sheet. Other title blocks or BOM layouts need
  parser changes.
- **OpenAI unit weights** are only for standard rolled designations missing from the table, and stay unverified —
  add confirmed values to `steel_tables.py` instead.

## Data handling

- The sample drawings (`*.pdf`) and the reference workbook `2GU1 BOQ.xlsx` are git-ignored and stay local.
- `results/` is committed: it holds the drawings' BOM data, title-block names and sheet renders.
- The OpenAI key is read from the environment only, never written to disk or logs.
- Only the selected page — its images and text — is sent to OpenAI.
