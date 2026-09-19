"""Inventory exports of a PageExtract: JSON, BOM CSV, multi-sheet Excel."""
import io

import pandas as pd


def _frames(x):
    tb = x.title_block
    title = {
        "drawing_no": tb.drawing_no, "rev": tb.rev, "sheet": tb.sheet_no, "size": tb.sheet_size,
        "weight_kg": tb.weight_kg, "department": tb.department, "equip_area": tb.equip_area,
        "project": tb.project, "title": " / ".join(tb.title_lines),
        "drawn": f"{tb.drn.name} {tb.drn.date}".strip(), "checked": f"{tb.chd.name} {tb.chd.date}".strip(),
        "approved": f"{tb.app.name} {tb.app.date}".strip(),
        "assembly_mark": ", ".join(dict.fromkeys(m.mark_no for m in x.mark_locations)),
        "erection_locations": "; ".join(f"{m.grid_location} {m.level}".strip() for m in x.mark_locations),
        "source_file": x.source_file,
    }
    bom_rows = []
    if x.bom:
        asm = x.bom.assembly
        for r in x.bom.parts:
            d = r.model_dump(exclude={"bbox", "erection_mark"})
            d["assembly_mark"] = asm.erection_mark if asm else ""
            d["assembly_qty"] = asm.qty if asm else None
            d["drawing_no"] = tb.drawing_no
            bom_rows.append(d)
    return {
        "Title": pd.DataFrame([title]),
        "BOM": pd.DataFrame(bom_rows),
        "Locations": pd.DataFrame([m.model_dump() for m in x.mark_locations]),
        "Abstract": pd.DataFrame([r.model_dump() for r in (x.abstract.rows if x.abstract else [])]),
        "Bolts": pd.DataFrame([r.model_dump() for r in x.bolts]),
        "Revisions": pd.DataFrame([r.model_dump() for r in x.revisions]),
        "Notes": pd.DataFrame({"note": x.notes}),
        "Views": pd.DataFrame([v.model_dump(exclude={"bbox"}) for v in x.view_labels]),
        "Checks": pd.DataFrame([c.model_dump() for c in x.checks]),
    }


def inventory_frames(inv) -> dict:
    joined = lambda d, k: {**d, k: ", ".join(d[k])}
    summary = [
        ("Assembly", f"{inv.assembly_mark} x {inv.assembly_qty}"),
        ("Total steel (kg, BOM gross x qty)", inv.total_steel_kg),
        ("Plates (kg)", round(sum(p.weight_kg for p in inv.plates), 2)),
        ("Sections (kg)", round(sum(s.weight_kg for s in inv.sections), 2)),
        ("Paint area (m2)", inv.paint_area_m2),
        ("Weld metal (kg, model-read estimate, unverified)", inv.weld_metal_kg),
        ("Electrode (kg, model-read estimate, unverified)", inv.electrode_kg),
        ("OpenAI model", inv.model or "not run"),
    ]
    return {
        "Inv Summary": pd.DataFrame(summary, columns=["item", "value"]),
        "Inv Plates": pd.DataFrame([joined(p.model_dump(), "sources") for p in inv.plates]),
        "Inv Sections": pd.DataFrame([joined(s.model_dump(), "sources") for s in inv.sections]),
        "Inv Fasteners": pd.DataFrame([joined(f.model_dump(), "connected_assemblies") for f in inv.fasteners]),
        "Inv Welds": pd.DataFrame([joined(w.model_dump(), "parts") for w in inv.welds]),
        "Inv Review": pd.DataFrame([u.model_dump() for u in inv.unclassified]
                                   + [{"mark": "", "section": "weld", "description": r, "accepted": False,
                                       "note": "rejected by guardrail"} for r in inv.rejected_welds]),
        "Inv Checks": pd.DataFrame([c.model_dump() for c in inv.checks]),
    }


BOQ_HEADERS = ["DRAWING NO", "ITEM TYPE", "MARK NO", "ITEMNO", "SECTION", "WIDTH", "LENGTH", "QTY", "FAB QTY",
               "TOTAL QTY", "UNIT WT", " CALCULATED WT", "TOTAL CALCULATED WT", "WT", "TOTAL DRG WT", "DIFFRENCE",
               "GRADE", "UNIT WT SOURCE", "NOTE"]           # spelling as in the reference BOQ (2GU1 BOQ.xlsx)


def write_boq_sheet(ws, rows):
    """BOQ with live formulas in the reference layout: row 1 SUBTOTALs, row 2 headers, data from row 3."""
    for col in "JLMNOP":                                  # open range, as in the reference: added rows count
        ws[f"{col}1"] = f"=SUBTOTAL(9,{col}3:{col}105848)"
    ws.append(BOQ_HEADERS)
    for i, r in enumerate(rows, start=3):
        plate = r.unit_wt_basis == "kg/m2"
        thk = r.section[2:] if plate else ""
        ws.append([
            r.drawing_no, r.item_type, r.mark_no, r.item_no, r.section, r.width if plate else None, r.length,
            r.qty, r.fab_qty, f"=H{i}*I{i}",
            (f"=7.85*{thk}" if plate else r.unit_wt),
            (f"=(F{i}/1000)*(G{i}/1000)*H{i}*K{i}" if plate else f"=(G{i}/1000)*H{i}*K{i}")
            if r.unit_wt is not None else None,
            f"=L{i}*I{i}" if r.unit_wt is not None else None,
            None if r.drg_wt is None else round(r.drg_wt, 4), f"=N{i}*I{i}",
            f"=M{i}-O{i}" if r.difference is not None else None,
            r.grade, r.unit_wt_source, r.note,
        ])


def to_json(x) -> str:
    return x.model_dump_json(indent=2)


def bom_csv(x) -> str:
    return _frames(x)["BOM"].to_csv(index=False)


def to_excel(x, inventory=None) -> bytes:
    """Extract sheets; with an inventory, a 'BOQ' sheet (first, live formulas) plus the inventory summaries."""
    frames = _frames(x) | (inventory_frames(inventory) if inventory is not None else {})
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        if inventory is not None:
            write_boq_sheet(w.book.create_sheet("BOQ", 0), inventory.boq)
        for name, df in frames.items():
            df.to_excel(w, sheet_name=name, index=False)
    return buf.getvalue()


def boq_excel(inventory) -> bytes:
    """Just the BOQ sheet, in the reference layout."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOQ"
    write_boq_sheet(ws, inventory.boq)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
