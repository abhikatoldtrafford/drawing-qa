# TST-SFD-46-01-01-07-000-09970

- **Source file:** `TST-SFD-46-01-01-07-000-09970_20260808171139762.pdf` (page 1)
- **Title:** SHED FOR POCIL PLOT LOT-4 / DETAIL OF DOWN COMER MKD AS -4DC3
- **Project / department / area:**  / DESIGN & ENGINEERING-STRUCTURAL / HOT ROLLED PICKLING GALVANIZED LINE (HRPGL)
- **Rev / sheet / size:** 0 / 1 OF 1 / A1
- **Drawn / checked / approved:** IRCON 27.02.2026 / SKS/NBT 27.02.2026 / SSA 27.02.2026
- **Title-block weight:** 432.62 kg
- **Assembly:** 4DC3 × 1 (DOWN COMER)
- **Erection locations:** 4DC3 @ 5/<LEG-1 EL. +4.475
- **Run time:** 72 s; OpenAI model: gpt-5.4-mini (sections) + gpt-5.5 (welds); usage: {'gpt-5.4-mini:input': 18370, 'gpt-5.4-mini:output': 496, 'gpt-5.4-mini:cached': 18048, 'gpt-5.4-mini:calls': 1, 'gpt-5.5:input': 18370, 'gpt-5.5:output': 4287, 'gpt-5.5:calls': 1}

## Checks (PyMuPDF guardrails)

| level | check | message |
|---|---|---|
| pass | bom.row_arith | All 11 rows: qty × pc wt = gross (± rounding). |
| pass | bom.gross_total | Σ part gross × assembly qty 1 = 432.62; grand total = 432.62. |
| pass | bom.assembly_row | Assembly row 4DC3 gross 432.62 vs grand total 432.62. |
| pass | bom.net_total | Σ part net = 425.12 (× qty 1 = 425.12); net total = 425.11. Tekla net totals often differ; informational. |
| pass | bom.crosscheck | find_tables() second parse agrees on every row (section, length, qty, gross, material). |
| pass | marks.bom_on_sheet | Every BOM mark appears on the drawing. |
| pass | marks.extra | Marks on sheet not in BOM (connected/referenced assemblies): ['4PSB2', '4PSB5', '4PSB6'] |
| pass | title.weight | Title block weight 432.62 vs BOM gross 432.62. |
| pass | mark_location.assembly | Mark box ['4DC3'] vs BOM assembly '4DC3'. |
| pass | mark_location.count | 1 erection location(s) listed; assembly qty 1. |
| pass | abstract.total | Σ abstract = 432.62; abstract total = 432.62; BOM gross = 432.62. |
| pass | abstract.by_section | Every abstract row equals the BOM gross for that section/plate thickness. |
| pass | title.drawing_no | Drawing no. TST-SFD-46-01-01-07-000-09970 matches file name. |

## Bill of materials

| mark | section | length mm | qty | pc wt | gross kg | grade |
|---|---|---|---|---|---|---|
| 4DC3 | PIPE508*6 | 2,234 | 1 | 155.47 | 155.47 | YST 240 |
| 4m665 | PIPE508*6 | 2,055 | 1 | 132.45 | 132.45 | YST 240 |
| 4m666 | PIPE508*6 | 1,184 | 1 | 77.82 | 77.82 | YST 240 |
| 4m706 | PIPE219.1*5.4 | 325 | 1 | 9.18 | 9.18 | YST 240 |
| 4m707 | ROD20 | 301 | 1 | 0.74 | 0.74 | E250A |
| 4p637 | PL10*150 | 832 | 2 | 9.80 | 19.61 | E350A |
| 4p638 | PL6*50 | 807 | 2 | 1.90 | 3.80 | E350A |
| 4p639 | PL8*94 | 150 | 4 | 0.89 | 3.55 | E350A |
| 4p640 | PL8*155 | 173 | 4 | 1.68 | 6.72 | E350A |
| 4p641 | PL8*83 | 150 | 4 | 0.78 | 3.13 | E350A |
| 4p660 | PL10*358 | 358 | 2 | 10.08 | 20.15 | E350A |

Totals: net 425.11 kg, gross 432.62 kg, surface 9.71 m²

## Fabrication BOQ

| item | section | width | length | qty | fab | unit wt | calc kg | drg kg | diff kg | grade | unit wt source |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 4DC3 | PIPE508*6 |  | 2,233.9 | 1 | 1 | 74.280 | 165.934 | 155.470 | 10.464 | YST 240 | computed (pi (OD-t) t x 7850) |
| 4m665 | PIPE508*6 |  | 2,054.9 | 1 | 1 | 74.280 | 152.638 | 132.450 | 20.188 | YST 240 | computed (pi (OD-t) t x 7850) |
| 4m666 | PIPE508*6 |  | 1,184.2 | 1 | 1 | 74.280 | 87.962 | 77.820 | 10.142 | YST 240 | computed (pi (OD-t) t x 7850) |
| 4m706 | PIPE219.1*5.4 |  | 325.3 | 1 | 1 | 28.459 | 9.258 | 9.180 | 0.078 | YST 240 | computed (pi (OD-t) t x 7850) |
| 4m707 | ROD20 |  | 301.4 | 1 | 1 | 2.470 | 0.744 | 0.740 | 0.004 | E250A | IS 808 table |
| 4p637 | PL10 | 150.0 | 832.5 | 2 | 1 | 78.500 | 19.605 | 19.610 | -0.005 | E350A | 7.85 x t |
| 4p638 | PL6 | 50.0 | 807.4 | 2 | 1 | 47.100 | 3.803 | 3.800 | 0.003 | E350A | 7.85 x t |
| 4p639 | PL8 | 94.0 | 150.0 | 4 | 1 | 62.800 | 3.542 | 3.550 | -0.008 | E350A | 7.85 x t |
| 4p640 | PL8 | 155.0 | 173.0 | 4 | 1 | 62.800 | 6.736 | 6.720 | 0.016 | E350A | 7.85 x t |
| 4p641 | PL8 | 83.0 | 150.0 | 4 | 1 | 62.800 | 3.127 | 3.130 | -0.003 | E350A | 7.85 x t |
| 4p660 | PL10 | 358.0 | 358.3 | 2 | 1 | 78.500 | 20.139 | 20.150 | -0.011 | E350A | 7.85 x t |

