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
    st.caption(f"Assembly {inv.assembly_mark} × {inv.assembly_qty} · Tekla gross (stock) weights, no wastage · "
               f"steel {inv.total_steel_kg} kg · paint {inv.paint_area_m2} m²")
    if use_llm:
        label = "Re-run OpenAI step" if key in ss.inventories else "Run OpenAI step (welds, unknown sections)"
        if st.button(label):
            with st.spinner("Reading welds and unknown sections from the sheet…"):
                ss.inventories[key] = build_inventory(x, page, PageLayout.from_page(page), ss.llm, model,
                                                      None if deep else settings.deep_model,
                                                      cache_dir=settings.cache_dir)
            for k, chat in ss.chats.items():
                if k[:2] == key:
                    chat.set_inventory(ss.inventories[key])
            st.rerun()
    else:
        st.info("Plates, sections, fasteners and paint are computed from the extract. "
                "Enable OpenAI for welds and unknown sections.")
    st.subheader(f"Fabrication BOQ — {inv.item_type or 'assembly'} {inv.assembly_mark} × {inv.assembly_qty}")
    if inv.boq:
        boq_df = pd.DataFrame([r.model_dump() for r in inv.boq])
        st.dataframe(boq_df, width="stretch", hide_index=True)
        tot = lambda k: sum(getattr(r, k) or 0 for r in inv.boq)
        st.caption(f"Total qty {tot('total_qty')} · calculated {tot('total_calc_wt'):.2f} kg · drawing "
                   f"{tot('total_drg_wt'):.2f} kg · difference {tot('difference'):+.2f} kg. Plates: 7.85 × t kg/m²; "
                   "rolled sections: IS 808 handbook kg/m; WT = drawing (Tekla) gross weight.")
        st.download_button("BOQ (Excel, live formulas)", export.boq_excel(inv),
                           f"{inv.drawing_no or 'drawing'}_BOQ.xlsx")
    st.subheader("Plates (by thickness and grade)")
    st.dataframe(pd.DataFrame([{**p.model_dump(), "sources": ", ".join(p.sources)} for p in inv.plates]),
                 width="stretch", hide_index=True)
    st.subheader("Sections (by profile and grade)")
    st.dataframe(pd.DataFrame([{**s.model_dump(), "sources": ", ".join(s.sources)} for s in inv.sections]),
                 width="stretch", hide_index=True)
    if inv.fasteners:
        st.subheader(f"Fasteners (as listed in the bolt table; not multiplied by assembly qty × {inv.assembly_qty})")
        st.dataframe(pd.DataFrame([f.model_dump() for f in inv.fasteners]), width="stretch", hide_index=True)
    if inv.unclassified:
        st.subheader("Needs review")
        st.dataframe(pd.DataFrame([u.model_dump() for u in inv.unclassified]), width="stretch", hide_index=True)
    if inv.welds or inv.rejected_welds:
        st.subheader(f"Welds: model-read estimate, unverified — weld metal {inv.weld_metal_kg} kg, "
                     f"electrode {inv.electrode_kg} kg")
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
