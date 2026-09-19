"""Run the whole pipeline on every PDF in a folder and save the results.

    python scripts/run_all.py [pdf_dir] [out_dir] [--offline] [--no-qa]

For each distinct drawing (duplicate files are detected by SHA-256) and each page, writes to
<out_dir>/<drawing no>[_p<n>]/:
    sheet.png        overview render of the sheet
    extract.json     PyMuPDF extract (title block, BOM, abstract, bolts, revisions, notes, locations, views, checks)
    bom.csv          BOM rows
    inventory.json   inventory + BOQ (OpenAI-assisted unless --offline)
    boq.xlsx         fabrication BOQ in the reference layout, live formulas
    workbook.xlsx    everything: BOQ sheet first, extract sheets, inventory sheets
    qa.md            answers to a fixed set of questions, asked in one conversation (skipped with --no-qa/--offline)
    report.md        human-readable summary of the above
and <out_dir>/README.md (index of all drawings) plus, when a reference BOQ matches a drawing, benchmark_<drawing>.md.
"""
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drawing_qa.benchmark import compare_boq  # noqa: E402
from drawing_qa.chat import ChatSession  # noqa: E402
from drawing_qa.config import Settings  # noqa: E402
from drawing_qa.export import bom_csv, boq_excel, to_excel, to_json  # noqa: E402
from drawing_qa.extract import extract_page  # noqa: E402
from drawing_qa.inventory import build_inventory, deterministic_inventory  # noqa: E402
from drawing_qa.layout import PageLayout  # noqa: E402
from drawing_qa.llm import LLM  # noqa: E402
from drawing_qa.render import render_overview  # noqa: E402

QUESTIONS = [
    "What does this drawing fabricate, how many assemblies, where are they erected (grid and level), "
    "and what is the total weight?",
    "Which BOM part is the heaviest, what is its section and size, and where is it shown on the sheet?",
    "List every plate thickness used and the parts that use each one.",
    "What bolts, nuts and washers are needed, and which assemblies do they connect?",
]
# reference BOQs: workbook -> drawing number it belongs to
REFERENCES = {"2GU1 BOQ.xlsx": "16807"}


def fmt(v, nd=2):
    return "" if v is None else (f"{v:,.{nd}f}" if isinstance(v, float) else str(v))


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in r) + " |" for r in rows]
    return "\n".join(out)


