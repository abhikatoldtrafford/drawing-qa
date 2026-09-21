# TST-SFD-46-01-01-07-000-16362

- **Source file:** `TST-SFD-46-01-01-07-000-16362_20260813153914809.pdf` (page 1)
- **Title:** SHED FOR POCIL PLOT LOT-1 / DETAIL OF DOWN COMER MKD AS -1DC1
- **Project / department / area:**  / DESIGN & ENGINEERING-STRUCTURAL / HOT ROLLED PICKLING GALVANIZED LINE (HRPGL)
- **Rev / sheet / size:** 0 / 1 OF 1 / A1
- **Drawn / checked / approved:** IRCON 09.07.2026 / SKS/NBT 09.07.2026 / SSA 09.07.2026
- **Title-block weight:** 350.52 kg
- **Assembly:** 1DC1 × 2 (DOWN COMER)
- **Erection locations:** 1DC1 @ 19-20/<LEG-1 EL. +17.065; 1DC1 @ 22-23/<LEG-1 EL. +17.049
- **Run time:** 89 s; OpenAI model: gpt-5.4-mini (sections) + gpt-5.5 (welds); usage: {'gpt-5.4-mini:input': 16518, 'gpt-5.4-mini:output': 420, 'gpt-5.4-mini:cached': 15488, 'gpt-5.4-mini:calls': 1, 'gpt-5.5:input': 16518, 'gpt-5.5:output': 6013, 'gpt-5.5:calls': 1}

## Checks (PyMuPDF guardrails)

| level | check | message |
|---|---|---|
| pass | bom.row_arith | All 7 rows: qty × pc wt = gross (± rounding). |
| pass | bom.gross_total | Σ part gross × assembly qty 2 = 350.54; grand total = 350.52. |
| pass | bom.assembly_row | Assembly row 1DC1 gross 350.52 vs grand total 350.52. |
| pass | bom.net_total | Σ part net = 161.88 (× qty 2 = 323.76); net total = 161.64. Tekla net totals often differ; informational. |
| pass | bom.crosscheck | find_tables() second parse agrees on every row (section, length, qty, gross, material). |
| pass | marks.bom_on_sheet | Every BOM mark appears on the drawing. |
| pass | title.weight | Title block weight 350.52 vs BOM gross 350.52. |
| pass | mark_location.assembly | Mark box ['1DC1', '1DC1'] vs BOM assembly '1DC1'. |
| pass | mark_location.count | 2 erection location(s) listed; assembly qty 2. |
| pass | abstract.total | Σ abstract = 350.52; abstract total = 350.52; BOM gross = 350.52. |
| pass | abstract.by_section | Every abstract row equals the BOM gross for that section/plate thickness. |
| pass | title.drawing_no | Drawing no. TST-SFD-46-01-01-07-000-16362 matches file name. |

## Bill of materials

| mark | section | length mm | qty | pc wt | gross kg | grade |
|---|---|---|---|---|---|---|
| 1DC1 | PIPE508*6 | 400 | 1 | 29.59 | 29.59 | YST 240 |
| 1m470 | SPD508*508*608*608*8 | 506 | 1 | 54.93 | 54.93 | YST 240 |
| 1m471 | ISMC150 | 800 | 1 | 13.16 | 13.16 | E250A |
| 1m472 | ISA75X75X8 | 800 | 1 | 7.15 | 7.15 | E250A |
| 1m473 | ROD8 | 608 | 22 | 0.22 | 4.75 | E250A |
| 1p374 | PL6*800 | 1,478 | 1 | 55.71 | 55.71 | E350A |
| 1p375 | PL6*75 | 1,412 | 2 | 4.99 | 9.98 | E350A |

Totals: net 161.64 kg, gross 350.52 kg, surface 9.72 m²

## Fabrication BOQ

