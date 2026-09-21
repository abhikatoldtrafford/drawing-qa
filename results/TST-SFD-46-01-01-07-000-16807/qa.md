# Q&A — TST-SFD-46-01-01-07-000-16807

Asked in one conversation (each question sees the earlier turns). The model gets the full sheet (grid-tagged text layer + tiles + validated extract) and can call query_bom / search_text / zoom.

## Q1. What does this drawing fabricate, how many assemblies, where are they erected (grid and level), and what is the total weight?

*Tools used:* none

This drawing fabricates **one gutter assembly** marked **2GU1**.

- **Assembly count:** 1 assembly, per BOM/abstract and title block
  - BOM erection mark: **2GU1** at **A21–A22**
  - Abstract total: **976.84 kg** at **A17–A18**
  - Title block weight: **976.84 kg** at **R23**

- **Where erected:**
  - **Grid location:** **14-15/<LEG-1**
  - **Level:** **EL. +17.115**
  - Evidence: mark location box at **A2** and the sheet’s mark location entry

- **What it fabricates:**
  - Title/description: **DETAIL OF GUTTER MKD AS -2GU1**
  - Drawing title block at **R23**
  - Also noted in the view as **ONE-GUTTER MARKED AS 2GU1** at **M4**

- **Total weight:** **976.84 kg**

So, in short: **1 gutter assembly (2GU1), erected at grid 14-15/<LEG-1, level EL. +17.115, total weight 976.84 kg.**

## Q2. Which BOM part is the heaviest, what is its section and size, and where is it shown on the sheet?

*Tools used:* query_bom(), search_text(2p208)

The heaviest BOM part is **2p208**.

- **Section / size:** **PL6*1478**
- **Length:** **2000.0 mm**
- **Quantity:** **4**
- **Weight:** **557.07 kg** gross, which is the largest part weight in the BOM  
  Evidence: BOM row in **A21–A22** and inventory/BOM JSON.

**Where it is shown on the sheet:**
- **B19** in the BOM list
- **E17** as the detail view: **MARK. NO:- 2p208 / PL6*1478 * 2000**
- **D18** in the side/detail drawing
- Also called out in section/view **H-H** at **H11, H7, H3, H15** and in **A-A / B-B** related callouts, with the main part detail clearly at **E17**

So: **2p208, PL6*1478, 2000 mm long, 4 pieces, 557.07 kg, shown mainly at E17 and listed at B19.**

## Q3. List every plate thickness used and the parts that use each one.

*Tools used:* none

The sheet uses **two plate thicknesses**:

### 1) **PL 6 THK** / **PL6**
Parts using 6 mm plate:
- **2GU1** — **PL6*1067**  
  Evidence: BOM **A21–A22**, detail at **D7**
- **2p208** — **PL6*1478**  
  Evidence: BOM **A21–A22**, detail at **E17**
- **2p209** — **PL6*75**  
  Evidence: BOM **A21–A22**, detail at **D15**

### 2) **PL 8 THK** / **PLT8*50**
Parts using 8 mm plate:
- **2p205** — **PLT8*50**  
  Evidence: BOM **A21–A22**, detail at **C9**
- **2p206** — **PLT8*50**  
  Evidence: BOM **A21–A22**, detail at **B9**
- **2p207** — **PLT8*50**  
  Evidence: BOM **A21–A22**, detail at **C9**

So, by abstract:
- **6 mm plates:** 2GU1, 2p208, 2p209
- **8 mm plates:** 2p205, 2p206, 2p207

## Q4. What bolts, nuts and washers are needed, and which assemblies do they connect?

*Tools used:* none

This sheet does **not** list any actual bolt/nut/washer sizes or quantities in the visible text layer/BOM. The **“List of Permanent Bolts”** table is present in the title block area (**Q16–Q22 / H16–R24**), but its cells are blank in the parsed text.

What the sheet **does** say:
- **Notes at R7**: “**ALL PERMANENT BOLTS ARE FULL THREADED.**”
- **Notes at R7**: “**ERECTION BOLT/‘C’ CLAMP/‘L’ CLAMP AS APPLICABLE SHALL BE USED DURING STRUCTURAL ASSEMBLY IN FABRICATION SHOP.**”

So, based on this sheet alone:
- **Bolts:** not specified
- **Nuts:** not specified
- **Washers:** not specified
- **Which assemblies they connect:** not explicitly given in the bolt table on this sheet

If you want, I can also inspect the connection views and tell you **which parts are welded/connected at each joint** from the drawing views.
