"""Tab: a green/red score strip per house over time."""
from __future__ import annotations

import streamlit as st

from ..analysis.houses import HOUSE_AREAS
from ..viz.house_figure import build_house_figure
from . import state
from .state import View


def render(v: View) -> None:
    c_ref, c_pick = st.columns([1, 3])
    ref = c_ref.radio("Count houses from", ["Lagna", "Moon"], horizontal=True,
                      help="Lagna: the usual life-area houses. Moon: the classical transit "
                           "reference, consistent with the Life Weather tab.")
    shown = c_pick.multiselect("Houses", list(range(1, 13)), default=list(range(1, 13)),
                               format_func=lambda h: f"H{h} · {HOUSE_AREAS[h].split(',')[0]}")
    hdf = state.houses(v.birth, v.end_year, v.node, ref)   # independent of the factor toggles
    if shown:
        st.plotly_chart(build_house_figure(v.lw, hdf, sorted(shown), ref, marker=v.pick),
                        use_container_width=True)
    st.caption(
        "Each strip = one house, same scale for all, 3-month average. "
        "**Score = ½ dasa focus + ½ transit touch.** Dasa focus: the Maha-dasa / sub-period lord's "
        "weight, for every house that lord rules or sits in. Transit touch: Jupiter (+) and "
        "Saturn, Rahu, Ketu (−, but + in houses 3/6/11) sitting in the house (full) or aspecting it "
        "(half). Hover for the reasons on any date.")
    with st.expander("Assumptions behind the house scores"):
        st.markdown(
            "- Aspects: Jupiter 5th/7th/9th, Saturn 3rd/7th/10th, Rahu/Ketu 7th only (whole-sign).\n"
            "- An aspect counts **half** of sitting in the house — this ratio is our assumption, "
            "not a classical number.\n"
            "- Benefic/malefic signs are classical natural natures; malefics doing well in 3/6/11 "
            "is classical (upachaya).\n"
            "- Mars and the fast planets are left out on a multi-year view.\n"
            "- All values live in `life_weather/analysis/assumptions.py`.")