def report(x, inv, qa_turns, elapsed):
    tb, b = x.title_block, x.bom
    asm = b.assembly if b else None
    lines = [f"# {tb.drawing_no or x.source_file}", "",
             f"- **Source file:** `{x.source_file}` (page {x.page_index + 1})",
             f"- **Title:** {' / '.join(tb.title_lines)}",
             f"- **Project / department / area:** {tb.project} / {tb.department} / {tb.equip_area}",
             f"- **Rev / sheet / size:** {tb.rev} / {tb.sheet_no} / {tb.sheet_size}",
             f"- **Drawn / checked / approved:** {tb.drn.name} {tb.drn.date} / {tb.chd.name} {tb.chd.date} / "
             f"{tb.app.name} {tb.app.date}",
             f"- **Title-block weight:** {fmt(tb.weight_kg)} kg",
             f"- **Assembly:** {asm.erection_mark if asm else '?'} × {asm.qty if asm else '?'}"
             f" ({inv.item_type or 'item type not stated'})",
             f"- **Erection locations:** "
             + ("; ".join(f"{m.mark_no} @ {m.grid_location} {m.level}".strip() for m in x.mark_locations) or "none"),
             f"- **Run time:** {elapsed:.0f} s; OpenAI model: {inv.model or 'not run'}; usage: {inv.usage or '-'}",
             "", "## Checks (PyMuPDF guardrails)", ""]
    lines.append(md_table(["level", "check", "message"], [(c.level, c.id, c.message) for c in x.checks]))
    lines += ["", "## Bill of materials", ""]
    if b:
        lines.append(md_table(["mark", "section", "length mm", "qty", "pc wt", "gross kg", "grade"],
                              [(p.item_no, p.section, fmt(p.length_mm, 0), p.qty, fmt(p.pc_wt), fmt(p.gross_kg),
                                p.material) for p in b.parts]))
        lines.append(f"\nTotals: net {fmt(b.totals.net_kg)} kg, gross {fmt(b.totals.gross_kg)} kg, "
                     f"surface {fmt(b.totals.surface_area_m2)} m²")
    lines += ["", "## Fabrication BOQ", ""]
    lines.append(md_table(
        ["item", "section", "width", "length", "qty", "fab", "unit wt", "calc kg", "drg kg", "diff kg", "grade",
         "unit wt source"],
        [(r.item_no, r.section, fmt(r.width, 1), fmt(r.length, 1), r.qty, r.fab_qty, fmt(r.unit_wt, 3),
          fmt(r.total_calc_wt, 3), fmt(r.total_drg_wt, 3), fmt(r.difference, 3), r.grade, r.unit_wt_source)
         for r in inv.boq]))
    tot = lambda k: sum(getattr(r, k) or 0 for r in inv.boq)
    lines.append(f"\nBOQ totals: calculated {tot('total_calc_wt'):,.3f} kg, drawing {tot('total_drg_wt'):,.3f} kg, "
                 f"difference {tot('difference'):+,.3f} kg")
    lines += ["", "## Inventory", "", f"Total steel (BOM gross × assembly qty): **{fmt(inv.total_steel_kg)} kg**; "
              f"paint area {fmt(inv.paint_area_m2)} m²", ""]
    if inv.plates:
        lines.append(md_table(["plate", "grade", "pieces", "area m²", "kg", "sources"],
                              [(f"PL{p.thickness_mm:g}", p.grade, p.pieces, fmt(p.area_m2, 3), fmt(p.weight_kg),
                                ", ".join(p.sources)) for p in inv.plates]))
    if inv.sections:
        lines += ["", md_table(["profile", "family", "grade", "pieces", "length m", "kg", "sources"],
                               [(s.profile, s.family, s.grade, s.pieces, fmt(s.total_length_m, 3), fmt(s.weight_kg),
                                 ", ".join(s.sources)) for s in inv.sections])]
    if inv.fasteners:
        lines += ["", md_table(["item", "dia", "length", "type", "grade", "qty", "assemblies"],
                               [(f.item, f.dia_mm, f.length_mm, f.type, f.grade, f.qty,
                                 ", ".join(f.connected_assemblies)) for f in inv.fasteners])]
    lines += ["", "### Welds (model-read estimate, unverified)", ""]
    if inv.welds:
        lines.append(md_table(["parts", "size mm", "edge", "sides", "count", "tack", "total m", "metal kg", "evidence"],
                              [(" → ".join(w.parts), fmt(w.size_mm, 0), w.edge, w.sides, w.count, w.tack,
                                fmt(w.total_length_m, 3), fmt(w.weld_metal_kg, 3), w.evidence) for w in inv.welds]))
        lines.append(f"\nWeld metal {fmt(inv.weld_metal_kg, 3)} kg, electrode {fmt(inv.electrode_kg, 3)} kg")
    else:
        lines.append("None accepted." if inv.model else "Not run (offline).")
    if inv.rejected_welds:
        lines += ["", "Rejected by guardrails:", *[f"- {r}" for r in inv.rejected_welds]]
    if inv.unclassified:
        lines += ["", "### Sections interpreted by OpenAI", "",
                  md_table(["mark", "section", "accepted", "description", "note"],
                           [(u.mark, u.section, u.accepted, u.description, u.note) for u in inv.unclassified])]
    lines += ["", "### Inventory checks", "",
              md_table(["level", "check", "message"], [(c.level, c.id, c.message) for c in inv.checks])]
    if qa_turns:
        lines += ["", "## Q&A", "", "See [qa.md](qa.md)."]
    return "\n".join(lines) + "\n"


