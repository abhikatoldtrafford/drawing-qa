# TST-SFD-46-01-01-07-000-14278

- **Source file:** `TST-SFD-46-01-01-07-000-14278(UPDATED).pdf` (page 1)
- **Title:** PROCESS BAY : POT AREA WITH EXIT ECR LOT-3 / DETAIL OF COLUMN MKD AS -3C1
- **Project / department / area:** CRC WEST TARAPUR, HRPGL / DESIGN & ENGINEERING-STRUCTURAL / HOT ROLLED PICKLING GALVANIZING LINE (HRPGL)
- **Rev / sheet / size:** 1 / 1 OF 1 / A0
- **Drawn / checked / approved:** IRCON 01.06.2026 / TML/NBT 01.06.2026 / SSA 01.06.2026
- **Title-block weight:** 33,496.76 kg
- **Assembly:** 3C1 × 1 (COLUMN)
- **Erection locations:** 3C1 @ 37a-39a/LA EL. +9.675
- **Run time:** 43 s; OpenAI model: gpt-5.4-mini; usage: {'gpt-5.4-mini:input': 30272, 'gpt-5.4-mini:output': 919, 'gpt-5.4-mini:cached': 29824, 'gpt-5.4-mini:calls': 1}

## Checks (PyMuPDF guardrails)

| level | check | message |
|---|---|---|
| pass | bom.row_arith | All 43 rows: qty × pc wt = gross (± rounding). |
| pass | bom.gross_total | Σ part gross × assembly qty 1 = 33496.76; grand total = 33496.76. |
| pass | bom.assembly_row | Assembly row 3C1 gross 33496.76 vs grand total 33496.76. |
| pass | bom.net_total | Σ part net = 31174.66 (× qty 1 = 31174.66); net total = 31196.03. Tekla net totals often differ; informational. |
| pass | bom.crosscheck | find_tables() second parse agrees on every row (section, length, qty, gross, material). |
| pass | marks.bom_on_sheet | Every BOM mark appears on the drawing. |
| pass | title.weight | Title block weight 33496.76 vs BOM gross 33496.76. |
| pass | mark_location.assembly | Mark box ['3C1'] vs BOM assembly '3C1'. |
| pass | mark_location.count | 1 erection location(s) listed; assembly qty 1. |
| pass | abstract.total | Σ abstract = 33496.76; abstract total = 33496.76; BOM gross = 33496.76. |
| pass | abstract.by_section | Every abstract row equals the BOM gross for that section/plate thickness. |
| pass | title.drawing_no | Drawing no. TST-SFD-46-01-01-07-000-14278 matches file name. |

## Bill of materials

