"""Tab: the Life Weather chart, the reasons on the chosen date, and the dasa weights."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ..analysis.timeline import score_of
from ..viz.figure import LANE_TITLES, build_figure
from .state import View


def render(v: View) -> None:
    lw, df = v.lw, v.lw.frame
    st.plotly_chart(build_figure(lw, v.factors, marker=v.pick), use_container_width=True)
    st.caption("Green = supportive, red = challenging. Hover any point or lane for the reason. "
               "Lanes share one colour scale, so a pale lane contributes little. "
               "Dotted purple line = the date chosen in the sidebar.")

    exact = lw.on(v.pick)                                                   # reasons: exact date
    nearest = df.iloc[(df["date"] - pd.Timestamp(v.pick)).abs().argmin()]  # 3-month average only
    st.subheader(f"Why — {v.when_label}")
    c1, c2 = st.columns([1, 3])
    c1.metric("Overall (3-month avg)", f"{nearest.smoothed:+.2f}")
    c1.metric("This date", f"{score_of(exact, v.factors):+.2f}")
    c2.markdown("\n".join(
        f"- {'**Dasa** ' if lane == 'dasa' else ''}{exact[f'why_{lane}']}"
        + ("" if lane in v.factors else " *(off)*")
        for lane in LANE_TITLES
    ))

    with st.expander("Dasa weights — how each planet is rated for this chart"):
        st.dataframe(
            pd.DataFrame([{"Planet": w.planet, "Weight": w.total, "Lordship": w.lordship,
                           "Dignity": w.dignity, "Placement": w.placement,
                           "Why": "; ".join(w.reasons)}
                          for w in sorted(lw.weights.values(), key=lambda w: -w.total)]),
            hide_index=True, use_container_width=True,
        )
        st.caption("All rule values live in life_weather/analysis/assumptions.py.")
