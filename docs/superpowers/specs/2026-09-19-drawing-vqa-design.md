# Drawing Q&A — Design (v2)

**Date:** 2026-09-19 · **Status:** v1 audited in 3 rounds (APPROVE); v2 audited (approve with changes, resolved); BOQ audited (approve with changes, resolved; see the addendum).

## Goal

A local Streamlit app for one page of a Tekla structural-steel fabrication drawing (TATA STEEL template, vector PDF). It:
- turns the page into a validated, exportable record;
- lists the materials needed to fabricate it;
- answers questions about the sheet.

PyMuPDF produces every number. OpenAI reads the whole page (image and text) to answer questions and to assist the inventory. Code guardrails decide what OpenAI output is kept.

## Decisions (from the user)

| Topic | Decision |
|---|---|
| Extraction | PyMuPDF only (no model calls) |
| Q&A | OpenAI gets the whole page on every call (sheet tiles + full grid-tagged text + extract), plus a zoom tool; strictly the selected page |
| Inventory | Selected page. Contents: raw material (plates by thickness+grade, sections by profile+grade), fasteners, paint and weld estimates. Built-ups are decomposed into plates. No wastage allowance. Welds are read by OpenAI. |
| Models | `gpt-5.4-mini` by default; the inventory step escalates to `gpt-5.5` when its answer is weak; a "deep mode" toggle forces `gpt-5.5` |
| Input | Vector CAD PDFs only (no OCR) |
| Grounding | Text citations (marks, BOM rows, grid cells, view labels) |
| Editing / deployment | Read-only; local single user; key from `OPENAI_API_KEY`; disk cache by file SHA-256 |

## What the sample sheets look like (measured on 5 files, confirmed by the independent audit)

- **Sheets:** one page each, A1 (2591×1729 pt) or A0 (~3399×2412 pt), with a full text layer.
- **Anchors:** regions are found by anchor text: `BILL OF MATERIALS`, `ABSTRACT`, `List of Permanent Bolts`, `TATA STEEL LIMITED`, `GRID LOCATION`, `1. ALL DIMENSIONS`, `NO. DATE REVISION`.
- **BOM table:** rows are separated by full-width rules and the numeric columns are ruled, but the MARK|ITEM|SECTION block isn't. Page-wide `find_tables()` merges the ABSTRACT into the BOM. Clipped to the BOM frame it reads the same rows as the primary parser, so it serves as an independent second parse.
- **Title block:** every field is a bordered cell to the right of its label. A blank PROJECT cell reads as the next label ("MATERIAL") and is treated as empty.
- **BOM arithmetic:**
  - Gross total = Σ part gross × assembly qty (16362: qty 2).
  - Net totals drift in Tekla (informational).
  - Piece weights are rounded, so the row tolerance scales with qty.
  - Each abstract row = BOM gross for that section or plate thickness (`PL` and `PLT`) × qty.
- **Mark box:** one row per erected instance.
- **Sections:** every one parses into a known family except `SPD508*508*608*608*8`. WH/T built-up recipes reproduce BOM piece weights to 0.00%.

## Architecture

```
PDF ─► PageLayout ─► parsers ─► run_checks ─► PageExtract (cached)          [no model calls]
                                                 │
            context.page_context(page, layout) ──┼──► ChatSession (+ extract JSON + inventory JSON, tools)
            (grid-tagged text + sheet tiles)     │
                                                 └──► inventory: deterministic lines ─► OpenAI welds/unknowns
                                                      ─► guardrails ─► escalate once if weak ─► Inventory
```

### Guardrails
1. **Extract.** Checks: row arithmetic, gross total × qty, assembly row, abstract total and abstract-by-section, the second BOM parse, every BOM mark on the drawing, title weight = BOM, mark box = assembly and its row count = qty.
2. **Inventory weight.** Plates + sections must equal the BOM gross total (0.5%). Paint area must be within 5% of Σ row area × qty.
3. **Unknown sections.** An OpenAI plate breakdown is kept only if it weighs within 2% of the BOM member; otherwise the member stays "needs review".
4. **Welds.** A weld is rejected if:
   - its size is not on the sheet (general note, or near `TYP.`);
   - a part is not in the BOM;
   - its length exceeds twice the smaller part's (length + width);
   - its count exceeds 2 × part qty;
   - it exceeds the per-part joint budget (2 per piece of the repeated part).

   Weld metal and electrode are estimates. A coverage check warns when weld metal is under 0.5% of the steel weight.