| mark | section | length mm | qty | pc wt | gross kg | grade |
|---|---|---|---|---|---|---|
| 3C1 | WH1200X500X50X32 | 8,726 | 1 | 5,836.46 | 5,836.46 | E350BR(UT) |
| 3m470 | WH1200X500X50X32 | 8,726 | 1 | 5,836.46 | 5,836.46 | E350BR(UT) |
| 3m481 | T 300X250X25X20 | 1,950 | 8 | 179.86 | 1,438.91 | E350BR |
| 3m482 | T 300X250X25X20 | 1,625 | 2 | 149.92 | 299.84 | E350BR |
| 3m483 | T 300X250X25X20 | 2,503 | 6 | 230.89 | 1,385.34 | E350BR |
| 3m500 | ISMC300 | 600 | 2 | 21.81 | 43.61 | E250A |
| 3m766 | ISMC150 | 1,380 | 6 | 23.07 | 138.43 | E250A |
| 3p262 | PL50*1850 | 1,996 | 4 | 1,449.71 | 5,798.83 | E350BR(UT) |
| 3p263 | PL25*596 | 907 | 4 | 106.09 | 424.35 | E350BR |
| 3p264 | PL63*1600 | 1,850 | 2 | 1,463.87 | 2,927.74 | E350BR(UT) |
| 3p265 | PL50*198 | 1,200 | 2 | 93.26 | 186.52 | E350BR(UT) |
| 3p266 | PL50*198 | 573 | 4 | 44.53 | 178.12 | E350BR(UT) |
| 3p267 | PL25*348 | 596 | 32 | 40.70 | 1,302.52 | E350BR |
| 3p268 | PL25*160 | 160 | 8 | 5.02 | 40.19 | E350BR |
| 3p269 | PL40*290 | 290 | 16 | 26.41 | 422.52 | E350BR(UT) |
| 3p270 | PL80*350 | 350 | 16 | 76.93 | 1,230.88 | E350BR(UT) |
| 3p271 | PL16*273 | 360 | 2 | 12.34 | 24.69 | E350A |
| 3p272 | PL25*827 | 1,352 | 2 | 219.61 | 439.22 | E350BR |
| 3p273 | PL25*704 | 1,650 | 2 | 228.17 | 456.34 | E350BR |
| 3p274 | PL25*638 | 1,736 | 2 | 217.36 | 434.71 | E350BR |
| 3p293 | PL32*1096 | 1,996 | 2 | 549.67 | 1,099.33 | E350BR |
| 3p294 | PL25*907 | 1,096 | 4 | 195.09 | 780.35 | E350BR |
| 3p295 | PL32*500 | 1,200 | 2 | 150.72 | 301.44 | E350BR |
| 3p305 | PL25*573 | 589 | 8 | 66.24 | 529.94 | E350BR |
| 3p306 | PL25*600 | 1,698 | 4 | 199.86 | 799.43 | E350BR |
| 3p424 | PL16*200 | 390 | 1 | 9.80 | 9.80 | E350A |
| 3p425 | PL16*230 | 443 | 2 | 12.80 | 25.59 | E350A |
| 3p426 | PL10*200 | 443 | 2 | 6.96 | 13.91 | E350A |
| 3p427 | PL16*200 | 259 | 2 | 6.51 | 13.01 | E350A |
| 3p428 | PL8*259 | 384 | 2 | 6.25 | 12.49 | E350A |
| 3p430 | PL16*200 | 390 | 1 | 9.80 | 9.80 | E350A |
| 3p435 | PL12*145 | 200 | 1 | 2.73 | 2.73 | E350A |
| 3p463 | PL10*200 | 471 | 2 | 7.39 | 14.79 | E350A |
| 3p464 | PL25*250 | 259 | 2 | 12.71 | 25.41 | E350BR |
| 3p465 | PL16*259 | 375 | 2 | 12.20 | 24.40 | E350A |
| 3p467 | PL25*250 | 385 | 1 | 18.89 | 18.89 | E350BR |
| 3p469 | PL25*280 | 471 | 2 | 25.88 | 51.76 | E350BR |
| 3p471 | PL25*250 | 385 | 1 | 18.89 | 18.89 | E350BR |
| 3p516 | PL20*805 | 932 | 2 | 117.79 | 235.58 | E350A |
| 3p556 | PL25*234 | 1,100 | 8 | 50.51 | 404.12 | E350BR |
| 3p567 | PL12*200 | 631 | 8 | 11.89 | 95.10 | E350A |
| 3p569 | PL16*260 | 629 | 7 | 20.54 | 143.78 | E350A |
| 3p612 | PL16*260 | 629 | 1 | 20.54 | 20.54 | E350A |

Totals: net 31,196.03 kg, gross 33,496.76 kg, surface 243.73 m²

## Fabrication BOQ

