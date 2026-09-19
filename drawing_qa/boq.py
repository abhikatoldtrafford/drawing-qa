"""Fabrication BOQ: one row per BOM part, in the layout of the user's reference BOQ (2GU1 BOQ.xlsx).

  DRAWING NO | ITEM TYPE | MARK NO | ITEMNO | SECTION | WIDTH | LENGTH | QTY | FAB QTY | TOTAL QTY | UNIT WT |
  CALCULATED WT | TOTAL CALCULATED WT | WT | TOTAL DRG WT | DIFFERENCE | GRADE

Plates: SECTION 'PL<t>' + WIDTH, UNIT WT = 7.85 x t (kg/m²), CALCULATED WT = W x L x QTY x UNIT WT.
Rolled sections: UNIT WT from the IS 808 handbook table (kg/m), CALCULATED WT = L x QTY x UNIT WT.
WT is the drawing's (Tekla) gross weight of the row, so DIFFERENCE shows handbook vs drawing.
Welded built-ups (WH / T) and rolled cones (SPD, developed on the mean diameters) are listed as their plates.
A rolled designation missing from the handbook table gets an OpenAI handbook value (always flagged 'verify')
or, failing that, the drawing's own kg/m. An unknown section is listed as plates when an accepted breakdown
exists, otherwise as itself with the drawing's kg/m. When the unit weight comes from the drawing, DIFFERENCE is
left blank: a 0.00 would only compare the drawing with itself."""
import re

from .models import BoqRow
from .sections import decompose, develop_cone, parse_section
from .steel_tables import handbook_unit_weight, plate_unit_weight

ITEM_TYPE = re.compile(r"DETAIL\s+OF\s+(.+?)\s+MKD\s+AS", re.I)


def item_type(x) -> str:
    """'DETAIL OF GUTTER MKD AS -2GU1' -> 'GUTTER'."""
    for line in x.title_block.title_lines:
        if m := ITEM_TYPE.search(line):
            return m.group(1).strip().upper()
    return ""


def tekla_unit_weight(p) -> float | None:
    """kg/m implied by the drawing's own gross weight (used as the fallback and as the plausibility reference)."""
    if not (p.gross_kg and p.length_mm and p.qty):
        return None
    return p.gross_kg / (p.length_mm / 1000 * p.qty)


def _row(x, itype, p, fab, **kw):
    r = BoqRow(drawing_no=x.title_block.drawing_no, item_type=itype,
               mark_no=x.bom.assembly.erection_mark if x.bom.assembly else "", item_no=kw.pop("item_no", p.item_no),
               grade=p.material, fab_qty=fab, qty=kw.pop("qty", p.qty or 0), total_qty=0, **kw)
    r.total_qty = r.qty * fab
    if r.unit_wt is not None and r.length is not None:
        per_len = r.length / 1000 * r.qty * r.unit_wt
        r.calc_wt = per_len * r.width / 1000 if r.unit_wt_basis == "kg/m2" else per_len
        r.total_calc_wt = r.calc_wt * fab
    if r.drg_wt is not None:
        r.total_drg_wt = r.drg_wt * fab
    if r.total_calc_wt is not None and r.total_drg_wt is not None:
        r.difference = r.total_calc_wt - r.total_drg_wt
    return r


def build_boq(x, unit_weights=None, breakdowns=None) -> list[BoqRow]:
    """unit_weights: {section: (kg/m, source)} for rolled sections missing from the handbook table.
    breakdowns: {mark: [Plate, ...]} accepted plate breakdowns of unknown sections."""
    if x.bom is None:
        return []
    unit_weights, breakdowns = unit_weights or {}, breakdowns or {}
    itype = item_type(x)
    fab = x.bom.assembly.qty if x.bom.assembly and x.bom.assembly.qty else 1
    rows = []
    for p in x.bom.parts:
        ps = parse_section(p.section)
        plates = None
        if ps.family == "built_up":
            plates = [(f"{p.item_no} {'flange' if i == 0 else 'web'}", pl) for i, pl in
                      enumerate(decompose(ps, p.length_mm or 0))]
            note = f"{p.section} decomposed into plates"
        elif ps.family == "cone":
            plates = [(f"{p.item_no} cone plate", develop_cone(ps, p.length_mm or 0))]
            note = f"{p.section}: rolled cone, developed plate (mean circumference x slant height)"
        elif p.item_no in breakdowns:
            plates = [(f"{p.item_no} plate {i + 1}", pl) for i, pl in enumerate(breakdowns[p.item_no])]
            note = f"{p.section}: OpenAI plate breakdown (weight and thickness checked)"
        if ps.family == "plate":
            rows.append(_row(x, itype, p, fab, section=f"PL{ps.thickness_mm:g}", width=ps.width_mm,
                             length=p.length_mm, unit_wt=plate_unit_weight(ps.thickness_mm), unit_wt_basis="kg/m2",
                             drg_wt=p.gross_kg, unit_wt_source="7.85 x t"))
        elif plates:
            total = sum(pl.weight_kg for _, pl in plates) or 1.0
            for item_no, pl in plates:
                rows.append(_row(x, itype, p, fab, item_no=item_no, qty=pl.count * (p.qty or 0),
                                 section=f"PL{pl.thickness_mm:g}", width=pl.width_mm, length=pl.length_mm,
                                 unit_wt=plate_unit_weight(pl.thickness_mm), unit_wt_basis="kg/m2",
                                 drg_wt=(p.gross_kg or 0) * pl.weight_kg / total, unit_wt_source="7.85 x t",
                                 note=note + "; WT shared by plate weight"))
        else:
            uw, src = handbook_unit_weight(p.section)
            if uw is None and ps.profile in unit_weights:
                uw, src = unit_weights[ps.profile]
            note = ""
            drawing_uw = tekla_unit_weight(p)
            if src.startswith("OpenAI") and drawing_uw:
                note = f"handbook value from OpenAI, unverified; drawing implies {drawing_uw:.2f} kg/m"
            if uw is None:
                uw, src = drawing_uw, "drawing (no handbook value)"
                note = "unit weight taken from the drawing's own weight; verify" + (
                    "; procure per the drawing" if ps.family == "unknown" else "")
            if ps.family == "pipe":
                note = "BOM length is the longest length; DIFFERENCE includes mitre / hole cut-off"
            r = _row(x, itype, p, fab, section=ps.profile, length=p.length_mm,
                     unit_wt=round(uw, 4) if uw else None, unit_wt_basis="kg/m", drg_wt=p.gross_kg,
                     unit_wt_source=src, note=note)
            if src.startswith("drawing"):
                r.difference = None                     # drawing vs itself is not a check
            rows.append(r)
    return rows


ROLLED = re.compile(r"^IS[A-Z]{1,3}\d")              # ISA / ISMC / ISMB / ISLB / ISHB / ISJC ... designations


def missing_unit_weights(x) -> dict[str, float]:
    """Rolled IS designations with no handbook-table value: {section: drawing-implied kg/m (shown beside the
    OpenAI value, never used to accept it)}. Unknown families (e.g. transitions) are not asked about."""
    out = {}
    for p in (x.bom.parts if x.bom else []):
        ps = parse_section(p.section)
        if ROLLED.match(ps.profile) and handbook_unit_weight(p.section)[0] is None:
            out[ps.profile] = tekla_unit_weight(p)
    return out
