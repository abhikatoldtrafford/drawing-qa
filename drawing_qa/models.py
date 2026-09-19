"""Typed records for one extracted drawing page. Everything the UI, validator,
exporter and chat see goes through these models."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

Box = tuple[float, float, float, float]


class BomRow(BaseModel):
    erection_mark: str = ""
    item_no: str = ""
    section: str = ""
    length_mm: Optional[float] = None
    qty: Optional[int] = None
    pc_wt: Optional[float] = None
    net_kg: Optional[float] = None
    gross_kg: Optional[float] = None
    material: str = ""
    remarks: str = ""
    surface_area_m2: Optional[float] = None
    bbox: Box


class BomTotals(BaseModel):
    net_kg: Optional[float] = None
    gross_kg: Optional[float] = None
    surface_area_m2: Optional[float] = None


class Bom(BaseModel):
    assembly: Optional[BomRow] = None
    parts: list[BomRow] = Field(default_factory=list)
    totals: BomTotals = Field(default_factory=BomTotals)
    bbox: Box


class AbstractRow(BaseModel):
    sr: int
    description: str
    total_wt: Optional[float] = None


class Abstract(BaseModel):
    rows: list[AbstractRow] = Field(default_factory=list)
    total_kg: Optional[float] = None


class BoltRow(BaseModel):
    assembly_mark: str = ""
    bolt_dia: str = ""
    bolt_type: str = ""
    bolt_length: str = ""
    bolt_qty: str = ""
    bolt_grade: str = ""
    bolt_spec: str = ""
    bolt_material: str = ""
    nut_dia: str = ""
    nut_qty: str = ""
    nut_grade: str = ""
    nut_spec: str = ""
    nut_material: str = ""
    washer_dia: str = ""
    washer_type: str = ""
    washer_qty: str = ""
    washer_spec: str = ""
    washer_material: str = ""
    taper_dia: str = ""
    taper_type: str = ""
    taper_qty: str = ""
    taper_spec: str = ""
    taper_material: str = ""


class Person(BaseModel):
    name: str = ""
    date: str = ""


class TitleBlock(BaseModel):
    drawing_no: str = ""
    rev: str = ""
    sheet_no: str = ""
    sheet_size: str = ""
    weight_kg: Optional[float] = None
    department: str = ""
    equip_area: str = ""
    project: str = ""
    title_lines: list[str] = Field(default_factory=list)
    drn: Person = Field(default_factory=Person)
    chd: Person = Field(default_factory=Person)
    app: Person = Field(default_factory=Person)


class MarkLocation(BaseModel):
    mark_no: str = ""
    grid_location: str = ""
    level: str = ""


class RevisionRow(BaseModel):
    rev: str
    date: str
    description: str
    drn: str = ""
    chd: str = ""
    app: str = ""


class ViewLabel(BaseModel):
    label: str               # "A - A" or "MARK. NO:- 4p637"
    kind: Literal["section", "detail"]
    ref: str                 # "A" or "4p637"
    scale: str = ""
    bbox: Box
    cell: str = ""


class Check(BaseModel):
    id: str
    level: Literal["pass", "warn", "fail"]
    message: str
    region: str = ""


class PageExtract(BaseModel):
    source_file: str
    file_sha256: str
    page_index: int
    page_size_pt: tuple[float, float]
    has_text_layer: bool
    title_block: TitleBlock = Field(default_factory=TitleBlock)
    mark_locations: list[MarkLocation] = Field(default_factory=list)   # one row per erected instance
    bom: Optional[Bom] = None
    abstract: Optional[Abstract] = None
    bolts: list[BoltRow] = Field(default_factory=list)
    revisions: list[RevisionRow] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    part_marks: list[str] = Field(default_factory=list)
    view_labels: list[ViewLabel] = Field(default_factory=list)
    regions: dict[str, Box] = Field(default_factory=dict)
    bom_crosscheck: Optional[list[str]] = None   # find_tables() vs parse_bom mismatches; None = unavailable
    pipeline_errors: list[Check] = Field(default_factory=list)   # parser errors (kept across cache loads)
    checks: list[Check] = Field(default_factory=list)


# ---------------------------------------------------------------- inventory (per page)
class PlateLine(BaseModel):
    thickness_mm: float
    grade: str
    pieces: int
    area_m2: float
    weight_kg: float
    sources: list[str] = Field(default_factory=list)       # BOM marks, "3m471 (WH decomposed)", ...


class SectionLine(BaseModel):
    profile: str                                           # "ISA75X75X8", "PIPE508*6"
    family: str                                            # angle | channel | pipe | round | other
    grade: str
    pieces: int
    total_length_m: float
    weight_kg: float
    sources: list[str] = Field(default_factory=list)


class FastenerLine(BaseModel):
    item: Literal["bolt", "nut", "plain washer", "taper washer"]
    dia_mm: str
    length_mm: str = ""
    type: str = ""
    grade: str = ""
    spec: str = ""
    material: str = ""
    qty: int
    connected_assemblies: list[str] = Field(default_factory=list)


class WeldLine(BaseModel):
    parts: list[str]                                       # [attached part, base part]
    size_mm: float
    length_mm: float                                       # per joint, computed from BOM geometry x sides
    count: int                                             # joints per assembly
    edge: str = ""                                         # length | width | perimeter | circumference
    sides: int = 1
    tack: bool = False                                     # tack welds carry no weld-metal estimate
    evidence: str = ""                                     # grid cell / view label the model cited
    total_length_m: float = 0.0                            # × count × assembly qty
    weld_metal_kg: float = 0.0


class InventoryItem(BaseModel):
    """A BOM member the code could not classify, as interpreted by the LLM (flagged for review)."""
    mark: str
    section: str
    description: str
    accepted: bool
    note: str = ""


class Inventory(BaseModel):
    drawing_no: str
    assembly_mark: str
    assembly_qty: int
    plates: list[PlateLine] = Field(default_factory=list)
    sections: list[SectionLine] = Field(default_factory=list)
    fasteners: list[FastenerLine] = Field(default_factory=list)
    unclassified: list[InventoryItem] = Field(default_factory=list)
    welds: list[WeldLine] = Field(default_factory=list)
    rejected_welds: list[str] = Field(default_factory=list)  # model welds that failed the guardrails, with reasons
    paint_area_m2: Optional[float] = None
    weld_metal_kg: float = 0.0
    electrode_kg: float = 0.0
    total_steel_kg: float = 0.0                            # Σ BOM gross × assembly qty
    model: str = ""                                        # model that produced the OpenAI-assisted parts
    checks: list[Check] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
