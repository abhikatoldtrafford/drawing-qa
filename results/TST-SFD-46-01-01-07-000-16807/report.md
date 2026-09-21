# TST-SFD-46-01-01-07-000-16807

- **Source file:** `TST-SFD-46-01-01-07-000-16807_20260813154646827.pdf` (page 1)
- **Title:** SHED FOR POCIL PLOT LOT-2 / DETAIL OF GUTTER MKD AS -2GU1
- **Project / department / area:**  / DESIGN & ENGINEERING-STRUCTURAL / HOT ROLLED PICKLING GALVANIZED LINE (HRPGL)
- **Rev / sheet / size:** 0 / 1 OF 1 / A0
- **Drawn / checked / approved:** IRCON 18.07.2026 / SKS/NBT 18.07.2026 / SSA 18.07.2026
- **Title-block weight:** 976.84 kg
- **Assembly:** 2GU1 × 1 (GUTTER)
- **Erection locations:** 2GU1 @ 14-15/<LEG-1 EL. +17.115
- **Run time:** 80 s; OpenAI model: gpt-5.4-mini (sections) + gpt-5.5 (welds); usage: {'gpt-5.4-mini:input': 23659, 'gpt-5.4-mini:output': 693, 'gpt-5.4-mini:calls': 1, 'gpt-5.5:input': 23659, 'gpt-5.5:output': 5730, 'gpt-5.5:calls': 1}

## Checks (PyMuPDF guardrails)

| level | check | message |
|---|---|---|
| pass | bom.row_arith | All 8 rows: qty × pc wt = gross (± rounding). |
| pass | bom.gross_total | Σ part gross × assembly qty 1 = 976.84; grand total = 976.84. |
| pass | bom.assembly_row | Assembly row 2GU1 gross 976.84 vs grand total 976.84. |
| warn | bom.net_total | Σ part net = 974.13 (× qty 1 = 974.13); net total = 971.51. Tekla net totals often differ; informational. |
| pass | bom.crosscheck | find_tables() second parse agrees on every row (section, length, qty, gross, material). |
| pass | marks.bom_on_sheet | Every BOM mark appears on the drawing. |
| pass | title.weight | Title block weight 976.84 vs BOM gross 976.84. |
| pass | mark_location.assembly | Mark box ['2GU1'] vs BOM assembly '2GU1'. |
| pass | mark_location.count | 1 erection location(s) listed; assembly qty 1. |
| pass | abstract.total | Σ abstract = 976.84; abstract total = 976.84; BOM gross = 976.84. |
| pass | abstract.by_section | Every abstract row equals the BOM gross for that section/plate thickness. |
| pass | title.drawing_no | Drawing no. TST-SFD-46-01-01-07-000-16807 matches file name. |

## Bill of materials

| mark | section | length mm | qty | pc wt | gross kg | grade |
|---|---|---|---|---|---|---|
| 2GU1 | PL6*1067 | 1,478 | 1 | 74.30 | 74.30 | E350A |
| 2m272 | ISMC150 | 9,088 | 1 | 149.48 | 149.48 | E250A |
| 2m273 | ISA75X75X8 | 9,088 | 1 | 81.18 | 81.18 | E250A |
| 2p205 | PLT8*50 | 400 | 18 | 1.26 | 22.62 | E350A |
| 2p206 | PLT8*50 | 739 | 18 | 2.32 | 41.73 | E350A |
| 2p207 | PLT8*50 | 451 | 18 | 1.42 | 25.51 | E350A |
| 2p208 | PL6*1478 | 2,000 | 4 | 139.27 | 557.07 | E350A |
| 2p209 | PL6*75 | 1,412 | 5 | 4.99 | 24.95 | E350A |

Totals: net 971.51 kg, gross 976.84 kg, surface 39.16 m²

## Fabrication BOQ