| item | section | width | length | qty | fab | unit wt | calc kg | drg kg | diff kg | grade | unit wt source |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3C1 flange | PL50 | 500.0 | 8,726.5 | 2 | 1 | 392.500 | 3,425.151 | 3,425.153 | -0.001 | E350BR(UT) | 7.85 x t |
| 3C1 web | PL32 | 1,100.0 | 8,726.5 | 1 | 1 | 251.200 | 2,411.306 | 2,411.307 | -0.001 | E350BR(UT) | 7.85 x t |
| 3m470 flange | PL50 | 500.0 | 8,726.5 | 2 | 1 | 392.500 | 3,425.151 | 3,425.153 | -0.001 | E350BR(UT) | 7.85 x t |
| 3m470 web | PL32 | 1,100.0 | 8,726.5 | 1 | 1 | 251.200 | 2,411.306 | 2,411.307 | -0.001 | E350BR(UT) | 7.85 x t |
| 3m481 flange | PL25 | 250.0 | 1,950.0 | 8 | 1 | 196.250 | 765.375 | 765.378 | -0.003 | E350BR | 7.85 x t |
| 3m481 web | PL20 | 275.0 | 1,950.0 | 8 | 1 | 157.000 | 673.530 | 673.532 | -0.002 | E350BR | 7.85 x t |
| 3m482 flange | PL25 | 250.0 | 1,625.4 | 2 | 1 | 196.250 | 159.492 | 159.489 | 0.003 | E350BR | 7.85 x t |
| 3m482 web | PL20 | 275.0 | 1,625.4 | 2 | 1 | 157.000 | 140.353 | 140.351 | 0.003 | E350BR | 7.85 x t |
| 3m483 flange | PL25 | 250.0 | 2,503.2 | 6 | 1 | 196.250 | 736.879 | 736.883 | -0.003 | E350BR | 7.85 x t |
| 3m483 web | PL20 | 275.0 | 2,503.2 | 6 | 1 | 157.000 | 648.454 | 648.457 | -0.003 | E350BR | 7.85 x t |
| 3m500 | ISMC300 |  | 600.0 | 2 | 1 | 36.300 | 43.560 | 43.610 | -0.050 | E250A | IS 808 table |
| 3m766 | ISMC150 |  | 1,379.9 | 6 | 1 | 16.800 | 139.094 | 138.430 | 0.664 | E250A | IS 808 table |
| 3p262 | PL50 | 1,850.0 | 1,996.5 | 4 | 1 | 392.500 | 5,798.834 | 5,798.830 | 0.004 | E350BR(UT) | 7.85 x t |
| 3p263 | PL25 | 596.0 | 907.0 | 4 | 1 | 196.250 | 424.349 | 424.350 | -0.001 | E350BR | 7.85 x t |
| 3p264 | PL63 | 1,600.0 | 1,850.0 | 2 | 1 | 494.550 | 2,927.736 | 2,927.740 | -0.004 | E350BR(UT) | 7.85 x t |
| 3p265 | PL50 | 198.0 | 1,200.0 | 2 | 1 | 392.500 | 186.516 | 186.520 | -0.004 | E350BR(UT) | 7.85 x t |
| 3p266 | PL50 | 198.0 | 573.0 | 4 | 1 | 392.500 | 178.123 | 178.120 | 0.003 | E350BR(UT) | 7.85 x t |
| 3p267 | PL25 | 348.0 | 596.0 | 32 | 1 | 196.250 | 1,302.522 | 1,302.520 | 0.002 | E350BR | 7.85 x t |
| 3p268 | PL25 | 160.0 | 160.0 | 8 | 1 | 196.250 | 40.192 | 40.190 | 0.002 | E350BR | 7.85 x t |
| 3p269 | PL40 | 290.0 | 290.0 | 16 | 1 | 314.000 | 422.518 | 422.520 | -0.002 | E350BR(UT) | 7.85 x t |
| 3p270 | PL80 | 350.0 | 350.0 | 16 | 1 | 628.000 | 1,230.880 | 1,230.880 | 0.000 | E350BR(UT) | 7.85 x t |
| 3p271 | PL16 | 273.0 | 360.0 | 2 | 1 | 125.600 | 24.688 | 24.690 | -0.002 | E350A | 7.85 x t |
| 3p272 | PL25 | 827.0 | 1,352.5 | 2 | 1 | 196.250 | 439.018 | 439.220 | -0.202 | E350BR | 7.85 x t |
| 3p273 | PL25 | 704.0 | 1,650.5 | 2 | 1 | 196.250 | 456.066 | 456.340 | -0.274 | E350BR | 7.85 x t |
| 3p274 | PL25 | 638.0 | 1,736.2 | 2 | 1 | 196.250 | 434.771 | 434.710 | 0.061 | E350BR | 7.85 x t |
| 3p293 | PL32 | 1,096.0 | 1,996.5 | 2 | 1 | 251.200 | 1,099.334 | 1,099.330 | 0.004 | E350BR | 7.85 x t |
| 3p294 | PL25 | 907.0 | 1,096.0 | 4 | 1 | 196.250 | 780.347 | 780.350 | -0.003 | E350BR | 7.85 x t |
| 3p295 | PL32 | 500.0 | 1,200.0 | 2 | 1 | 251.200 | 301.440 | 301.440 | 0.000 | E350BR | 7.85 x t |
| 3p305 | PL25 | 573.0 | 589.1 | 8 | 1 | 196.250 | 529.960 | 529.940 | 0.020 | E350BR | 7.85 x t |
| 3p306 | PL25 | 600.0 | 1,698.2 | 4 | 1 | 196.250 | 799.852 | 799.430 | 0.422 | E350BR | 7.85 x t |
| 3p424 | PL16 | 200.0 | 390.0 | 1 | 1 | 125.600 | 9.797 | 9.800 | -0.003 | E350A | 7.85 x t |
| 3p425 | PL16 | 230.0 | 443.0 | 2 | 1 | 125.600 | 25.595 | 25.590 | 0.005 | E350A | 7.85 x t |
| 3p426 | PL10 | 200.0 | 443.0 | 2 | 1 | 78.500 | 13.910 | 13.910 | 0.000 | E350A | 7.85 x t |
| 3p427 | PL16 | 200.0 | 259.0 | 2 | 1 | 125.600 | 13.012 | 13.010 | 0.002 | E350A | 7.85 x t |
| 3p428 | PL8 | 259.0 | 384.0 | 2 | 1 | 62.800 | 12.492 | 12.490 | 0.002 | E350A | 7.85 x t |
| 3p430 | PL16 | 200.0 | 390.0 | 1 | 1 | 125.600 | 9.797 | 9.800 | -0.003 | E350A | 7.85 x t |
| 3p435 | PL12 | 145.0 | 200.0 | 1 | 1 | 94.200 | 2.732 | 2.730 | 0.002 | E350A | 7.85 x t |
| 3p463 | PL10 | 200.0 | 471.0 | 2 | 1 | 78.500 | 14.789 | 14.790 | -0.001 | E350A | 7.85 x t |
| 3p464 | PL25 | 250.0 | 259.0 | 2 | 1 | 196.250 | 25.414 | 25.410 | 0.004 | E350BR | 7.85 x t |
| 3p465 | PL16 | 259.0 | 375.0 | 2 | 1 | 125.600 | 24.398 | 24.400 | -0.002 | E350A | 7.85 x t |
| 3p467 | PL25 | 250.0 | 385.0 | 1 | 1 | 196.250 | 18.889 | 18.890 | -0.001 | E350BR | 7.85 x t |
| 3p469 | PL25 | 280.0 | 471.0 | 2 | 1 | 196.250 | 51.763 | 51.760 | 0.003 | E350BR | 7.85 x t |
| 3p471 | PL25 | 250.0 | 385.0 | 1 | 1 | 196.250 | 18.889 | 18.890 | -0.001 | E350BR | 7.85 x t |
| 3p516 | PL20 | 805.0 | 932.4 | 2 | 1 | 157.000 | 235.683 | 235.580 | 0.103 | E350A | 7.85 x t |
| 3p556 | PL25 | 234.0 | 1,100.0 | 8 | 1 | 196.250 | 404.118 | 404.120 | -0.002 | E350BR | 7.85 x t |
| 3p567 | PL12 | 200.0 | 631.0 | 8 | 1 | 94.200 | 95.104 | 95.100 | 0.004 | E350A | 7.85 x t |
| 3p569 | PL16 | 260.0 | 629.0 | 7 | 1 | 125.600 | 143.784 | 143.780 | 0.004 | E350A | 7.85 x t |
| 3p612 | PL16 | 260.0 | 629.0 | 1 | 1 | 125.600 | 20.541 | 20.540 | 0.001 | E350A | 7.85 x t |

