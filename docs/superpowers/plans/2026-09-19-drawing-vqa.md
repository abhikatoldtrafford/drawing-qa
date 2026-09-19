# Drawing Q&A Implementation Plan (v2: deterministic extract, full-page OpenAI Q&A, inventory)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local Streamlit app for one page at a time of a Tekla fabrication-drawing PDF. It:
- extracts a validated record (title block, BOM, abstract, bolts, revisions, notes, erection locations, view labels) with PyMuPDF only;
- builds a material inventory (plates, sections, fasteners, paint, welds);
- answers questions with OpenAI, which reads the whole sheet image and the PyMuPDF text;
- exports everything.

**Architecture:**
- **Extract.** PyMuPDF reads the page once into a `PageLayout`. Deterministic parsers produce typed Pydantic records. Checks guard every number: arithmetic, marks, abstract-by-section, and a second independent BOM parse.
- **Page context.** Built once per page and placed first in every OpenAI request: the full text layer tagged with sheet-grid cells, plus high-res tiles of the whole sheet. Because the prefix is identical, OpenAI's prompt cache serves most of it on later calls.
- **Chat** uses the page context, the extract JSON (plus the inventory JSON when built) and zoom/search tools.
- **Inventory** is deterministic for plates, sections, fasteners and paint, with WH/T built-ups decomposed into plates. One OpenAI call adds welds and interpretations of unknown sections. Guardrails reject anything the sheet can't support, and the call escalates once to `gpt-5.5` when the answer is weak.

**Tech Stack:** Python 3.13, PyMuPDF ≥1.28, openai ≥1.72 (Responses API: `responses.parse` + function tools), Pydantic 2, Streamlit ≥1.50, pandas + openpyxl, pytest.

**Spec:** `docs/superpowers/specs/2026-09-19-drawing-vqa-design.md`

## Global Constraints

- Platform: Windows 11, Python 3.13. Run tests with `python -m pytest` (the `pytest` script is not on PATH).
- Models: `gpt-5.4-mini` by default, `gpt-5.5` for escalation and deep mode. Override with `DQA_MODEL` / `DQA_DEEP_MODEL`. The API key comes only from `OPENAI_API_KEY` and is never written to disk or logs.
- **Extraction makes no model calls.** OpenAI is used only for Q&A (chat) and the inventory's weld / unknown-section step.
- Every OpenAI request carries the whole page: the grid-tagged text layer and the sheet tiles (4 on A1, 6 on A0).
- Numbers (weights, quantities, lengths) come from the PyMuPDF extract. An OpenAI-proposed plate breakdown is used only if its steel weight is within 2% of the BOM member. Weld figures are estimates and labelled as such.
- An OpenAI/API failure never crashes the UI or discards deterministic data. It becomes an `inventory.llm` warning, or an `st.error` in chat.
- Vector PDFs only, no OCR. A page with fewer than 50 words gives `has_text_layer=False` and a `text_layer` fail check.
- Sample PDFs stay in the repo root and are git-ignored (proprietary). Tests find them via `DQA_SAMPLES` (default: repo root) and skip when absent. Offline tests never call OpenAI; they use `tests/fakes.py`.
- Every source file below was run against the 5 sample drawings before this plan was written: 122 tests pass. Copy code verbatim. If a golden value disagrees with a sheet, stop and report; do not loosen the test.

## File map

| File | Responsibility |
|---|---|
| `drawing_qa/config.py` | `Settings` (models, cache dir, render sizes, chat limits, API timeout/retries), `SCHEMA_VERSION` |
| `drawing_qa/geometry.py` | word-tuple helpers: `cluster`, `num`, `join_tokens`, `GridMap` (sheet border grid) |
| `drawing_qa/models.py` | Pydantic records: `PageExtract` and parts, `Check`, `Inventory` and its lines |
| `drawing_qa/layout.py` | `PageLayout`: words, text lines, line segments, grid, `find`, `words_in` |
| `drawing_qa/parsers/bom.py` | BILL OF MATERIALS → `Bom`; `cross_check_bom` (clipped `find_tables`) |
| `drawing_qa/parsers/tables.py` | abstract, permanent bolts, revisions, notes, erection-location rows |
| `drawing_qa/parsers/titleblock.py` | title block from bordered cells |
| `drawing_qa/parsers/views.py` | part marks on the sheet, view labels (+ scale, grid cell) |
| `drawing_qa/render.py` | region crops / overview / tiles as PNG |
| `drawing_qa/llm.py` | OpenAI wrapper: `parse`, `parse_content`, `create`, per-model token accounting |
| `drawing_qa/validate.py` | guardrail checks over the extract |
| `drawing_qa/extract.py` | deterministic pipeline + disk cache |
| `drawing_qa/context.py` | whole-page model input (grid-tagged text + tiles) |
| `drawing_qa/sections.py` | section families, WH/T plate recipes, weight check |
| `drawing_qa/inventory.py` | deterministic inventory + OpenAI weld/unknown step + guardrails + escalation |
| `drawing_qa/chat.py` | multi-turn Q&A with full-page context and tools |
| `drawing_qa/export.py` | Excel (extract + inventory sheets) / CSV / JSON |
| `app.py` | Streamlit UI |
| `scripts/live_smoke.py` | opt-in real-API end-to-end run |

---

### Task 1: Project scaffold, geometry helpers, data models

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `.gitignore`, `drawing_qa/__init__.py` (empty), `drawing_qa/config.py`, `drawing_qa/geometry.py`, `drawing_qa/models.py`, `tests/__init__.py` (empty), `tests/conftest.py`, `tests/test_geometry.py`

**Interfaces:**
- Produces:
  - `Settings(model, deep_model, cache_dir, crop_dpi, crop_max_px, chat_max_tool_rounds, chat_keep_turns, api_timeout_s, api_max_retries)`. Env vars are read when `Settings()` is constructed, not at import.
  - `SCHEMA_VERSION`.
  - Geometry: `cluster(values, tol)`, `num(s) -> float|None`, `xc(w)`, `yc(w)`, and `join_tokens(words, gap=1.5)`. `join_tokens` concatenates touching fragments, drops exact duplicates, and never inserts characters.
  - `GridMap.from_words(words)`, `.ok`, `.cell_of(x, y) -> "E7"`, `.cell_rect("E7")` (raises `ValueError("unknown grid cell …")`).
  - Models: `PageExtract` (`title_block`, `mark_locations: list`, `bom`, `abstract`, `bolts`, `revisions`, `notes`, `part_marks`, `view_labels`, `regions`, `bom_crosscheck`, `pipeline_errors`, `checks`) and `Inventory` (`plates`, `sections`, `fasteners`, `unclassified`, `welds`, `rejected_welds`, `paint_area_m2`, `weld_metal_kg`, `electrode_kg`, `total_steel_kg`, `model`, `checks`, `usage`).
  - Test helpers: `GOLDEN`, `TITLE`, `sample_path(drg)`, fixtures `layouts` and `settings`, and `det(drg, settings)` (memoised deterministic extract, returned as a deep copy).
- Words are PyMuPDF tuples `(x0, y0, x1, y1, text, block, line, word)` everywhere.

- [ ] **Step 1: Initialise the repo and install dependencies**

```powershell
cd D:\ed
git init
python -m pip install --default-timeout=300 -r requirements.txt   # after creating the file below
```

`requirements.txt`:
```text
pymupdf>=1.28,<2   # parsers measured on 1.28 (no decimal-split words)
openai>=1.72
pydantic>=2.7
streamlit>=1.50
pandas>=2.2
openpyxl>=3.1
pytest>=8
```

`pytest.ini`:
```ini
[pytest]
testpaths = tests
pythonpath = .
```

`.gitignore`:
```text
__pycache__/
.pytest_cache/
.dqa_cache/
*.pyc
# proprietary client drawings: keep local, never commit
*.pdf
```

- [ ] **Step 2: Write the test helpers and failing geometry tests**

`tests/conftest.py`:
- `GOLDEN` was read off the 5 sheets: BOM grand-total line, abstract, bolt list, mark box.
- `TITLE` is title-block text that the independent auditor checked against the rendered sheets.

```python
import os
from pathlib import Path

import pymupdf
import pytest

SAMPLES = Path(os.getenv("DQA_SAMPLES", Path(__file__).resolve().parents[1]))   # sample PDFs live in the repo root

# Golden values read off the sample sheets (BOM grand-total line, abstract, bolt list, mark box).
GOLDEN = {
    "09970": dict(asm="4DC3", asm_qty=1, parts=11, gross=432.62, net=425.11, area=9.71, abstract_rows=6,
                  bolts=4, rev="0", size="A1", labels=15, level="EL. +4.475"),
    "14278": dict(asm="3C1", asm_qty=1, parts=43, gross=33496.76, net=31196.03, area=243.73, abstract_rows=15,
                  bolts=0, rev="1", size="A0", labels=9, level="EL. +9.675"),
    "14281": dict(asm="3C2", asm_qty=1, parts=71, gross=26121.53, net=25826.95, area=254.57, abstract_rows=14,
                  bolts=2, rev="0", size="A0", labels=27, level="EL. +24.500"),
    "16362": dict(asm="1DC1", asm_qty=2, parts=7, gross=350.52, net=161.64, area=9.72, abstract_rows=6,
                  bolts=0, rev="0", size="A1", labels=8, level="EL. +17.065"),
    "16807": dict(asm="2GU1", asm_qty=1, parts=8, gross=976.84, net=971.51, area=39.16, abstract_rows=4,
                  bolts=0, rev="0", size="A0", labels=11, level="EL. +17.115"),
}


# Title-block text, checked against the rendered sheets by the independent auditor (rounds 1-3).
TITLE = {
    "09970": dict(equip="HOT ROLLED PICKLING GALVANIZED LINE (HRPGL)", project="", persons=("SKS/NBT", "27.02.2026"),
                  lines=["SHED FOR POCIL PLOT LOT-4", "DETAIL OF DOWN COMER MKD AS -4DC3"]),
    "14278": dict(equip="HOT ROLLED PICKLING GALVANIZING LINE (HRPGL)", project="CRC WEST TARAPUR, HRPGL",
                  persons=("TML/NBT", "01.06.2026"),
                  lines=["PROCESS BAY : POT AREA WITH EXIT ECR LOT-3", "DETAIL OF COLUMN MKD AS -3C1"]),
    "14281": dict(equip="HOT ROLLED PICKLING GALVANIZING LINE (HRPGL)", project="CRC WEST TARAPUR, HRPGL",
                  persons=("TML/NBT", "01.06.2026"),
                  lines=["PROCESS BAY : POT AREA WITH EXIT ECR LOT-3", "DETAIL OF COLUMN MKD AS -3C2"]),
    "16362": dict(equip="HOT ROLLED PICKLING GALVANIZED LINE (HRPGL)", project="", persons=("SKS/NBT", "09.07.2026"),
                  lines=["SHED FOR POCIL PLOT LOT-1", "DETAIL OF DOWN COMER MKD AS -1DC1"]),
    "16807": dict(equip="HOT ROLLED PICKLING GALVANIZED LINE (HRPGL)", project="", persons=("SKS/NBT", "18.07.2026"),
                  lines=["SHED FOR POCIL PLOT LOT-2", "DETAIL OF GUTTER MKD AS -2GU1"]),
}


def sample_path(drg):
    hits = sorted(SAMPLES.glob(f"*{drg}*.pdf"))
    if not hits:
        pytest.skip(f"sample drawing {drg} not found in {SAMPLES}")
    return hits[0]


@pytest.fixture(scope="session")
def layouts():
    cache = {}

    def get(drg):
        from drawing_qa.layout import PageLayout      # lazy: layout.py arrives in Task 2
        if drg not in cache:
            cache[drg] = PageLayout.from_page(pymupdf.open(sample_path(drg))[0])
        return cache[drg]
    return get


@pytest.fixture
def settings(tmp_path):
    from drawing_qa.config import Settings
    return Settings(model="mini", deep_model="deep", cache_dir=str(tmp_path / "cache"))


_DET = {}


def det(drg, settings):
    """Deterministic (no-LLM) extract of a sample sheet. Memoised (find_tables on A0 takes seconds);
    returns a deep copy so tests may mutate it."""
    from drawing_qa.extract import extract_page
    if drg not in _DET:
        p = sample_path(drg)
        _DET[drg] = extract_page(p.read_bytes(), 0, p.name, settings=settings, use_cache=False)
    return _DET[drg].model_copy(deep=True)
```

`tests/test_geometry.py`:
```python
from drawing_qa.geometry import GridMap, cluster, join_tokens, num


def test_cluster_groups_close_values():
    assert cluster([10, 1, 2, 11, 30], tol=2) == [[1, 2], [10, 11], [30]]


def test_num_parses_and_rejects():
    assert num("1,234.5") == 1234.5
    assert num("E350A") is None
    assert num(None) is None


def test_join_tokens_concatenates_touching_fragments_without_inventing_characters():
    words = [(20.5, 0, 50, 10, "508*6"), (0, 0, 20, 10, "PIPE"), (140, 0, 150, 10, "kg")]
    assert [t[4] for t in join_tokens(words)] == ["PIPE508*6", "kg"]


def test_join_tokens_drops_duplicate_overlapping_word():
    words = [(100, 0, 110, 10, "75"), (100.3, 0, 110.3, 10, "75"), (130, 0, 140, 10, "75")]
    assert [t[4] for t in join_tokens(words)] == ["75", "75"]


def _grid():
    cols = [(100 + 50 * i, i + 1) for i in range(10)]          # x=100..550 -> 1..10
    rows = [(100 + 40 * i, ch) for i, ch in enumerate("ABCDEFGHJK")]
    return GridMap(cols, rows)


def test_grid_cell_of_and_rect_roundtrip():
    g = _grid()
    assert g.cell_of(151, 141) == "B2"
    x0, y0, x1, y1 = g.cell_rect("B2")
    assert (x0, y0, x1, y1) == (125, 120, 175, 160)
    assert g.cell_of((x0 + x1) / 2, (y0 + y1) / 2) == "B2"


def test_grid_rejects_unknown_cell():
    import pytest
    with pytest.raises(ValueError, match="unknown grid cell 'Z99'"):
        _grid().cell_rect("Z99")
```

- [ ] **Step 3: Run to verify failure**

Run: `python -m pytest tests/test_geometry.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'drawing_qa'`.

- [ ] **Step 4: Implement config, geometry, models**

`drawing_qa/config.py`:
```python
import os
from dataclasses import dataclass, field

SCHEMA_VERSION = 3   # bump when PageExtract or extraction logic changes: invalidates the disk cache


def _env(name, default):
    return field(default_factory=lambda: os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    """Read from the environment when constructed (not at import), so tests and the app see current values."""
    model: str = _env("DQA_MODEL", "gpt-5.4-mini")
    deep_model: str = _env("DQA_DEEP_MODEL", "gpt-5.5")
    cache_dir: str = _env("DQA_CACHE_DIR", ".dqa_cache")
    crop_dpi: int = 200
    crop_max_px: int = 2400
    chat_max_tool_rounds: int = 6
    chat_keep_turns: int = 8
    api_timeout_s: float = 120.0
    api_max_retries: int = 2
```

`drawing_qa/geometry.py`:
```python
"""Small, dependency-free helpers over PyMuPDF word tuples (x0, y0, x1, y1, text, ...)."""
import re

Word = tuple  # (x0, y0, x1, y1, text, block, line, word)


def cluster(values, tol):
    """Group sorted numbers whose consecutive gap is <= tol."""
    groups = []
    for v in sorted(values):
        if groups and v - groups[-1][-1] <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return groups


def num(s):
    """Parse '1,234.5' -> 1234.5; anything else -> None."""
    try:
        return float(str(s).replace(",", ""))
    except (TypeError, ValueError):
        return None


def xc(w):
    return (w[0] + w[2]) / 2


def yc(w):
    return (w[1] + w[3]) / 2


def join_tokens(words, gap=1.5):
    """Order words left to right, drop exact duplicates (same text drawn twice at the same spot) and
    concatenate fragments that touch (-0.5..gap pt apart). Never inserts characters."""
    out = []
    for w in sorted(words, key=lambda w: w[0]):
        if out and w[4] == out[-1][4] and abs(w[0] - out[-1][0]) < 1:
            continue
        if out and -0.5 <= w[0] - out[-1][2] <= gap:
            out[-1] = (out[-1][0], min(out[-1][1], w[1]), w[2], max(out[-1][3], w[3]), out[-1][4] + w[4])
        else:
            out.append(tuple(w[:5]))
    return out


class GridMap:
    """Sheet border labels (rows A..R top-down, columns 1..24 left-right)."""

    def __init__(self, col_x, row_y):
        self.col_x = col_x  # [(x_center, int)]
        self.row_y = row_y  # [(y_center, 'A')]

    @classmethod
    def from_words(cls, words):
        def aligned(cands, axis, min_n):
            groups = {}
            for w in cands:
                key = round((xc(w) if axis == "x" else yc(w)) / 4)
                groups.setdefault(key, {})[w[4]] = w
            return [g for g in groups.values() if len(g) >= min_n]

        letters = [w for w in words if re.fullmatch(r"[A-Z]", w[4])]
        numbers = [w for w in words if re.fullmatch(r"\d{1,2}", w[4])]
        row_y, col_x = {}, {}
        for g in aligned(letters, "x", 8):
            for k, w in g.items():
                row_y.setdefault(k, []).append(yc(w))
        for g in aligned(numbers, "y", 8):
            for k, w in g.items():
                col_x.setdefault(int(k), []).append(xc(w))
        return cls(sorted((sum(v) / len(v), k) for k, v in col_x.items()),
                   sorted((sum(v) / len(v), k) for k, v in row_y.items()))

    @property
    def ok(self):
        return len(self.col_x) >= 8 and len(self.row_y) >= 8

    def cell_of(self, x, y):
        if not self.ok:
            return ""
        c = min(self.col_x, key=lambda t: abs(t[0] - x))[1]
        r = min(self.row_y, key=lambda t: abs(t[0] - y))[1]
        return f"{r}{c}"

    def cell_rect(self, cell):
        """'E7' -> (x0, y0, x1, y1) spanning the midpoints to neighbouring labels."""
        m = re.fullmatch(r"([A-Z])(\d{1,2})", cell.strip().upper())
        if not m or not self.ok:
            raise ValueError(f"unknown grid cell {cell!r}")
        r, c = m.group(1), int(m.group(2))
        xs = [t[0] for t in self.col_x]
        ys = [t[0] for t in self.row_y]
        col_keys, row_keys = [t[1] for t in self.col_x], [t[1] for t in self.row_y]
        if c not in col_keys or r not in row_keys:
            raise ValueError(f"unknown grid cell {cell!r}: rows {row_keys[0]}-{row_keys[-1]}, "
                             f"columns {col_keys[0]}-{col_keys[-1]}")
        ci, ri = col_keys.index(c), row_keys.index(r)
        half_w = (xs[-1] - xs[0]) / (len(xs) - 1) / 2
        half_h = (ys[-1] - ys[0]) / (len(ys) - 1) / 2
        return (xs[ci] - half_w, ys[ri] - half_h, xs[ci] + half_w, ys[ri] + half_h)
```

