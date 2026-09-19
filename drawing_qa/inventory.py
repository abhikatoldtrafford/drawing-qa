"""Inventory for one page: what material, how much.

Deterministic (from the validated extract; independently re-computed by the auditor):
  plates by thickness + grade (incl. WH / T built-ups decomposed into plates, weight-checked),
  sections by profile + grade, fasteners from the bolt list, paint area from the BOM.
  Weights are Tekla GROSS (stock) weights; no wastage allowance.
OpenAI-assisted (one structured call with the full page image + text):
  - sections the code cannot parse (e.g. SPD508*508*608*608*8): description + plate breakdown, accepted only
    if every plate thickness is written in the section name and the plates weigh within 2% of the BOM member;
  - welds: the model reads the TOPOLOGY only (which part is welded to which, which edge, sides, fillet size,
    how many, tack or not). The weld LENGTH is computed by code from BOM geometry (part length / width,
    plate perimeter, or pi x diameter for circular joints), so copied view dimensions cannot become lengths.
Weld metal and electrode figures are model-read estimates, unverified, and labelled as such."""
import hashlib
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .boq import build_boq, item_type, missing_unit_weights
from .config import SCHEMA_VERSION
from .context import page_context
from .geometry import num, xc, yc
from .models import Check, FastenerLine, Inventory, InventoryItem, PlateLine, SectionLine, WeldLine
from .sections import STEEL_KG_M3, Plate, decompose, develop_cone, parse_section, weight_matches

FILLET_SIZES = {3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 25}
ELECTRODE_PER_WELD_METAL = 1 / 0.6          # ~60 % deposition efficiency for manual metal arc (estimate)


# ---- schema sent to the model (strict structured output: every field required, no defaults)
class PlateLLM(BaseModel):
    thickness_mm: float
    width_mm: float
    length_mm: float
    count: int


class UnknownSectionLLM(BaseModel):
    mark: str
    description: str
    plates: list[PlateLLM]


class WeldLLM(BaseModel):
    attached: str                                   # the part whose edge is welded (e.g. a lug plate)
    base: str                                       # the part it is welded to (e.g. the pipe)
    edge: Literal["length", "width", "perimeter", "circumference"]
    sides: int                                      # 1 or 2 (fillet on both sides)
    size_mm: float
    count: int                                      # such joints per assembly
    tack: bool                                      # drawing says tack welded
    evidence: str


class UnitWeightLLM(BaseModel):
    section: str
    kg_per_m: float


class InventoryLLM(BaseModel):
    unknown_sections: list[UnknownSectionLLM]
    welds: list[WeldLLM]
    unit_weights: list[UnitWeightLLM]


INSTRUCTIONS = """You assist a steel fabrication estimator. You get one drawing sheet (full text layer tagged with grid
cells, and images of the whole sheet), its validated bill of materials, and a list of UNKNOWN sections.
1. unknown_sections: for each listed mark only, say what the member is (description) and give the plates it is
   fabricated from for ONE piece (thickness, width, length in mm, count), e.g. the developed plate of a cone.
   Plate thickness must be the one written in the section name. Leave plates empty if unsure.
2. welds: list the welds shown in the views for ONE assembly. For each joint type give:
   attached = the part whose edge is welded (e.g. a stiffener, lug, cleat); base = the part it is welded to
   (attached and base are part MARKS only, exactly as in the BOM, e.g. '4p639' - no descriptions);
   edge = which edge of the ATTACHED part carries the weld: 'length' (its long edge), 'width' (its short edge),
   'perimeter' (all round a plate), 'circumference' (all round a pipe / circular joint);
   sides = 2 if welded on both sides (symbol on both sides or 'both sides'), else 1;
   size_mm = fillet leg written at the weld symbol (use the general-note size when none is written);
   count = how many such joints per assembly (e.g. 'TYP.' on a part with qty 4 -> 4);
   tack = true only if the drawing says the part is tack welded;
   evidence = view label and/or grid cell where you read it.
   Do not give lengths: they are computed from the bill of materials. Do not invent welds you cannot see.
3. unit_weights: for each MISSING rolled section listed, its IS 808 handbook weight per metre in kg/m for
   that exact designation. Omit a section if you do not know the handbook value; never estimate from the
   drawing."""


