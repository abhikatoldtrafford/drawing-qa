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
