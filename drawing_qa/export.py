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


def to_json(x) -> str:
    return x.model_dump_json(indent=2)


def bom_csv(x) -> str:
    return _frames(x)["BOM"].to_csv(index=False)


def to_excel(x, inventory=None) -> bytes:
    frames = _frames(x) | (inventory_frames(inventory) if inventory is not None else {})
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for name, df in frames.items():
            df.to_excel(w, sheet_name=name, index=False)
    return buf.getvalue()
