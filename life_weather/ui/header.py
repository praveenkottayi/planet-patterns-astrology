"""Page title, method summary and the birth-time warning."""
from __future__ import annotations

import streamlit as st

from ..analysis.dasa_weight import dasa_scale
from ..core.constants import SIGNS_EN, SIGNS_ML
from ..viz.figure import LANE_TITLES
from . import state
from .state import View


def _formula(factors: tuple[str, ...]) -> str:
    transit = [LANE_TITLES[f] for f in ("jupiter", "saturn", "nodes") if f in factors]
    parts = ["½ dasa" if "dasa" in factors else "",
             f"½ ({' + '.join(transit)})" if transit else ""]
    return " + ".join(filter(None, parts)) or "0 (no factors selected)"


def _minutes(m: int | None) -> str:
    return f"{m} min" if m is not None else "more than 4 h"


def render(v: View) -> None:
    chart = v.lw.chart
    nak, pada = chart.nakshatra("Moon")
    lagna, moon = chart.sign("Lagna"), chart.sign("Moon")

    st.title(f"Life Weather · {v.birth.name}")
    st.caption(
        f"Lagna **{SIGNS_ML[lagna]}** ({SIGNS_EN[lagna]}) · Moon **{SIGNS_ML[moon]}** "
        f"({SIGNS_EN[moon]}), {nak}-{pada} · Lahiri, {v.node} node · transits from the Moon · "
        f"dasa on a fixed scale (÷{dasa_scale():g}) · overall = {_formula(v.factors)}, "
        f"3-month average"
    )

    s = state.sensitivity(v.birth, v.node)
    margin = min(m for m in (s.lagna_earlier, s.lagna_later, 10 ** 6) if m is not None)
    note = (f"**Birth-time check:** the Lagna stays {SIGNS_ML[lagna]} only if the recorded time is "
            f"accurate to within **{_minutes(s.lagna_earlier)} earlier / "
            f"{_minutes(s.lagna_later)} later** — beyond that every house shifts by one. "
            f"Dasa dates move about **{s.dasa_days_per_10min} days per 10 minutes** of "
            f"birth-time error.")
    (st.warning if margin < 30 else st.info)(note)
