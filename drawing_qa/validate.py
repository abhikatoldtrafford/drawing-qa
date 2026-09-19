"""Deterministic guardrails over the PyMuPDF extract. Each check names the region it guards. 'fail' = the numbers on the sheet disagree with
what we extracted; 'warn' = worth a human look, not proof of an error."""
import re

from .models import Check, PageExtract


def _close(a, b, rel=0.0005, abs_=0.05):
    return a is not None and b is not None and abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))


def _abstract_key(section: str) -> str:
    """BOM section -> ABSTRACT description key: 'PL10*150' / 'PLT8*50' -> 'PL10THK' / 'PL8THK' (the abstract
    groups all plates by thickness), 'T 300X250' -> 'T300X250'."""
    s = section.replace(" ", "").upper()
    m = re.match(r"^PLT?(\d+(?:\.\d+)?)\*", s)
    return f"PL{m.group(1)}THK" if m else s


def run_checks(x: PageExtract) -> list[Check]:
    out: list[Check] = []
    add = lambda id_, level, msg, region: out.append(Check(id=id_, level=level, message=msg, region=region))

    if not x.has_text_layer:
        add("text_layer", "fail", "Page has no usable text layer; nothing can be verified.", "page")
        return out

    b = x.bom
    if b is None or not b.parts:
        add("bom.found", "fail", "Bill of materials not found or empty.", "bom")
    else:
        asm_qty = (b.assembly.qty if b.assembly and b.assembly.qty else 1)
        bad = []
        for p in b.parts:
            if None in (p.qty, p.pc_wt, p.gross_kg):
                bad.append(f"{p.item_no or '?'} (missing qty/pc wt/gross)")
            elif abs(p.qty * p.pc_wt - p.gross_kg) > 0.006 * p.qty + 0.02:   # pc wt is rounded to 0.01
                bad.append(f"{p.item_no}: {p.qty}×{p.pc_wt}={p.qty * p.pc_wt:.2f} ≠ {p.gross_kg}")
        add("bom.row_arith", "fail" if bad else "pass",
            "; ".join(bad) if bad else f"All {len(b.parts)} rows: qty × pc wt = gross (± rounding).", "bom")
        s_gross = sum(p.gross_kg or 0 for p in b.parts) * asm_qty
        add("bom.gross_total", "pass" if _close(s_gross, b.totals.gross_kg) else "fail",
            f"Σ part gross × assembly qty {asm_qty} = {s_gross:.2f}; grand total = {b.totals.gross_kg}.", "bom")
        if b.assembly:
            add("bom.assembly_row", "pass" if _close(b.assembly.gross_kg, b.totals.gross_kg) else "fail",
                f"Assembly row {b.assembly.erection_mark} gross {b.assembly.gross_kg} vs grand total "
                f"{b.totals.gross_kg}.", "bom")
        s_net = sum(p.net_kg or 0 for p in b.parts)
        ok = _close(s_net, b.totals.net_kg, rel=0.002) or _close(s_net * asm_qty, b.totals.net_kg, rel=0.002)
        add("bom.net_total", "pass" if ok else "warn",
            f"Σ part net = {s_net:.2f} (× qty {asm_qty} = {s_net * asm_qty:.2f}); net total = {b.totals.net_kg}. "
            "Tekla net totals often differ; informational.", "bom")
        if x.bom_crosscheck is None:
            add("bom.crosscheck", "warn", "Second parse (find_tables) unavailable; BOM checked by arithmetic only.", "bom")
        else:
            add("bom.crosscheck", "fail" if x.bom_crosscheck else "pass",
                "; ".join(x.bom_crosscheck[:10]) if x.bom_crosscheck else
                "find_tables() second parse agrees on every row (section, length, qty, gross, material).", "bom")
        on_sheet = set(x.part_marks)
        missing = [p.item_no for p in b.parts if p.item_no not in on_sheet]
        add("marks.bom_on_sheet", "fail" if missing else "pass",
            f"BOM marks not found in drawing views: {missing}" if missing else "Every BOM mark appears on the drawing.",
            "bom")
        extra = sorted(on_sheet - {p.item_no for p in b.parts} - {b.assembly.erection_mark if b.assembly else ""})
        if extra:
            add("marks.extra", "pass", f"Marks on sheet not in BOM (connected/referenced assemblies): {extra}", "views")
        if x.title_block.weight_kg is not None:
            add("title.weight", "pass" if _close(x.title_block.weight_kg, b.totals.gross_kg) else "fail",
                f"Title block weight {x.title_block.weight_kg} vs BOM gross {b.totals.gross_kg}.", "title_block")
        if b.assembly and x.mark_locations:
            wrong = [m.mark_no for m in x.mark_locations if m.mark_no != b.assembly.erection_mark]
            add("mark_location.assembly", "fail" if wrong else "pass",
                f"Mark box {[m.mark_no for m in x.mark_locations]} vs BOM assembly '{b.assembly.erection_mark}'.", "bom")
            n = len(x.mark_locations)
            add("mark_location.count", "pass" if n == asm_qty else "warn",
                f"{n} erection location(s) listed; assembly qty {asm_qty}.", "bom")

    a = x.abstract
    if a and a.rows:
        s = sum(r.total_wt or 0 for r in a.rows)
        ok = _close(s, a.total_kg) and (b is None or _close(a.total_kg, b.totals.gross_kg))
        add("abstract.total", "pass" if ok else "fail",
            f"Σ abstract = {s:.2f}; abstract total = {a.total_kg}; BOM gross = {b.totals.gross_kg if b else None}.",
            "abstract")
        if b and b.parts:
            asm_qty = (b.assembly.qty if b.assembly and b.assembly.qty else 1)
            by_key = {}
            for p in b.parts:
                k = _abstract_key(p.section)
                by_key[k] = by_key.get(k, 0) + (p.gross_kg or 0) * asm_qty
            bad = [f"{r.description}: abstract {r.total_wt} vs BOM {by_key.get(_abstract_key(r.description), 0):.2f}"
                   for r in a.rows if not _close(r.total_wt, by_key.get(_abstract_key(r.description), 0))]
            add("abstract.by_section", "fail" if bad else "pass",
                "; ".join(bad) if bad else "Every abstract row equals the BOM gross for that section/plate thickness.",
                "bom")

    tb = x.title_block
    if not tb.drawing_no:
        add("title.drawing_no", "fail", "Drawing number not found in title block.", "title_block")
    elif tb.drawing_no not in x.source_file:
        add("title.drawing_no", "warn", f"Drawing no. {tb.drawing_no} does not match file name {x.source_file}.",
            "title_block")
    else:
        add("title.drawing_no", "pass", f"Drawing no. {tb.drawing_no} matches file name.", "title_block")
    missing = [f for f in ("department", "equip_area", "title_lines") if not getattr(tb, f)]
    if missing:
        add("title.fields", "warn", f"Title-block fields not found: {missing}", "title_block")
    return out