def _asm_qty(x):
    b = x.bom
    return b.assembly.qty if b and b.assembly and b.assembly.qty else 1


def _nums(section):
    return [float(v) for v in re.findall(r"\d+(?:\.\d+)?", section)]


def _diameter(row):
    """Outside diameter of a circular part (pipe, round bar, conical/unknown shell), else None."""
    p = parse_section(row.section)
    if p.family in ("pipe", "round"):
        return _nums(p.profile)[0]
    if p.family == "unknown":
        big = [v for v in _nums(p.profile) if v >= 50]
        return min(big) if big else None
    return None


def weld_length_mm(edge, att, base):
    """Length of one weld run from BOM geometry; None when the edge does not apply to the part."""
    p = parse_section(att.section)
    if edge == "length":
        return att.length_mm
    if edge == "width":
        if p.family == "plate":
            return p.width_mm
        if p.family == "built_up":
            return p.d
        n = _nums(p.profile)
        return n[0] if n and p.family in ("angle", "channel", "beam") else None
    if edge == "perimeter":
        return 2 * (att.length_mm + p.width_mm) if p.family == "plate" else None
    if edge == "circumference":
        ds = [d for d in (_diameter(att), _diameter(base) if base else None) if d]
        return math.pi * min(ds) if ds else None
    return None


def allowed_weld_sizes(layout, notes, regions=()) -> set[float]:
    """Fillet sizes the sheet shows: the general-note size, plus standard sizes written on the same row as a
    'TYP.' / 'CONT.' weld callout (e.g. '6 TYP.', '4/4 CONT.'), ignoring the BOM, bolt and title tables."""
    sizes = {float(m) for n in notes for m in re.findall(r"(\d+)\s*MM FILLET", n.upper())}
    inside = lambda w: any(r[0] <= xc(w) <= r[2] and r[1] <= yc(w) <= r[3] for r in regions)
    anchors = [w for w in layout.words if w[4] in ("TYP.", "TYP", "CONT.", "CONT") and not inside(w)]
    for w in layout.words:
        m = re.fullmatch(r"(\d{1,2})(?:/(\d{1,2}))?", w[4])
        if not m or inside(w):
            continue
        if any(abs(yc(w) - yc(a)) <= 12 and abs(xc(a) - xc(w)) < 80 for a in anchors):
            sizes |= {float(g) for g in m.groups() if g and int(g) in FILLET_SIZES}
    return sizes