BOQ totals: calculated 473.489 kg, drawing 432.620 kg, difference +40.869 kg

## Inventory

Total steel (BOM gross × assembly qty): **432.62 kg**; paint area 9.71 m²

| plate | grade | pieces | area m² | kg | sources |
|---|---|---|---|---|---|
| PL6 | E350A | 2 | 0.081 | 3.80 | 4p638 |
| PL8 | E350A | 12 | 0.213 | 13.40 | 4p639, 4p640, 4p641 |
| PL10 | E350A | 4 | 0.506 | 39.76 | 4p637, 4p660 |

| profile | family | grade | pieces | length m | kg | sources |
|---|---|---|---|---|---|---|
| PIPE219.1*5.4 | pipe | YST 240 | 1 | 0.325 | 9.18 | 4m706 |
| PIPE508*6 | pipe | YST 240 | 3 | 5.473 | 365.74 | 4DC3, 4m665, 4m666 |
| ROD20 | round | E250A | 1 | 0.301 | 0.74 | 4m707 |

| item | dia | length | type | grade | qty | assemblies |
|---|---|---|---|---|---|---|
| bolt | 16 | 60 | HEX | 8.8XOX | 18 | 4PSB2, 4PSB5, 4PSB6 |
| nut | 16 |  |  | 8.8XOX | 26 | 4PSB2, 4PSB5, 4PSB6 |
| plain washer | 18 |  | FLAT-E |  | 18 | 4PSB2, 4PSB5, 4PSB6 |

### Welds (model-read estimate, unverified)

| parts | size mm | edge | sides | count | tack | total m | metal kg | evidence |
|---|---|---|---|---|---|---|---|---|
| 4p638 → 4p637 | 6 | length | 1 | 2 | False | 1.615 | 0.228 | Top collar detail / section A-A, grid B4-C8: 6 TYP weld symbol at 4p638/4p637 collar plates. |
| 4p640 → 4DC3 | 6 | perimeter | 1 | 4 | False | 2.624 | 0.371 | Bracket arrangement and section B-B, grid E4-F9: 6 TYP weld symbols at 4p640 pads on 4DC3. |
| 4p639 → 4p640 | 6 | width | 2 | 4 | False | 0.752 | 0.106 | Bracket detail, grid E4-E9 and section B-B: weld symbol shows 6 both sides / TYP at 4p639 lug to bracket pad. |
| 4p641 → 4p640 | 6 | length | 2 | 4 | False | 1.200 | 0.170 | Bracket detail and section B-B, grid E4-F9: 6 TYP / both-side weld indication at 4p641 with 4p640. |
| 4m706 → 4m665 | 6 | circumference | 1 | 1 | False | 0.688 | 0.097 | Section C-C, grid H8: 6 TYP weld symbol around 4m706 pipe connection to 4m665. |
| 4p660 → 4m706 | 6 | circumference | 1 | 2 | False | 1.377 | 0.195 | Section D-D, grid J8-K8: 6 TYP weld symbol at 4p660 circular plates on 4m706. |
| 4m707 → 4m706 | 6 | circumference | 1 | 2 | False | 0.126 | 0.018 | Nozzle/rod detail, grid F2-G3: 4m707 CTR'D with 6 TYP weld symbol at rod attachment. |
| 4m665 → 4DC3 | 6 | circumference | 1 | 1 | False | 1.596 | 0.226 | Main assembly view, grid G6-H8: TYP weld symbol at pipe-to-pipe joint; general note gives 6 mm U.N.O. |
| 4m666 → 4m665 | 6 | circumference | 1 | 1 | False | 1.596 | 0.226 | Main assembly view, grid J6-J8: TYP weld symbol at mitred pipe joint; general note gives 6 mm U.N.O. |

Weld metal 1.640 kg, electrode 2.730 kg

### Inventory checks

| level | check | message |
|---|---|---|
| pass | boq.drawing_weight | BOQ total drawing weight 432.62 kg; BOM gross total 432.62 kg. |
| warn | boq.calculated | BOQ calculated 473.49 kg vs drawing 432.62 kg (+40.87 kg). Rows off by >5%: ['4DC3 PIPE508*6: +10.46 kg', '4m665 PIPE508*6: +20.19 kg', '4m666 PIPE508*6: +10.14 kg']. |
| pass | inventory.unclassified | Every BOM member is classified. |
| pass | inventory.welds | 9 weld runs accepted |
| warn | inventory.weld_estimate | Weld metal 1.64 kg (0.38% of steel; fabricated steel is typically 1-2%) is a model-read estimate, unverified: topology read by OpenAI, lengths computed from the BOM, tack welds excluded. |
| pass | inventory.weight | Plates + sections = 432.62 kg; BOM gross total = 432.62 kg. |
| pass | inventory.paint | Paint area 9.71 m² (BOM total); Σ row area × qty = 9.70 m². |
| warn | inventory.taper_qty | Taper washers listed without a quantity for ['4PSB2', '4PSB5', '4PSB6']; not counted. |

## Q&A

See [qa.md](qa.md).