5. **Escalation.** When unknowns are unresolved or more than 30% of the welds are rejected, the step re-runs once on `gpt-5.5` and the better result is kept.
6. **Chat.** Extract numbers are authoritative. The model must look (and zoom) before it answers, cite its sources, and copy identifiers exactly. Tool rounds are capped at 6. Old images are dropped from history. Bad tool arguments go back to the model as errors.
7. **Failure isolation.** An API error never loses deterministic data or crashes the UI.

### Cost profile (measured, gpt-5.4-mini)
- **Page context per call:** about 17k input tokens on A1 and about 36k on A0; 94–98% is a cache hit on repeat calls. Latency is 4–6 s on A1 and about 20 s on A0.
- **Inventory OpenAI step:** 16–39k input tokens. Escalation adds the same on `gpt-5.5`.
- **Deterministic extraction:** about 0.5 s, plus the `find_tables` cross-check (0.2 s on A1, 2–4 s on A0).

## Out of scope
OCR / scanned PDFs, cross-document questions and inventory, editing extracted data, multi-user deployment, image overlays, wastage allowances.

## Addendum (2026-09-19): fabrication BOQ tuned to the user's ground truth

The user supplied `2GU1 BOQ.xlsx` (for drawing 16807) as the expected inventory output. The Inventory mode's
primary output is now that BOQ: one row per BOM part, the same columns, and live formulas with SUBTOTALs.
- **Plates:** `PL<t>` + width, 7.85 × t kg/m² (`PLT` counts as a plate).
- **Rolled sections:** IS 808 handbook kg/m, transcribed from a cited public table. The benchmark does not
  use the reference's own values, which avoids a circular test; the table agrees with them anyway (ISMC150 16.8,
  ISA75X75X8 8.9).
- **Pipes and bars not in the table:** computed from geometry.
- **Built-ups:** listed as their plates.
- **Unknown sections:** an OpenAI breakdown when accepted; otherwise the drawing-implied kg/m, flagged.
- **OpenAI unit weights** for untabulated sections are accepted only within ±5% of the drawing weight.
- **Checks:** BOQ drawing weight = BOM gross; per-row differences over 5%, missing unit weights and
  drawing-derived unit weights are flagged.
- **Benchmark on 16807** (deterministic and OpenAI mode): 8/8 rows, 135/136 fields; the one difference is the
  reference's grade typo `E2350A`. 0 formula differences, all subtotals equal.

**BOQ audit (independent; approve with changes, all resolved):**
- **Confirmed independently.** The auditor's own PyMuPDF-only BOQ gives 135/136, with the typo as the only
  difference, and the exported formulas evaluate correctly on all 5 sheets.
- **Unit weights (M1).** The OpenAI unit weight is no longer "accepted within ±5% of the drawing", which was
  circular. It is requested only for rolled IS designations missing from the table, the prompt carries no piece
  weights, and the value is always shown as unverified beside the drawing-implied kg/m.
- **Cone (M2).** The SPD member is a circular cone, developed deterministically on the mean diameters into a PL t
  plate row (16362: PL8 1727.9 × 508.5, +0.44% vs BOM). A drawing-derived unit weight leaves DIFFERENCE blank.
- **Table and export.** ISA 150×150×15 is corrected to 33.8 (the source cell was truncated), with a geometric
  screen test over the whole angle table. The SUBTOTAL range is open (row 105848), as in the reference. Pipe rows
  note their mitre and hole cut-off.
- **Benchmark.** It now also evaluates the exported workbook's formulas: 0 evaluated-cell differences from
  the reference.