def deterministic_inventory(x) -> Inventory:
    tb, b = x.title_block, x.bom
    q_asm = _asm_qty(x)
    inv = Inventory(drawing_no=tb.drawing_no, assembly_mark=b.assembly.erection_mark if b and b.assembly else "",
                    assembly_qty=q_asm)
    if b is None:
        inv.checks.append(Check(id="inventory.bom", level="fail", message="No BOM on this page.", region="inventory"))
        return inv
    plates, sections = {}, {}

    def add_plate(t, grade, pieces, area, kg, src):
        pl = plates.setdefault((t, grade), PlateLine(thickness_mm=t, grade=grade, pieces=0, area_m2=0, weight_kg=0))
        pl.pieces += pieces
        pl.area_m2 += area
        pl.weight_kg += kg
        pl.sources.append(src)

    for p in b.parts:
        q = (p.qty or 0) * q_asm
        ps = parse_section(p.section)
        if ps.family == "plate":
            add_plate(ps.thickness_mm, p.material, q, ps.width_mm * (p.length_mm or 0) * q / 1e6,
                      (p.gross_kg or 0) * q_asm, p.item_no)
            continue
        if ps.family in ("built_up", "cone"):
            pls = decompose(ps, p.length_mm or 0) if ps.family == "built_up" else [develop_cone(ps, p.length_mm or 0)]
            if weight_matches(pls, p.pc_wt, (p.net_kg or 0) / (p.qty or 1)):
                kind = ps.kind if ps.family == "built_up" else "cone"
                share = sum(pl.weight_kg for pl in pls) or 1.0
                for pl in pls:                        # drawing (gross) weight shared by plate weight, as in the BOQ
                    add_plate(pl.thickness_mm, p.material, pl.count * q, pl.area_m2 * q,
                              (p.gross_kg or 0) * q_asm * pl.weight_kg / share,
                              f"{p.item_no} ({kind} {pl.width_mm:g}x{pl.thickness_mm:g})")
                continue
            inv.checks.append(Check(id=f"inventory.decompose.{p.item_no}", level="warn", region="inventory",
                                    message=f"{p.item_no} {p.section}: plate recipe does not match BOM weight; "
                                            "kept as a section."))
        family = {"built_up": "built-up", "unknown": "other"}.get(ps.family, ps.family)
        sl = sections.setdefault((ps.profile, p.material), SectionLine(profile=ps.profile, family=family,
                                                                       grade=p.material, pieces=0,
                                                                       total_length_m=0, weight_kg=0))
        sl.pieces += q
        sl.total_length_m += (p.length_mm or 0) * q / 1000
        sl.weight_kg += (p.gross_kg or 0) * q_asm
        sl.sources.append(p.item_no)
        if ps.family == "unknown":
            inv.unclassified.append(InventoryItem(mark=p.item_no, section=p.section, description="", accepted=False,
                                                  note="not a known section family"))
    inv.plates = sorted(plates.values(), key=lambda v: (v.thickness_mm, v.grade))
    inv.sections = sorted(sections.values(), key=lambda v: (v.family, v.profile))
    for pl in inv.plates:
        pl.area_m2, pl.weight_kg = round(pl.area_m2, 3), round(pl.weight_kg, 2)
    for sl in inv.sections:
        sl.total_length_m, sl.weight_kg = round(sl.total_length_m, 3), round(sl.weight_kg, 2)
    inv.fasteners = fasteners(x.bolts)
    inv.total_steel_kg = b.totals.gross_kg or 0.0
    inv.paint_area_m2 = b.totals.surface_area_m2
    inv.item_type = item_type(x)
    inv.boq = build_boq(x)
    _steel_checks(inv, x)
    _boq_checks(inv)
    return inv


def _boq_checks(inv):
    rows = inv.boq
    drg = sum(r.total_drg_wt or 0 for r in rows)
    ok = abs(drg - inv.total_steel_kg) <= max(0.1, 0.005 * inv.total_steel_kg)
    _set_check(inv, Check(id="boq.drawing_weight", level="pass" if ok else "fail", region="inventory",
                          message=f"BOQ total drawing weight {drg:.2f} kg; BOM gross total {inv.total_steel_kg} kg."))
    calc = sum(r.total_calc_wt or 0 for r in rows)
    missing = [r.item_no for r in rows if r.total_calc_wt is None]
    far = [f"{r.item_no} {r.section}: {r.difference:+.2f} kg" for r in rows
           if r.difference is not None and r.total_drg_wt and abs(r.difference) > 0.05 * r.total_drg_wt]
    drawing_uw = [r.item_no for r in rows if r.unit_wt_source.startswith("drawing")]
    level = "warn" if (missing or far or drawing_uw) else "pass"
    msg = f"BOQ calculated {calc:.2f} kg vs drawing {drg:.2f} kg ({calc - drg:+.2f} kg)."
    if far:
        msg += f" Rows off by >5%: {far}."
    if missing:
        msg += f" No unit weight: {missing}."
    if drawing_uw:
        msg += f" Unit weight taken from the drawing (no handbook value): {drawing_uw}."
    _set_check(inv, Check(id="boq.calculated", level=level, region="inventory", message=msg))