`drawing_qa/models.py`:
```python
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
    parts: list[str]
    size_mm: float
    length_mm: float                                       # per joint
    count: int                                             # joints per assembly
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
```

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest tests/test_geometry.py -q`
Expected: `6 passed`.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini .gitignore drawing_qa tests docs
git commit -m "feat: scaffold, geometry helpers and data models"
```

---

### Task 2: PageLayout and BILL OF MATERIALS parser (+ independent cross-check)

**Files:**
- Create: `drawing_qa/layout.py`, `drawing_qa/parsers/__init__.py` (empty), `drawing_qa/parsers/bom.py`, `tests/test_bom.py`

**Interfaces:**
- Consumes: `GridMap`, `cluster`, `join_tokens`, `num`, `xc`, `yc`; `Bom`, `BomRow`, `BomTotals`.
- Produces:
  - `PageLayout.from_page(page)`, with attributes `.page .words .width .height .has_text_layer .lines .segments .grid` and methods `.find(text, clip=None)` and `.words_in(rect)`.
  - `open_pdf(bytes)`, `sha256(bytes)`.
  - `parse_bom(layout) -> Bom | None`.
  - `cross_check_bom(layout, bom) -> list[str] | None`. It compares section, length, qty, gross and material. Columns are located by header text; it returns `None` when `find_tables` finds no table or its header can't be mapped.

Layout facts, verified independently by the auditor:
- Rows are separated by full-width rules and the numeric columns have vertical rulings, but the MARK/ITEM/SECTION block has none.
- Page-wide `find_tables()` merges the ABSTRACT into the BOM. Clipped to the BOM frame, it reads the same rows as `parse_bom` on all 5 sheets, and it is the only check that catches length or material errors.
- Numeric column edges come from header words, snapped to a ruling between neighbouring headers. Rows come from word y-centres.
- A stray line off the page on 14278 (x≈5221–8048) means the frame must span the title and stay on the page.

- [ ] **Step 1: Write failing tests**

`tests/test_bom.py`:
```python
import pytest

from drawing_qa.parsers.bom import parse_bom

from .conftest import GOLDEN

DRGS = sorted(GOLDEN)


@pytest.mark.parametrize("drg", DRGS)
def test_bom_matches_golden(layouts, drg):
    g, b = GOLDEN[drg], parse_bom(layouts(drg))
    assert b.assembly.erection_mark == g["asm"]
    assert b.assembly.qty == g["asm_qty"]
    assert len(b.parts) == g["parts"]
    assert (b.totals.gross_kg, b.totals.net_kg, b.totals.surface_area_m2) == (g["gross"], g["net"], g["area"])
    assert sum(p.gross_kg for p in b.parts) * g["asm_qty"] == pytest.approx(g["gross"], abs=0.05)
    for p in b.parts:
        assert p.item_no and p.section and p.material and p.qty and p.length_mm, p


def test_bom_row_values_09970(layouts):
    rows = {p.item_no: p for p in parse_bom(layouts("09970")).parts}
    r = rows["4p660"]
    assert (r.section, r.length_mm, r.qty, r.pc_wt, r.net_kg, r.gross_kg, r.material, r.surface_area_m2) == \
        ("PL10*358", 358.3, 2, 10.08, 15.88, 20.15, "E350A", 0.21)
    assert rows["4m706"].section == "PIPE219.1*5.4"


def test_bom_section_with_long_name_16362(layouts):
    rows = {p.item_no: p for p in parse_bom(layouts("16362")).parts}
    assert rows["1m470"].section == "SPD508*508*608*608*8"
    assert rows["1m473"].qty == 22


@pytest.mark.parametrize("drg,cols,rows", [("09970", 16, 12), ("14281", 24, 16)])
def test_sheet_grid_detected(layouts, drg, cols, rows):
    g = layouts(drg).grid
    assert (len(g.col_x), len(g.row_y)) == (cols, rows)


@pytest.mark.parametrize("drg", DRGS)
def test_find_tables_crosscheck_agrees_and_catches_corruption(layouts, drg):
    from drawing_qa.parsers.bom import cross_check_bom
    L = layouts(drg)
    b = parse_bom(L)
    assert cross_check_bom(L, b) == []
    b.parts[1].length_mm *= 10                     # arithmetic checks cannot see length or material errors
    b.parts[2].material = "E250A" if b.parts[2].material != "E250A" else "E350A"
    assert len(cross_check_bom(L, b)) == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_bom.py -q`
Expected: `ModuleNotFoundError: No module named 'drawing_qa.parsers'`.

- [ ] **Step 3: Implement**

`drawing_qa/layout.py`:
```python
"""One-pass PyMuPDF read of a page: words, text lines, vector segments, sheet grid.
Parsers only consume a PageLayout, never the raw page, so they are cheap to test."""
import hashlib
from dataclasses import dataclass, field
from functools import cached_property

import pymupdf

from .geometry import GridMap


@dataclass
class TextLine:
    text: str
    bbox: tuple[float, float, float, float]
    horizontal: bool


@dataclass
class PageLayout:
    page: pymupdf.Page
    words: list = field(default_factory=list)

    @classmethod
    def from_page(cls, page):
        return cls(page=page, words=page.get_text("words"))

    @property
    def width(self):
        return self.page.rect.width

    @property
    def height(self):
        return self.page.rect.height

    @property
    def has_text_layer(self):
        return len(self.words) >= 50

    @cached_property
    def lines(self):
        out = []
        for b in self.page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                text = " ".join(" ".join(s["text"] for s in ln["spans"]).split())
                if text:
                    out.append(TextLine(text, tuple(ln["bbox"]), abs(ln["dir"][1]) < 0.01))
        return out

    @cached_property
    def segments(self):
        """Straight line segments as (x0, y0, x1, y1), on-page only."""
        segs = []
        W, H = self.width, self.height
        for d in self.page.get_drawings():
            for it in d["items"]:
                if it[0] == "l":
                    a, b = it[1], it[2]
                    if 0 <= a.x <= W and 0 <= b.x <= W and 0 <= a.y <= H and 0 <= b.y <= H:
                        segs.append((a.x, a.y, b.x, b.y))
        return segs

    @cached_property
    def grid(self):
        return GridMap.from_words(self.words)

    def find(self, text, clip=None):
        """All hit rects of an exact phrase (PyMuPDF search is case-insensitive)."""
        return self.page.search_for(text, clip=clip) if clip is not None else self.page.search_for(text)

    def words_in(self, rect):
        x0, y0, x1, y1 = rect
        return [w for w in self.words if x0 <= (w[0] + w[2]) / 2 <= x1 and y0 <= (w[1] + w[3]) / 2 <= y1]


def open_pdf(data: bytes):
    return pymupdf.open(stream=data, filetype="pdf")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
```

`drawing_qa/parsers/bom.py`:
```python
"""Tekla 'BILL OF MATERIALS' table.

Layout facts (checked independently on the 5 samples, PyMuPDF 1.28):
- Header frame: the longest horizontal line just under the title that spans it. Sheet 14278 also has a
  stray line off the page (x 5221-8048), so the frame must span the title and lie on the page.
- Rows are separated by full-width rules and the numeric columns have vertical rulings, but the
  MARK | ITEM | SECTION block has no vertical rulings, and page-wide find_tables() merges ABSTRACT into
  the BOM. So numeric column edges come from the header words (snapped to a ruling between two headers
  when present), the left block is split by tokens, and rows come from clustering word y-centres.
- find_tables() clipped to the BOM frame reads the same rows; cross_check_bom() uses it as an
  independent second parse.
- The first row with a value in the ERECTION MARK column is the assembly row.
"""
import re

import pymupdf

from ..geometry import cluster, join_tokens, num, xc, yc
from ..models import Bom, BomRow, BomTotals

HEADER_ANCHORS = ["LENGTH", "Qty./", "PC.", "NET(KG)", "GROSS(KG)", "MATERIAL", "REMARKS", "SURFACE"]
MARK_CELL = re.compile(r"^\d[A-Za-z]{1,4}\d+$")
CROSS_HEADERS = {"item": "ITEM", "section": "SECTION", "length": "LENGTH", "qty": "QTY",
                 "gross": "GROSS", "material": "MATERIAL"}
NUMERIC_COLS = ["length_mm", "qty", "pc_wt", "net_kg", "gross_kg", "material", "remarks", "surface_area_m2"]


def _frame(layout, title):
    best = None
    for x0, y0, x1, y1 in layout.segments:
        if abs(y0 - y1) < 0.5 and 0 < y0 - title.y1 < 15:
            a, b = sorted((x0, x1))
            if a < title.x0 and b > title.x1 and (best is None or b - a > best[1] - best[0]):
                best = (a, b, y0)
    return best


def _to_int(s):
    v = num(s)
    return int(v) if v is not None and v == int(v) else None


def parse_bom(layout):
    titles, totals = layout.find("BILL OF MATERIALS"), layout.find("GRAND TOTAL")
    if not titles or not totals:
        return None
    title, total = titles[0], totals[0]
    frame = _frame(layout, title)
    if frame is None:
        return None
    x_left, x_right, y_top = frame
    region = (x_left - 1, y_top - 1, x_right + 1, total.y1 + 2)
    words = layout.words_in(region)
    hdr = {}
    for w in words:
        if w[1] < y_top + 45 and w[4] not in hdr:
            hdr[w[4]] = w
    missing = [k for k in HEADER_ANCHORS + ["ITEM"] if k not in hdr]
    if missing:
        raise ValueError(f"BOM header words not found: {missing}")
    y_hdr_bottom = max(hdr[k][3] for k in ("MARK.", "NO.", "mm.") if k in hdr)
    xs = [s[0] for s in layout.segments
          if abs(s[0] - s[2]) < 0.5 and x_left + 5 < s[0] < x_right - 5 and region[1] <= min(s[1], s[3]) <= region[3]]
    rulings = sorted(sum(g) / len(g) for g in cluster(xs, 1.5) if len(g) >= 3)
    anchors = [hdr[k] for k in HEADER_ANCHORS]
    lefts = [x for x in rulings if x < anchors[0][0]]
    edges = [max(lefts) if lefts else anchors[0][0] - 5]
    for a, b in zip(anchors, anchors[1:]):
        between = [x for x in rulings if a[2] - 2 <= x <= b[0] + 2]
        edges.append(between[0] if between else (a[2] + b[0]) / 2)
    edges.append(x_right)
    body = [w for w in words if y_hdr_bottom + 1 < yc(w) < total.y0 - 1]
    row_ys = [sum(g) / len(g) for g in cluster([yc(w) for w in body if w[0] >= edges[0]], 4)]
    item_hdr_x0 = hdr["ITEM"][0]
    assembly, parts = None, []
    for i, y in enumerate(row_ys):
        y0 = (row_ys[i - 1] + y) / 2 if i else y_hdr_bottom + 1
        y1 = (y + row_ys[i + 1]) / 2 if i + 1 < len(row_ys) else total.y0 - 1
        rw = [w for w in body if y0 <= yc(w) < y1]
        cells = {"erection_mark": "", "item_no": "", "section": ""}
        rest = []
        for t in join_tokens([w for w in rw if w[2] <= edges[0] + 1]):
            if t[0] < item_hdr_x0 - 25 and not cells["erection_mark"]:
                cells["erection_mark"] = t[4]
            else:
                rest.append(t[4])
        if rest:
            cells["item_no"], cells["section"] = rest[0], " ".join(rest[1:])
        for name, cx0, cx1 in zip(NUMERIC_COLS, edges, edges[1:]):
            cells[name] = " ".join(t[4] for t in join_tokens([w for w in rw if cx0 <= xc(w) < cx1]))
        row = BomRow(
            erection_mark=cells["erection_mark"], item_no=cells["item_no"], section=cells["section"],
            length_mm=num(cells["length_mm"]), qty=_to_int(cells["qty"]), pc_wt=num(cells["pc_wt"]),
            net_kg=num(cells["net_kg"]), gross_kg=num(cells["gross_kg"]), material=cells["material"],
            remarks=cells["remarks"], surface_area_m2=num(cells["surface_area_m2"]),
            bbox=(x_left, y0, x_right, y1),
        )
        if row.erection_mark and assembly is None:
            assembly = row
        else:
            parts.append(row)
    # grand total line: "<net> GRAND TOTAL WEIGHT IN KGS = <gross> ... <area> M 2"
    line = join_tokens(layout.words_in((x_left, total.y0 - 3, layout.width, total.y1 + 3)))
    vals = [num(t[4]) for t in line if num(t[4]) is not None]
    totals_ = BomTotals()
    if len(vals) >= 3:
        totals_ = BomTotals(net_kg=vals[0], gross_kg=vals[1], surface_area_m2=vals[2])
    return Bom(assembly=assembly, parts=parts, totals=totals_, bbox=(x_left, y_top, x_right, total.y1))


def cross_check_bom(layout, bom):
    """Second, independent parse: PyMuPDF find_tables() clipped to the BOM frame (exact on the samples when
    clipped; unusable on the whole page). Returns mismatch descriptions, or None if no table was found."""
    try:
        tables = layout.page.find_tables(clip=pymupdf.Rect(bom.bbox)).tables
    except Exception:
        return None
    if not tables:
        return None
    data = [[" ".join((c or "").split()) for c in r] for r in tables[0].extract()]
    col = {}
    for key, needle in CROSS_HEADERS.items():                 # locate columns by header text, not position
        hits = [j for r in data[:6] for j, c in enumerate(r) if needle in c.upper()]
        if not hits:
            return None                                       # unknown layout: cross-check unavailable
        col[key] = hits[0]
    rows = {}
    for cells in data:
        if len(cells) > max(col.values()) and MARK_CELL.match(cells[col["item"]]):
            rows[cells[col["item"]]] = cells
    if not rows:
        return None
    issues = []
    for p in bom.parts:
        c = rows.pop(p.item_no, None)
        if c is None:
            issues.append(f"{p.item_no}: not found by find_tables")
            continue
        theirs = (c[col["section"]], num(c[col["length"]]), num(c[col["qty"]]), num(c[col["gross"]]),
                  c[col["material"]])
        ours = (p.section, p.length_mm, p.qty, p.gross_kg, p.material)
        if theirs != ours:
            issues.append(f"{p.item_no}: parser {ours} vs find_tables {theirs}")
    issues += [f"{m}: only found by find_tables" for m in rows]
    return issues
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_bom.py -q`
Expected: `14 passed`.

- [ ] **Step 5: Commit**

```bash
git add drawing_qa/layout.py drawing_qa/parsers tests/test_bom.py
git commit -m "feat: page layout, BOM parser and find_tables cross-check"
```

---

### Task 3: Abstract, bolts, revisions, notes, erection-location parsers

**Files:**
- Create: `drawing_qa/parsers/tables.py`, `tests/test_tables.py`

**Interfaces:**
- Produces: `parse_abstract(layout) -> Abstract | None`, `parse_bolts(layout) -> list[BoltRow]`, `parse_revisions(layout) -> list[RevisionRow]` (top row = latest), `parse_notes(layout) -> list[str]`, `parse_mark_locations(layout) -> list[MarkLocation]` (one row per erected instance), `BOLT_COLS`.

Measured details:
- **Abstract:** bounded by its own `SR.`/`WT.` header words.
- **Bolt list:** the header repeats `Dia/Quantity/Specification/Material`, so cells go to the nearest header centre, anchored on `HEX`. Sheets 14278, 16362 and 16807 have an empty bolt list, which is correct.
- **Revision table:** the leftmost `NO.` wins, because `REF. DRG. NO.` repeats it.
- **Mark box:** rows are separated by rules that span the header rule's width (16362 has two erection locations).

- [ ] **Step 1: Write failing tests**

`tests/test_tables.py`:
```python
import pytest

from drawing_qa.parsers.tables import parse_abstract, parse_bolts, parse_mark_locations, parse_notes, parse_revisions

from .conftest import GOLDEN

DRGS = sorted(GOLDEN)


@pytest.mark.parametrize("drg", DRGS)
def test_abstract_sums_to_total(layouts, drg):
    a = parse_abstract(layouts(drg))
    assert len(a.rows) == GOLDEN[drg]["abstract_rows"]
    assert a.total_kg == GOLDEN[drg]["gross"]
    assert sum(r.total_wt for r in a.rows) == pytest.approx(a.total_kg, abs=0.05)
    assert [r.sr for r in a.rows] == list(range(1, len(a.rows) + 1))


@pytest.mark.parametrize("drg", DRGS)
def test_bolt_row_count(layouts, drg):
    assert len(parse_bolts(layouts(drg))) == GOLDEN[drg]["bolts"]


def test_bolt_row_values_14281(layouts):
    rows = parse_bolts(layouts("14281"))
    assert [(r.assembly_mark, r.bolt_dia, r.bolt_length, r.bolt_qty, r.bolt_grade) for r in rows] == \
        [("3FR3", "20", "105", "8", "8.8XOX"), ("3C1", "24", "150", "88", "10.9XOX")]
    assert rows[1].nut_qty == "176" and rows[1].washer_type == "FLAT-E"
    assert rows[0].bolt_material == "IS:1367 (I) 2014"


@pytest.mark.parametrize("drg", DRGS)
def test_revisions_latest_first(layouts, drg):
    revs = parse_revisions(layouts(drg))
    assert revs[0].rev == GOLDEN[drg]["rev"]
    assert all(r.description == "ISSUED FOR CONSTRUCTION" and r.drn == "IRCON" and r.app == "SSA" for r in revs)


def test_revisions_two_rows_14278(layouts):
    assert [(r.rev, r.date) for r in parse_revisions(layouts("14278"))] == [("1", "14.08.2026"), ("0", "01.06.2026")]


@pytest.mark.parametrize("drg", DRGS)
def test_notes_and_mark_location(layouts, drg):
    notes = parse_notes(layouts(drg))
    assert len(notes) == 5 and notes[0].startswith("1. ALL DIMENSIONS")
    assert notes[4].endswith("FABRICATION SHOP.")
    locs = parse_mark_locations(layouts(drg))
    assert len(locs) == GOLDEN[drg]["asm_qty"]                 # one row per erected instance
    assert all(m.mark_no == GOLDEN[drg]["asm"] for m in locs)
    assert locs[0].level == GOLDEN[drg]["level"]


def test_mark_locations_two_instances_16362(layouts):
    assert [(m.grid_location, m.level) for m in parse_mark_locations(layouts("16362"))] ==         [("19-20/<LEG-1", "EL. +17.065"), ("22-23/<LEG-1", "EL. +17.049")]
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_tables.py -q`
Expected: `ModuleNotFoundError: No module named 'drawing_qa.parsers.tables'`.