| item | section | width | length | qty | fab | unit wt | calc kg | drg kg | diff kg | grade | unit wt source |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1DC1 | PIPE508*6 |  | 400.0 | 1 | 2 | 74.280 | 59.424 | 59.180 | 0.244 | YST 240 | computed (pi (OD-t) t x 7850) |
| 1m470 cone plate | PL8 | 1,727.9 | 508.5 | 1 | 2 | 62.800 | 110.357 | 109.860 | 0.497 | YST 240 | 7.85 x t |
| 1m471 | ISMC150 |  | 800.0 | 1 | 2 | 16.800 | 26.880 | 26.320 | 0.560 | E250A | IS 808 table |
| 1m472 | ISA75X75X8 |  | 800.0 | 1 | 2 | 8.900 | 14.240 | 14.300 | -0.060 | E250A | IS 808 table |
| 1m473 | ROD8 |  | 608.0 | 22 | 2 | 0.395 | 10.567 | 9.500 | 1.067 | E250A | computed (pi d²/4 x 7850) |
| 1p374 | PL6 | 800.0 | 1,478.4 | 1 | 2 | 47.100 | 111.412 | 111.420 | -0.008 | E350A | 7.85 x t |
| 1p375 | PL6 | 75.0 | 1,412.4 | 2 | 2 | 47.100 | 19.957 | 19.960 | -0.003 | E350A | 7.85 x t |

BOQ totals: calculated 352.837 kg, drawing 350.540 kg, difference +2.297 kg

## Inventory

Total steel (BOM gross × assembly qty): **350.52 kg**; paint area 9.72 m²

| plate | grade | pieces | area m² | kg | sources |
|---|---|---|---|---|---|
| PL6 | E350A | 6 | 2.789 | 131.38 | 1p374, 1p375 |
| PL8 | YST 240 | 2 | 1.757 | 109.86 | 1m470 (cone 1727.9x8) |

| profile | family | grade | pieces | length m | kg | sources |
|---|---|---|---|---|---|---|
| ISA75X75X8 | angle | E250A | 2 | 1.600 | 14.30 | 1m472 |
| ISMC150 | channel | E250A | 2 | 1.600 | 26.32 | 1m471 |
| PIPE508*6 | pipe | YST 240 | 2 | 0.800 | 59.18 | 1DC1 |
| ROD8 | round | E250A | 44 | 26.752 | 9.50 | 1m473 |

### Welds (model-read estimate, unverified)

| parts | size mm | edge | sides | count | tack | total m | metal kg | evidence |
|---|---|---|---|---|---|---|---|---|
| 1DC1 → 1m470 | 6 | circumference | 1 | 1 | False | 3.192 | 0.451 | Section/B-B area F-G: pipe 1DC1 to reducer 1m470 joint marked TYP.; general note 6 mm fillet U.N.O. |
| 1m473 → 1p374 | 6 | length | 1 | 22 | True | 26.752 | 0.000 | A-A view C-D/F: rod cage labelled 11x 1m473 each way; note at D4 says CAGE TO BE TACK WELDED; general note 6 mm fillet U.N.O. |
| 1m471 → 1p374 | 4 | length | 2 | 1 | False | 3.200 | 0.201 | Side/section detail around E-F: weld symbol 4/4 CONT. at 1m471 to 1p374 joint. |
| 1m472 → 1p374 | 4 | length | 1 | 1 | False | 1.600 | 0.100 | Side/section detail E-F: CONT. 4 weld symbol at 1m472 angle to plate joint. |

Weld metal 0.750 kg, electrode 1.250 kg

Rejected by guardrails:
- 1m470->1p374 circumference 6mm: edge 'circumference' does not apply to 1m470 SPD508*508*608*608*8

### Inventory checks

| level | check | message |
|---|---|---|
| pass | boq.drawing_weight | BOQ total drawing weight 350.54 kg; BOM gross total 350.52 kg. |
| warn | boq.calculated | BOQ calculated 352.84 kg vs drawing 350.54 kg (+2.30 kg). Rows off by >5%: ['1m473 ROD8: +1.07 kg']. |
| pass | inventory.unclassified | Every BOM member is classified. |
| warn | inventory.welds | 4 weld runs accepted; 1 rejected: 1m470->1p374 circumference 6mm: edge 'circumference' does not apply to 1m470 SPD508*508*608*608*8 |
| warn | inventory.weld_estimate | Weld metal 0.75 kg (0.21% of steel; fabricated steel is typically 1-2%) is a model-read estimate, unverified: topology read by OpenAI, lengths computed from the BOM, tack welds excluded. |
| pass | inventory.weight | Plates + sections = 350.54 kg; BOM gross total = 350.52 kg. |
| pass | inventory.paint | Paint area 9.72 m² (BOM total); Σ row area × qty = 9.50 m². |

## Q&A

See [qa.md](qa.md).