def fasteners(bolts) -> list[FastenerLine]:
    acc = {}

    def add(item, dia, qty, length="", type_="", grade="", spec="", material="", asm=""):
        n = num(qty)
        if not dia or n is None:
            return
        key = (item, dia, length, type_, grade, spec, material)
        fl = acc.setdefault(key, FastenerLine(item=item, dia_mm=dia, length_mm=length, type=type_, grade=grade,
                                              spec=spec, material=material, qty=0))
        fl.qty += int(n)
        if asm and asm not in fl.connected_assemblies:
            fl.connected_assemblies.append(asm)

    for r in bolts:
        a = r.assembly_mark
        add("bolt", r.bolt_dia, r.bolt_qty, r.bolt_length, r.bolt_type, r.bolt_grade, r.bolt_spec, r.bolt_material, a)
        add("nut", r.nut_dia, r.nut_qty, grade=r.nut_grade, spec=r.nut_spec, material=r.nut_material, asm=a)
        add("plain washer", r.washer_dia, r.washer_qty, type_=r.washer_type, spec=r.washer_spec,
            material=r.washer_material, asm=a)
        add("taper washer", r.taper_dia, r.taper_qty, type_=r.taper_type, spec=r.taper_spec,
            material=r.taper_material, asm=a)
    return sorted(acc.values(), key=lambda f: (f.item, f.dia_mm, f.length_mm))


def _set_check(inv, check):
    inv.checks = [c for c in inv.checks if c.id != check.id] + [check]


def _steel_checks(inv, x):
    listed = sum(p.weight_kg for p in inv.plates) + sum(s.weight_kg for s in inv.sections)
    ok = abs(listed - inv.total_steel_kg) <= max(0.1, 0.005 * inv.total_steel_kg)
    _set_check(inv, Check(id="inventory.weight", level="pass" if ok else "fail", region="inventory",
                          message=f"Plates + sections = {listed:.2f} kg; BOM gross total = {inv.total_steel_kg} kg."))
    per_piece = sum((p.surface_area_m2 or 0) * (p.qty or 0) for p in x.bom.parts) * inv.assembly_qty
    if inv.paint_area_m2:
        ok = abs(per_piece - inv.paint_area_m2) <= 0.05 * inv.paint_area_m2
        _set_check(inv, Check(id="inventory.paint", level="pass" if ok else "warn", region="inventory",
                              message=f"Paint area {inv.paint_area_m2} m² (BOM total); Σ row area × qty = "
                                      f"{per_piece:.2f} m²."))
    bad_taper = [r.assembly_mark or "(own)" for r in x.bolts if r.taper_dia and num(r.taper_qty) is None]
    if bad_taper:
        _set_check(inv, Check(id="inventory.taper_qty", level="warn", region="inventory",
                              message=f"Taper washers listed without a quantity for {bad_taper}; not counted."))


# ------------------------------------------------------------------ OpenAI-assisted step
def _rejection_rate(inv):
    n = len(inv.welds) + len(inv.rejected_welds)
    return len(inv.rejected_welds) / n if n else 0.0


def _needs_escalation(inv) -> bool:
    if any(c.id == "inventory.llm" for c in inv.checks):
        return True                                               # the mini call itself failed
    unresolved = any(not u.accepted for u in inv.unclassified)
    proposed = len(inv.welds) + len(inv.rejected_welds)
    return unresolved or (proposed > 2 and _rejection_rate(inv) > 0.3)


def _cache_file(cache_dir, x, model, deep_model):
    tag = hashlib.sha256(f"{SCHEMA_VERSION}|{model}|{deep_model}".encode()).hexdigest()[:10]
    return Path(cache_dir) / f"{x.file_sha256[:20]}_p{x.page_index}_inventory_{tag}.json"


