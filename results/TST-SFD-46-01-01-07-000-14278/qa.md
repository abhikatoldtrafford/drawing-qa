# Q&A — TST-SFD-46-01-01-07-000-14278

Asked in one conversation (each question sees the earlier turns). The model gets the full sheet (grid-tagged text layer + tiles + validated extract) and can call query_bom / search_text / zoom.

## Q1. What does this drawing fabricate, how many assemblies, where are they erected (grid and level), and what is the total weight?

*Tools used:* none

This sheet fabricates **one column assembly marked 3C1** — title block says **“DETAIL OF COLUMN MKD AS -3C1”** and the BOM assembly row is **Erection mark 3C1**, **qty 1**.

- **Assemblies:** 1 assembly
- **Erected at:** **37a-39a/LA**, **EL. +9.675** (mark location table and A2)
- **Total weight:** **33496.76 kg**  
  - title block weight: **33496.76**
  - BOM gross total: **33496.76**
  - abstract total: **33496.76**

Evidence:
- Title block / drawing description: **DETAIL OF COLUMN MKD AS -3C1** (R23)
- Mark location: **3C1**, **37a-39a/LA**, **EL. +9.675** (A1–A2)
- BOM assembly row: **3C1**, **qty 1**, **gross 33496.76 kg** (A21–A22)
- Total weight in title block: **33496.76** (R23)

## Q2. Which BOM part is the heaviest, what is its section and size, and where is it shown on the sheet?

*Tools used:* query_bom()

The **heaviest BOM part** is **3C1** and it is also tied with **3m470** for the same weight.

- **Item / mark:** **3C1**  
- **Section:** **WH1200X500X50X32**  
- **Weight:** **5836.46 kg gross**  
- **Size shown in BOM:** **length 8726.5 mm**  
- **Where shown on the sheet:**  
  - **BOM table** at **A19–A23**  
  - **Main elevation view** at **H/L area**: the large vertical member labeled **3C1** in the column view  
  - Also identified in the title/mark box as the assembly mark **3C1** (A1–A2)

If you want, I can also point out the **heaviest unique part family** after combining duplicates, or the **heaviest plate piece** separately.

## Q3. List every plate thickness used and the parts that use each one.

*Tools used:* none

Here are **every plate thickness used on the sheet** and the **parts that use each thickness** from the BOM/abstract:

- **8 mm**: **3p428**  
  Evidence: BOM row **3p428 – PL8*259** (A19–A22, and plate abstract A17–A18)

- **10 mm**: **3p426, 3p463**  
  Evidence: **3p426 – PL10*200**, **3p463 – PL10*200**

- **12 mm**: **3p435, 3p567**  
  Evidence: **3p435 – PL12*145**, **3p567 – PL12*200**

- **16 mm**: **3p271, 3p424, 3p425, 3p427, 3p430, 3p465, 3p569, 3p612**  
  Evidence:  
  - **3p271 – PL16*273**  
  - **3p424 – PL16*200**  
  - **3p425 – PL16*230**  
  - **3p427 – PL16*200**  
  - **3p430 – PL16*200**  
  - **3p465 – PL16*259**  
  - **3p569 – PL16*260**  
  - **3p612 – PL16*260**

- **20 mm**: **3p516**  
  Evidence: **3p516 – PL20*805**

- **25 mm**: **3m481, 3m482, 3m483, 3p263, 3p267, 3p268, 3p272, 3p273, 3p274, 3p294, 3p305, 3p306, 3p464, 3p467, 3p469, 3p471, 3p556**  
  Evidence: all of these are listed as **PL25** in the BOM.

- **32 mm**: **3p293, 3p295**  
  Evidence: **3p293 – PL32*1096**, **3p295 – PL32*500**

- **40 mm**: **3p269**  
  Evidence: **3p269 – PL40*290**

- **50 mm**: **3C1, 3m470, 3p262, 3p265, 3p266**  
  Evidence:  
  - **3C1 – WH1200X500X50X32**  
  - **3m470 – WH1200X500X50X32**  
  - **3p262 – PL50*1850**  
  - **3p265 – PL50*198**  
  - **3p266 – PL50*198**

- **63 mm**: **3p264**  
  Evidence: **3p264 – PL63*1600**

- **80 mm**: **3p270**  
  Evidence: **3p270 – PL80*350**

If you want, I can also reorganize this as a **thickness-by-thickness table with quantities and total weights**.

## Q4. What bolts, nuts and washers are needed, and which assemblies do they connect?

*Tools used:* none

This sheet does **not list any bolt, nut, or washer items in the “List of Permanent Bolts” table**. The bolt schedule area at **H16–R24** shows only the headings:

- **CONNECTED ASSEMBLY MARK**
- **Dia**
- **Type**
- **Length**
- **Quantity**
- **Specification**
- **Grade**
- **Material**
- **Nut Details**
- **Plain Washer Details**
- **Taper Washer(for beam & channel) Details**

but there are **no filled-in bolt rows** on this sheet.

What is shown instead:
- Connection callouts and weld marks in the views, e.g. **3p262 / 3p263 / 3p264 / 3p265 / 3p266 / 3p267 / 3p268 / 3p269 / 3p270 / 3p271 / 3p272 / 3p293 / 3p294 / 3p295 / 3p305 / 3p306 / 3p424 / 3p425 / 3p426 / 3p427 / 3p428 / 3p430 / 3p435 / 3p463 / 3p464 / 3p465 / 3p467 / 3p469 / 3p471 / 3p516 / 3p556 / 3p567 / 3p569 / 3p612** in the drawing views, but these are **part marks and weld details**, not a populated bolt schedule.

So, **from this sheet alone, I cannot identify any bolt/nut/washer quantities or the exact assemblies they connect**.