- [ ] **Step 3: Implement**

`drawing_qa/parsers/tables.py`:
```python
"""Abstract, permanent-bolt list, revision table, notes, mark/grid/level box."""
import re

import pymupdf

from ..geometry import cluster, join_tokens, num, xc, yc
from ..models import Abstract, AbstractRow, BoltRow, MarkLocation, RevisionRow

DATE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
MARK_RE = re.compile(r"^\d[A-Za-z]{1,4}\d+$")
BOLT_COLS = list(BoltRow.model_fields)


def _rows_by_y(words, tol=4):
    rows = {}
    for w in words:
        rows.setdefault(round(yc(w) / tol), []).append(w)
    return [sorted(v, key=lambda w: w[0]) for _, v in sorted(rows.items())]


def parse_abstract(layout):
    head, end = layout.find("ABSTRACT"), layout.find("TOTAL IN KGS.")
    if not head or not end:
        return None
    head, end = head[0], end[0]
    hdr = layout.words_in((head.x0 - 150, head.y1, head.x1 + 150, head.y1 + 20))
    sr = [w for w in hdr if w[4] == "SR."]
    wt = [w for w in hdr if w[4] == "WT."]
    if not sr or not wt:
        return None
    y_body = max(w[3] for w in hdr) + 1                      # below "SR. No. DESCRIPTION TOTAL WT."
    region = (sr[0][0] - 5, y_body, wt[0][2] + 15, end.y1 + 2)
    rows, total = [], None
    for line in _rows_by_y(layout.words_in(region)):
        toks = [t[4] for t in join_tokens(line)]
        if toks[:3] == ["TOTAL", "IN", "KGS."]:
            total = num(toks[-1])
        elif len(toks) >= 3 and toks[0].isdigit() and num(toks[-1]) is not None:
            rows.append(AbstractRow(sr=int(toks[0]), description=" ".join(toks[1:-1]), total_wt=num(toks[-1])))
    return Abstract(rows=rows, total_kg=total)


def parse_bolts(layout):
    t = layout.find("List of Permanent Bolts")
    tb = layout.find("TATA STEEL LIMITED")
    if not t or not tb:
        return []
    t, tb = t[0], tb[0]
    conn = layout.find("CONNECTED", clip=pymupdf.Rect(0, t.y0 - 5, t.x0, t.y1 + 40))
    x0 = conn[0].x0 - 5 if conn else t.x0 - 450
    circ = [r for r in layout.find("TSL INTERNAL CIRCULATION") if r.x0 > t.x1]
    x1 = circ[0].x0 - 5 if circ else layout.width - 20
    words = layout.words_in((x0, t.y1, x1, tb.y0 - 5))
    spec = [w for w in words if w[4] == "Specification"]
    if not spec:
        return []
    y_hdr = min(w[1] for w in spec)
    hdr = sorted([w for w in words if abs(w[1] - y_hdr) < 4 and w[4] not in ("ASSEMBLY", "MARK")], key=lambda w: w[0])
    centers = [x0 + 25] + [xc(w) for w in hdr]
    if len(centers) != len(BOLT_COLS):
        raise ValueError(f"bolt header has {len(centers)} columns, expected {len(BOLT_COLS)}")
    body = [w for w in words if w[1] > y_hdr + 8]
    anchors = sorted(yc(w) for w in body if w[4] == "HEX" and abs(xc(w) - centers[2]) < 25)
    rows = []
    for i, y in enumerate(anchors):
        y0 = (anchors[i - 1] + y) / 2 if i else y_hdr + 8
        y1 = (y + anchors[i + 1]) / 2 if i + 1 < len(anchors) else tb.y0 - 5
        cells = {c: [] for c in BOLT_COLS}
        for w in sorted([w for w in body if y0 <= yc(w) < y1], key=lambda w: (round(w[1]), w[0])):
            j = min(range(len(centers)), key=lambda k: abs(centers[k] - xc(w)))
            cells[BOLT_COLS[j]].append(w[4])
        rows.append(BoltRow(**{k: " ".join(v) for k, v in cells.items()}))
    return rows


def parse_revisions(layout):
    hdrs = [h for h in layout.find("REVISION") if h.y0 > layout.height * 0.8 and h.x0 < layout.width * 0.3]
    if not hdrs:
        return []
    h = hdrs[0]
    hw = layout.words_in((0, h.y0 - 3, h.x1 + 700, h.y1 + 3))
    cols = {}
    for w in sorted(hw, key=lambda w: w[0]):                  # leftmost wins ("REF. DRG. NO." also has NO.)
        if w[4] in ("NO.", "DATE", "REVISION", "DRN.", "CHD.", "APP.") and w[4] not in cols:
            cols[w[4]] = xc(w)
    if not {"DATE", "DRN.", "CHD.", "APP."} <= cols.keys():
        return []
    x_max = cols["APP."] + 30
    words = layout.words_in((0, h.y0 - 200, x_max, h.y0 - 1))
    rows = []
    for d in sorted((w for w in words if DATE.match(w[4])), key=lambda w: w[1]):
        line = [w for w in words if abs(yc(w) - yc(d)) < 5]
        def col(name, lo, hi):
            return " ".join(w[4] for w in line if lo <= xc(w) < hi)
        mid = lambda a, b: (cols[a] + cols[b]) / 2
        rev_lo = cols.get("NO.", cols["DATE"]) - 15            # border grid letter sits ~20pt left
        rows.append(RevisionRow(
            rev=col("rev", rev_lo, mid("NO.", "DATE") if "NO." in cols else cols["DATE"] - 20),
            date=d[4],
            description=col("desc", d[2] + 1, mid("REVISION", "DRN.") if "REVISION" in cols else cols["DRN."] - 30),
            drn=col("drn", mid("REVISION", "DRN.") if "REVISION" in cols else cols["DRN."] - 30, mid("DRN.", "CHD.")),
            chd=col("chd", mid("DRN.", "CHD."), mid("CHD.", "APP.")),
            app=col("app", mid("CHD.", "APP."), x_max),
        ))
    return rows


def parse_notes(layout):
    first = layout.find("1. ALL DIMENSIONS")
    if not first:
        return []
    f = first[0]
    stop = [r for r in layout.find("NOTES") if r.y0 > f.y0]
    y1 = min(r.y0 for r in stop) - 1 if stop else f.y0 + 90
    notes = []
    for line in _rows_by_y(layout.words_in((f.x0 - 5, f.y0 - 2, f.x0 + 420, y1)), tol=3):
        s = " ".join(w[4] for w in line)
        if re.match(r"^\d+\.\s", s):
            notes.append(s)
        elif notes:
            notes[-1] += " " + s
    return notes


def parse_mark_locations(layout):
    """MARK NO. / GRID LOCATION / LEVEL box: one row per erected instance (16362 has two),
    rows separated by horizontal rules spanning the box."""
    g = layout.find("GRID LOCATION")
    if not g:
        return []
    g = g[0]
    hdr = layout.words_in((0, g.y0 - 3, g.x1 + 200, g.y1 + 3))
    cols = {w[4]: xc(w) for w in hdr if w[4] in ("MARK", "GRID", "LEVEL")}
    if len(cols) < 3:
        return []
    spans = lambda s: (min(s[0], s[2]), max(s[0], s[2]))
    rules = [s for s in layout.segments if abs(s[1] - s[3]) < 0.5 and g.y1 - 2 <= s[1] <= g.y1 + 120
             and spans(s)[0] < cols["MARK"] and spans(s)[1] > cols["LEVEL"]]
    head = [s for s in rules if s[1] <= g.y1 + 3]
    if head:   # row rules span exactly the header rule's width; drawing lines below the box do not
        hx0, hx1 = spans(head[0])
        rules = [s for s in rules if abs(spans(s)[0] - hx0) < 3 and abs(spans(s)[1] - hx1) < 3]
    x0 = min(spans(s)[0] for s in rules) if rules else cols["MARK"] - 40
    x1 = max(spans(s)[1] for s in rules) if rules else cols["LEVEL"] + 60
    ys = [sum(c) / len(c) for c in cluster([s[1] for s in rules], 1.5)]
    bands = [(a, b) for a, b in zip(ys, ys[1:]) if b - a < 25] or [(g.y1 + 1, g.y1 + 16)]
    mid_mg, mid_gl = (cols["MARK"] + cols["GRID"]) / 2, (cols["GRID"] + cols["LEVEL"]) / 2
    rows = []
    for y0, y1 in bands:
        ws = sorted(layout.words_in((x0, y0, x1, y1)), key=lambda w: w[0])
        mark = " ".join(w[4] for w in ws if xc(w) < mid_mg)
        grid = " ".join(w[4] for w in ws if mid_mg <= xc(w) < mid_gl)
        level = " ".join(w[4] for w in ws if xc(w) >= mid_gl)
        if MARK_RE.match(mark):
            rows.append(MarkLocation(mark_no=mark, grid_location=grid, level=level))
    return rows
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_tables.py -q`
Expected: `23 passed`.

- [ ] **Step 5: Commit**

```bash
git add drawing_qa/parsers/tables.py tests/test_tables.py
git commit -m "feat: abstract, bolt list, revisions, notes and erection-location parsers"
```

---

### Task 4: Title block from bordered cells; part marks and view labels

**Files:**
- Create: `drawing_qa/parsers/titleblock.py`, `drawing_qa/parsers/views.py`, `tests/test_titleblock_views.py`

**Interfaces:**
- Produces: `title_block_rect(layout)`, `all_drawing_numbers(layout)`, `label_cells(layout, rect, label) -> list[(text, label_word)]`, `parse_title_block(layout) -> TitleBlock` (every field deterministic), `part_marks(layout, exclude_rects)`, `view_labels(layout) -> list[ViewLabel]`, regex `MARK`.

Every title-block field is the whole bordered cell to the right of its label; cell edges are the vertical rules crossing the label's row. Title lines are the rows of the DRAWING DESCRIPTION cell between EQUIP/AREA and PROJECT, each bounded by its cell's right edge (this drops the sheet-border grid letter). A cell that starts with another label, such as a blank PROJECT row reading "MATERIAL", counts as empty. This replaced the v1 OpenAI title-block step: live, gpt-5.4-mini sometimes read 16807's title-block values one row off, while this parser matches the image-verified values on all 5 sheets.

- [ ] **Step 1: Write failing tests**

`tests/test_titleblock_views.py`:
```python
import pytest

from drawing_qa.parsers.bom import parse_bom
from drawing_qa.parsers.titleblock import parse_title_block
from drawing_qa.parsers.views import part_marks, view_labels

from .conftest import GOLDEN, TITLE

DRGS = sorted(GOLDEN)


@pytest.mark.parametrize("drg", DRGS)
def test_title_block_deterministic_fields(layouts, drg):
    tb = parse_title_block(layouts(drg))
    assert tb.drawing_no == f"TST-SFD-46-01-01-07-000-{drg}"
    assert tb.sheet_size == GOLDEN[drg]["size"]
    assert tb.sheet_no == "1 OF 1"
    assert tb.weight_kg == GOLDEN[drg]["gross"]


@pytest.mark.parametrize("drg", DRGS)
def test_title_block_text_fields_from_bordered_cells(layouts, drg):
    t, tb = TITLE[drg], parse_title_block(layouts(drg))
    assert tb.department == "DESIGN & ENGINEERING-STRUCTURAL"
    assert (tb.equip_area, tb.project, tb.title_lines) == (t["equip"], t["project"], t["lines"])
    assert (tb.drn.name, tb.chd.name, tb.app.name) == ("IRCON", t["persons"][0], "SSA")
    assert tb.drn.date == tb.chd.date == tb.app.date == t["persons"][1]


def test_blank_project_cell_reads_empty_not_the_next_label(layouts):
    from drawing_qa.parsers.titleblock import label_cells, title_block_rect
    L = layouts("16807")
    assert [t for t, _ in label_cells(L, title_block_rect(L), "PROJECT")] == [""]


@pytest.mark.parametrize("drg", DRGS)
def test_every_bom_mark_is_on_the_sheet(layouts, drg):
    L = layouts(drg)
    b = parse_bom(L)
    assert {p.item_no for p in b.parts} <= set(part_marks(L, [b.bbox]))


@pytest.mark.parametrize("drg", DRGS)
def test_view_labels_have_cells_and_section_scales(layouts, drg):
    labels = view_labels(layouts(drg))
    assert len(labels) == GOLDEN[drg]["labels"]
    assert all(v.cell for v in labels)
    assert all(v.scale.startswith("1:") for v in labels if v.kind == "section")
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_titleblock_views.py -q`
Expected: `ModuleNotFoundError: No module named 'drawing_qa.parsers.titleblock'`.

- [ ] **Step 3: Implement**

`drawing_qa/parsers/titleblock.py`:
```python
"""Title block, fully deterministic.

Each labelled field is the whole bordered cell to the right of its label (cell edges = vertical rules
crossing the label's row). Title lines are the rows of the DRAWING DESCRIPTION cell between the
EQUIP/AREA and PROJECT rows. A cell that starts with another label is an empty field. Verified on the
5 samples (A1 and A0 templates), including the A1 sheets whose PROJECT row is blank."""
import re

from ..geometry import num, xc, yc
from ..models import Person, TitleBlock

DRG_NO = re.compile(r"^[A-Z]{2,5}-[A-Z]{2,5}(?:-\d+){5,}$")
SHEET_NO = re.compile(r"\b(\d+)\s+OF\s+(\d+)\b")
SIZE = re.compile(r"^A[0-4]$")
DATE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
TITLE_LABELS = {"DEPARTMENT", "EQUIP/AREA", "PROJECT", "MATERIAL", "DRN.", "CHD.", "APP.", "DRG.No.", "REV",
                "SHEET", "WEIGHT", "DRAWING", "DESCRIPTION", "SCALE", "TITLE"}


def title_block_rect(layout):
    tb = layout.find("TATA STEEL LIMITED")
    if not tb:
        return None
    tb = tb[0]
    return (tb.x0 - 320, tb.y0 - 10, layout.width, layout.height)


def all_drawing_numbers(layout):
    return sorted({w[4] for w in layout.words if DRG_NO.match(w[4])})


def _walls(layout, y):
    return sorted(s[0] for s in layout.segments if abs(s[0] - s[2]) < 0.5 and min(s[1], s[3]) < y < max(s[1], s[3]))


def _cell_right(layout, rect, x, y):
    return min([w for w in _walls(layout, y) if w > x + 1], default=rect[2])


def label_cells(layout, rect, label, tol=7) -> list[tuple[str, tuple]]:
    """For each occurrence of `label`: (full text of the bordered cell holding the first word to its right on
    the same row, label word). A cell starting with another label counts as empty."""
    words = layout.words_in(rect)
    out = []
    for lab in (w for w in words if w[4] == label):
        y = yc(lab)
        row = sorted((w for w in words if abs(yc(w) - y) <= tol and w[0] > lab[2]), key=lambda w: w[0])
        if not row or row[0][4] in TITLE_LABELS:
            out.append(("", lab))
            continue
        right = _cell_right(layout, rect, row[0][0], y)
        out.append((" ".join(w[4] for w in row if w[2] <= right + 1), lab))
    return out


def _field(layout, rect, label):
    """First non-empty cell for a label ('' if none)."""
    return next((t for t, _ in label_cells(layout, rect, label) if t), "")


def _person(layout, rect, label):
    words = layout.words_in(rect)
    for name, lab in label_cells(layout, rect, label):
        if not name or DATE.match(name):
            continue
        dates = sorted((w for w in words if DATE.match(w[4]) and abs(yc(w) - yc(lab)) <= 7 and w[0] > lab[2]),
                       key=lambda w: w[0])
        return Person(name=name, date=dates[0][4] if dates else "")
    return Person()


def _title_lines(layout, rect):
    words = layout.words_in(rect)
    eq = [w for w in words if w[4] == "EQUIP/AREA"]
    if not eq:
        return []
    eq = eq[0]
    proj = [w for w in words if w[4] == "PROJECT" and w[1] > eq[1]]
    if not proj:
        return []
    proj = min(proj, key=lambda w: w[1])
    mid = (eq[3] + proj[1]) / 2
    left = min([w for w in _walls(layout, mid) if w > eq[2]], default=eq[2])
    band = sorted((w for w in words if eq[3] + 1 < yc(w) < proj[1] - 1 and w[0] > left), key=yc)
    rows = []
    for w in band:
        if rows and abs(yc(w) - rows[-1][0]) <= 3:
            rows[-1][1].append(w)
        else:
            rows.append([yc(w), [w]])
    lines = []
    for y, ws in rows:
        ws.sort(key=lambda w: w[0])
        right = _cell_right(layout, rect, ws[0][0], y)      # drops the sheet-border grid letter
        text = " ".join(w[4] for w in ws if w[2] <= right + 1)
        if text:
            lines.append(text)
    return lines


def parse_title_block(layout) -> TitleBlock:
    rect = title_block_rect(layout)
    if rect is None:
        return TitleBlock()
    words = layout.words_in(rect)
    tb = TitleBlock()
    drg = [w[4] for w in words if DRG_NO.match(w[4])]
    if drg:
        tb.drawing_no = drg[0]
    m = SHEET_NO.search(" ".join(w[4] for w in words))
    if m:
        tb.sheet_no = f"{m.group(1)} OF {m.group(2)}"
    size = [w[4] for w in words if SIZE.match(w[4])]
    if size:
        tb.sheet_size = size[0]
    kg = [w for w in words if w[4] == "KG"]
    if kg:
        k = kg[0]
        wt = [w for w in words if abs(xc(w) - xc(k)) < 60 and 0 < w[1] - k[3] < 25 and re.fullmatch(r"\d+\.\d+", w[4])]
        if wt:
            tb.weight_kg = num(wt[0][4])
    revs = [w for w in words if w[4] == "REV"]
    if revs:
        r = max(revs, key=lambda w: w[1])
        below = [w for w in words if abs(xc(w) - xc(r)) < 15 and 0 < w[1] - r[3] < 25 and re.fullmatch(r"[0-9A-Z]{1,2}", w[4])]
        if below:
            tb.rev = below[0][4]
    tb.department = _field(layout, rect, "DEPARTMENT")
    tb.equip_area = _field(layout, rect, "EQUIP/AREA")
    tb.project = _field(layout, rect, "PROJECT")
    tb.title_lines = _title_lines(layout, rect)
    tb.drn, tb.chd, tb.app = (_person(layout, rect, lab) for lab in ("DRN.", "CHD.", "APP."))
    return tb
```