def _ask(x, page, layout, llm, model, unknown):
    """One structured OpenAI call with the whole page. Returns (InventoryLLM, None) or (None, error text)."""
    bom_txt = "\n".join(f"{p.item_no} | {p.section} | L={p.length_mm} | qty={p.qty} | {p.material}"
                        for p in x.bom.parts)          # no weights: code checks breakdowns against them
    asm = x.bom.assembly
    missing = sorted(missing_unit_weights(x))
    text = (f"ASSEMBLY {asm.erection_mark if asm else ''} x {asm.qty if asm and asm.qty else 1}\n"
            f"BOM (mark | section | length mm | qty | grade):\n{bom_txt}\nNOTES:\n" + "\n".join(x.notes)
            + f"\nUNKNOWN sections: {unknown or 'none'}\nMISSING unit weights: {missing or 'none'}")
    try:
        content = page_context(page, layout) + [{"type": "input_text", "text": text}]
        return llm.parse_content(model, INSTRUCTIONS, content, InventoryLLM), None
    except Exception as e:
        return None, f"{model}: {type(e).__name__}: {e}"


def _assemble(x, layout, unknown_answers, welds, model_label, errors, unit_weights=None) -> Inventory:
    inv = deterministic_inventory(x)
    inv.model = model_label
    rows = {p.item_no: p for p in x.bom.parts}
    breakdowns = {}
    if unknown_answers is not None:
        breakdowns = _apply_unknown(inv, unknown_answers, rows, [u.mark for u in inv.unclassified])
    accepted_uw = _apply_unit_weights(inv, unit_weights or [], missing_unit_weights(x))
    if breakdowns or accepted_uw:
        inv.boq = build_boq(x, accepted_uw, breakdowns)
        _boq_checks(inv)
    if welds is not None:
        _apply_welds(inv, welds, rows, allowed_weld_sizes(layout, x.notes, x.regions.values()))
    if errors and unknown_answers is None and welds is None:
        inv.checks.append(Check(id="inventory.llm", level="warn", region="inventory",
                                message=f"OpenAI step failed ({'; '.join(errors)}); deterministic inventory only."))
    _steel_checks(inv, x)
    return inv


def build_inventory(x, page, layout, llm=None, model="gpt-5.4-mini", deep_model=None, cache_dir=None) -> Inventory:
    """Deterministic inventory, then one OpenAI pass. Escalate once to deep_model when that pass failed, left an
    unknown section unresolved, or had >30% of >2 proposed welds rejected. After escalation each part is taken
    from the better run: unknown sections from the run that resolved more; welds from the run with the lower
    rejection rate (the number of accepted welds is deliberately not rewarded). Successful results are cached."""
    if llm is None or x.bom is None:
        return deterministic_inventory(x)
    cache = _cache_file(cache_dir, x, model, deep_model) if cache_dir else None
    if cache and cache.exists():
        return Inventory.model_validate_json(cache.read_text(encoding="utf-8"))
    before = llm.usage_summary()
    unknown = [u.mark for u in deterministic_inventory(x).unclassified]
    out, err = _ask(x, page, layout, llm, model, unknown)
    errors = [err] if err else []
    inv = _assemble(x, layout, out.unknown_sections if out else None, out.welds if out else None, model, errors,
                    out.unit_weights if out else None)
    if deep_model and deep_model != model and _needs_escalation(inv):
        deep, derr = _ask(x, page, layout, llm, deep_model, unknown)
        if derr:
            errors.append(derr)
        runs = [(model, out), (deep_model, deep)]
        runs = [(m, o) for m, o in runs if o is not None]
        if runs:
            trial = {m: _assemble(x, layout, o.unknown_sections, o.welds, m, [], o.unit_weights) for m, o in runs}
            u_m = max(trial, key=lambda m: sum(u.accepted for u in trial[m].unclassified))        # first wins ties
            w_m = min(trial, key=lambda m: _rejection_rate(trial[m]))
            label = u_m if u_m == w_m else f"{u_m} (sections) + {w_m} (welds)"
            src = dict(runs)
            inv = _assemble(x, layout, src[u_m].unknown_sections, src[w_m].welds, label, errors,
                            src[u_m].unit_weights)
    after = llm.usage_summary()
    inv.usage = {f"{m}:{k}": v - before.get(m, {}).get(k, 0) for m, u in after.items() for k, v in u.items()
                 if v - before.get(m, {}).get(k, 0)}
    if cache and not any(c.id == "inventory.llm" for c in inv.checks):
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(inv.model_dump_json(indent=1), encoding="utf-8")
    return inv


