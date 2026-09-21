# Drawing Q&A

Material inventory and visual Q&A for Tekla structural-steel fabrication drawings (vector PDFs on the TATA STEEL
sheet template). Upload a drawing to a Streamlit app, pick a page, and get:

- **a validated extract**: title block, bill of materials (BOM), abstract, bolt list, revisions, notes, erection
  locations, part marks and view labels. PyMuPDF reads it with no model calls, and arithmetic checks confirm it;
- **a fabrication BOQ** in the layout of the estimator's reference workbook (`2GU1 BOQ.xlsx`). It downloads as
  Excel with live formulas;
- **a material inventory**: plates by thickness and grade, rolled sections, fasteners, paint area, and an OpenAI
  weld estimate;
- **chat about the drawing**, with conversation context. The OpenAI model reads the sheet images *and* the
  PyMuPDF text layer, and can zoom and search;
- **exports**: Excel (all sheets), BOM CSV and JSON.

The design rule: **PyMuPDF reads and checks; OpenAI adds only what text parsing can't.** Every number the model
touches (weld lengths, section breakdowns, unit weights) is either computed by code from the BOM or checked
against it. Anything that cannot be verified is labelled unverified.

---

## Contents

1. [Quick start](#quick-start)
2. [The sample drawings](#the-sample-drawings)
3. [How it works](#how-it-works)
4. [Extraction (PyMuPDF)](#extraction-pymupdf)
5. [Guardrail checks](#guardrail-checks)
6. [OpenAI: page context, chat and inventory](#openai-page-context-chat-and-inventory)
7. [Fabrication BOQ](#fabrication-boq)
8. [Inventory](#inventory)
9. [Streamlit app](#streamlit-app)
10. [Batch run and the results folder](#batch-run-and-the-results-folder)
11. [Results on the sample drawings](#results-on-the-sample-drawings)
12. [Benchmark against the reference BOQ](#benchmark-against-the-reference-boq)
13. [Configuration](#configuration)
14. [Tests](#tests)
15. [Code map](#code-map)
16. [Known limitations](#known-limitations)
17. [Data handling](#data-handling)

---

## Quick start

```powershell
pip install -r requirements.txt
$env:OPENAI_API_KEY = "..."          # bash: export OPENAI_API_KEY=...
streamlit run app.py                 # the app
python -m pytest                     # offline tests (155)
python scripts/run_all.py            # every PDF in the repo root -> results/
python scripts/benchmark_boq.py "TST-SFD-46-01-01-07-000-16807_20260813154646827.pdf" "2GU1 BOQ.xlsx"
```

Python 3.10+ is required (developed on 3.13). Without `OPENAI_API_KEY`, the app still gives you:
- the extract and the checks;
- the deterministic inventory and BOQ;
- the exports.

The chat and the OpenAI inventory step need the key.

## The sample drawings

The repo root holds six client PDFs; the sixth is a byte-identical copy of 16807. Each is a single page.

| Drawing | Item | Assembly | Sheet | BOM rows | What makes it interesting |
|---|---|---|---|---|---|
| 09970 | Down comer | 4DC3 × 1 | A1 | 11 | Mitred pipes (BOM lengths are before cut-off); taper washers without a quantity |
| 14278 | Column | 3C1 × 1 | A0 | 43 | Heavy built-up column, 33.5 t; welded WH/T members decomposed into plates |
| 14281 | Column | 3C2 × 1 | A0 | 71 | Largest BOM; built-ups; the Tekla net total differs from the sum of the parts |
| 16362 | Down comer | 1DC1 × 2 | A1 | 7 | Rolled cone `SPD508*508*608*608*8`; fabrication quantity 2; rods |
| 16807 | Gutter | 2GU1 × 1 | A0 | 8 | Has the reference BOQ `2GU1 BOQ.xlsx` (ground truth for the BOQ) |

## How it works

### The problem, and the split

A Tekla fabrication sheet is a vector PDF: every number on it — the bill of materials, the title block, the
dimensions — is real text, positioned on the page. Nothing needs to be guessed. But a lot of what an estimator
needs is *not* text: which plate is welded to which, what a view is showing, how a rolled cone unrolls.

So the work is split by what each side is actually good at:

- **PyMuPDF reads and checks.** It recovers the tables exactly, and arithmetic proves the result: rows multiply
  out, totals add up, and a second independent parse agrees with the first. This costs nothing and never varies
  between runs.
- **OpenAI reads the drawing.** It sees the sheet as images *and* as text, and answers questions about it. In the
  inventory it supplies only what parsing cannot: which parts are welded together, what an unrecognised section
  is made from, and handbook weights for designations missing from the table.
- **Code has the last word on every number.** The model gives weld topology, not weld lengths — the lengths come
  from the BOM geometry. A plate breakdown is accepted only if it reconciles with the BOM weight. Anything that
  cannot be verified is labelled unverified and kept out of the BOQ.

Giving the model the text layer as well as the images is also what keeps the bill down: it doesn't have to squint
at a raster to read a number that PyMuPDF already has exactly.

### Stage by stage

**1. Open the page.** `PageLayout` wraps one PyMuPDF page: its words, text lines, drawn line segments, and the
sheet grid recovered from the numbers and letters printed around the border. That grid is what lets everything
afterwards say *where* something is — `[E7]` — in the same language the drawing itself uses.

**2. Read the sheet.** The parsers find each region by its printed title and the drawn cell borders, then read it:
the BOM, the abstract, the bolt list, the title block, revisions, notes, erection locations, part marks and view
labels. This is all deterministic: no model, no API key. The result is one `PageExtract` record, cached on disk by
file hash so a re-opened drawing is instant.

**3. Check it.** `run_checks` re-does the sheet's own arithmetic: qty × piece weight = gross on every row, the
part weights sum to the stated total, the abstract matches the BOM grouped by section, the title-block weight
matches, every BOM mark actually appears on a view, and a second BOM parse via `find_tables` agrees field by
field. A **fail** means the sheet and the extract disagree — don't trust the output until it's resolved. A
**warn** is worth a look. All five sample drawings run with zero fails.

**4. Build the inventory and the BOQ, without any model.** Each BOM section string is parsed into a shape:
`PL6*800` is a plate, `ISMC150` a channel, `PIPE508*6` a pipe, `WH1200X500X50X32` a welded built-up that
decomposes into flange and web plates, `SPD508*508*608*608*8` a rolled cone that unrolls into one flat plate.
Each shape gets a unit weight — 7.85 × t for plates, the IS 808 table for rolled sections, a formula for pipes and
rods — and that produces both the material inventory (plates by thickness, sections by profile, fasteners, paint
area) and the fabrication BOQ, in your reference workbook's layout with live formulas.

**5. Ask OpenAI for the rest.** One structured call sends the whole sheet — the grid-tagged text layer, tiles of
the full sheet, and the BOM *without its weights*, so the model cannot simply echo them back. It returns weld
topology, breakdowns for any section the code couldn't parse, and handbook weights for missing rolled
designations. Then the guardrails run: a weld whose size isn't a callout on the sheet, or that cites a part not in
the BOM, or whose length is geometrically impossible, or that exceeds the joint budget, is rejected with a reason.
A breakdown is accepted only if its thickness is in the section name and its weight is within ±2% of the BOM. If
the call fails, leaves a section unresolved, or gets most of its welds rejected, the step escalates once to the
deeper model and keeps the better result for each part.

**6. Ask questions.** Every chat turn starts from the same page context plus the validated extract and inventory,
so the model always has the whole sheet rather than a crop. When a detail is too small to read, it calls `zoom` on
a grid cell or a view label and gets a high-resolution image back; `search_text` locates a mark; `query_bom`
filters rows. Answers cite marks, BOM rows, grid cells and view labels, so each one can be checked against the
sheet. Because the context prefix is byte-identical on every call, OpenAI's prompt cache serves most of it — in
the last full run, 90% of the input tokens were cached.

**7. Export.** The BOQ downloads as Excel with live formulas and open-ended subtotals, so rows added by hand still
count. The full workbook adds the extract and inventory sheets; BOM CSV and JSON are there for other tools.

### One part, end to end

Take `1m470` on drawing 16362, a BOM row reading `SPD508*508*608*608*8`, length 506, qty 1, 54.93 kg:

1. PyMuPDF reads that row and confirms 1 × 54.93 = 54.93, and that the row's weight is part of a total that
   matches the title block.
2. `sections.py` recognises `SPD` as a rolled cone, 508 to 608 diameter, 8 mm thick.
3. The cone is developed flat on its mean diameters: a PL8 plate 1727.9 × 508.5 mm.
4. 7.85 × 8 mm gives 62.8 kg/m², so the plate calculates to 55.17 kg — within 0.5% of the drawing's 54.93 kg,
   which is the cross-check that the development is right.
5. It appears in the BOQ as `1m470 cone plate`, PL8, with the fabrication quantity of 2 applied, and in the
   inventory as 8 mm plate area rather than as a mystery section.

No model was involved. When the model *did* propose a weld around that cone, the guardrail rejected it, because a
"circumference" edge doesn't fit a cone's geometry — that rejection is recorded in
`results/TST-SFD-46-01-01-07-000-16362/report.md`.

### What it costs, and what runs without a key

The extract, the checks, the inventory, the BOQ and every export are free and offline. Only the chat and the
inventory's weld/unknown-section step call OpenAI. A full run over all five drawings — five inventory calls,
three escalations and twenty chat questions — used about 1.1 M input tokens on `gpt-5.4-mini`, 90% of them from
the prompt cache.

```
 PDF page
   │
   ├─► PageLayout (PyMuPDF: words, lines, drawing segments, sheet grid from border labels)
   │        │
   │        ├─► parsers ──► PageExtract (title block, BOM, abstract, bolts, revisions, notes,
   │        │                            mark locations, part marks, view labels, regions)
   │        │                    │
   │        │                    └─► validate.run_checks ──► pass / warn / fail checks
   │        │
   │        └─► context.page_context: grid-tagged text layer + hi-res tiles of the whole sheet
   │                          │  (identical prefix on every call → OpenAI prompt cache)
   │                          ▼
   ├─► deterministic_inventory ──► plates, sections, fasteners, paint, BOQ rows (IS 808 / 7.85 × t)
   │        │
   │        └─► OpenAI inventory step (one structured call; escalation to the deep model if needed)
   │               ├─ welds: topology only → code computes lengths from BOM geometry, guardrails filter
   │               ├─ unknown sections: plate breakdown → accepted only if thickness and weight match
   │               └─ missing rolled unit weights → used, but always flagged "unverified"
   │
   ├─► ChatSession (page context + extract + inventory; tools: query_bom, search_text, zoom)
   │
   └─► exports: BOQ .xlsx (live formulas), full workbook, BOM CSV, JSON
```

## Extraction (PyMuPDF)

Everything below is deterministic and needs no API key. The results are cached on disk under
`.dqa_cache/`, keyed by the file's SHA-256, the page number and `SCHEMA_VERSION`.

| Element | How it is read (`drawing_qa/parsers/…`) |
|---|---|
| **Sheet grid** | The border's column numbers and row letters give each text item a grid cell such as `E7`. The letters are found by alignment because they are inset from the border (`geometry.GridMap`). |
| **BOM** | The table frame is located from the `BILL OF MATERIALS` title; it must span the title and lie on the page. Columns are mapped from the header words (MARK, SECTION, LENGTH, QTY, …), and rows are grouped by y. The first row is the assembly; the rest are parts. Totals come from the footer. Fragments that touch are joined without inserting characters (`geometry.join_tokens`). |
| **BOM cross-check** | A second, independent parse with `page.find_tables()`, clipped to the same frame, is compared field by field with the first. |
| **Abstract** | The `ABSTRACT` table (SR. / description / WT.), bounded by its header. |
| **Bolts** | The `List of Permanent Bolts` table: bolt, nut, plain washer and taper washer columns per assembly. |
| **Title block** | Fully deterministic. Labelled cells are found from the drawn cell borders (`label_cells`). This gives the drawing no., rev, sheet, size, weight, department, equipment/area, project, title lines, and the drawn/checked/approved names and dates. |
| **Revisions, notes, mark locations** | Row-grouped tables. Mark locations give one row per erected instance: mark, grid location and level. |
| **Part marks, view labels** | Marks placed on the drawing views (outside the tables), plus section/detail labels (`A - A`, `MARK. NO:- 4p637`) with their scale and grid cell. |

The parsers were measured against PyMuPDF 1.28 (`requirements.txt` pins `>=1.28,<2`).

## Guardrail checks

`drawing_qa/validate.py` checks the extract. The inventory adds its own checks. **fail** means the numbers on
the sheet disagree with what was extracted. **warn** means a person should look; it is not proof of an error.

| Check | What it verifies |
|---|---|
| `text_layer` | The page has a usable text layer (scanned sheets fail here) |
| `bom.found`, `bom.assembly_row` | The BOM exists and has an assembly row |
| `bom.row_arith` | Every part row: qty × piece weight = gross (± rounding of the piece weight) |
| `bom.gross_total` | Σ part gross × assembly qty = BOM gross total |
| `bom.net_total` | The same for net weight. Informational: Tekla net totals often differ |
| `bom.crosscheck` | The `find_tables` parse agrees with the header-mapped parse |
| `abstract.by_section`, `abstract.total` | The abstract equals the BOM grouped by section; the abstract total equals the BOM total |
| `title.drawing_no`, `title.fields`, `title.weight` | The drawing no. matches the numbers elsewhere on the sheet; the required fields are present; the title-block weight equals the BOM total |
| `marks.bom_on_sheet`, `marks.extra` | Every BOM mark appears on a view; marks on the views that are not in the BOM |
| `mark_location.assembly`, `mark_location.count` | The erection-location table names the BOM assembly, and the number of rows matches the assembly qty |
| `bolt`, `nut` | Bolt-list rows are complete |
| `inventory.weight`, `inventory.bom` | The inventory's plates and sections add up to the BOM weight |
| `inventory.paint` | Paint area comes from the BOM surface area |
| `inventory.taper_qty` | Taper washers listed without a quantity (they are not counted) |
| `inventory.unclassified` | BOM sections the code could not classify |
| `inventory.welds`, `inventory.weld_estimate` | Weld guardrail results; the weld figures are labelled an estimate |
| `inventory.llm` | The OpenAI step failed, so the inventory is deterministic only |
| `boq.drawing_weight` | The BOQ drawing weights add up to the BOM total |
| `boq.calculated` | Calculated vs drawing weight; lists any rows that differ by more than 5% |
| `boq.unit_weights` | Unit weights supplied by OpenAI (always a warning, shown beside the drawing's value) |

## OpenAI: page context, chat and inventory

**Models:**
- `gpt-5.4-mini` by default;
- `gpt-5.5` for deep mode (a toggle in the app) and for automatic escalation of the inventory step.

The calls use the Responses API with strict Pydantic schemas (`responses.parse`) or function tools.

**Page context (`context.py`).** Every request starts with the same prefix, built once per page:
- the full PyMuPDF text layer, one line per text line, tagged with its grid cell (`[E7] 4p637`; rotated dimension
  text is marked `(vertical)`);
- high-resolution tiles of the whole sheet: 3 × 2 on A0 sheets, 2 × 2 on A1.

Because the prefix is identical on every call, OpenAI's prompt cache serves most of it. The prefix is about 17k
tokens on A1 and 36k on A0, and 94–98% of it was cached on repeat calls. The model therefore always sees the whole
sheet, not a crop.

**Chat (`chat.py`).** `ChatSession` adds the validated extract (and the inventory, once built) to the page
context. The model has three tools:

| Tool | Returns |
|---|---|
| `query_bom(contains)` | BOM rows whose mark, section or grade contains the text |
| `search_text(query)` | Hits on the sheet, each with its grid cell |
| `zoom(target)` | A high-resolution crop, returned as an image. The target can be a grid cell (`E7`), a range (`E7:G9`), a region (`bom`, `abstract`, `bolts`, `title_block`, `notes`, `mark_location`, `revisions`) or a view label (`B - B`, `4p637`) |

The instructions tell the model to:
- treat the extract's numbers as authoritative;
- cite marks, BOM rows, grid cells and view labels;
- copy text exactly as written;
- zoom before quoting a dimension;
- say plainly when the sheet doesn't contain the answer.
- when listing or totalling from a table, include every contributing row, including rows with a blank mark,
  and make stated totals equal the sum of the rows listed.

The session keeps the last 8 turns. Images are removed from the history so it doesn't grow, and each turn allows
at most 6 tool rounds.

**Inventory step (`inventory.py`).** It makes one structured call with the page context and the BOM, but *without
the BOM weights*, so the model cannot echo them back. The model returns three things:
1. **welds**: joint topology only. For each joint it gives the attached part, the base part, the welded edge
   (length / width / perimeter / circumference), the number of sides, the fillet size, the joint count, whether
   it is a tack weld, and the evidence it read (view label or grid cell). **Code computes the lengths** from the
   BOM geometry. A weld is rejected when:
   - its size is not a TYP./CONT. callout or note size on the sheet;
   - it cites a part not in the BOM;
   - its length is geometrically impossible;
   - it exceeds the joint budget for its (attached part, base part, edge).
2. **unknown sections**: a plate breakdown for sections the code cannot parse. A breakdown is accepted only if
   every plate's thickness appears in the section name and the total weight is within ±2% of the BOM.
3. **unit weights** for standard rolled sections that are missing from the IS 808 table. They are always
   labelled "OpenAI handbook value (unverified)".

The step escalates once to the deep model when:
- the mini call fails;
- an unknown section remains unresolved;
- or more than 30% of more than 2 proposed welds are rejected.

After escalation, each part is taken from the better run: sections from the run that resolved more, and welds from
the run with the lower rejection rate. Successful runs are cached.

## Fabrication BOQ

The primary non-chat output. It has one row per BOM part and the same layout, column spelling and formulas as the
reference `2GU1 BOQ.xlsx`:

| Col | Header | Content |
|---|---|---|
| A–E | DRAWING NO, ITEM TYPE, MARK NO, ITEMNO, SECTION | Item type from "DETAIL OF *GUTTER* MKD AS"; plates shown as `PL<t>` |
| F, G | WIDTH, LENGTH | mm (width for plates only) |
| H, I, J | QTY, FAB QTY, TOTAL QTY | `J = H*I`; FAB QTY is the assembly qty |
| K | UNIT WT | plates `=7.85*t` (kg/m²); rolled sections kg/m |
| L | CALCULATED WT | plates `=(F/1000)*(G/1000)*H*K`, others `=(G/1000)*H*K` |
| M | TOTAL CALCULATED WT | `=L*I` |
| N, O | WT, TOTAL DRG WT | Tekla gross weight of the row; `O = N*I` |
| P | DIFFRENCE | `=M-O` |
| Q | GRADE | |
| R, S | UNIT WT SOURCE, NOTE | extra columns: where K came from, and remarks |

Row 1 holds `=SUBTOTAL(9, X3:X105848)` for J, L, M, N, O and P over an open range, so rows added by hand are
included. Row 2 holds the headers.

**Unit weights (`steel_tables.py`):**

| Profile | Rule |
|---|---|
| Plate `PL`/`PLT` | 7.85 × t kg/m² |
| ISA (equal and unequal), ISMC, ISMB, round bars | IS 808 handbook table, transcribed from the Amardeep Steel weight chart and spot-checked against other published charts. ISA 150×150×15 is corrected to 33.8, because the source cell is truncated. |
| Pipe `PIPE od*t` | π (OD − t) t × 7850, computed |
| Rod `ROD d` | from the table, or π d²/4 × 7850 |
| Welded `WH`/`T` built-ups | split into flange and web plate rows (`3m471 flange`, `3m471 web`) |
| Rolled cone `SPD d1*d1*d2*d2*t` | developed flat on the mean diameters: width = π(r1 + r2), length = slant height. It becomes one `PL<t>` row (`1m470 cone plate`). |
| Other rolled designations missing from the table | OpenAI handbook value, flagged unverified |
| Anything else | OpenAI plate breakdown (checked on thickness and weight), or the drawing's own weight, with no difference computed |

No wastage is added. When one BOM part becomes several plates (a built-up), its drawing weight is shared among
them by plate weight.

## Inventory

`deterministic_inventory` (no API) produces:
- **plates** by thickness and grade: pieces, area and weight. Built-ups and cones are decomposed; each line lists
  its source marks;
- **sections** by profile and grade: pieces, total length and weight;
- **fasteners** from the bolt list: bolts, nuts, plain and taper washers by diameter, length, grade and
  specification, with the assemblies they connect;
- **paint area** from the BOM surface area;
- **total steel** = Σ BOM gross × assembly qty, reconciled against the plates plus the sections.

The OpenAI step adds welds (size, edge, sides, count, total length, weld-metal kg, evidence) and the electrode
estimate. These are always labelled **model-read estimate, unverified**, and they are kept out of the BOQ.

## Streamlit app

`streamlit run app.py`. Sidebar: upload a PDF, pick a page, and use two toggles: **Use OpenAI** (on when the key is
set) and **Deep mode** (`gpt-5.5` for everything). The sidebar also shows the check counts and the session's token
usage.

| Tab | Shows |
|---|---|
| Drawing | The sheet, plus a zoom box for a grid cell or range (`E7`, `E7:G9`) |
| Extract | Title block, BOM, abstract, bolts, revisions, notes, locations and view labels as tables |
| Checks | Every guardrail check, grouped by level |
| Inventory | BOQ first, with a **BOQ (Excel, live formulas)** download; plates, sections, fasteners, items for review; welds (model-read estimate, unverified). The **Run OpenAI step (welds, unknown sections)** button runs the OpenAI step. |
| Chat | Q&A with conversation context. Each answer shows the tools used and the zoomed crops the model looked at; **New conversation** resets the context. |
| Export | Full Excel workbook (BOQ sheet first), BOM CSV, extract JSON, inventory JSON |

## Batch run and the results folder

```powershell
python scripts/run_all.py [pdf_dir] [out_dir] [--offline] [--no-qa]     # defaults: .  results
```

The script runs the full pipeline on every PDF in `pdf_dir`. Byte-identical files are detected by SHA-256 and
skipped. For each drawing and page it writes `results/<drawing no>/`:

| File | Content |
|---|---|
| `report.md` | Readable summary: title block, checks, BOM, BOQ, inventory, welds, OpenAI usage |
| `qa.md` | Answers to four standard questions, asked in one conversation (overview and erection locations; heaviest part; plate thicknesses; fasteners) |
| `boq.xlsx` | The BOQ with live formulas, in the reference layout |
| `workbook.xlsx` | Everything: BOQ, extract sheets, inventory sheets |
| `extract.json`, `inventory.json`, `bom.csv` | Machine-readable outputs |
| `sheet.png` | Overview render of the sheet |

It also writes:
- `results/README.md`, an index of all drawings;
- `index.json`;
- `usage.json`, the tokens used per model;
- `benchmark_<drawing>.md/.json` wherever a reference BOQ matches a drawing (`2GU1 BOQ.xlsx` → 16807).

`--offline` skips OpenAI: the output is PyMuPDF extraction and the deterministic inventory and BOQ only.

## Results on the sample drawings

Full run on 2026-09-19 (`python scripts/run_all.py`, gpt-5.4-mini with escalation to gpt-5.5). The per-drawing
outputs are in `results/`; start with `results/README.md`.

| Drawing | Item | Assembly | BOM rows | BOM gross kg | BOQ rows | BOQ calculated kg | BOQ drawing kg | Welds accepted (rejected) | Checks pass / warn / fail |
|---|---|---|---|---|---|---|---|---|---|
| 09970 | Down comer | 4DC3 × 1 | 11 | 432.62 | 11 | 473.49 | 432.62 | 9 (0) | 18 / 3 / 0 |
| 14278 | Column | 3C1 × 1 | 43 | 33,496.76 | 48 | 33,497.51 | 33,496.76 | 18 (0) | 18 / 1 / 0 |
| 14281 | Column | 3C2 × 1 | 71 | 26,121.53 | 77 | 26,122.18 | 26,121.52 | 45 (0) | 18 / 2 / 0 |
| 16362 | Down comer | 1DC1 × 2 | 7 | 350.52 | 7 | 352.84 | 350.54 | 4 (1) | 16 / 3 / 0 |
| 16807 | Gutter | 2GU1 × 1 | 8 | 976.84 | 8 | 979.60 | 976.84 | 6 (0) | 17 / 2 / 0 |

**Every drawing:**
- **Zero failed checks.** Row arithmetic, BOM totals, the abstract, the title-block weight, the second BOM parse and
  the marks on the sheet all agree.
- **The BOQ's drawing weights add up to the BOM gross total.** The 0.01–0.02 kg gaps come from Tekla rounding the
  piece weights.
- **Plates + sections = BOM gross** in the inventory.

What the warnings are:

| Drawing | Warning | Why |
|---|---|---|
| 09970 | `boq.calculated` +40.87 kg | The three PIPE508*6 rows use the BOM length before the mitre cut-offs (+7–15%). This is expected; the rows are flagged. |
| 09970 | `inventory.taper_qty` | The bolt list names taper washers for 4PSB2/5/6 but prints no quantity, so none are counted |
| 14281, 16807 | `bom.net_total` | Tekla's net total differs from the sum of the part net weights. Informational only; gross totals match. |
| 16362 | `boq.calculated` +2.30 kg | The ROD8 cage is +1.07 kg against the drawing (computed π d²/4 vs Tekla's rounded piece weight) |
| 16362 | `inventory.welds`, 1 rejected | The model proposed a circumferential weld on the cone 1m470 to plate 1p374. The guardrail rejects it because that edge does not fit the cone's geometry. |
| all | `inventory.weld_estimate` | Weld metal is 0.01–1.0% of steel against a typical 1–2%. It is always flagged as a model-read estimate. The drawings do not show the flange-to-web seams of the built-up columns, so they are not counted. |

**BOQ unit weights.** All five drawings are covered by 7.85 × t, the IS 808 table, or the pipe/rod formulas. No
OpenAI unit weights were needed, and every section was classified without an OpenAI breakdown. The cone on 16362 is
developed by code as `1m470 cone plate` (PL8, 1727.9 × 508.5 mm, 0.5% above the drawing weight).

**Welds.** In this run the model correctly marked the 16362 rod cage as tack-welded (the note at D4, "CAGE TO BE
TACK WELDED"). An earlier run got it wrong, so the weld figures remain estimates.

**Q&A.** Four questions per drawing, asked in one conversation, are saved in `results/<drawing>/qa.md`. The
answers were spot-checked against the extract: the heaviest part is right on all five drawings, including the
14278 tie between 3C1 and its main-part row 3m470. The locations, plate thicknesses and bolt lists come back with
grid cells.

This run exposed one completeness bug, now fixed. On 09970 the bolt list has a row with no connected assembly
(10 bolts). The chat summary had left it out and reported 8 bolts instead of 18. `compact_extract` used to drop
empty fields, so that row reached the model without an assembly field; it now carries `"(blank on sheet)"`. A new
prompt rule also says to list every contributing row and make stated totals equal the listed rows. The re-run
answer lists all four rows: 18 bolts, 26 nuts and 18 washers, matching the deterministic fastener list.

**Cost of the full run** (5 drawings, one inventory call each, 3 escalations, 20 chat questions): gpt-5.4-mini
1.09 M input tokens (0.98 M served from the prompt cache) and 11.5 k output; gpt-5.5 59 k input and 16 k output;
34 calls in total.

## Benchmark against the reference BOQ

```powershell
python scripts/benchmark_boq.py <drawing.pdf> <reference.xlsx> [--openai]
```

The benchmark does three things:
- matches rows on ITEMNO and compares every value column;
- compares the formula structure of J, L, M, O and P, with row numbers normalised;
- **evaluates the exported workbook itself** with a small formula evaluator (`benchmark.evaluate`) and compares
  every computed cell and SUBTOTAL with the reference's values.

This proves the downloaded file computes the same numbers, not just that the Python rows match.

Result for 16807 vs `2GU1 BOQ.xlsx`, both deterministic and with `--openai`:

| Measure | Result |
|---|---|
| Rows | 8 / 8; none missing, none extra |
| Fields | 135 / 136 identical |
| Formula structure | 0 differences |
| Evaluated workbook | 0 cell differences |
| Subtotals | Total qty 66 · calculated 979.5946 kg · drawing 976.84 kg · difference +2.7546 kg (all equal) |

The one differing field is the reference's grade for 2GU1: `E2350A`, where the drawing's BOM says `E350A`. It looks
like a typo in the reference.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | none | Needed for chat and the OpenAI inventory step |
| `DQA_MODEL` | `gpt-5.4-mini` | Default model |
| `DQA_DEEP_MODEL` | `gpt-5.5` | Deep mode and escalation |
| `DQA_CACHE_DIR` | `.dqa_cache` | Extract and inventory cache |
| `DQA_SAMPLES` | repo root | Folder of sample PDFs for the tests |

Fixed in `config.Settings`:

| Setting | Value |
|---|---|
| Zoom crops | 200 dpi, at most 2400 px |
| Chat tool rounds per turn | 6 |
| Chat turns kept | 8 |
| API timeout | 120 s |
| API retries | 2 |

## Tests

```powershell
python -m pytest                     # 155 tests, offline, about 1 minute
```

The tests run against the real sample PDFs; tests whose PDF is missing are skipped. OpenAI is replaced by a fake
client (`tests/fakes.py`), so no tokens are used.

| File | Covers |
|---|---|
| `test_geometry.py` | Clustering, number parsing, token joining, grid map |
| `test_bom.py`, `test_tables.py`, `test_titleblock_views.py` | Every parser against golden values from the five drawings |
| `test_extract.py` | The full extract, the checks and the cache |
| `test_context.py`, `test_render_llm.py` | Page context, tiles, rendering, the LLM wrapper |
| `test_sections.py` | Section parsing, decomposition, cone development, the angle geometry screen |
| `test_inventory.py` | Deterministic inventory, weld guardrails, unknown sections, unit weights, escalation, cache |
| `test_boq.py` | BOQ rows against the 16807 golden values, the benchmark against the reference xlsx (when present), the evaluated workbook on all sheets |
| `test_chat.py`, `test_app.py`, `test_export.py` | Chat tool loop, Streamlit AppTest, exports |

Live checks that use the real API and cost tokens:

```powershell
python scripts/live_smoke.py <pdf> "question" ...
python scripts/benchmark_boq.py <pdf> "2GU1 BOQ.xlsx" --openai
python scripts/run_all.py
```

## Code map

```
app.py                      Streamlit UI
drawing_qa/
  config.py                 Settings (env), SCHEMA_VERSION
  geometry.py               cluster / num / join_tokens / GridMap
  layout.py                 PageLayout: words, lines, segments, grid over a PyMuPDF page
  parsers/bom.py            BOM parse + find_tables cross-check
  parsers/tables.py         abstract, bolts, revisions, notes, mark locations
  parsers/titleblock.py     bordered-cell title block
  parsers/views.py          part marks, view labels
  extract.py                PageExtract assembly + disk cache
  validate.py               guardrail checks
  models.py                 Pydantic records (extract, inventory, BoqRow)
  render.py                 PNG crops, overview and tiles
  context.py                page context sent to OpenAI
  llm.py                    OpenAI wrapper (parse / create / usage)
  chat.py                   ChatSession + tools
  sections.py               section parsing, built-up and cone decomposition
  steel_tables.py           IS 808 unit weights
  boq.py                    BOQ rows
  inventory.py              deterministic inventory + OpenAI step + guardrails
  export.py                 JSON / CSV / Excel, BOQ sheet with live formulas
  benchmark.py              BOQ comparison and formula evaluator
scripts/run_all.py          batch run → results/
scripts/benchmark_boq.py    BOQ vs reference workbook
scripts/live_smoke.py       real-API smoke test
docs/superpowers/           design spec and implementation plan (with the audit records)
```

## Known limitations

- **Welds are the weak spot.** The model reads weld topology from the views, and the answers vary from run to run.
  On 16362, one run marked the wrong joint as tack-welded. The guardrails reject impossible welds but cannot prove
  a plausible one is right. Weld and electrode figures are estimates and never go into the BOQ.
- **One reference BOQ.** Only 16807 has ground truth, and it contains only plates, channels and angles. The rules
  for built-ups, cones, pipes and a fabrication quantity above 1 are checked by tests and reconcile to the BOM
  weights, but no estimator's BOQ has confirmed them.
- **Pipe and rod rows run heavier than the drawing.** BOM lengths come before mitre or hole cut-offs, so the BOQ
  can be 7–15% heavier (09970) and flags such rows. This is expected, not an error.
- **Text layer required.** Scanned or raster-only PDFs fail the `text_layer` check; there is no OCR.
- **Template-specific.** The parsers target the TATA STEEL Tekla sheet layout. Other title blocks or BOM layouts
  need parser changes.
- **Unit weights from OpenAI** are only used for standard rolled designations that are missing from the table.
  They are always unverified; add confirmed values to `steel_tables.py` instead.

## Data handling

- The drawings (`*.pdf`) and the reference workbook `2GU1 BOQ.xlsx` are proprietary client data: git-ignored and
  never committed. Put them in the repo root (or point `DQA_SAMPLES` elsewhere) to run the app, the tests or a
  batch run.
- `results/` **is committed**, because the reports are the point of the repo. It contains the drawings' BOM data,
  so this repository is private and must stay private.
- The OpenAI key is read only from the environment and is never written to disk or logs.
- Only the selected page (its images and text) is sent to OpenAI.
