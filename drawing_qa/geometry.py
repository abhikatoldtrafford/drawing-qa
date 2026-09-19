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
