# Q&A — TST-SFD-46-01-01-07-000-16362

Asked in one conversation (each question sees the earlier turns). The model gets the full sheet (grid-tagged text layer + tiles + validated extract) and can call query_bom / search_text / zoom.

## Q1. What does this drawing fabricate, how many assemblies, where are they erected (grid and level), and what is the total weight?

*Tools used:* none

This drawing fabricates a **down comer**, marked **1DC1**.

- **Assembly:** **1DC1**
- **Quantity:** **2 assemblies**  
  Evidence: BOM assembly row in **A14–A16** / **B10–B16** shows erection mark **1DC1** with **qty 2**.

- **Erection locations:**
  - **19-20/<LEG-1** at **EL. +17.065**  
  - **22-23/<LEG-1** at **EL. +17.049**  
  Evidence: mark location table in **A1–A2**.

- **Total weight:** **350.52 kg**  
  Evidence: title block **M16** and BOM total in **B10–B16** both give **350.52**.

So, in short: **Detail of down comer mkd as 1DC1; 2 assemblies; erected at 19-20/<LEG-1 @ EL. +17.065 and 22-23/<LEG-1 @ EL. +17.049; total weight 350.52 kg.**

## Q2. Which BOM part is the heaviest, what is its section and size, and where is it shown on the sheet?

*Tools used:* query_bom(), search_text(MARK. NO:- 1m470), search_text(1m470), search_text(1p374)

The **heaviest BOM part** is **1p374**.

- **Section:** **PL6*800**
- **Size / length:** **1478.4 mm**
- **Weight:** **55.71 kg** per piece  
  Evidence: BOM row in **B12–B14** lists **1p374 / PL6*800 / 1478.4 / 1 / 55.71**.

**Where it is shown on the sheet:**
- In the BOM table at **B12–B14**
- In the detail view at **E8** / **F3–F4**, labeled **“MARK NO:- 1p374”**
- In the drawing view at **B2** and **F3–F4** as the plate profile marked **1p374**

So the heaviest single BOM part is **1p374, PL6*800, 1478.4 mm long, 55.71 kg**, shown in the **BOM table and the plate detail views**.

## Q3. List every plate thickness used and the parts that use each one.

*Tools used:* none

The drawing uses these plate thicknesses:

- **6 mm**:  
  - **1p374** — **PL6*800**  
  - **1p375** — **PL6*75**  
  Evidence: BOM rows **B12–B15** and abstract row **A9/A10** show **PL 6 THK**.

- **8 mm**:  
  - **1m470** — **SPD508*508*608*608*8**  
  Evidence: BOM row **B12–B15** and detail **H9** / **G2** show **1m470**.

No other plate thicknesses are listed on this sheet.

## Q4. What bolts, nuts and washers are needed, and which assemblies do they connect?

*Tools used:* zoom(L9:L15), search_text(4 - 18 Ø HOLES), search_text(PERMANENT BOLTS), search_text(1DC1)

The sheet has a **“List of Permanent Bolts”** table at **L9–L15**, but it is **blank** for the actual bolt/nut/washer entries. So the drawing does **not specify any bolt diameter, length, grade, nut, or washer details** on this sheet.

What can be said from the drawing:

- The assembly is **1DC1**.
- The permanent bolts table is intended for **connected assembly mark** at **L9**.
- The sheet shows **“4 - 18 Ø HOLES”** at **G13** on the **1m471** member, so that member has four 18 mm holes, but the **bolt hardware itself is not listed**.
- Note **M5** says: **“ALL PERMANENT BOLTS ARE FULL THREADED.”**

So, strictly from this sheet:

- **Bolts:** not specified
- **Nuts:** not specified
- **Washers:** not specified
- **Assemblies they connect:** the table is for the **connected assembly mark 1DC1**, but no hardware rows are filled in

If you want, I can also point out **which parts are likely the bolted connection members from the views** (from the drawing view), but the exact bolt schedule is not present here.