BOQ totals: calculated 33,497.506 kg, drawing 33,496.760 kg, difference +0.746 kg

## Inventory

Total steel (BOM gross × assembly qty): **33,496.76 kg**; paint area 243.73 m²

| plate | grade | pieces | area m² | kg | sources |
|---|---|---|---|---|---|
| PL8 | E350A | 2 | 0.199 | 12.49 | 3p428 |
| PL10 | E350A | 4 | 0.366 | 28.70 | 3p426, 3p463 |
| PL12 | E350A | 9 | 1.039 | 97.83 | 3p435, 3p567 |
| PL16 | E350A | 18 | 2.163 | 271.61 | 3p271, 3p424, 3p425, 3p427, 3p430, 3p465, 3p569, 3p612 |
| PL20 | E350A | 2 | 1.501 | 235.58 | 3p516 |
| PL20 | E350BR | 16 | 9.314 | 1,462.34 | 3m481 (T 275x20), 3m482 (T 275x20), 3m483 (T 275x20) |
| PL25 | E350BR | 96 | 37.645 | 7,387.87 | 3m481 (T 250x25), 3m482 (T 250x25), 3m483 (T 250x25), 3p263, 3p267, 3p268, 3p272, 3p273, 3p274, 3p294, 3p305, 3p306, 3p464, 3p467, 3p469, 3p471, 3p556 |
| PL32 | E350BR | 4 | 5.576 | 1,400.77 | 3p293, 3p295 |
| PL32 | E350BR(UT) | 2 | 19.198 | 4,822.61 | 3C1 (WH 1100x32), 3m470 (WH 1100x32) |
| PL40 | E350BR(UT) | 16 | 1.346 | 422.52 | 3p269 |
| PL50 | E350BR(UT) | 14 | 33.156 | 13,013.78 | 3C1 (WH 500x50), 3m470 (WH 500x50), 3p262, 3p265, 3p266 |
| PL63 | E350BR(UT) | 2 | 5.920 | 2,927.74 | 3p264 |
| PL80 | E350BR(UT) | 16 | 1.960 | 1,230.88 | 3p270 |

