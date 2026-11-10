"""Sidebar: prepare and download the PDF summary for the current selection."""
from __future__ import annotations

import streamlit as st

from ..report.pdf import pdf_filename
from . import state
from .state import View


def render(v: View) -> None:
    with st.sidebar:
        st.header("Download")
        key = state.pdf_key(v)
        if st.button("Prepare PDF summary", use_container_width=True,
                     help="A written report: the chosen date at a glance, birth chart with every planet "
                          "explained, planets in motion and the events ahead, the Life Weather "
                          "timeline with its key stretches, houses, dasa periods, and a glossary."):
            st.session_state["pdf"] = (key, state.pdf(v))
        saved = st.session_state.get("pdf")
        if saved and saved[0] == key:
            st.download_button("⬇️ Download PDF", data=saved[1], mime="application/pdf",
                               file_name=pdf_filename(v.birth, v.pick),
                               use_container_width=True, type="primary")
        elif saved:
            st.caption("Settings changed since the last PDF — prepare it again.")