`drawing_qa/parsers/views.py`:
```python
"""Part marks and view labels found in the drawing area."""
import re

from ..models import ViewLabel

# Tekla marks: parts '3p307' / '4m665', assemblies '3C2' / '4DC3' / '4PSB2' / '2GU1'
MARK = re.compile(r"^\d[a-z]\d+$|^\d[A-Z]{1,4}\d+$")
SECTION = re.compile(r"^([A-Z0-9]{1,2}) - \1$")
SCALE = re.compile(r"^1:\d+$")
DETAIL = re.compile(r"^MARK\. NO:-\s*(\S+)$")


def part_marks(layout, exclude_rects=()):
    def outside(w):
        cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        return not any(r[0] <= cx <= r[2] and r[1] <= cy <= r[3] for r in exclude_rects)
    return sorted({w[4] for w in layout.words if MARK.match(w[4]) and outside(w)})


def view_labels(layout):
    out = []
    lines = [ln for ln in layout.lines if ln.horizontal]
    for ln in lines:
        m = SECTION.match(ln.text)
        d = DETAIL.match(ln.text)
        if not (m or d):
            continue
        cx = (ln.bbox[0] + ln.bbox[2]) / 2
        scale = ""
        if m:
            below = [s for s in lines if SCALE.match(s.text) and abs((s.bbox[0] + s.bbox[2]) / 2 - cx) < 40
                     and -5 < s.bbox[1] - ln.bbox[3] < 25]
            scale = below[0].text if below else ""
        out.append(ViewLabel(
            label=ln.text, kind="section" if m else "detail", ref=m.group(1) if m else d.group(1),
            scale=scale, bbox=ln.bbox, cell=layout.grid.cell_of(cx, (ln.bbox[1] + ln.bbox[3]) / 2),
        ))
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_titleblock_views.py -q`
Expected: `21 passed`.

- [ ] **Step 5: Commit**

```bash
git add drawing_qa/parsers/titleblock.py drawing_qa/parsers/views.py tests/test_titleblock_views.py
git commit -m "feat: deterministic title block, part marks and view labels"
```

---

### Task 5: Rendering and the OpenAI wrapper

**Files:**
- Create: `drawing_qa/render.py`, `drawing_qa/llm.py`, `tests/fakes.py`, `tests/test_render_llm.py`

**Interfaces:**
- Produces:
  - Rendering: `render_clip(page, rect, max_px=2400, dpi=200) -> png`, `render_overview(page, max_px=1600)`, `tile_rects(page, cols, rows, overlap=0.04)`.
  - `image_part(png, detail)`, `LLMError`.
  - `LLM(client=None, timeout=120.0, max_retries=2)` with `.parse(model, instructions, text, images, schema)`, `.parse_content(model, instructions, content, schema)` (both raise `LLMError` on empty output), `.create(model, instructions, input, tools)` and `.usage_summary()`.
  - Test fakes: `FakeClient(parse_fn=None, script=None)`, `text_response`, `call_response`.

Verified live with openai 1.72: `responses.parse(text_format=PydanticModel)` works with `input_image` data URLs, and a `function_call_output` whose `output` is a list containing `input_image` is accepted.

- [ ] **Step 1: Write failing tests**

`tests/fakes.py`:
```python
"""Offline stand-ins for the OpenAI client (same attribute shape as openai>=1.72)."""
from types import SimpleNamespace


def _usage():
    return SimpleNamespace(input_tokens=100, output_tokens=10, input_tokens_details=SimpleNamespace(cached_tokens=0))


class Item(SimpleNamespace):
    def model_dump(self, exclude_none=True):
        return {k: v for k, v in vars(self).items() if v is not None}


def text_response(text):
    return SimpleNamespace(output=[Item(type="message", role="assistant",
                                        content=[{"type": "output_text", "text": text}])],
                           output_text=text, usage=_usage())


def call_response(name, arguments, call_id="call_1"):
    return SimpleNamespace(output=[Item(type="function_call", name=name, arguments=arguments, call_id=call_id)],
                           output_text="", usage=_usage())


class FakeResponses:
    def __init__(self, parse_fn=None, script=None):
        self.parse_fn, self.script = parse_fn, list(script or [])
        self.parse_calls, self.create_calls = [], []

    def parse(self, model, instructions, input, text_format):
        self.parse_calls.append((model, text_format.__name__, input))
        return SimpleNamespace(output_parsed=self.parse_fn(model, text_format), usage=_usage())

    def create(self, model, instructions, input, tools):
        self.create_calls.append((model, input))
        return self.script.pop(0)


class FakeClient:
    def __init__(self, **kw):
        self.responses = FakeResponses(**kw)
```

`tests/test_render_llm.py`:
```python
import pymupdf
from pydantic import BaseModel

import pytest

from drawing_qa.llm import LLM, LLMError
from drawing_qa.render import render_clip, render_overview, tile_rects

from .conftest import sample_path
from .fakes import FakeClient


def _png_size(png):
    pix = pymupdf.Pixmap(png)
    return pix.width, pix.height


def test_render_clip_caps_long_side():
    page = pymupdf.open(sample_path("14281"))[0]
    w, h = _png_size(render_clip(page, page.rect, max_px=1200))
    assert max(w, h) == 1200
    w, h = _png_size(render_clip(page, (0, 0, 72, 36), max_px=5000, dpi=144))
    assert (w, h) == (144, 72)                                 # small clips render at the requested dpi
    assert max(_png_size(render_overview(page, 800))) == 800


def test_tile_rects_cover_sheet_with_overlap():
    page = pymupdf.open(sample_path("09970"))[0]
    tiles = tile_rects(page, 2, 2)
    assert len(tiles) == 4
    assert tiles[0][0] == 0 and tiles[0][1] == 0
    assert tiles[-1][2] == page.rect.width and tiles[-1][3] == page.rect.height
    assert tiles[0][2] > tiles[1][0]                           # neighbours overlap


class Echo(BaseModel):
    value: str


def test_llm_parse_records_usage_per_model():
    client = FakeClient(parse_fn=lambda model, schema: schema(value=model))
    llm = LLM(client)
    assert llm.parse("m1", "sys", "hello", [b"png"], Echo).value == "m1"
    llm.parse("m1", "sys", "again", [], Echo)
    assert llm.usage_summary() == {"m1": {"input": 200, "output": 20, "cached": 0, "calls": 2}}
    content = client.responses.parse_calls[0][2][0]["content"]
    assert content[0] == {"type": "input_text", "text": "hello"}
    assert content[1]["type"] == "input_image" and content[1]["image_url"].startswith("data:image/png;base64,")


def test_llm_parse_raises_on_empty_output():
    llm = LLM(FakeClient(parse_fn=lambda model, schema: None))
    with pytest.raises(LLMError, match="returned no parsed Echo"):
        llm.parse("m1", "sys", "hi", [], Echo)
    assert llm.usage_summary()["m1"]["calls"] == 1           # tokens were still spent and are counted
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_render_llm.py -q`
Expected: `ModuleNotFoundError: No module named 'drawing_qa.llm'`.

- [ ] **Step 3: Implement**

`drawing_qa/render.py`:
```python
"""Rasterise regions of a sheet at a resolution the vision model can read."""
import pymupdf


def render_clip(page, rect, max_px=2400, dpi=200) -> bytes:
    """PNG of `rect` (PDF points) at `dpi`, downscaled so the long side <= max_px."""
    r = pymupdf.Rect(rect) & page.rect
    if r.is_empty:
        raise ValueError(f"empty clip {rect}")
    zoom = min(dpi / 72, max_px / max(r.width, r.height))
    return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=r, alpha=False).tobytes("png")


def render_overview(page, max_px=1600) -> bytes:
    return render_clip(page, page.rect, max_px=max_px, dpi=72)


def tile_rects(page, cols, rows, overlap=0.04):
    """Split the sheet into cols x rows tiles with a small overlap so labels on a seam survive."""
    W, H = page.rect.width, page.rect.height
    tw, th = W / cols, H / rows
    ox, oy = tw * overlap, th * overlap
    return [(max(0, c * tw - ox), max(0, r * th - oy), min(W, (c + 1) * tw + ox), min(H, (r + 1) * th + oy))
            for r in range(rows) for c in range(cols)]
```

`drawing_qa/llm.py`:
```python
"""Thin OpenAI Responses-API wrapper that records token usage per model.
Tests inject a fake `client` with the same `.responses.parse/.create` shape."""
import base64
from collections import defaultdict


def image_part(png: bytes, detail="high"):
    return {"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(png).decode(), "detail": detail}


class LLMError(RuntimeError):
    """The model returned nothing usable (refusal, empty or unparseable structured output)."""


class LLM:
    def __init__(self, client=None, timeout=120.0, max_retries=2):
        if client is None:
            from openai import OpenAI
            client = OpenAI(timeout=timeout, max_retries=max_retries)
        self.client = client
        self.usage = defaultdict(lambda: defaultdict(int))  # model -> {input, cached, output, calls}

    def _record(self, model, usage):
        if usage is None:
            return
        u = self.usage[model]
        u["input"] += usage.input_tokens
        u["output"] += usage.output_tokens
        details = getattr(usage, "input_tokens_details", None)
        u["cached"] += getattr(details, "cached_tokens", 0) or 0
        u["calls"] += 1

    def parse(self, model, instructions, text, images, schema):
        content = [{"type": "input_text", "text": text}] + [image_part(p) for p in images]
        return self.parse_content(model, instructions, content, schema)

    def parse_content(self, model, instructions, content, schema):
        """Structured output from prepared content parts (text + images)."""
        r = self.client.responses.parse(model=model, instructions=instructions,
                                        input=[{"role": "user", "content": content}], text_format=schema)
        self._record(model, r.usage)
        if r.output_parsed is None:
            raise LLMError(f"{model} returned no parsed {schema.__name__} (refusal or empty output)")
        return r.output_parsed

    def create(self, model, instructions, input, tools):
        r = self.client.responses.create(model=model, instructions=instructions, input=input, tools=tools)
        self._record(model, r.usage)
        return r

    def usage_summary(self):
        return {m: dict(v) for m, v in self.usage.items()}
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_render_llm.py -q`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add drawing_qa/render.py drawing_qa/llm.py tests/fakes.py tests/test_render_llm.py
git commit -m "feat: region rendering and OpenAI wrapper with usage accounting"
```

---

### Task 6: Guardrail checks and the deterministic extraction pipeline

**Files:**
- Create: `drawing_qa/validate.py`, `drawing_qa/extract.py`, `tests/test_extract.py`

**Interfaces:**
- Produces:
  - `run_checks(x) -> list[Check]`.
  - `deterministic_extract(layout, source_name, file_sha, page_index) -> PageExtract`.
  - `extract_page(pdf_bytes, page_index, source_name, settings=None, use_cache=True) -> PageExtract`. It makes no model calls. The cache file is `<cache_dir>/<sha[:20]>_p<page>_<hash(SCHEMA_VERSION)>.json`, and `source_file` and the checks are refreshed when loading from cache.
  - `PageExtract.regions` keys: `bom, title_block, abstract, bolts, notes, mark_location, revisions`.

Check semantics (measured, and confirmed by the auditor):
- **Gross total** is multiplied by the assembly qty (16362: 175.27 × 2 ≈ 350.52).
- **Net total** is only a warning: Tekla drifts, and on 16362 the net total is not multiplied by qty, so either form is accepted.
- **Row tolerance** is `0.006·qty + 0.02` kg, because piece weights are rounded.
- **`abstract.by_section`:** each abstract row equals the BOM gross for that section or plate thickness (`PL`/`PLT`) × qty.
- **`bom.crosscheck`:** the second parse. "Unavailable" is a warning.
- **Mark checks:** `mark_location.count` = assembly qty. Every BOM mark must appear on the drawing.
- **`title.fields`** warns if department, equip/area or title lines are missing.

- [ ] **Step 1: Write failing tests**

`tests/test_extract.py`:
```python
from pathlib import Path

import pytest

from drawing_qa.extract import extract_page
from drawing_qa.validate import run_checks

from .conftest import GOLDEN, det, sample_path


@pytest.mark.parametrize("drg", sorted(GOLDEN))
def test_deterministic_extract_has_no_failures(drg, settings):
    x = det(drg, settings)
    assert [c for c in x.checks if c.level == "fail"] == []
    assert {"bom", "title_block", "abstract", "notes", "mark_location", "revisions"} <= set(x.regions)
    assert x.title_block.rev == GOLDEN[drg]["rev"]                 # A1 sheets: from the revision table


def test_checks_catch_a_corrupted_row(settings):
    x = det("09970", settings)
    x.bom.parts[0].gross_kg += 5
    ids = {c.id for c in run_checks(x) if c.level == "fail"}
    assert {"bom.row_arith", "bom.gross_total"} <= ids


def test_checks_catch_missing_mark(settings):
    x = det("16807", settings)
    x.part_marks = [m for m in x.part_marks if m != "2p205"]
    fails = [c for c in run_checks(x) if c.level == "fail"]
    assert [c.id for c in fails] == ["marks.bom_on_sheet"] and "2p205" in fails[0].message


def test_assembly_qty_multiplies_gross(settings):
    x = det("16362", settings)          # assembly qty 2: Σ parts 175.27 × 2 = 350.54 ≈ 350.52 grand total
    assert next(c for c in x.checks if c.id == "bom.gross_total").level == "pass"


def test_new_checks_pass_on_all_samples(settings):
    for drg in sorted(GOLDEN):
        levels = {c.id: c.level for c in det(drg, settings).checks}
        assert levels["bom.crosscheck"] == "pass" and levels["abstract.by_section"] == "pass", drg
        assert levels["mark_location.count"] == "pass", drg
        assert "title.fields" not in levels, drg                    # department, equip/area, title lines found
    assert {c.id: c.level for c in det("16362", settings).checks}["bom.net_total"] == "pass"   # net not x qty


def test_extract_cache_roundtrip_and_file_name(settings):
    p = sample_path("16807")
    data = p.read_bytes()
    a = extract_page(data, 0, p.name, settings=settings)
    b = extract_page(data, 0, p.name, settings=settings)
    assert a == b
    assert len(list(Path(settings.cache_dir).glob("*.json"))) == 1
    renamed = extract_page(data, 0, "copy.pdf", settings=settings)          # cache hit under a new name
    assert renamed.source_file == "copy.pdf"
    assert next(c for c in renamed.checks if c.id == "title.drawing_no").level == "warn"


def test_settings_read_environment_at_construction(monkeypatch):
    from drawing_qa.config import Settings
    monkeypatch.setenv("DQA_MODEL", "m-x")
    monkeypatch.setenv("DQA_CACHE_DIR", "somewhere")
    s = Settings()
    assert (s.model, s.cache_dir) == ("m-x", "somewhere")


@pytest.mark.parametrize("tables", [[], "odd"], ids=["no_table", "unexpected_columns"])
def test_unavailable_crosscheck_is_a_warning_not_a_failure(settings, monkeypatch, tables):
    import pymupdf
    from types import SimpleNamespace
    if tables == "odd":        # a table whose header matches none of ITEM/SECTION/LENGTH/QTY/GROSS/MATERIAL
        odd = SimpleNamespace(extract=lambda: [["A", "B", "C"], ["1", "2", "3"]])
        monkeypatch.setattr(pymupdf.Page, "find_tables", lambda self, **kw: SimpleNamespace(tables=[odd]))
    else:
        monkeypatch.setattr(pymupdf.Page, "find_tables", lambda self, **kw: SimpleNamespace(tables=[]))
    p = sample_path("16807")
    x = extract_page(p.read_bytes(), 0, p.name, settings=settings, use_cache=False)
    assert x.bom_crosscheck is None
    levels = {c.id: c.level for c in x.checks}
    assert levels["bom.crosscheck"] == "warn" and "fail" not in levels.values()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_extract.py -q`
Expected: `ModuleNotFoundError: No module named 'drawing_qa.extract'`.

- [ ] **Step 3: Implement**

`drawing_qa/validate.py`:
```python
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
```

`drawing_qa/extract.py`:
```python
"""Page extraction: 100% PyMuPDF (no model calls), then guardrail checks, then a disk cache.
OpenAI is used later, for Q&A (chat.py) and the inventory (inventory.py), on top of this extract."""
import hashlib
from pathlib import Path

from .config import SCHEMA_VERSION, Settings
from .layout import PageLayout, open_pdf, sha256
from .models import Check, PageExtract
from .parsers.bom import cross_check_bom, parse_bom
from .parsers.tables import parse_abstract, parse_bolts, parse_mark_locations, parse_notes, parse_revisions
from .parsers.titleblock import parse_title_block, title_block_rect
from .parsers.views import part_marks, view_labels
from .validate import run_checks


def _safe(name, fn, errors, default=None):
    try:
        return fn()
    except Exception as e:  # a broken parser must not take down the page
        errors.append(Check(id=f"parse.{name}", level="fail", message=f"{name} parser error: {e}", region=name))
        return default


