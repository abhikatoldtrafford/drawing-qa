# Q&A — TST-SFD-46-01-01-07-000-09970

Asked in one conversation (each question sees the earlier turns). The model gets the full sheet (grid-tagged text layer + tiles + validated extract) and can call query_bom / search_text / zoom.

## Q1. What does this drawing fabricate, how many assemblies, where are they erected (grid and level), and what is the total weight?

*Tools used:* none

This drawing fabricates a **down comer**, specifically **“DETAIL OF DOWN COMER MKD AS -4DC3”** in the title block and note area ([M16], [L2]).

- **Assembly mark:** **4DC3**  
- **Assembly quantity:** **1** assembly, from the BOM assembly row ([B11] / extract BOM)

**Erection location:**
- **Grid location:** **5/<LEG-1** ([A1])
- **Level:** **EL. +4.475** ([A2])

**Total weight:**
- **432.62 kg** total weight, shown in the title block and BOM grand total ([M16], [B10], [C13]/[C15])

So, in short: **1 down comer assembly (4DC3), erected at grid 5/<LEG-1, level EL. +4.475, total weight 432.62 kg.**

## Q2. Which BOM part is the heaviest, what is its section and size, and where is it shown on the sheet?

*Tools used:* query_bom(), search_text(MARK. NO:- 4DC3), search_text(PIPE508*6 * 2234)

The **heaviest BOM part** is **item 4DC3**.

- **Section:** `PIPE508*6`
- **Size / length:** `2233.9 mm` in the BOM, shown as `PIPE508*6 * 2234` on the detail view due to rounding ([BOM row 4DC3], [H12])

**Where shown on the sheet:**
- **BOM table:** item `4DC3` in the Bill of Materials ([B11]/[B12])
- **Detail view:** `MARK. NO:- 4DC3` at **H12** ([H12])
- It is also the main assembly member shown in the central drawing view ([from the drawing view], around the large vertical member)

**Weight:** `155.47 kg` (pc wt / gross wt for that part in the BOM row).

## Q3. List every plate thickness used and the parts that use each one.

*Tools used:* none

Plate thicknesses used on this sheet are:

- **6 mm**
  - Part: **4p638**
  - Section: `PL6*50`
  - BOM qty: **2**
  - Appears in the detail view at **F12** and on section/detail views around **B4/B8** ([BOM], [F12], [B4]/[B8])

- **8 mm**
  - Parts: **4p639, 4p640, 4p641**
  - Sections:
    - **4p639** → `PL8*94`
    - **4p640** → `PL8*155`
    - **4p641** → `PL8*83`
  - BOM qtys:
    - **4p639** qty **4**
    - **4p640** qty **4**
    - **4p641** qty **4**
  - These appear in the bracket/detail views and sections **E14, F14, G11** and related callouts ([E14], [F14], [G11])

- **10 mm**
  - Parts: **4p637, 4p660**
  - Sections:
    - **4p637** → `PL10*150`
    - **4p660** → `PL10*358`
  - BOM qtys:
    - **4p637** qty **2**
    - **4p660** qty **2**
  - These appear in the top collar and circular plate details at **H14** and **E15** ([H14], [E15])

If you want, I can also group them by **part mark + dimensions + quantity + weight** in a compact table.

## Q4. What bolts, nuts and washers are needed, and which assemblies do they connect?

*Tools used:* none

The sheet’s **List of Permanent Bolts** gives these fasteners, and the connected assemblies are the ones listed in the inventory / bolt table context on the sheet:

### 1) Assembly mark **(blank on sheet)** / main 4DC3 connection set
This is the top row in **K13–K15**.

- **Bolts:** `16` dia, `HEX`, `60` long, **qty 10**
- **Nuts:** `16` dia, **qty 10**
- **Plain washers:** `18` dia, `FLAT-E`, **qty 10**
- **Taper washers:** not shown with a quantity in the table row, so I won’t assign one

### 2) **4PSB2**
- **Bolts:** `16` dia, `HEX`, `60` long, **qty 4**
- **Nuts:** `16` dia, **qty 8**
- **Plain washers:** `18` dia, `FLAT-E`, **qty 4**
- **Taper washers:** `16` dia, type `C`
- **Connects assembly:** **4PSB2** ([K13–K15], and the assembly mark appears at [K9])

### 3) **4PSB5**
- **Bolts:** `16` dia, `HEX`, `60` long, **qty 2**
- **Nuts:** `16` dia, **qty 4**
- **Plain washers:** `18` dia, `FLAT-E`, **qty 2**
- **Taper washers:** `16` dia, type `C`
- **Connects assembly:** **4PSB5** ([L9–L15])

### 4) **4PSB6**
- **Bolts:** `16` dia, `HEX`, `60` long, **qty 2**
- **Nuts:** `16` dia, **qty 4**
- **Plain washers:** `18` dia, `FLAT-E`, **qty 2**
- **Taper washers:** `16` dia, type `C`
- **Connects assembly:** **4PSB6** ([L9–L15])

### Totals from the table
- **Bolts:** 10 + 4 + 2 + 2 = **18**
- **Nuts:** 10 + 8 + 4 + 4 = **26**
- **Plain washers:** 10 + 4 + 2 + 2 = **18**

Note: the table also shows **taper washers for beam & channel**, but the quantity cells are blank in the visible sheet, so I’m not counting a total for them.
