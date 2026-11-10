"""Tab: South-Indian chart with transits on the chosen date, house explainer and house table."""
from __future__ import annotations

from datetime import datetime, time

import pandas as pd
import streamlit as st

from ..analysis.houses import describe_house, house_table
from ..analysis.narrative import chart_guide
from ..core.chart import house_between, retrograde, sidereal_longitudes, sign_of, to_jd
from ..core.constants import SIGNS_ML
from ..core.dasa import period_at
from ..viz.south_chart import render_south_chart
from .state import View

def _guide_markdown(name: str, lagna: str, moon: str, when: str) -> str:
    parts = []
    for heading, points in chart_guide(name, lagna, moon, when, in_app=True):
        parts.append(f"**{heading}**")
        parts += [p if len(points) == 1 else f"- {p}" for p in points]
        parts.append("")
    return "\n".join(parts)


def _tag(bodies, flags=None) -> str:
    return ", ".join(b + (" ℞" if flags and flags.get(b) else "") for b in bodies) or "—"


def render(v: View) -> None:
    chart, lw, when = v.lw.chart, v.lw, v.when_label
    lagna, moon = chart.sign("Lagna"), chart.sign("Moon")
    jd = to_jd(datetime.combine(v.pick, time(12)), v.birth.tz_hours)
    transit = sidereal_longitudes(jd, v.node)
    retro = retrograde(jd)
    period = period_at(lw.periods, jd)
    rows = house_table(chart, lw.weights, transit)

    with st.expander("📖 How to read this tab", expanded=True):
        st.markdown(_guide_markdown(v.birth.name, SIGNS_ML[lagna], SIGNS_ML[moon], when))

    left, right = st.columns([5, 4])
    with left:
        st.markdown(render_south_chart(chart, transit, retro, v.birth.name, f"transits {when}"),
                    unsafe_allow_html=True)
    with right:
        st.markdown(f"**Dasa on {when}:** {period.md} / {period.ad} (until {period.end:%b %Y})")
        st.markdown("**Slow planets on this date** — the ones that shape months and years")
        st.dataframe(pd.DataFrame([{
            "Planet": p + (" ℞" if retro.get(p) else ""),
            "Sign": SIGNS_ML[sign_of(transit[p])],
            "House from Lagna": f"H{house_between(sign_of(transit[p]), lagna)}",
            "From Moon": f"☾{house_between(sign_of(transit[p]), moon)}",
        } for p in ("Jupiter", "Saturn", "Rahu", "Ketu")]), hide_index=True,
            use_container_width=True)

        st.markdown("**Explain one house**")
        pick_h = st.selectbox("House", range(1, 13), index=9, label_visibility="collapsed",
                              format_func=lambda h: f"H{h} · {rows[h - 1].area}")
        st.markdown(describe_house(rows[pick_h - 1], lw.weights, when, retro))

    st.subheader("All houses at a glance")
    st.dataframe(pd.DataFrame([{
        "House": f"H{r.house}", "Life area": r.area, "Sign": r.sign_label,
        "Ruled by": r.lord, "Ruler sits in": f"H{r.lord_house}",
        "Ruler weight": r.lord_weight, "Born with": _tag(r.natal),
        f"Passing through {when}": _tag(r.transit, retro),
        "From Moon": f"☾{r.house_from_moon}",
    } for r in rows]), hide_index=True, use_container_width=True, height=458)
    st.caption("Read a row left to right: *this house* covers *these life areas*; in this chart it "
               "is *this sign*, *ruled by* a planet that *sits in* another house with *this weight* "
               "(+ supportive, − strained; same number the Dasa lane uses). Then the planets born "
               "there and the ones passing through on the chosen date. Descriptive only — no "
               "house-strength score yet.")