def _regions(layout, bom):
    out = {}
    if bom:
        out["bom"] = bom.bbox
    tb = title_block_rect(layout)
    if tb:
        out["title_block"] = tb
    hit = lambda s: (layout.find(s) or [None])[0]
    a, e = hit("ABSTRACT"), hit("TOTAL IN KGS.")
    if a and e:
        out["abstract"] = (e.x0 - 40, a.y0 - 5, a.x1 + 150, e.y1 + 5)
    b, t = hit("List of Permanent Bolts"), hit("TATA STEEL LIMITED")
    if b and t:
        out["bolts"] = (b.x0 - 450, b.y0 - 5, b.x1 + 650, t.y0 - 5)
    n = hit("1. ALL DIMENSIONS")
    if n:
        out["notes"] = (n.x0 - 5, n.y0 - 5, n.x0 + 420, n.y0 + 95)
    g = hit("GRID LOCATION")
    if g:
        out["mark_location"] = (max(0, g.x0 - 120), g.y0 - 45, g.x1 + 150, g.y1 + 45)
    r = [h for h in layout.find("REVISION") if h.y0 > layout.height * 0.8 and h.x0 < layout.width * 0.3]
    if r:
        out["revisions"] = (0, r[0].y0 - 200, r[0].x1 + 450, r[0].y1 + 5)
    return {k: tuple(float(v) for v in rect) for k, rect in out.items()}


def deterministic_extract(layout, source_name, file_sha, page_index) -> PageExtract:
    errors: list[Check] = []
    bom = _safe("bom", lambda: parse_bom(layout), errors)
    revisions = _safe("revisions", lambda: parse_revisions(layout), errors, [])
    tb = _safe("title_block", lambda: parse_title_block(layout), errors)
    if tb is not None and not tb.rev and revisions:
        tb.rev = revisions[0].rev                       # top row = latest revision (A1 title block has no REV cell)
    x = PageExtract(
        source_file=source_name, file_sha256=file_sha, page_index=page_index,
        page_size_pt=(layout.width, layout.height), has_text_layer=layout.has_text_layer,
        bom=bom,
        abstract=_safe("abstract", lambda: parse_abstract(layout), errors),
        bolts=_safe("bolts", lambda: parse_bolts(layout), errors, []),
        revisions=revisions,
        notes=_safe("notes", lambda: parse_notes(layout), errors, []),
        mark_locations=_safe("mark_location", lambda: parse_mark_locations(layout), errors, []),
        part_marks=_safe("marks", lambda: part_marks(layout, [bom.bbox] if bom else []), errors, []),
        view_labels=_safe("view_labels", lambda: view_labels(layout), errors, []),
        bom_crosscheck=_safe("bom_crosscheck", lambda: cross_check_bom(layout, bom), errors) if bom else None,
        regions=_regions(layout, bom),
    )
    if tb is not None:
        x.title_block = tb
    x.pipeline_errors = errors
    return x


def _cache_path(settings, file_sha, page_index):
    tag = hashlib.sha256(f"{SCHEMA_VERSION}".encode()).hexdigest()[:10]
    return Path(settings.cache_dir) / f"{file_sha[:20]}_p{page_index}_{tag}.json"


def extract_page(pdf_bytes: bytes, page_index: int, source_name: str, settings: Settings | None = None,
                 use_cache=True) -> PageExtract:
    settings = settings or Settings()
    file_sha = sha256(pdf_bytes)
    cache = _cache_path(settings, file_sha, page_index)
    if use_cache and cache.exists():
        x = PageExtract.model_validate_json(cache.read_text(encoding="utf-8"))
        x.source_file = source_name                    # same bytes may arrive under another name
        x.checks = x.pipeline_errors + run_checks(x)
        return x
    layout = PageLayout.from_page(open_pdf(pdf_bytes)[page_index])
    x = deterministic_extract(layout, source_name, file_sha, page_index)
    x.checks = x.pipeline_errors + run_checks(x)
    if use_cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(x.model_dump_json(indent=1), encoding="utf-8")
    return x
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_extract.py -q`
Expected: `13 passed`. All 5 sheets have zero `fail` checks.

- [ ] **Step 5: Commit**

```bash
git add drawing_qa/validate.py drawing_qa/extract.py tests/test_extract.py
git commit -m "feat: guardrail checks and deterministic extraction pipeline with cache"
```

---

### Task 7: Whole-page model context

**Files:**
- Create: `drawing_qa/context.py`, `tests/test_context.py`

**Interfaces:**
- Consumes: `PageLayout.lines`, `.grid`, `render_clip`, `tile_rects`, `image_part`.
- Produces: `page_text(layout) -> str` (one `[cell] text` line per text line, with `(vertical)` marked), `tiles(page, layout) -> [(caption, png)]` (3×2 on A0-size sheets, 2×2 otherwise), and `page_context(page, layout) -> list[content part]`, which is deterministic so that it caches.

Measured live with gpt-5.4-mini, repeating the same prefix twice:

| Sheet | Input tokens per call | Cached on 2nd call | Latency |
|---|---|---|---|
| A1 (09970) | 17,112 | 16,000 | 4–6 s |
| A0 (14281) | 35,799 | 34,944 | ≈20 s |

- [ ] **Step 1: Write failing tests**

`tests/test_context.py`:
```python
import pymupdf

from drawing_qa.context import page_context, page_text, tiles

from .conftest import sample_path


def test_page_text_tags_every_line_with_a_grid_cell(layouts):
    txt = page_text(layouts("14281"))
    lines = txt.splitlines()
    assert len(lines) == len(layouts("14281").lines)
    assert all(ln.startswith("[") for ln in lines)
    assert "37a-39a/LA" in txt and "[A21] BILL OF MATERIALS" in txt


def test_tiles_cover_the_sheet_by_size(layouts):
    for drg, n in (("09970", 4), ("14281", 6)):
        page = pymupdf.open(sample_path(drg))[0]
        t = tiles(page, layouts(drg))
        assert len(t) == n and all(cap.startswith("tile ") and png[:4] == b"\x89PNG" for cap, png in t)


def test_page_context_is_deterministic(layouts):
    page = pymupdf.open(sample_path("09970"))[0]
    a, b = page_context(page, layouts("09970")), page_context(page, layouts("09970"))
    assert a == b                                    # identical prefix -> prompt-cache hits
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_context.py -q`
Expected: `ModuleNotFoundError: No module named 'drawing_qa.context'`.

- [ ] **Step 3: Implement**

`drawing_qa/context.py`:
```python
"""The whole page as model input: every text line of the PyMuPDF text layer tagged with its sheet grid
cell, plus high-resolution tiles of the full sheet. Built once per page and placed first in every
request, so the identical prefix is served from OpenAI's prompt cache on later calls."""
from .llm import image_part
from .render import render_clip, tile_rects


def page_text(layout) -> str:
    """'[E7] 4p637' lines in reading order (grid row, grid column, then position). Rotated text is kept and
    marked '(vertical)'; dimension figures are often vertical on these sheets."""
    rows = []
    for ln in layout.lines:
        x = (ln.bbox[0] + ln.bbox[2]) / 2
        y = (ln.bbox[1] + ln.bbox[3]) / 2
        cell = layout.grid.cell_of(x, y) or "?"
        rows.append((cell[:1], int(cell[1:] or 0) if cell[1:].isdigit() else 0, round(y), round(x),
                     f"[{cell}] {ln.text}" + ("" if ln.horizontal else " (vertical)")))
    return "\n".join(r[-1] for r in sorted(rows))


def tiles(page, layout, max_px=2000, dpi=150):
    """[(caption, png)] covering the sheet: 3x2 tiles on A0-size sheets, 2x2 otherwise."""
    cols, nrows = (3, 2) if layout.width > 3000 else (2, 2)
    out = []
    for i, r in enumerate(tile_rects(page, cols, nrows)):
        c0 = layout.grid.cell_of(r[0] + 5, r[1] + 5) or "?"
        c1 = layout.grid.cell_of(r[2] - 5, r[3] - 5) or "?"
        out.append((f"tile {i + 1}: grid cells {c0}..{c1}", render_clip(page, r, max_px=max_px, dpi=dpi)))
    return out


def page_context(page, layout) -> list[dict]:
    """Content parts for one user message: the sheet text, then the captioned tiles."""
    t = tiles(page, layout)
    parts = [{"type": "input_text", "text":
              "SHEET TEXT LAYER (from the PDF; authoritative for characters). Format: [grid cell] text.\n"
              + page_text(layout)
              + "\n\nSHEET IMAGES follow in this order: " + "; ".join(c for c, _ in t)}]
    for caption, png in t:
        parts += [{"type": "input_text", "text": caption}, image_part(png, detail="high")]
    return parts
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_context.py -q`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add drawing_qa/context.py tests/test_context.py
git commit -m "feat: whole-page model context (grid-tagged text + sheet tiles)"
```

---

### Task 8: Sections and the inventory

**Files:**
- Create: `drawing_qa/sections.py`, `drawing_qa/inventory.py`, `tests/test_sections.py`, `tests/test_inventory.py`

**Interfaces:**
- Consumes: `PageExtract`, `page_context`, `LLM.parse_content`, the models' `Inventory*` lines.
- Produces:
  - Sections: `parse_section(s) -> Parsed(family, …)`, `decompose(parsed, length) -> list[Plate]`, `weight_matches(plates, pc_wt, net_per_piece, tol=0.02)`, `Plate`, `STEEL_KG_M3`.
  - `deterministic_inventory(x) -> Inventory`, `fasteners(bolts)`, `allowed_weld_sizes(layout, notes)`.
  - `build_inventory(x, page, layout, llm=None, model="gpt-5.4-mini", deep_model=None) -> Inventory`.
  - `InventoryLLM` (strict schema: `unknown_sections`, `welds`).

Decisions (user):
- Built-ups are decomposed into plates, with no wastage allowance (net as drawn).
- Welds are read by OpenAI.
- Contents: raw material, fasteners, paint and welds.

**Deterministic parts (measured):**
- **Section families.** Every section on the 5 sheets parses except `SPD508*508*608*608*8`: `PL`/`PLT`, `ISA`, `ISMC`, `PIPE`, `ROD`, `WH d×b×tf×tw` (2 flanges + web of d−2tf), `T d×b×tf×tw` (flange + web of d−tf).
- **Built-up recipes.** They reproduce every built-up BOM piece weight to 0.00%, and every plate is within 2%. So WH/T decomposition is done by code; OpenAI only interprets unknown sections, under the same 2% weight check.
- **Reconciliation.** Plates + sections equal the BOM gross total on all 5 sheets. Paint area (BOM total) is within 5% of Σ row area × qty.
- **Fasteners** are listed as the bolt table gives them. A taper washer with a blank qty is warned about and not counted.

**Weld guardrails** (each one seen live or in a test). A weld is rejected when:
- its size is not on the sheet (general-note size, or a standard fillet size written next to `TYP.`);
- it cites a part not in the BOM;
- its length is over twice the smaller part's (length + width);
- its count is over 2 × part qty;
- it exceeds the **per-part joint budget**: 2 joints per piece of the repeated part. Live, the model counted 09970's 4 lug plates against three neighbours, 12 joints for 4 plates.

Weld metal = length × a²/2 × 7850; electrode = weld metal / 0.6. Both are labelled estimates. `inventory.weld_coverage` warns when weld metal is under 0.5% of the steel weight. Live on 14281 it was 0.98 kg for 26 t, because built-up flange-to-web seams aren't drawn.

**Escalation.** If mini leaves an unknown section unresolved, or more than 30% of its welds are rejected, the OpenAI step re-runs once on `gpt-5.5`, and the better result is kept (more accepted unknowns, then more accepted and fewer rejected welds).

- [ ] **Step 1: Write failing tests**

`tests/test_sections.py`:
```python
import pytest

from drawing_qa.parsers.bom import parse_bom
from drawing_qa.sections import Plate, decompose, parse_section, weight_matches

from .conftest import GOLDEN


@pytest.mark.parametrize("section,family", [
    ("PL10*150", "plate"), ("PLT8*50", "plate"), ("WH1200X500X40X32", "built_up"), ("T 300X250X25X20", "built_up"),
    ("ISA75X75X8", "angle"), ("ISMC150", "channel"), ("PIPE219.1*5.4", "pipe"), ("ROD20", "round"),
    ("SPD508*508*608*608*8", "unknown"),
])
def test_parse_section_families(section, family):
    assert parse_section(section).family == family


def test_wh_and_tee_recipes():
    wh = decompose(parse_section("WH1200X500X40X32"), 7989.5)
    assert wh == [Plate(40, 500, 7989.5, 2), Plate(32, 1120, 7989.5, 1)]
    tee = decompose(parse_section("T 300X250X25X20"), 1950)
    assert tee == [Plate(25, 250, 1950, 1), Plate(20, 275, 1950, 1)]
    assert sum(p.weight_kg for p in wh) == pytest.approx(4756.50, abs=0.05)      # BOM piece weight of 3C2


@pytest.mark.parametrize("drg", sorted(GOLDEN))
def test_every_built_up_and_plate_matches_its_bom_weight(layouts, drg):
    for p in parse_bom(layouts(drg)).parts:
        ps = parse_section(p.section)
        if ps.family == "built_up":
            assert weight_matches(decompose(ps, p.length_mm), p.pc_wt, p.net_kg / p.qty), p.item_no
        elif ps.family == "plate":
            assert weight_matches([Plate(ps.thickness_mm, ps.width_mm, p.length_mm)], p.pc_wt, p.net_kg / p.qty), \
                p.item_no


def test_weight_matches_rejects_a_wrong_breakdown():
    assert not weight_matches([Plate(8, 200, 506)], 54.93, 54.93)
```

`tests/test_inventory.py`:
```python
import pymupdf
import pytest

from drawing_qa.inventory import InventoryLLM, allowed_weld_sizes, build_inventory, deterministic_inventory
from drawing_qa.layout import PageLayout
from drawing_qa.llm import LLM

from .conftest import GOLDEN, det, sample_path
from .fakes import FakeClient


@pytest.mark.parametrize("drg", sorted(GOLDEN))
def test_deterministic_inventory_reconciles_with_bom(drg, settings):
    inv = deterministic_inventory(det(drg, settings))
    levels = {c.id: c.level for c in inv.checks}
    assert levels["inventory.weight"] == "pass" and levels["inventory.paint"] == "pass"
    listed = sum(p.weight_kg for p in inv.plates) + sum(s.weight_kg for s in inv.sections)
    assert listed == pytest.approx(GOLDEN[drg]["gross"], abs=0.1)
    assert inv.assembly_qty == GOLDEN[drg]["asm_qty"] and inv.paint_area_m2 == GOLDEN[drg]["area"]


def test_built_ups_become_plates_14281(settings):
    inv = deterministic_inventory(det("14281", settings))
    assert not [s for s in inv.sections if s.family == "built-up"]
    pl40 = next(p for p in inv.plates if p.thickness_mm == 40 and p.grade == "E350BR(UT)")
    assert pl40.pieces == 8                                        # 4 WH1200X500X40X32 members x 2 flanges
    assert pl40.weight_kg == pytest.approx(9265.51, abs=0.05)
    assert any("3m471 (WH 500x40)" == s for s in pl40.sources)


def test_assembly_qty_multiplies_pieces_16362(settings):
    inv = deterministic_inventory(det("16362", settings))
    rod = next(s for s in inv.sections if s.profile == "ROD8")
    assert (rod.pieces, rod.total_length_m) == (44, 26.752)       # 22 per assembly x 2 assemblies
    assert [u.mark for u in inv.unclassified] == ["1m470"]


def test_fasteners_from_bolt_table_09970(settings):
    inv = deterministic_inventory(det("09970", settings))
    got = {(f.item, f.dia_mm, f.length_mm, f.qty) for f in inv.fasteners}
    assert got == {("bolt", "16", "60", 18), ("nut", "16", "", 26), ("plain washer", "18", "", 18)}
    assert {c.id: c.level for c in inv.checks}["inventory.taper_qty"] == "warn"   # qty column blank on sheet


def test_allowed_weld_sizes_include_general_note(layouts, settings):
    sizes = allowed_weld_sizes(layouts("09970"), det("09970", settings).notes)
    assert 6.0 in sizes and 7.0 not in sizes


def _llm_answer(unknown=(), welds=()):
    return lambda model, schema: InventoryLLM(unknown_sections=list(unknown), welds=list(welds))


def _run(drg, settings, fn, deep_model=None):
    p = sample_path(drg)
    page = pymupdf.open(p)[0]
    client = FakeClient(parse_fn=fn)
    inv = build_inventory(det(drg, settings), page, PageLayout.from_page(page), LLM(client), "mini", deep_model)
    return inv, client


def test_weld_guardrails_09970(settings):
    welds = [
        {"parts": ["4p639", "4DC3"], "size_mm": 6, "length_mm": 150, "count": 4, "evidence": "B - B"},     # ok
        {"parts": ["4p639", "4m666"], "size_mm": 6, "length_mm": 150, "count": 4, "evidence": "B - B"},    # ok (8 = 2x4)
        {"parts": ["4p639", "4m665"], "size_mm": 6, "length_mm": 150, "count": 4, "evidence": "E7"},       # over budget
        {"parts": ["4p637", "4DC3"], "size_mm": 6, "length_mm": 2233.9, "count": 1, "evidence": "A - A"},  # too long
        {"parts": ["4p999", "4DC3"], "size_mm": 6, "length_mm": 100, "count": 1, "evidence": ""},          # unknown part
        {"parts": ["4p660", "4m706"], "size_mm": 7, "length_mm": 300, "count": 2, "evidence": "D - D"},    # size not on sheet
    ]
    inv, _ = _run("09970", settings, _llm_answer(welds=welds))
    assert [w.parts for w in inv.welds] == [["4p639", "4DC3"], ["4p639", "4m666"]]
    reasons = " | ".join(inv.rejected_welds)
    for needle in ("max 8", "exceeds joint bound", "unknown parts ['4p999']", "size 7 not on sheet"):
        assert needle in reasons
    w = inv.welds[0]
    assert w.total_length_m == 0.6 and w.weld_metal_kg == pytest.approx(0.6 * 18e-6 * 7850, abs=1e-3)
    assert inv.electrode_kg == pytest.approx(inv.weld_metal_kg / 0.6, abs=0.01)


def test_unknown_section_breakdown_accepted_only_with_matching_weight(settings):
    good = {"mark": "1m470", "description": "square-to-square transition", "plates": [
        {"thickness_mm": 8, "width_mm": 1729, "length_mm": 506, "count": 1}]}             # 54.94 kg vs 54.93
    inv, _ = _run("16362", settings, _llm_answer(unknown=[good]))
    item = inv.unclassified[0]
    assert item.accepted and "SPD508*508*608*608*8" not in {s.profile for s in inv.sections}
    assert {c.id: c.level for c in inv.checks}["inventory.weight"] == "pass"
    bad = {**good, "plates": [{"thickness_mm": 8, "width_mm": 600, "length_mm": 506, "count": 1}]}
    inv, _ = _run("16362", settings, _llm_answer(unknown=[bad]))
    assert not inv.unclassified[0].accepted and "rejected" in inv.unclassified[0].note
    assert "SPD508*508*608*608*8" in {s.profile for s in inv.sections}


def test_escalates_once_and_keeps_the_better_answer(settings):
    good = {"mark": "1m470", "description": "transition", "plates": [
        {"thickness_mm": 8, "width_mm": 1729, "length_mm": 506, "count": 1}]}
    fn = lambda model, schema: InventoryLLM(unknown_sections=[good] if model == "deep" else [], welds=[])
    inv, client = _run("16362", settings, fn, deep_model="deep")
    assert [m for m, _, _ in client.responses.parse_calls] == ["mini", "deep"]
    assert inv.model == "deep" and inv.unclassified[0].accepted


def test_openai_failure_keeps_deterministic_inventory(settings):
    def boom(model, schema):
        raise RuntimeError("connection reset")
    inv, _ = _run("14281", settings, boom, deep_model="deep")
    assert {c.id: c.level for c in inv.checks}["inventory.llm"] == "warn"
    assert inv.plates and inv.welds == []


def test_request_carries_full_page_context(settings):
    inv, client = _run("09970", settings, _llm_answer())
    content = client.responses.parse_calls[0][2][0]["content"]
    assert content[0]["text"].startswith("SHEET TEXT LAYER") and "[D8] A - A" in content[0]["text"]
    assert sum(c["type"] == "input_image" for c in content) == 4      # 2x2 tiles on an A1 sheet
    assert "UNKNOWN sections: none" in content[-1]["text"]


def test_weld_coverage_warns_when_estimate_is_implausibly_small(settings):
    welds = [{"parts": ["3p307", "3C2"], "size_mm": 10, "length_mm": 400, "count": 4, "evidence": "A - A"}]
    inv, _ = _run("14281", settings, _llm_answer(welds=welds))
    c = next(c for c in inv.checks if c.id == "inventory.weld_coverage")
    assert c.level == "warn" and "flange-to-web seams" in c.message        # 14281 has WH built-ups
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_sections.py tests/test_inventory.py -q`
Expected: `ModuleNotFoundError: No module named 'drawing_qa.sections'` (and `'drawing_qa.inventory'`).