| item | section | width | length | qty | fab | unit wt | calc kg | drg kg | diff kg | grade | unit wt source |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2GU1 | PL6 | 1,067.0 | 1,478.4 | 1 | 1 | 47.100 | 74.298 | 74.300 | -0.002 | E350A | 7.85 x t |
| 2m272 | ISMC150 |  | 9,088.0 | 1 | 1 | 16.800 | 152.678 | 149.480 | 3.198 | E250A | IS 808 table |
| 2m273 | ISA75X75X8 |  | 9,088.0 | 1 | 1 | 8.900 | 80.883 | 81.180 | -0.297 | E250A | IS 808 table |
| 2p205 | PL8 | 50.0 | 400.3 | 18 | 1 | 62.800 | 22.625 | 22.620 | 0.005 | E350A | 7.85 x t |
| 2p206 | PL8 | 50.0 | 738.6 | 18 | 1 | 62.800 | 41.746 | 41.730 | 0.016 | E350A | 7.85 x t |
| 2p207 | PL8 | 50.0 | 451.3 | 18 | 1 | 62.800 | 25.507 | 25.510 | -0.003 | E350A | 7.85 x t |
| 2p208 | PL6 | 1,478.0 | 2,000.0 | 4 | 1 | 47.100 | 556.910 | 557.070 | -0.160 | E350A | 7.85 x t |
| 2p209 | PL6 | 75.0 | 1,412.4 | 5 | 1 | 47.100 | 24.947 | 24.950 | -0.003 | E350A | 7.85 x t |

BOQ totals: calculated 979.595 kg, drawing 976.840 kg, difference +2.755 kg

## Inventory

Total steel (BOM gross × assembly qty): **976.84 kg**; paint area 39.16 m²

| plate | grade | pieces | area m² | kg | sources |
|---|---|---|---|---|---|
| PL6 | E350A | 10 | 13.931 | 656.32 | 2GU1, 2p208, 2p209 |
| PL8 | E350A | 54 | 1.431 | 89.86 | 2p205, 2p206, 2p207 |

| profile | family | grade | pieces | length m | kg | sources |
|---|---|---|---|---|---|---|
| ISA75X75X8 | angle | E250A | 1 | 9.088 | 81.18 | 2m273 |
| ISMC150 | channel | E250A | 1 | 9.088 | 149.48 | 2m272 |

### Welds (model-read estimate, unverified)

| parts | size mm | edge | sides | count | tack | total m | metal kg | evidence |
|---|---|---|---|---|---|---|---|---|
| 2m273 → 2p208 | 5 | length | 1 | 1 | False | 9.088 | 0.892 | Longitudinal view G3-G4: CONT. 5 weld callout at 2m273. |
| 2m272 → 2p208 | 5 | length | 2 | 1 | False | 18.176 | 1.784 | Longitudinal view J4-J5: CONT. 5/5 weld callout at 2m272. |
| 2p205 → 2p208 | 5 | length | 2 | 18 | False | 14.411 | 1.414 | Section A-A, K-L: TYP. 5/5 weld callouts at 2p205; quantity from BOM. |
| 2p206 → 2p208 | 5 | length | 2 | 18 | False | 26.590 | 2.609 | Section A-A, L3-L4: TYP. 5/5 weld callout at 2p206; quantity from BOM. |
| 2p207 → 2p208 | 5 | length | 2 | 18 | False | 16.247 | 1.594 | Section A-A, L4-L5: TYP. 5/5 weld callout at 2p207; quantity from BOM. |
| 2p209 → 2p208 | 5 | perimeter | 1 | 5 | False | 14.874 | 1.460 | Longitudinal view H20 / tile 3 H: '3 SIDES TYP.' with 5 mm weld callout at 2p209; quantity from BOM. |

Weld metal 9.750 kg, electrode 16.250 kg

### Inventory checks

| level | check | message |
|---|---|---|
| pass | boq.drawing_weight | BOQ total drawing weight 976.84 kg; BOM gross total 976.84 kg. |
| pass | boq.calculated | BOQ calculated 979.59 kg vs drawing 976.84 kg (+2.75 kg). |
| pass | inventory.unclassified | Every BOM member is classified. |
| pass | inventory.welds | 6 weld runs accepted |
| warn | inventory.weld_estimate | Weld metal 9.75 kg (1.00% of steel; fabricated steel is typically 1-2%) is a model-read estimate, unverified: topology read by OpenAI, lengths computed from the BOM, tack welds excluded. |
| pass | inventory.weight | Plates + sections = 976.84 kg; BOM gross total = 976.84 kg. |
| pass | inventory.paint | Paint area 39.16 m² (BOM total); Σ row area × qty = 39.06 m². |

## Q&A

See [qa.md](qa.md).
