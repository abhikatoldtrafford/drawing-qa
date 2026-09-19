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