- [ ] **Step 3: Implement**

`drawing_qa/sections.py`:
```python
"""Tekla section strings -> procurement families.

Parsed deterministically (families seen on the sample sheets):
  PL t*w / PLT t*w          plate, thickness t, width w (length from the BOM row)
  ISA a X b X t             equal/unequal angle
  ISMC d / ISMB d           channel / beam
  PIPE od*t                 pipe
  ROD d                     round bar
  WH d X b X tf X tw        welded H: 2 flanges b x tf + web (d - 2 tf) x tw
  T d X b X tf X tw         welded tee: 1 flange b x tf + web (d - tf) x tw
Anything else (e.g. SPD508*508*608*608*8) is 'unknown' and goes to the LLM, whose answer must pass
the same weight check before it is used."""
import re
from dataclasses import dataclass

STEEL_KG_M3 = 7850.0


@dataclass(frozen=True)
class Plate:
    thickness_mm: float
    width_mm: float
    length_mm: float
    count: int = 1

    @property
    def area_m2(self):
        return self.width_mm * self.length_mm * self.count / 1e6

    @property
    def weight_kg(self):
        return self.thickness_mm * self.width_mm * self.length_mm * self.count * 1e-9 * STEEL_KG_M3


@dataclass(frozen=True)
class Parsed:
    family: str                     # plate | built_up | angle | channel | beam | pipe | round | unknown
    profile: str                    # normalised profile name
    thickness_mm: float | None = None
    width_mm: float | None = None
    d: float | None = None
    b: float | None = None
    tf: float | None = None
    tw: float | None = None
    kind: str = ""                  # WH | T for built-ups


N = r"(\d+(?:\.\d+)?)"


def parse_section(section: str) -> Parsed:
    s = section.replace(" ", "").upper()
    if m := re.fullmatch(rf"PLT?{N}\*{N}", s):
        return Parsed("plate", s, thickness_mm=float(m[1]), width_mm=float(m[2]))
    if m := re.fullmatch(rf"(WH|T){N}X{N}X{N}X{N}", s):
        return Parsed("built_up", s, d=float(m[2]), b=float(m[3]), tf=float(m[4]), tw=float(m[5]), kind=m[1])
    if re.fullmatch(rf"ISA{N}X{N}X{N}", s):
        return Parsed("angle", s)
    if re.fullmatch(rf"ISMC{N}", s):
        return Parsed("channel", s)
    if re.fullmatch(rf"ISMB{N}", s):
        return Parsed("beam", s)
    if re.fullmatch(rf"PIPE{N}\*{N}", s):
        return Parsed("pipe", s)
    if re.fullmatch(rf"ROD{N}", s):
        return Parsed("round", s)
    return Parsed("unknown", s)


def decompose(p: Parsed, length_mm: float) -> list[Plate]:
    """Plates that make up one built-up member of the given length."""
    if p.family != "built_up":
        raise ValueError(f"{p.profile} is not a built-up section")
    if p.kind == "WH":
        return [Plate(p.tf, p.b, length_mm, 2), Plate(p.tw, p.d - 2 * p.tf, length_mm, 1)]
    return [Plate(p.tf, p.b, length_mm, 1), Plate(p.tw, p.d - p.tf, length_mm, 1)]


def weight_matches(plates: list[Plate], bom_net_kg: float | None, bom_gross_kg: float | None, tol=0.02) -> bool:
    """Plate weight must be within tol of the member's BOM net or gross weight (cut-outs make net < gross)."""
    w = sum(pl.weight_kg for pl in plates)
    return any(ref and abs(w - ref) <= tol * ref for ref in (bom_net_kg, bom_gross_kg))
```

`drawing_qa/inventory.py`:
```python
"""Inventory for one page: what material, how much.

Deterministic (from the validated extract):
  plates by thickness + grade (incl. WH / T built-ups decomposed into plates, weight-checked),
  sections by profile + grade, fasteners from the bolt list, paint area from the BOM.
OpenAI-assisted (one structured call with the full page image + text):
  - sections the code cannot parse (e.g. SPD508*508*608*608*8): description + plate breakdown,
    accepted only if the plates weigh within 2% of the BOM member;
  - welds read from the views: parts joined, fillet size, length, count. Guardrails reject welds whose
    size is not on the sheet, that cite unknown parts, or that are longer than the parts can carry.
Weld metal and electrode figures are estimates and labelled as such."""
import re
from collections import defaultdict

from pydantic import BaseModel

from .context import page_context
from .geometry import num, xc, yc
from .models import Check, FastenerLine, Inventory, InventoryItem, PlateLine, SectionLine, WeldLine
from .sections import STEEL_KG_M3, Plate, decompose, parse_section, weight_matches

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
    parts: list[str]
    size_mm: float
    length_mm: float
    count: int
    evidence: str


class InventoryLLM(BaseModel):
    unknown_sections: list[UnknownSectionLLM]
    welds: list[WeldLLM]


INSTRUCTIONS = """You assist a steel fabrication estimator. You get one drawing sheet (full text layer tagged with grid
cells, and images of the whole sheet), its validated bill of materials, and a list of UNKNOWN sections.
1. unknown_sections: for each listed mark only, say what the member is (description) and give the plates it
   is fabricated from for ONE piece (thickness, width, length in mm, count). Leave plates empty if it is not
   made from plates.
2. welds: list every weld you can see in the views for ONE assembly. For each: the part marks it joins
   (use marks exactly as written; include the assembly main part if a part is welded to it), fillet leg size
   in mm (as written at the weld symbol; the general note gives the size when no size is shown), weld length
   per joint in mm (from the dimensions of the joined edge; count both sides if the symbol says so or shows
   both sides), how many such joints the assembly has (e.g. 'TYP.' on a part with qty 4), and evidence
   (view label and/or grid cell where you read it). Do not invent welds you cannot see."""


def _asm_qty(x):
    b = x.bom
    return b.assembly.qty if b and b.assembly and b.assembly.qty else 1


def _width_mm(section, length):
    """A generous joint-length bound: the part's edge perimeter proxy (mm)."""
    p = parse_section(section)
    nums = [float(v) for v in re.findall(r"\d+(?:\.\d+)?", p.profile)]
    if p.family == "plate":
        return p.width_mm
    if p.family == "built_up":
        return 2 * p.b + p.d
    if p.family in ("pipe", "round"):
        return 3.1416 * nums[0]
    if nums:
        return sum(nums[:2]) if p.family == "angle" else 2 * nums[0]
    return length


def allowed_weld_sizes(layout, notes) -> set[float]:
    """Fillet sizes the sheet actually shows: the general-note size plus standard sizes written near 'TYP.'."""
    sizes = {float(m) for n in notes for m in re.findall(r"(\d+)\s*MM FILLET", n.upper())}
    typ = [w for w in layout.words if w[4].startswith("TYP")]
    for w in layout.words:
        if re.fullmatch(r"\d{1,2}", w[4]) and int(w[4]) in FILLET_SIZES and \
                any(abs(xc(w) - xc(t)) < 60 and abs(yc(w) - yc(t)) < 40 for t in typ):
            sizes.add(float(w[4]))
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
        if ps.family == "built_up":
            pls = decompose(ps, p.length_mm or 0)
            if weight_matches(pls, p.pc_wt, (p.net_kg or 0) / (p.qty or 1)):
                for pl in pls:
                    add_plate(pl.thickness_mm, p.material, pl.count * q, pl.area_m2 * q, pl.weight_kg * q,
                              f"{p.item_no} ({ps.kind} {pl.width_mm:g}x{pl.thickness_mm:g})")
                continue
            inv.checks.append(Check(id=f"inventory.decompose.{p.item_no}", level="warn", region="inventory",
                                    message=f"{p.item_no} {p.section}: plate recipe does not match BOM weight; "
                                            "kept as a section."))
        family = ps.family if ps.family not in ("built_up",) else "built-up"
        key = (ps.profile, p.material)
        sl = sections.setdefault(key, SectionLine(profile=ps.profile, family=family if family != "unknown" else "other",
                                                  grade=p.material, pieces=0, total_length_m=0, weight_kg=0))
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
    _steel_checks(inv, x)
    return inv


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


def _steel_checks(inv, x):
    listed = sum(p.weight_kg for p in inv.plates) + sum(s.weight_kg for s in inv.sections)
    ok = abs(listed - inv.total_steel_kg) <= max(0.1, 0.005 * inv.total_steel_kg)
    inv.checks = [c for c in inv.checks if c.id != "inventory.weight"]
    inv.checks.append(Check(id="inventory.weight", level="pass" if ok else "fail", region="inventory",
                            message=f"Plates + sections = {listed:.2f} kg; BOM gross total = {inv.total_steel_kg} kg."))
    b = x.bom
    per_piece = sum((p.surface_area_m2 or 0) * (p.qty or 0) for p in b.parts) * inv.assembly_qty
    if inv.paint_area_m2:
        ok = abs(per_piece - inv.paint_area_m2) <= 0.05 * inv.paint_area_m2
        inv.checks = [c for c in inv.checks if c.id != "inventory.paint"]
        inv.checks.append(Check(id="inventory.paint", level="pass" if ok else "warn", region="inventory",
                                message=f"Paint area {inv.paint_area_m2} m² (BOM total); Σ row area × qty = "
                                        f"{per_piece:.2f} m²."))
    bad_taper = [r.assembly_mark or "(own)" for r in x.bolts if r.taper_dia and num(r.taper_qty) is None]
    if bad_taper:
        inv.checks.append(Check(id="inventory.taper_qty", level="warn", region="inventory",
                                message=f"Taper washers listed without a quantity for {bad_taper}; not counted."))


def _needs_escalation(inv) -> bool:
    unresolved = any(not u.accepted for u in inv.unclassified)
    rejected = len(inv.rejected_welds)
    return unresolved or rejected > 0.3 * max(1, rejected + len(inv.welds))


def _score(inv):
    return (sum(u.accepted for u in inv.unclassified), len(inv.welds) - 2 * len(inv.rejected_welds))


def build_inventory(x, page, layout, llm=None, model="gpt-5.4-mini", deep_model=None) -> Inventory:
    """Deterministic inventory, then one OpenAI pass; if that pass leaves unknown sections unresolved or has
    more than 30% of its welds rejected, one retry on deep_model and the better-scoring result is kept."""
    if llm is None or x.bom is None:
        return deterministic_inventory(x)
    before = llm.usage_summary()
    inv = _llm_inventory(x, page, layout, llm, model)
    if deep_model and deep_model != model and not any(c.id == "inventory.llm" for c in inv.checks)             and _needs_escalation(inv):
        deep = _llm_inventory(x, page, layout, llm, deep_model)
        if not any(c.id == "inventory.llm" for c in deep.checks) and _score(deep) > _score(inv):
            inv = deep
    after = llm.usage_summary()
    inv.usage = {f"{m}:{k}": v - before.get(m, {}).get(k, 0) for m, u in after.items() for k, v in u.items()
                 if v - before.get(m, {}).get(k, 0)}
    return inv


def _llm_inventory(x, page, layout, llm, model) -> Inventory:
    inv = deterministic_inventory(x)
    inv.model = model
    rows = {p.item_no: p for p in x.bom.parts}
    unknown = [u.mark for u in inv.unclassified]
    bom_txt = "\n".join(f"{p.item_no} | {p.section} | L={p.length_mm} | qty={p.qty} | pc_wt={p.pc_wt} | {p.material}"
                        for p in x.bom.parts)
    text = (f"ASSEMBLY {inv.assembly_mark} x {inv.assembly_qty}\nBOM (mark | section | length mm | qty | piece kg | "
            f"grade):\n{bom_txt}\nNOTES:\n" + "\n".join(x.notes) + f"\nUNKNOWN sections: {unknown or 'none'}")
    try:
        content = page_context(page, layout) + [{"type": "input_text", "text": text}]
        out = llm.parse_content(model, INSTRUCTIONS, content, InventoryLLM)
    except Exception as e:
        inv.checks.append(Check(id="inventory.llm", level="warn", region="inventory",
                                message=f"OpenAI step failed ({type(e).__name__}: {e}); deterministic inventory only."))
        return inv
    _apply_unknown(inv, out.unknown_sections, rows, unknown)
    _apply_welds(inv, out.welds, rows, allowed_weld_sizes(layout, x.notes))
    _steel_checks(inv, x)
    return inv


def _apply_unknown(inv, answers, rows, unknown):
    by_mark = {a.mark: a for a in answers if a.mark in unknown}
    for item in inv.unclassified:
        a = by_mark.get(item.mark)
        if a is None:
            item.note = "model gave no interpretation"
            continue
        p = rows[item.mark]
        pls = [Plate(pl.thickness_mm, pl.width_mm, pl.length_mm, pl.count) for pl in a.plates]
        item.description = a.description
        if pls and weight_matches(pls, p.pc_wt, (p.net_kg or 0) / (p.qty or 1)):
            item.accepted = True
            item.note = "plate breakdown matches BOM weight (±2%)"
            q = (p.qty or 0) * inv.assembly_qty
            _move_to_plates(inv, p, pls, q)
        else:
            w = sum(pl.weight_kg for pl in pls)
            item.note = (f"plate breakdown {w:.2f} kg vs BOM {p.pc_wt} kg per piece: rejected, kept as a section"
                         if pls else "no plate breakdown: kept as a section")
    pending = [i.mark for i in inv.unclassified if not i.accepted]
    inv.checks.append(Check(id="inventory.unclassified", level="warn" if pending else "pass", region="inventory",
                            message=f"Sections needing review: {pending}" if pending else
                            "Every BOM member is classified."))


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
    marks = set(rows) | ({inv.assembly_mark} if inv.assembly_mark else set())
    rejected = []
    used = defaultdict(int)
    for w in welds:
        unknown = [m for m in w.parts if m not in marks]
        why = []
        if not w.parts or unknown:
            why.append(f"unknown parts {unknown}")
        if w.size_mm not in sizes:
            why.append(f"size {w.size_mm:g} not on sheet {sorted(sizes)}")
        cited = [rows[m] for m in w.parts if m in rows]
        if cited:
            limit = min(2 * ((r.length_mm or 0) + _width_mm(r.section, r.length_mm or 0)) for r in cited)
            if w.length_mm <= 0 or w.length_mm > limit:
                why.append(f"length {w.length_mm:g} mm exceeds joint bound {limit:.0f} mm")
            if w.count < 1 or w.count > 2 * max((r.qty or 1) for r in cited):
                why.append(f"count {w.count} implausible for part qty")
        if cited and not why:
            # joint budget: the attached part (the repeated, highest-qty one, e.g. 4 lugs on 1 pipe) carries at
            # most 2 joints per piece (both sides); stops the model counting one plate's welds once per neighbour
            att = max(cited, key=lambda r: r.qty or 1)
            if used[att.item_no] + w.count > 2 * (att.qty or 1):
                why.append(f"{att.item_no} would have {used[att.item_no] + w.count} joints; max {2 * (att.qty or 1)}")
            else:
                used[att.item_no] += w.count
        if why:
            rejected.append(f"{'+'.join(w.parts)} {w.size_mm:g}mm: {'; '.join(why)}")
            continue
        total_m = w.length_mm * w.count * inv.assembly_qty / 1000
        metal = total_m * (w.size_mm ** 2 / 2) * 1e-6 * STEEL_KG_M3
        inv.welds.append(WeldLine(parts=w.parts, size_mm=w.size_mm, length_mm=w.length_mm, count=w.count,
                                  evidence=w.evidence, total_length_m=round(total_m, 3), weld_metal_kg=round(metal, 3)))
    inv.rejected_welds = rejected
    inv.weld_metal_kg = round(sum(w.weld_metal_kg for w in inv.welds), 2)
    inv.electrode_kg = round(inv.weld_metal_kg * ELECTRODE_PER_WELD_METAL, 2)
    inv.checks.append(Check(id="inventory.welds", level="warn" if rejected else "pass", region="inventory",
                            message=(f"{len(inv.welds)} weld runs accepted (estimates)"
                                     + (f"; {len(rejected)} rejected: " + " | ".join(rejected[:8]) if rejected else ""))))
    share = inv.weld_metal_kg / inv.total_steel_kg if inv.total_steel_kg else 0
    seams = [s for p in inv.plates for s in p.sources if "(WH " in s or "(T " in s]
    inv.checks.append(Check(
        id="inventory.weld_coverage", level="pass" if share >= 0.005 else "warn", region="inventory",
        message=f"Weld metal {inv.weld_metal_kg} kg = {share:.2%} of steel weight (fabricated steel is typically "
                "1-2%). The estimate covers only welds drawn with symbols in the views"
                + ("; flange-to-web seams of built-up members are not drawn and not included" if seams else "")
                + "."))
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_sections.py tests/test_inventory.py -q`
Expected: `31 passed`.