def qa_markdown(x, turns):
    out = [f"# Q&A — {x.title_block.drawing_no}", "",
           "Asked in one conversation (each question sees the earlier turns). The model gets the full sheet "
           "(grid-tagged text layer + tiles + validated extract) and can call query_bom / search_text / zoom.", ""]
    for i, t in enumerate(turns, 1):
        out += [f"## Q{i}. {t.question}", "", f"*Tools used:* {', '.join(t.tool_log) or 'none'}", "", t.answer, ""]
    return "\n".join(out)


def benchmark_md(inv, res, ref):
    ok = res["fields_checked"] - len(res["field_diffs"])
    lines = [f"# Benchmark: {inv.drawing_no} vs `{ref}`", "",
             f"- Rows: ours {res['our_rows']}, reference {res['gt_rows']}; missing {res['missing'] or 'none'}; "
             f"extra {res['extra'] or 'none'}",
             f"- Fields: **{ok}/{res['fields_checked']} identical**",
             f"- Formula structure differences: {len(res['formula_diffs'])}",
             f"- Evaluated exported workbook vs reference values: {len(res['evaluated_diffs'])} cell differences", ""]
    if res["field_diffs"]:
        lines += [md_table(["item", "field", "ours", "reference"],
                           [(d["item"], d["field"], d["ours"], d["gt"]) for d in res["field_diffs"]]), ""]
    lines += ["## Subtotals (row 1)", "", md_table(["column", "ours", "reference", "match"],
              [(k, f"{v['ours']:.4f}", f"{v['gt']:.4f}", "OK" if v["match"] else "DIFF")
               for k, v in res["totals"].items()])]
    return "\n".join(lines) + "\n"


def index_md(index, bench, offline):
    rows = [r for r in index if "folder" in r]
    lines = ["# Results", "",
             "Generated by `python scripts/run_all.py` " + ("(offline: PyMuPDF only)" if offline else
             "(PyMuPDF extract + OpenAI-assisted inventory + Q&A)") + ". One folder per drawing; open "
             "`report.md` first. Proprietary: derived from the client drawings, git-ignored.", "",
             md_table(["drawing", "item", "assembly", "BOM rows", "BOM gross kg", "BOQ rows", "BOQ calc kg",
                       "BOQ drg kg", "welds (rejected)", "checks pass/warn/fail", "model"],
                      [(f"[{r['drawing_no'][-5:]}]({r['folder']}/report.md)", r["item_type"], r["assembly"],
                        r["bom_rows"], fmt(r["bom_gross_kg"]), r["boq_rows"], fmt(r["boq_calc_kg"]),
                        fmt(r["boq_drg_kg"]), f"{r['welds']} ({r['rejected_welds']})",
                        f"{r['pass']}/{r['warn']}/{r['fail']}", r["model"] or "-") for r in rows])]
    dups = [r for r in index if "duplicate_of" in r]
    if dups:
        lines += ["", *[f"- `{r['file']}` is byte-identical to `{r['duplicate_of']}` (skipped)." for r in dups]]
    for dno, ref, res in bench:
        ok = res["fields_checked"] - len(res["field_diffs"])
        lines += ["", f"**Benchmark {dno} vs `{ref}`:** {ok}/{res['fields_checked']} fields identical, "
                  f"{len(res['formula_diffs'])} formula differences, {len(res['evaluated_diffs'])} evaluated-cell "
                  f"differences — see [benchmark_{dno}.md](benchmark_{dno}.md)."]
    lines += ["", "Per-drawing files: `report.md` (summary), `qa.md` (Q&A), `boq.xlsx` (BOQ, live formulas), "
              "`workbook.xlsx` (all sheets), `extract.json`, `inventory.json`, `bom.csv`, `sheet.png`."]
    return "\n".join(lines) + "\n"