| profile | family | grade | pieces | length m | kg | sources |
|---|---|---|---|---|---|---|
| ISMC150 | channel | E250A | 6 | 8.279 | 138.43 | 3m766 |
| ISMC300 | channel | E250A | 2 | 1.200 | 43.61 | 3m500 |

### Welds (model-read estimate, unverified)

| parts | size mm | edge | sides | count | tack | total m | metal kg | evidence |
|---|---|---|---|---|---|---|---|---|
| 3p435 → 3C1 | 6 | perimeter | 1 | 1 | False | 0.690 | 0.097 | A/B, detail R-R and view near A10 |
| 3m766 → 3C1 | 6 | length | 2 | 2 | False | 5.520 | 0.780 | A/B, view Q-Q and note 2 |
| 3p427 → 3p424 | 6 | length | 1 | 1 | False | 0.259 | 0.037 | A/G, detail S-S and view near F/G |
| 3p428 → 3p425 | 6 | length | 1 | 1 | False | 0.384 | 0.054 | A/G, detail U-U and view near F/G |
| 3p430 → 3p425 | 6 | length | 1 | 1 | False | 0.390 | 0.055 | A/G, detail U-U and view near F/G |
| 3p467 → 3p464 | 6 | perimeter | 1 | 1 | False | 1.270 | 0.179 | H/J, detail X and section around H7-H8 |
| 3p469 → 3p464 | 6 | perimeter | 1 | 1 | False | 1.502 | 0.212 | H/J, detail X and section around H7-H8 |
| 3p463 → 3p464 | 6 | perimeter | 1 | 1 | False | 1.342 | 0.190 | H/J, detail X and section around H7-H8 |
| 3p467 → 3p465 | 6 | length | 1 | 1 | False | 0.385 | 0.054 | H/J, detail X and view around H11-H13 |
| 3p469 → 3p465 | 6 | length | 1 | 1 | False | 0.471 | 0.067 | H/J, detail X and view around H11-H13 |
| 3p463 → 3p465 | 6 | length | 1 | 1 | False | 0.471 | 0.067 | H/J, detail X and view around H11-H13 |
| 3p567 → 3m766 | 6 | length | 1 | 1 | False | 0.631 | 0.089 | C/H, detail N and view H3-H4 |
| 3p556 → 3m766 | 6 | length | 1 | 1 | False | 1.100 | 0.155 | H/J, views H7-H11 |
| 3p471 → 3p556 | 6 | perimeter | 1 | 1 | False | 1.270 | 0.179 | H/H, detail Y and view H7-H11 |
| 3p469 → 3p556 | 6 | length | 1 | 1 | False | 0.471 | 0.067 | H/J, view H7-H11 |
| 3p567 → 3p469 | 6 | length | 1 | 1 | False | 0.631 | 0.089 | H/J, view H7-H11 |
| 3p556 → 3p469 | 6 | length | 1 | 1 | False | 1.100 | 0.155 | H/J, view H7-H11 |
| 3p463 → 3p469 | 6 | length | 1 | 1 | False | 0.471 | 0.067 | H/J, view H7-H11 |

Weld metal 2.590 kg, electrode 4.320 kg

### Inventory checks

| level | check | message |
|---|---|---|
| pass | boq.drawing_weight | BOQ total drawing weight 33496.76 kg; BOM gross total 33496.76 kg. |
| pass | boq.calculated | BOQ calculated 33497.51 kg vs drawing 33496.76 kg (+0.75 kg). |
| pass | inventory.unclassified | Every BOM member is classified. |
| pass | inventory.welds | 18 weld runs accepted |
| warn | inventory.weld_estimate | Weld metal 2.59 kg (0.01% of steel; fabricated steel is typically 1-2%) is a model-read estimate, unverified: topology read by OpenAI, lengths computed from the BOM, tack welds excluded; flange-to-web seams of built-up members are not drawn and not included. |
| pass | inventory.weight | Plates + sections = 33496.76 kg; BOM gross total = 33496.76 kg. |
| pass | inventory.paint | Paint area 243.73 m² (BOM total); Σ row area × qty = 243.65 m². |

## Q&A

See [qa.md](qa.md).