- [ ] **Step 5: Commit**

```bash
git add drawing_qa/sections.py drawing_qa/inventory.py tests/test_sections.py tests/test_inventory.py
git commit -m "feat: material inventory with built-up decomposition and guarded OpenAI weld step"
```

---

### Task 9: Visual Q&A chat with full-page context

**Files:**
- Create: `drawing_qa/chat.py`, `tests/test_chat.py`

**Interfaces:**
- Produces:
  - `ChatSession(extract, page, layout, llm, model, settings, inventory=None)` with `.ask(question) -> Turn(question, answer, images, tool_log)`, `.set_inventory(inv)`, `.turns` and `._rect_for(target)`.
  - `compact_extract(x)`, `TOOLS`, `INSTRUCTIONS`.
- Context order: page context (grid-tagged text + tiles), then extract JSON, then inventory JSON if present.
- Tools: `query_bom`, `search_text`, `zoom` (grid cell / range / region / view label; a duplicated label asks for a grid cell).
- Robustness:
  - Bad tool arguments are returned to the model as `error: …`.
  - Zoom images are stripped from stored history.
  - Only the last `chat_keep_turns` turns are kept.
  - The prompt rule is to copy identifiers exactly.

Live on 14281 with gpt-5.4-mini, answers were correct and cited their sources:
- "How much 40 mm plate …" → 8 pcs, 9265.51 kg, from the 4 WH1200X500X40X32 members.
- "What bolts connect 3C1 …" → 88 × M24×150 10.9 from the bolt table. It zoomed the bolt table and view G - G.

Two questions used 4 calls: 181k input tokens, 93k of them cached. A0 context is about 40k per call.

- [ ] **Step 1: Write failing tests**

`tests/test_chat.py`:
```python
import json

import pymupdf
import pytest

from drawing_qa.chat import ChatSession
from drawing_qa.layout import PageLayout
from drawing_qa.llm import LLM

from .conftest import det, sample_path
from .fakes import FakeClient, call_response, text_response


def test_chat_runs_tools_and_keeps_history(settings):
    p = sample_path("09970")
    x = det("09970", settings)
    page = pymupdf.open(p)[0]
    script = [call_response("zoom", json.dumps({"target": "bom"})),
              text_response("12 plates, 13.40 kg (4p639, 4p640, 4p641)."),
              call_response("query_bom", json.dumps({"contains": "4p660"}), call_id="call_2"),
              text_response("E350A.")]
    client = FakeClient(script=script)
    chat = ChatSession(x, page, PageLayout.from_page(page), LLM(client), "mini", settings)
    t1 = chat.ask("How many 8 mm plates?")
    assert t1.tool_log == ["zoom(bom)"] and len(t1.images) == 1 and "13.40" in t1.answer
    t2 = chat.ask("Material of 4p660?")
    assert t2.tool_log == ["query_bom(4p660)"] and t2.answer == "E350A."
    second_input = client.responses.create_calls[2][1]
    assert any(isinstance(i, dict) and i.get("content") == "How many 8 mm plates?" for i in second_input)
    old_zoom = [i for i in second_input if isinstance(i, dict) and i.get("type") == "function_call_output"]
    assert old_zoom and isinstance(old_zoom[0]["output"], str)   # earlier image stripped from history
    assert all(not isinstance(i.get("output"), list) for i in chat.history if isinstance(i, dict))


def test_chat_survives_malformed_tool_arguments(settings):
    p = sample_path("09970")
    x = det("09970", settings)
    page = pymupdf.open(p)[0]
    client = FakeClient(script=[call_response("zoom", "{not json"), text_response("Could not zoom.")])
    chat = ChatSession(x, page, PageLayout.from_page(page), LLM(client), "mini", settings)
    turn = chat.ask("Zoom somewhere")
    assert turn.tool_log == ["zoom: error"] and turn.answer == "Could not zoom."
    sent = client.responses.create_calls[1][1]
    assert any(isinstance(i, dict) and str(i.get("output", "")).startswith("error:") for i in sent)


def test_chat_zoom_targets(settings):
    p = sample_path("14281")
    x = det("14281", settings)
    page = pymupdf.open(p)[0]
    chat = ChatSession(x, page, PageLayout.from_page(page), LLM(FakeClient()), "mini", settings)
    for target in ["E7", "E7:G9", "bom", "B - B", "title_block"]:
        r = chat._rect_for(target)
        assert r[2] > r[0] and r[3] > r[1], target
    with pytest.raises(ValueError):
        chat._rect_for("nowhere")
    with pytest.raises(ValueError, match="occurs 2 times"):   # 'M - M' is drawn at N13 and P18
        chat._rect_for("M - M")
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_chat.py -q`
Expected: `ModuleNotFoundError: No module named 'drawing_qa.chat'`.

- [ ] **Step 3: Implement**

`drawing_qa/chat.py`:
```python
"""Visual Q&A over one page. Every request starts with the same prefix: the whole sheet (grid-tagged
text layer + high-res tiles, see context.py), the validated PyMuPDF extract and, once built, the inventory.
Tools fetch more evidence: query_bom, search_text, zoom (hi-res crop returned as an image)."""
import json
import re
from dataclasses import dataclass, field

from .context import page_context
from .llm import image_part
from .render import render_clip

INSTRUCTIONS = """You are a structural-steel fabrication drawing analyst answering questions about ONE drawing sheet
(Tekla export). Ground rules:
1. You see the whole sheet: its complete text layer (tagged with grid cells) and images of every part of it.
   The EXTRACT JSON was produced by deterministic PDF parsing and passed arithmetic checks; treat its numbers as
   authoritative. Never invent quantities, weights, sizes or marks. INVENTORY JSON (if present) lists material
   totals; its weld and electrode figures are estimates.
2. Read geometry, connections, welds and view dimensions from the sheet images and text. When a detail is too
   small to read, call zoom on the grid cell(s); use search_text to locate marks/labels. Look before you answer.
3. Cite evidence inline: part marks (e.g. 3p307), BOM rows, grid cells (e.g. E7), view labels (e.g. B - B).
4. If the sheet does not contain the answer, say so plainly. Label visual inferences as "from the drawing view".
5. Units: lengths mm, levels m, weights kg unless the sheet says otherwise. Show arithmetic when you compute.
6. Copy marks, grid locations, levels, sections and specifications exactly as written on the sheet
   (e.g. '19-20/<LEG-1' stays as is); never add or normalise characters."""

REGION_NAMES = ["bom", "abstract", "bolts", "title_block", "notes", "mark_location", "revisions"]

TOOLS = [
    {"type": "function", "name": "query_bom", "strict": True,
     "description": "Filter BOM rows by case-insensitive substring over mark, section and material. Empty string = all rows.",
     "parameters": {"type": "object", "properties": {"contains": {"type": "string"}},
                    "required": ["contains"], "additionalProperties": False}},
    {"type": "function", "name": "search_text", "strict": True,
     "description": "Find text on the sheet (marks, labels, numbers). Returns each hit with its grid cell.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                    "required": ["query"], "additionalProperties": False}},
    {"type": "function", "name": "zoom", "strict": True,
     "description": ("Look at part of the sheet at high resolution. target is a grid cell ('E7'), a cell range "
                     "('E7:G9'), a region name (" + ", ".join(REGION_NAMES) + ") or a view label ('B - B', '4p637')."),
     "parameters": {"type": "object", "properties": {"target": {"type": "string"}},
                    "required": ["target"], "additionalProperties": False}},
]


@dataclass
class Turn:
    question: str
    answer: str
    images: list = field(default_factory=list)      # [(caption, png_bytes)]
    tool_log: list = field(default_factory=list)    # ["zoom(E7)", ...]


def compact_extract(x) -> dict:
    d = x.model_dump(exclude={"regions", "usage", "file_sha256"})
    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items() if k != "bbox" and v not in ("", None, [], {})}
        if isinstance(o, list):
            return [strip(v) for v in o]
        return o
    return strip(d)


class ChatSession:
    def __init__(self, extract, page, layout, llm, model, settings, inventory=None):
        self.x, self.page, self.layout, self.llm, self.model, self.s = extract, page, layout, llm, model, settings
        self.turns: list[Turn] = []
        self.history: list = []          # Responses-API input items for completed turns
        self._sheet = page_context(page, layout)        # identical on every call -> prompt-cache hits
        self.set_inventory(inventory)

    def set_inventory(self, inventory):
        """(Re)build the fixed context prefix; called when the inventory becomes available."""
        data = "EXTRACT JSON:\n" + json.dumps(compact_extract(self.x), separators=(",", ":"))
        if inventory is not None:
            data += "\n\nINVENTORY JSON:\n" + inventory.model_dump_json(exclude={"usage"})
        self._context = [{"role": "user", "content": self._sheet + [{"type": "input_text", "text": data}]}]

    # ---- tools
    def _rect_for(self, target):
        t = target.strip()
        if t.lower() in self.x.regions:
            return self.x.regions[t.lower()]
        m = re.fullmatch(r"([A-Za-z]\d{1,2})(?::([A-Za-z]\d{1,2}))?", t)
        if m:
            a = self.layout.grid.cell_rect(m.group(1))
            b = self.layout.grid.cell_rect(m.group(2)) if m.group(2) else a
            return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))
        hits = [v for v in self.x.view_labels if t in (v.label, v.ref)]
        if len(hits) > 1:
            raise ValueError(f"view label {t!r} occurs {len(hits)} times, at {[v.cell for v in hits]}; "
                             "zoom a grid cell instead")
        if not hits:
            raise ValueError(f"unknown zoom target {target!r}")
        v = hits[0]
        cx, cy = (v.bbox[0] + v.bbox[2]) / 2, (v.bbox[1] + v.bbox[3]) / 2
        r = self.layout.grid.cell_rect(v.cell)
        w, h = (r[2] - r[0]) * 1.5, (r[3] - r[1]) * 2.2
        return (cx - w, cy - 2 * h * 0.8, cx + w, cy + h * 0.3)   # views sit above their label

    def _run_tool(self, name, args, turn):
        if name == "query_bom":
            q = args["contains"].lower()
            rows = [r.model_dump(exclude={"bbox"}) for r in (self.x.bom.parts if self.x.bom else [])
                    if not q or q in f"{r.item_no} {r.section} {r.material}".lower()]
            return json.dumps({"rows": rows, "totals": self.x.bom.totals.model_dump() if self.x.bom else None})
        if name == "search_text":
            q = args["query"].strip()
            hits = [{"text": w[4], "cell": self.layout.grid.cell_of((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)}
                    for w in self.layout.words if q.lower() in w[4].lower()]
            if not hits:
                hits = [{"text": q, "cell": self.layout.grid.cell_of((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)}
                        for r in self.layout.find(q)]
            return json.dumps({"hits": hits[:40], "total": len(hits)})
        if name == "zoom":
            rect = self._rect_for(args["target"])
            png = render_clip(self.page, rect, max_px=self.s.crop_max_px, dpi=self.s.crop_dpi)
            turn.images.append((f"zoom {args['target']}", png))
            return [{"type": "input_text", "text": f"Zoom of {args['target']}:"}, image_part(png)]
        raise ValueError(f"unknown tool {name}")

    # ---- conversation
    def _trimmed_history(self):
        starts = [i for i, it in enumerate(self.history) if isinstance(it, dict) and it.get("role") == "user"]
        if len(starts) > self.s.chat_keep_turns:
            return self.history[starts[-self.s.chat_keep_turns]:]
        return self.history

    @staticmethod
    def _without_images(items):
        """Finished turns keep tool text but not images: the model can zoom again, memory stays flat."""
        out = []
        for it in items:
            if isinstance(it, dict) and it.get("type") == "function_call_output" and isinstance(it.get("output"), list):
                it = {**it, "output": "[zoom image from an earlier turn omitted; call zoom again if needed]"}
            out.append(it)
        return out

    def ask(self, question: str) -> Turn:
        turn = Turn(question=question, answer="")
        items = [{"role": "user", "content": question}]
        for _ in range(self.s.chat_max_tool_rounds + 1):
            r = self.llm.create(self.model, INSTRUCTIONS, self._context + self._trimmed_history() + items, TOOLS)
            calls = [o for o in r.output if o.type == "function_call"]
            items += [o.model_dump(exclude_none=True) for o in r.output]
            if not calls:
                turn.answer = r.output_text
                break
            for c in calls:
                try:
                    args = json.loads(c.arguments)
                    turn.tool_log.append(f"{c.name}({', '.join(str(v) for v in args.values())})")
                    out = self._run_tool(c.name, args, turn)
                except Exception as e:           # bad arguments or target: tell the model, keep the turn alive
                    turn.tool_log.append(f"{c.name}: error")
                    out = f"error: {e}"
                items.append({"type": "function_call_output", "call_id": c.call_id, "output": out})
        else:
            turn.answer = "Stopped after too many tool calls; please narrow the question."
        self.history += self._without_images(items)
        self.turns.append(turn)
        return turn
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_chat.py -q`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add drawing_qa/chat.py tests/test_chat.py
git commit -m "feat: multi-turn Q&A over the whole sheet with query_bom, search_text and zoom"
```

---

### Task 10: Exports

**Files:**
- Create: `drawing_qa/export.py`, `tests/test_export.py`

**Interfaces:**
- Produces:
  - `to_json(x)` and `bom_csv(x)`.
  - `inventory_frames(inv)`.
  - `to_excel(x, inventory=None) -> bytes`. Its sheets are `Title, BOM, Locations, Abstract, Bolts, Revisions, Notes, Views, Checks`, plus `Inv Summary, Inv Plates, Inv Sections, Inv Fasteners, Inv Welds, Inv Review, Inv Checks` when an inventory is given.

- [ ] **Step 1: Write failing test**

`tests/test_export.py`:
```python
import io
import json

import openpyxl

from drawing_qa import export

from .conftest import det


def test_exports(settings):
    from drawing_qa.inventory import deterministic_inventory
    x = det("14281", settings)
    base = ["Title", "BOM", "Locations", "Abstract", "Bolts", "Revisions", "Notes", "Views", "Checks"]
    assert openpyxl.load_workbook(io.BytesIO(export.to_excel(x))).sheetnames == base
    wb = openpyxl.load_workbook(io.BytesIO(export.to_excel(x, deterministic_inventory(x))))
    assert wb.sheetnames == base + ["Inv Summary", "Inv Plates", "Inv Sections", "Inv Fasteners", "Inv Welds",
                                    "Inv Review", "Inv Checks"]
    assert wb["Inv Plates"].max_row == 9 + 1
    assert wb["BOM"].max_row == 71 + 1
    csv = export.bom_csv(x).splitlines()
    assert csv[0].startswith("item_no,section,length_mm,qty") and len(csv) == 72
    assert json.loads(export.to_json(x))["title_block"]["drawing_no"].endswith("14281")
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_export.py -q`
Expected: `ImportError: cannot import name 'export'`.

- [ ] **Step 3: Implement**

`drawing_qa/export.py`:
```python
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
        ("Weld metal (kg, estimate)", inv.weld_metal_kg),
        ("Electrode (kg, estimate)", inv.electrode_kg),
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
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_export.py -q`
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add drawing_qa/export.py tests/test_export.py
git commit -m "feat: Excel, CSV and JSON exports including the inventory"
```

---

### Task 11: Streamlit app, README, live smoke run

**Files:**
- Create: `app.py`, `tests/test_app.py`, `README.md`, `scripts/live_smoke.py`

**Interfaces:**
- The UI:
  - **Sidebar:** upload, page picker, OpenAI toggle (disabled without a key), deep-mode toggle, checks metric, session tokens.
  - **Tabs:**
    - **Drawing:** overview + grid-cell zoom.
    - **Extract.**
    - **Checks.**
    - **Inventory:** the deterministic tables are always shown. A "Run OpenAI step" button adds welds and unknown sections; the rejected welds are in an expander, followed by the inventory checks.
    - **Chat:** per page and model, receives the inventory once it is built.
    - **Export.**
  - `Settings()` is built on every run. A PDF that won't open, and a failed chat request, show `st.error`. A failed inventory OpenAI step shows as an `inventory.llm` warning.

- [ ] **Step 1: Write failing app tests**

`tests/test_app.py`:
```python
from pathlib import Path

from streamlit.testing.v1 import AppTest

from .conftest import sample_path

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_app_prompts_for_upload():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert [i.value for i in at.info] == ["Upload a drawing PDF to begin."]
    assert not at.exception


def test_app_extracts_uploaded_pdf_without_llm(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DQA_CACHE_DIR", str(tmp_path))
    p = sample_path("16807")
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.file_uploader[0].upload(p.name, p.read_bytes(), "application/pdf")
    at.run()
    assert not at.exception
    assert [t.value for t in at.title] == ["TST-SFD-46-01-01-07-000-16807"]
    assert at.metric[0].value.endswith("0 ❌")


def test_app_survives_unreachable_openai(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:9/v1")      # nothing listens here
    monkeypatch.setenv("DQA_CACHE_DIR", str(tmp_path))
    p = sample_path("16807")
    at = AppTest.from_file(APP, default_timeout=180).run()
    at.file_uploader[0].upload(p.name, p.read_bytes(), "application/pdf")
    at.run()
    assert not at.exception
    assert [t.value for t in at.title] == ["TST-SFD-46-01-01-07-000-16807"]   # extraction never needs OpenAI
    assert at.metric[0].value.endswith("0 ❌")
    run = next(b for b in at.button if b.label.startswith("Run OpenAI step"))
    run.click().run()                                                      # inventory OpenAI step fails...
    assert not at.exception                                                # ...without crashing the page
    shown = " ".join(str(df.value.to_dict()) for df in at.dataframe)
    assert "inventory.llm" in shown                                        # reported as a warning
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_app.py -q`
Expected: FAIL. `AppTest.from_file` cannot find `app.py`.