def _mark(s, known):
    """'1m470 conical reducer' -> '1m470' when the leading token is a known mark; otherwise unchanged."""
    head = re.split(r"[\s,(/]", s.strip(), maxsplit=1)[0]
    return head if head in known else s.strip()


def _apply_unit_weights(inv, answers, missing) -> dict:
    """Use an OpenAI handbook unit weight for a rolled designation missing from the table. It is NOT accepted by
    agreement with the drawing (that would be circular: coped or notched parts differ legitimately, and a value
    copied from the drawing would pass); it is always shown as unverified, beside the drawing-implied kg/m."""
    used = {}
    for a in answers:
        key = a.section.replace(" ", "").upper()
        if key in missing and a.kg_per_m > 0:
            used[key] = (a.kg_per_m, "OpenAI handbook value (unverified)")
    if used:
        shown = [f"{k}: {v[0]} kg/m (drawing {missing[k]:.2f} kg/m)" if missing[k] else f"{k}: {v[0]} kg/m"
                 for k, v in used.items()]
        _set_check(inv, Check(id="boq.unit_weights", level="warn", region="inventory",
                              message=f"Unit weights from OpenAI, not in the handbook table; verify: {shown}"))
    return used


def _apply_unknown(inv, answers, rows, unknown):
    accepted = {}
    by_mark = {_mark(a.mark, set(unknown)): a for a in answers if _mark(a.mark, set(unknown)) in unknown}
    for item in inv.unclassified:
        a = by_mark.get(item.mark)
        if a is None:
            item.note = "model gave no interpretation"
            continue
        p = rows[item.mark]
        pls = [Plate(pl.thickness_mm, pl.width_mm, pl.length_mm, pl.count) for pl in a.plates]
        item.description = a.description
        written = set(_nums(p.section))
        wrong_t = sorted({pl.thickness_mm for pl in pls} - written)
        if pls and not wrong_t and weight_matches(pls, p.pc_wt, (p.net_kg or 0) / (p.qty or 1)):
            item.accepted = True
            item.note = "plate breakdown matches BOM weight (±2%) and the thickness in the section name"
            _move_to_plates(inv, p, pls, (p.qty or 0) * inv.assembly_qty)
            accepted[item.mark] = pls
        elif wrong_t:
            item.note = f"plate thickness {wrong_t} is not in the section name {p.section}: rejected"
        else:
            w = sum(pl.weight_kg for pl in pls)
            item.note = (f"plate breakdown {w:.2f} kg vs BOM {p.pc_wt} kg per piece: rejected, kept as a section"
                         if pls else "no plate breakdown: kept as a section")
    pending = [i.mark for i in inv.unclassified if not i.accepted]
    _set_check(inv, Check(id="inventory.unclassified", level="warn" if pending else "pass", region="inventory",
                          message=f"Sections needing review: {pending}" if pending else
                          "Every BOM member is classified."))
    return accepted


def _move_to_plates(inv, p, pls, q):
    for sl in inv.sections:
        if p.item_no in sl.sources:
            sl.sources.remove(p.item_no)
            sl.pieces -= q
            sl.total_length_m = round(sl.total_length_m - (p.length_mm or 0) * q / 1000, 3)
            sl.weight_kg = round(sl.weight_kg - (p.gross_kg or 0) * inv.assembly_qty, 2)
    inv.sections = [s for s in inv.sections if s.pieces > 0]
    idx = {(pl.thickness_mm, pl.grade): pl for pl in inv.plates}
    for pl in pls:
        line = idx.get((pl.thickness_mm, p.material))
        if line is None:
            line = PlateLine(thickness_mm=pl.thickness_mm, grade=p.material, pieces=0, area_m2=0, weight_kg=0)
            inv.plates.append(line)
            idx[(pl.thickness_mm, p.material)] = line
        line.pieces += pl.count * q
        line.area_m2 = round(line.area_m2 + pl.area_m2 * q, 3)
        line.weight_kg = round(line.weight_kg + pl.weight_kg * q, 2)
        line.sources.append(f"{p.item_no} (LLM breakdown {pl.width_mm:g}x{pl.thickness_mm:g})")
    inv.plates.sort(key=lambda v: (v.thickness_mm, v.grade))


