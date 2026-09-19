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
   (e.g. '19-20/<LEG-1' stays as is); never add or normalise characters.
7. Before quoting a dimension from a view, zoom in and say which two features its extension lines span;
   if you cannot tell, say the dimension is ambiguous rather than guessing.
8. When you list or total items from a table (BOM, bolts, abstract), include EVERY contributing row, including
   rows with a blank mark or assembly; any total you state must equal the sum of the rows you list."""

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
    for b in d["bolts"]:            # a bolt row with no connected assembly is still a row: keep it visible
        b["assembly_mark"] = b["assembly_mark"] or "(blank on sheet)"
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
