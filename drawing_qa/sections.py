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