def main(pdf_dir=".", out_dir="results", offline=False, qa=True):
    pdf_dir, out_dir = Path(pdf_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    s = Settings()
    llm = None if offline else LLM(timeout=s.api_timeout_s, max_retries=s.api_max_retries)
    seen, index, bench = {}, [], []
    for pdf in sorted(pdf_dir.glob("*.pdf"), key=lambda p: (re.sub(r" \(\d+\)", "", p.name), len(p.name))):
        data = pdf.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if sha in seen:
            print(f"skip {pdf.name}: identical to {seen[sha]}")
            index.append({"file": pdf.name, "duplicate_of": seen[sha]})
            continue
        seen[sha] = pdf.name
        doc = pymupdf.open(stream=data, filetype="pdf")
        for pi in range(len(doc)):
            t0 = time.time()
            x = extract_page(data, pi, pdf.name, settings=s, use_cache=False)
            page = doc[pi]
            layout = PageLayout.from_page(page)
            inv = build_inventory(x, page, layout, llm, s.model, s.deep_model) if llm else deterministic_inventory(x)
            turns = []
            if llm and qa:
                chat = ChatSession(x, page, layout, llm, s.model, s, inventory=inv)
                turns = [chat.ask(q) for q in QUESTIONS]
            name = (x.title_block.drawing_no or pdf.stem) + (f"_p{pi + 1}" if len(doc) > 1 else "")
            d = out_dir / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "sheet.png").write_bytes(render_overview(page, max_px=2400))
            (d / "extract.json").write_text(to_json(x), encoding="utf-8")
            (d / "bom.csv").write_text(bom_csv(x), encoding="utf-8")
            (d / "inventory.json").write_text(inv.model_dump_json(indent=2), encoding="utf-8")
            (d / "boq.xlsx").write_bytes(boq_excel(inv))
            (d / "workbook.xlsx").write_bytes(to_excel(x, inv))
            if turns:
                (d / "qa.md").write_text(qa_markdown(x, turns), encoding="utf-8")
            elapsed = time.time() - t0
            (d / "report.md").write_text(report(x, inv, turns, elapsed), encoding="utf-8")
            count = lambda lv: sum(c.level == lv for c in x.checks + inv.checks)
            b = x.bom
            index.append({
                "file": pdf.name, "page": pi + 1, "folder": name, "drawing_no": x.title_block.drawing_no,
                "title": " / ".join(x.title_block.title_lines), "item_type": inv.item_type,
                "assembly": f"{inv.assembly_mark} x {inv.assembly_qty}", "bom_rows": len(b.parts) if b else 0,
                "bom_gross_kg": b.totals.gross_kg if b else None, "total_steel_kg": inv.total_steel_kg,
                "boq_rows": len(inv.boq), "boq_calc_kg": round(sum(r.total_calc_wt or 0 for r in inv.boq), 3),
                "boq_drg_kg": round(sum(r.total_drg_wt or 0 for r in inv.boq), 3),
                "welds": len(inv.welds), "rejected_welds": len(inv.rejected_welds),
                "weld_metal_kg": inv.weld_metal_kg, "pass": count("pass"), "warn": count("warn"),
                "fail": count("fail"), "model": inv.model, "seconds": round(elapsed),
            })
            print(f"{name}: {index[-1]['bom_rows']} BOM rows, {len(inv.boq)} BOQ rows, "
                  f"checks {index[-1]['pass']}/{index[-1]['warn']}/{index[-1]['fail']} (pass/warn/fail), "
                  f"{elapsed:.0f}s")
            for ref, dno in REFERENCES.items():
                if dno in (x.title_block.drawing_no or "") and (pdf_dir / ref).exists():
                    res = compare_boq(inv, pdf_dir / ref)
                    (out_dir / f"benchmark_{dno}.md").write_text(benchmark_md(inv, res, ref), encoding="utf-8")
                    (out_dir / f"benchmark_{dno}.json").write_text(json.dumps(res, indent=2, default=str),
                                                                   encoding="utf-8")
                    bench.append((dno, ref, res))
    (out_dir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    (out_dir / "README.md").write_text(index_md(index, bench, offline), encoding="utf-8")
    if llm:
        (out_dir / "usage.json").write_text(json.dumps(llm.usage_summary(), indent=2), encoding="utf-8")
    return index, bench


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(*(args + [".", "results"][len(args):]), offline="--offline" in sys.argv, qa="--no-qa" not in sys.argv)
