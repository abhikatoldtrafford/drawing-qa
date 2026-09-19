"""Handbook unit weights (kg/m) for hot-rolled Indian sections, used by the BOQ's calculated weight.

Source: "ISA / ISMC / ISMB hot-rolled steel sections, weight per metre", Amardeep Steel (headers: angles
IS 808:1976, beams IS 800:1964; channel values are the IS 808:1989 figures),
https://www.amardeepsteel.com/weight-per-metre-structurals-1.pdf (transcribed 2026-09-19). ISMC values agree
with the IS 808:1989 channel chart at metalweightpro.com for ISMC 150 (16.8) and ISMC 300 (36.3); the user's
2GU1 BOQ uses the same values (ISMC150 16.8, ISA75X75X8 8.9). Edit here to follow a different edition."""
import math
import re

STEEL_KG_PER_M3 = 7850.0

# equal angles ISA a x a x t
_ISA_EQUAL = {
    20: {3: 0.9, 4: 1.1}, 25: {3: 1.1, 4: 1.4, 5: 1.8}, 30: {3: 1.4, 4: 1.8, 5: 2.2},
    35: {3: 1.6, 4: 2.1, 5: 2.6, 6: 3.0}, 40: {3: 1.8, 4: 2.4, 5: 3.0, 6: 3.5}, 45: {3: 2.1, 4: 2.7, 5: 3.4, 6: 4.0},
    50: {3: 2.3, 4: 3.0, 5: 3.8, 6: 4.5, 7: 5.15, 8: 5.82}, 55: {5: 4.1, 6: 4.9, 8: 6.4, 10: 7.9},
    60: {4: 3.7, 5: 4.5, 6: 5.4, 8: 7.0, 10: 8.6}, 65: {5: 4.9, 6: 5.8, 8: 7.7, 10: 9.4},
    70: {5: 5.3, 6: 6.3, 7: 7.38, 8: 8.3, 10: 10.2}, 75: {5: 5.7, 6: 6.8, 8: 8.9, 10: 11.0},
    80: {6: 7.3, 8: 9.6, 10: 11.8, 12: 14.0}, 90: {6: 8.2, 8: 10.8, 10: 13.4, 12: 15.8},
    100: {6: 9.2, 6.5: 9.99, 8: 12.1, 10: 14.9, 12: 17.7, 15: 21.9}, 110: {8: 13.4, 10: 16.6, 12: 19.7, 16: 25.7},
    120: {8: 14.7, 10: 18.2, 12: 21.6, 15: 26.6}, 130: {8: 15.9, 10: 19.7, 12: 23.5, 16: 30.7},
    # 150x150x15: the source cell is truncated to "33."; IS 808 gives 33.8
    150: {10: 22.9, 12: 27.3, 15: 33.8, 16: 35.8, 18: 40.1, 20: 44.1}, 180: {15: 40.9, 18: 48.6, 20: 53.7},
    200: {12: 36.9, 16: 48.5, 20: 60.0, 24: 71.1, 25: 73.9},
}
# unequal angles ISA a x b x t
_ISA_UNEQUAL = {
    (30, 20): {3: 1.1, 4: 1.4, 5: 1.8}, (40, 25): {3: 1.5, 4: 1.9, 5: 2.4, 6: 2.8},
    (45, 30): {3: 1.7, 4: 2.2, 5: 2.8, 6: 3.3}, (50, 30): {3: 1.8, 4: 2.4, 5: 3.0, 6: 3.5},
    (60, 40): {5: 3.7, 6: 4.4, 8: 5.8}, (65, 45): {5: 4.1, 6: 4.9, 8: 6.4},
    (70, 45): {5: 4.3, 6: 5.2, 8: 6.7, 10: 8.3}, (75, 50): {5: 4.7, 6: 5.6, 8: 7.4, 10: 9.0},
    (80, 50): {5: 4.9, 6: 5.9, 8: 7.7, 10: 9.4}, (90, 60): {6: 6.8, 8: 8.9, 10: 11.0, 12: 13.0},
    (100, 65): {6: 7.5, 8: 9.9, 10: 12.2}, (100, 75): {6: 8.0, 8: 10.5, 10: 13.0, 12: 15.4},
    (125, 75): {6: 9.2, 8: 12.1, 10: 14.9}, (125, 95): {6: 10.1, 8: 13.4, 10: 16.5, 12: 19.7},
    (150, 75): {8: 13.7, 10: 17.0, 12: 20.2}, (150, 115): {8: 16.3, 10: 20.1, 12: 24.0, 16: 31.4},
    (200, 100): {10: 22.9, 12: 27.3, 16: 35.8}, (200, 150): {10: 26.9, 12: 32.1, 16: 42.2, 20: 52.0},
}
_ISMC = {75: 7.14, 100: 9.56, 125: 13.1, 150: 16.8, 175: 19.6, 200: 22.3, 225: 26.1, 250: 30.6, 300: 36.3,
         350: 42.7, 400: 50.1}
_ISMB = {100: 11.5, 125: 13.0, 150: 14.9, 175: 19.3, 200: 25.4, 225: 31.2, 250: 37.3, 300: 44.2, 350: 52.4,
         400: 61.6, 450: 72.4, 500: 86.9, 550: 103.7, 600: 122.6}
_ROUND = {12: 0.89, 16: 1.58, 18: 2.00, 20: 2.47, 22: 2.98, 25: 3.85, 28: 4.83, 30: 5.55, 32: 6.31, 36: 7.99,
          40: 9.86, 45: 12.49, 50: 15.41, 56: 19.34, 63: 24.47}

N = r"(\d+(?:\.\d+)?)"


def _key(v):
    return int(v) if float(v).is_integer() else float(v)


def handbook_unit_weight(section: str):
    """(kg/m, source) for a rolled section, or (None, '') if it is not a tabulated or computable profile."""
    s = section.replace(" ", "").upper()
    if m := re.fullmatch(rf"ISA{N}X{N}X{N}", s):
        a, b, t = _key(m[1]), _key(m[2]), _key(m[3])
        table = _ISA_EQUAL.get(a, {}) if a == b else _ISA_UNEQUAL.get((max(a, b), min(a, b)), {})
        return (table[t], "IS 808 table") if t in table else (None, "")
    if m := re.fullmatch(rf"ISMC{N}", s):
        v = _ISMC.get(_key(m[1]))
        return (v, "IS 808 table") if v else (None, "")
    if m := re.fullmatch(rf"ISMB{N}", s):
        v = _ISMB.get(_key(m[1]))
        return (v, "IS 808 table") if v else (None, "")
    if m := re.fullmatch(rf"ROD{N}", s):
        d = _key(m[1])
        if d in _ROUND:
            return _ROUND[d], "IS 808 table"
        return round(math.pi * d * d / 4 * 1e-6 * STEEL_KG_PER_M3, 3), "computed (pi d²/4 x 7850)"
    if m := re.fullmatch(rf"PIPE{N}\*{N}", s):
        od, t = float(m[1]), float(m[2])
        return round(math.pi * (od - t) * t * 1e-6 * STEEL_KG_PER_M3, 3), "computed (pi (OD-t) t x 7850)"
    return None, ""


def plate_unit_weight(thickness_mm: float) -> float:
    """kg/m² of steel plate: 7.85 x t (the BOQ's convention)."""
    return round(7.85 * thickness_mm, 4)