def _apply_welds(inv, welds, rows, sizes):
    rejected, used = [], defaultdict(int)
    known = set(rows) | {inv.assembly_mark}
    for w in welds:
        w = w.model_copy(update={"attached": _mark(w.attached, known), "base": _mark(w.base, known)})
        att, base = rows.get(w.attached), rows.get(w.base)
        why = []
        if att is None or (base is None and w.base != inv.assembly_mark):
            why.append(f"unknown part(s) {[m for m in (w.attached, w.base) if m not in rows]}")
        if w.attached == w.base:
            why.append("a part cannot be welded to itself")
        if w.size_mm not in sizes:
            why.append(f"size {w.size_mm:g} not on sheet {sorted(sizes)}")
        if w.sides not in (1, 2):
            why.append(f"sides {w.sides} must be 1 or 2")
        run = weld_length_mm(w.edge, att, base) if att is not None else None
        if att is not None and not run:
            why.append(f"edge '{w.edge}' does not apply to {att.item_no} {att.section}")
        if att is not None and not why:
            # budget per (attached, base, edge): at most 2 joints per piece of the attached part
            key = (w.attached, w.base, w.edge)
            if w.count < 1 or used[key] + w.count > 2 * (att.qty or 1):
                why.append(f"{w.attached} would have {used[key] + w.count} '{w.edge}' joints to {w.base}; "
                           f"max {2 * (att.qty or 1)}")
            else:
                used[key] += w.count
        if why:
            rejected.append(f"{w.attached}->{w.base} {w.edge} {w.size_mm:g}mm: {'; '.join(why)}")
            continue
        length = run * w.sides
        total_m = length * w.count * inv.assembly_qty / 1000
        metal = 0.0 if w.tack else total_m * (w.size_mm ** 2 / 2) * 1e-6 * STEEL_KG_M3
        inv.welds.append(WeldLine(parts=[w.attached, w.base], size_mm=w.size_mm, length_mm=round(length, 1),
                                  count=w.count, edge=w.edge, sides=w.sides, tack=w.tack, evidence=w.evidence,
                                  total_length_m=round(total_m, 3), weld_metal_kg=round(metal, 3)))
    inv.rejected_welds = rejected
    inv.weld_metal_kg = round(sum(w.weld_metal_kg for w in inv.welds), 2)
    inv.electrode_kg = round(inv.weld_metal_kg * ELECTRODE_PER_WELD_METAL, 2)
    _set_check(inv, Check(id="inventory.welds", level="warn" if rejected else "pass", region="inventory",
                          message=(f"{len(inv.welds)} weld runs accepted"
                                   + (f"; {len(rejected)} rejected: " + " | ".join(rejected[:8]) if rejected else ""))))
    share = inv.weld_metal_kg / inv.total_steel_kg if inv.total_steel_kg else 0
    seams = any("(WH " in s or "(T " in s for p in inv.plates for s in p.sources)
    _set_check(inv, Check(
        id="inventory.weld_estimate", level="warn", region="inventory",
        message=f"Weld metal {inv.weld_metal_kg} kg ({share:.2%} of steel; fabricated steel is typically 1-2%) is a "
                "model-read estimate, unverified: topology read by OpenAI, lengths computed from the BOM, tack welds "
                "excluded" + ("; flange-to-web seams of built-up members are not drawn and not included" if seams
                              else "") + "."))