- [ ] **Step 3: Implement app, README, smoke script**

`app.py`:
```python
"""Streamlit UI: upload a drawing PDF, pick a page, review the PyMuPDF extract and its checks, build the
material inventory (OpenAI-assisted), ask questions about the sheet, export everything."""
import os

import pandas as pd
import streamlit as st

from drawing_qa import export
from drawing_qa.chat import ChatSession
from drawing_qa.config import Settings
from drawing_qa.extract import extract_page
from drawing_qa.inventory import build_inventory, deterministic_inventory
from drawing_qa.layout import PageLayout, open_pdf, sha256
from drawing_qa.llm import LLM
from drawing_qa.render import render_clip, render_overview

st.set_page_config(page_title="Drawing Q&A", layout="wide")
ss = st.session_state
settings = Settings()        # read env every run
for k in ("extracts", "chats", "docs", "inventories"):
    ss.setdefault(k, {})
icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}


@st.cache_data(max_entries=8)
def overview_png(file_sha, page_index, _page):
    return render_overview(_page, 2400)


with st.sidebar:
    st.header("Drawing")
    up = st.file_uploader("Upload PDF", type=["pdf"])
    has_key = bool(os.getenv("OPENAI_API_KEY"))
    use_llm = st.toggle("Use OpenAI (chat + inventory)", value=has_key, disabled=not has_key,
                        help=None if has_key else "Set OPENAI_API_KEY to enable.")
    deep = st.toggle(f"Deep mode ({settings.deep_model} for everything)", value=False, disabled=not use_llm)
    model = settings.deep_model if deep else settings.model
    st.caption(f"Model: {model}" + ("" if deep else f" · escalation: {settings.deep_model}"))
    if use_llm and "llm" not in ss:
        ss.llm = LLM(timeout=settings.api_timeout_s, max_retries=settings.api_max_retries)

if not up:
    st.info("Upload a drawing PDF to begin.")
    st.stop()

data = up.getvalue()
sha = sha256(data)
if sha not in ss.docs:
    try:
        ss.docs[sha] = open_pdf(data)
    except Exception as e:
        st.error(f"Could not open this PDF: {e}")
        st.stop()
doc = ss.docs[sha]
page_index = st.sidebar.selectbox("Page", range(doc.page_count), format_func=lambda i: f"Page {i + 1}")
page = doc[page_index]
key = (sha, page_index)

if key not in ss.extracts:
    with st.spinner("Reading the sheet with PyMuPDF…"):
        ss.extracts[key] = extract_page(data, page_index, up.name, settings=settings)
x = ss.extracts[key]
inv = ss.inventories.get(key) or deterministic_inventory(x)

with st.sidebar:
    fails = sum(c.level == "fail" for c in x.checks)
    warns = sum(c.level == "warn" for c in x.checks)
    st.metric("Checks", f"{len(x.checks) - fails - warns} ✅ · {warns} ⚠️ · {fails} ❌")
    if use_llm:
        st.caption("Session tokens")
        st.json(ss.llm.usage_summary(), expanded=False)

tb = x.title_block
st.title(tb.drawing_no or up.name)
st.caption(" · ".join(filter(None, [" / ".join(tb.title_lines), f"Rev {tb.rev}" if tb.rev else "",
                                   tb.sheet_size, f"{tb.weight_kg} kg" if tb.weight_kg else ""])))

tab_draw, tab_extract, tab_checks, tab_inv, tab_chat, tab_export = st.tabs(
    ["Drawing", "Extract", "Checks", "Inventory", "Chat", "Export"])

with tab_draw:
    st.image(overview_png(sha, page_index, page), width="stretch")
    cell = st.text_input("Zoom to grid cell or range (e.g. E7 or E7:G9)")
    if cell:
        try:
            layout = PageLayout.from_page(page)
            a, _, b = cell.upper().partition(":")
            r1 = layout.grid.cell_rect(a)
            r2 = layout.grid.cell_rect(b) if b else r1
            rect = (min(r1[0], r2[0]), min(r1[1], r2[1]), max(r1[2], r2[2]), max(r1[3], r2[3]))
            st.image(render_clip(page, rect), caption=cell.upper())
        except ValueError as e:
            st.error(str(e))

with tab_extract:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Title block")
        st.table(pd.DataFrame([
            ("Drawing no.", tb.drawing_no), ("Rev", tb.rev), ("Sheet", f"{tb.sheet_no} ({tb.sheet_size})"),
            ("Weight (kg)", tb.weight_kg), ("Department", tb.department), ("Equip/area", tb.equip_area),
            ("Project", tb.project), ("Title", " / ".join(tb.title_lines)),
            ("Drawn", f"{tb.drn.name} {tb.drn.date}"), ("Checked", f"{tb.chd.name} {tb.chd.date}"),
            ("Approved", f"{tb.app.name} {tb.app.date}"),
        ], columns=["Field", "Value"]).astype(str))
    with c2:
        st.subheader("Erection locations")
        st.dataframe(pd.DataFrame([m.model_dump() for m in x.mark_locations]), width="stretch", hide_index=True)
        st.subheader("Notes")
        for n in x.notes:
            st.markdown(f"- {n}")
    if x.bom:
        st.subheader(f"Bill of materials — {len(x.bom.parts)} parts")
        st.dataframe(pd.DataFrame([r.model_dump(exclude={"bbox"}) for r in x.bom.parts]), width="stretch")
        st.caption(f"Totals: {x.bom.totals.model_dump()}")
    for title, rows in (("Abstract", x.abstract.rows if x.abstract else []), ("Permanent bolts", x.bolts),
                        ("Revisions", x.revisions)):
        if rows:
            st.subheader(title)
            st.dataframe(pd.DataFrame([r.model_dump() for r in rows]), width="stretch")
    if x.view_labels:
        st.subheader(f"Views — {len(x.view_labels)}")
        st.dataframe(pd.DataFrame([v.model_dump(exclude={"bbox"}) for v in x.view_labels]), width="stretch",
                     hide_index=True)

with tab_checks:
    st.dataframe(pd.DataFrame([{"": icon[c.level], "check": c.id, "region": c.region, "detail": c.message}
                               for c in x.checks]), width="stretch", hide_index=True)

with tab_inv:
    st.caption(f"Assembly {inv.assembly_mark} × {inv.assembly_qty} · quantities net as drawn · "
               f"steel {inv.total_steel_kg} kg · paint {inv.paint_area_m2} m²")
    if use_llm:
        label = "Re-run OpenAI step" if key in ss.inventories else "Run OpenAI step (welds, unknown sections)"
        if st.button(label):
            with st.spinner("Reading welds and unknown sections from the sheet…"):
                ss.inventories[key] = build_inventory(x, page, PageLayout.from_page(page), ss.llm, model,
                                                      None if deep else settings.deep_model)
            for k, chat in ss.chats.items():
                if k[:2] == key:
                    chat.set_inventory(ss.inventories[key])
            st.rerun()
    else:
        st.info("Plates, sections, fasteners and paint are computed from the extract. "
                "Enable OpenAI for welds and unknown sections.")
    st.subheader("Plates (by thickness and grade)")
    st.dataframe(pd.DataFrame([{**p.model_dump(), "sources": ", ".join(p.sources)} for p in inv.plates]),
                 width="stretch", hide_index=True)
    st.subheader("Sections (by profile and grade)")
    st.dataframe(pd.DataFrame([{**s.model_dump(), "sources": ", ".join(s.sources)} for s in inv.sections]),
                 width="stretch", hide_index=True)
    if inv.fasteners:
        st.subheader("Fasteners (as listed in the bolt table)")
        st.dataframe(pd.DataFrame([f.model_dump() for f in inv.fasteners]), width="stretch", hide_index=True)
    if inv.unclassified:
        st.subheader("Needs review")
        st.dataframe(pd.DataFrame([u.model_dump() for u in inv.unclassified]), width="stretch", hide_index=True)
    if inv.welds or inv.rejected_welds:
        st.subheader(f"Welds (estimates) — weld metal {inv.weld_metal_kg} kg, electrode {inv.electrode_kg} kg")
        st.dataframe(pd.DataFrame([{**w.model_dump(), "parts": " + ".join(w.parts)} for w in inv.welds]),
                     width="stretch", hide_index=True)
        if inv.rejected_welds:
            with st.expander(f"{len(inv.rejected_welds)} weld(s) rejected by guardrails"):
                for r in inv.rejected_welds:
                    st.markdown(f"- {r}")
    st.dataframe(pd.DataFrame([{"": icon[c.level], "check": c.id, "detail": c.message} for c in inv.checks]),
                 width="stretch", hide_index=True)

with tab_chat:
    if not use_llm:
        st.info("Enable OpenAI in the sidebar to chat with the drawing.")
    else:
        ckey = (sha, page_index, model)
        if ckey not in ss.chats:
            with st.spinner("Preparing the sheet for the model…"):
                ss.chats[ckey] = ChatSession(x, page, PageLayout.from_page(page), ss.llm, model, settings,
                                             inventory=ss.inventories.get(key))
        chat = ss.chats[ckey]
        if st.button("New conversation"):
            del ss.chats[ckey]
            st.rerun()
        for t in chat.turns:
            st.chat_message("user").write(t.question)
            with st.chat_message("assistant"):
                st.markdown(t.answer)
                if t.tool_log:
                    st.caption("Looked at: " + " · ".join(t.tool_log))
                for cap, png in t.images:
                    with st.expander(cap):
                        st.image(png)
        q = st.chat_input("Ask about this sheet…")
        if q:
            try:
                with st.spinner("Reading the drawing…"):
                    chat.ask(q)
                st.rerun()
            except Exception as e:   # API/network errors: keep the session, show the problem
                st.error(f"Question failed ({type(e).__name__}): {e}")

with tab_export:
    base = (tb.drawing_no or up.name.rsplit(".", 1)[0]) + f"_p{page_index + 1}"
    st.download_button("Excel (extract + inventory)", export.to_excel(x, inv), f"{base}.xlsx")
    st.download_button("BOM CSV", export.bom_csv(x), f"{base}_bom.csv", "text/csv")
    st.download_button("JSON (extract)", export.to_json(x), f"{base}.json", "application/json")
    st.download_button("JSON (inventory)", inv.model_dump_json(indent=2), f"{base}_inventory.json",
                       "application/json")
```

`README.md`:
```markdown
# Drawing Q&A

Streamlit app for Tekla structural-steel fabrication drawings (vector PDF, TATA STEEL template). Upload a sheet to:
- get a validated extract (title block, BOM, abstract, bolts, revisions, notes, erection locations, view labels);
- build a material inventory;
- ask questions about the drawing;
- export everything to Excel, CSV or JSON.

- **Extract: PyMuPDF only.** No model calls. Checks guard every number: qty × piece weight = gross, Σ gross × assembly
  qty = grand total, abstract = BOM by section, a second independent BOM parse, and every BOM mark appears on the drawing.
- **Q&A: OpenAI** (`gpt-5.4-mini`; deep mode `gpt-5.5`). The model sees the whole sheet on every call: the full text
  layer tagged with grid cells, high-resolution tiles, and the validated extract. It can zoom and search, and it cites
  marks, grid cells and BOM rows.
- **Inventory:** plates by thickness and grade (welded WH/T members decomposed into plates), sections by profile,
  fasteners from the bolt list, and paint area. All of these are deterministic and reconcile to the BOM weight.
  OpenAI reads the welds from the views and interprets unknown sections. Guardrails reject:
  - weld sizes that are not on the sheet;
  - welds citing unknown parts;
  - impossible weld lengths;
  - joint counts over budget;
  - plate breakdowns whose weight doesn't match the BOM.

  Weld metal and electrode figures are estimates.

## Run

    pip install -r requirements.txt
    $env:OPENAI_API_KEY="..."        # bash: export OPENAI_API_KEY=...
    streamlit run app.py

Environment: `DQA_MODEL` (default gpt-5.4-mini), `DQA_DEEP_MODEL` (default gpt-5.5), `DQA_CACHE_DIR` (default .dqa_cache).

## Test

    python -m pytest                                  # offline; sample PDFs in the repo root (or DQA_SAMPLES)
    python scripts/live_smoke.py <pdf> "question"     # real API, costs tokens
```

`scripts/live_smoke.py`:
```python
"""Opt-in end-to-end run against the real OpenAI API (costs tokens).

    python scripts/live_smoke.py <pdf> ["question" ...]
"""
import sys
import time
from pathlib import Path

import pymupdf

from drawing_qa.chat import ChatSession
from drawing_qa.config import Settings
from drawing_qa.extract import extract_page
from drawing_qa.inventory import build_inventory
from drawing_qa.layout import PageLayout
from drawing_qa.llm import LLM


def main(pdf, questions):
    data = Path(pdf).read_bytes()
    settings = Settings()
    llm = LLM(timeout=settings.api_timeout_s, max_retries=settings.api_max_retries)
    t = time.time()
    x = extract_page(data, 0, Path(pdf).name, settings=settings, use_cache=False)
    print(f"extract (PyMuPDF only): {time.time() - t:.1f}s")
    for c in x.checks:
        if c.level != "pass":
            print(f"  [{c.level}] {c.id}: {c.message}")
    print(f"title: {x.title_block.title_lines}  project={x.title_block.project!r}")
    page = pymupdf.open(stream=data, filetype="pdf")[0]
    layout = PageLayout.from_page(page)
    t = time.time()
    inv = build_inventory(x, page, layout, llm, settings.model, settings.deep_model)
    print(f"\ninventory: {time.time() - t:.0f}s  model={inv.model}  usage={inv.usage}")
    for p in inv.plates:
        print(f"  PL{p.thickness_mm:g} {p.grade}: {p.pieces} pcs, {p.area_m2} m2, {p.weight_kg} kg")
    for s in inv.sections:
        print(f"  {s.profile} {s.grade}: {s.pieces} pcs, {s.total_length_m} m, {s.weight_kg} kg")
    print(f"  welds accepted {len(inv.welds)}, rejected {len(inv.rejected_welds)}; weld metal {inv.weld_metal_kg} kg")
    for c in inv.checks:
        print(f"  [{c.level}] {c.id}: {c.message[:160]}")
    chat = ChatSession(x, page, layout, llm, settings.model, settings, inventory=inv)
    for q in questions:
        turn = chat.ask(q)
        print(f"\nQ: {q}\n  tools: {turn.tool_log}\n  A: {turn.answer}")
    print(f"\nsession usage: {llm.usage_summary()}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:] or ["What is the total gross weight and which part is heaviest?"])
```

- [ ] **Step 4: Run the full offline suite**

Run: `python -m pytest -q`
Expected: `122 passed` (about 50 s).

- [ ] **Step 5: Live smoke run (real API, about 100–200k input tokens on an A0 sheet, mostly cached)**

Run: `$env:PYTHONPATH="."; python scripts/live_smoke.py "TST-SFD-46-01-01-07-000-14281(UPDATED).pdf" "How much 40 mm plate do I need to buy for this column, and where does it go?"`

Expected:
- Extraction takes about 5 s with no fail checks, and the project is `CRC WEST TARAPUR, HRPGL`.
- Plates + sections = 26121.52 kg (`inventory.weight` pass). PL40 E350BR(UT) is 8 pcs, 9265.51 kg.
- Welds: some accepted, and `inventory.weld_coverage` is a warning (flange-to-web seams aren't drawn).
- The answer states 8 pieces / 9265.51 kg and names the WH1200X500X40X32 members.

- [ ] **Step 6: Manual UI check**

Run: `streamlit run app.py`. Upload `…16362….pdf` and check:
- Extract shows 2 erection locations.
- Inventory lists ROD8 as 44 pcs and flags `1m470 SPD…` for review.
- Run OpenAI step: welds appear. The SPD member is either accepted with a matching plate weight or stays flagged.
- Chat: "Where is 1DC1 erected?" gives both locations.

- [ ] **Step 7: Commit**

```bash
git add app.py tests/test_app.py README.md scripts/live_smoke.py
git commit -m "feat: Streamlit UI with inventory tab, README and live smoke script"
```

---

## Known limitations (accepted)

- **Weld estimates cover only welds drawn with symbols.** Built-up flange-to-web seams aren't drawn, so large built-up sheets under-report weld metal; `inventory.weld_coverage` says so.
- **The unknown `SPD508*508*608*608*8` (16362) may stay "needs review".** Live, both gpt-5.4-mini and gpt-5.5 proposed breakdowns that failed the 2% weight check (19.32 kg vs 54.93 kg), so it stays listed as a section with the model's description.
- **Fastener quantities are taken as the bolt table lists them** (not multiplied by assembly qty). Blank taper-washer quantities are warned about, not guessed.
- **Cost.** Chat on A0 costs about 40k input tokens per API call (mostly cached after the first), and 20 s latency is typical. The inventory OpenAI step costs about 16–39k input tokens, plus the same again when it escalates to gpt-5.5.
- **Template.** The parsers are tuned to the TATA STEEL template; on another template the extract checks will report missing regions.
- **Duplicate labels.** A view label drawn twice (`M - M` on 14281) can only be zoomed by grid cell.

## Audit record

**v1 plan: 3 independent audit rounds, final verdict APPROVE** (all findings fixed; details are in git history).
- **Round 1:** 3 major + 9 minor findings, including OpenAI errors crashing the extract, the lost second erection row, and loose verification.
- **Round 2:** 1 medium + 4 minor, including paid BOM re-reads that could never help, and truncated title values.
- **Round 3:** none.

Every fix carries into v2: error isolation, erection-location rows, the cross-check with header-mapped columns, cache keys, env read at construction, chat robustness, `join_tokens` without invented characters, and duplicate-label handling.

**v2 changes (user decision, 2026-09-19):**
- OpenAI reads the whole page image plus the PyMuPDF text for Q&A.
- Extraction becomes 100% PyMuPDF: the v1 OpenAI title-block and view steps, and their escalation machinery, are removed. The title block is now read from bordered cells.
- New inventory mode.
- v2 is audited below.
