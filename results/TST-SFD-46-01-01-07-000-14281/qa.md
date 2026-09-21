# Q&A — TST-SFD-46-01-01-07-000-14281

Asked in one conversation (each question sees the earlier turns). The model gets the full sheet (grid-tagged text layer + tiles + validated extract) and can call query_bom / search_text / zoom.

## Q1. What does this drawing fabricate, how many assemblies, where are they erected (grid and level), and what is the total weight?

*Tools used:* none

This sheet fabricates **one steel column assembly marked 3C2** — title block: **“DETAIL OF COLUMN MKD AS -3C2”** and BOM assembly row **3C2**.

- **Assemblies:** **1** (BOM / mark box: **3C2**, qty **1**)
- **Erection location:** **37a-39a/LA** at **EL. +24.500**  
  - from mark location table: **A2**
  - title/mark box repeats the same location and level
- **Total weight:** **26121.53 kg**  
  - from title block and BOM grand total
  - BOM assembly row **3C2** gross weight = **26121.53 kg**



## Q2. Which BOM part is the heaviest, what is its section and size, and where is it shown on the sheet?

*Tools used:* query_bom(), search_text(3C2), zoom(bom)

The **heaviest BOM part** is **3C2** itself.

- **Item / mark:** **3C2**
- **Section:** **WH1200X500X40X32**
- **Weight:** **4756.50 kg** gross, **4748.68 kg** net
- **Size / length:** **7989.5 mm**

**Where shown on the sheet:**
- In the **BOM** table, first data row under **ERECTION MARK. 3C2** — the part row for **3C2** is at the top of the BOM, and it is the highest gross weight there.
- It is also shown in the drawing views as the main vertical column member labeled **3C2** — e.g. in **A-A** and **B-B** views on the sheet (**P3**, **N11**, and the mark box at **A1/A18**).

## Q3. List every plate thickness used and the parts that use each one.

*Tools used:* none

Every plate thickness used on this sheet, with the BOM parts that use each one:

- **10 mm**
  - **3m503** — WH500X300X16X10
  - **3m504** — WH400X500X20X10
  - **3p32** — PL10*287
  - **3p37** — PL10*379
  - **3p439** — PL10*255
  - **3p463** — PL10*200
  - **3p618** — PL10*229
  - **3p624** — PL10*250

- **12 mm**
  - **3p437** — PL12*225
  - **3p567** — PL12*200
  - **3p586** — PL12*164
  - **3p615** — PL12*250
  - **3p626** — PL12*350
  - **3p631** — PL12*200

- **14 mm**
  - **3p307** — PL14*234
  - **3p530** — PL14*452
  - **3p741** — PL14*471

- **16 mm**
  - **3m503** — WH500X300X16X10
  - **3p283** — PL16*646
  - **3p308** — PL16*234
  - **3p332** — PL16*473
  - **3p333** — PL16*496
  - **3p334** — PL16*490
  - **3p465** — PL16*259
  - **3p525** — PL16*359
  - **3p569** — PL16*260

- **20 mm**
  - **3m504** — WH400X500X20X10
  - **3p33** — PL20*200
  - **3p34** — PL20*200
  - **3p36** — PL20*200
  - **3p309** — PL20*234
  - **3p436** — PL20*230
  - **3p438** — PL20*200
  - **3p440** — PL20*200
  - **3p441** — PL20*200
  - **3p511** — PL20*630
  - **3p518** — PL20*630
  - **3p531** — PL20*630
  - **3p616** — PL20*200
  - **3p617** — PL20*200
  - **3p620** — PL20*200

- **25 mm**
  - **3p51** — PL25*200
  - **3p319** — PL25*650
  - **3p464** — PL25*250
  - **3p467** — PL25*250
  - **3p469** — PL25*280
  - **3p471** — PL25*250
  - **3p526** — PL25*200
  - **3p527** — PL25*230
  - **3p528** — PL25*200
  - **3p557** — PL25*234
  - **3p622** — PL25*200
  - **3p623** — PL25*200
  - **3p625** — PL25*200
  - **3p627** — PL25*200
  - **3p628** — PL25*200
  - **3p630** — PL25*200

- **32 mm**
  - **3p295** — PL32*500
  - **3C2** — WH1200X500X40X32
  - **3m471** — WH1200X500X40X32
  - **3m496** — WH1200X500X40X32
  - **3m497** — WH1200X500X40X32

If you want, I can also regroup these by **part mark** instead of thickness, or total the weight per thickness.

## Q4. What bolts, nuts and washers are needed, and which assemblies do they connect?

*Tools used:* none

The **List of Permanent Bolts** on the sheet shows these fastener sets:

- **3FR3**
  - **Bolts:** HEX, **20 dia × 105 long**, grade **8.8XOX**, spec **IS:1364(II)-2023**, material **IS:1367 (I) 2014**, **qty 8**
  - **Nuts:** **20 dia**, grade **8.8XOX**, spec **IS:1364(III)-2018**, material **IS:1367 (VI) 2025**, **qty 16**
  - **Washers:** **22 dia**, **FLAT-E**, spec **IS:2016 - 1967**, material **IS:1570 (II) 1979**, **qty 8**

- **3C1**
  - **Bolts:** HEX, **24 dia × 150 long**, grade **10.9XOX**, spec **IS:1364(II)-2023**, material **IS:1367 (I) 2014**, **qty 88**
  - **Nuts:** **24 dia**, grade **10.9XOX**, spec **IS:1364(III)-2018**, material **IS:1367 (VI) 2025**, **qty 176**
  - **Washers:** **26 dia**, **FLAT-E**, spec **IS:2016 - 1967**, material **IS:1570 (II) 1979**, **qty 88**

So the assemblies connected by permanent bolts are **3FR3** and **3C1**.
