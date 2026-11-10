"""Page title, method summary and the birth-time warning."""
from __future__ import annotations

import streamlit as st

from ..analysis.dasa_weight import dasa_scale
from ..analysis.narrative import key_facts
from ..core.constants import SIGNS_ML
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


def _key_facts(v: View) -> None:
    """The basics a person can check against their own horoscope before reading further."""
    b = v.birth
    where = f" · {b.place}" if b.place else ""
    with st.container(border=True):
        st.markdown(f"**Key facts — check these against your horoscope**  \n"
                    f"<small>Born {b.when_local:%d %b %Y, %H:%M}{where}</small>",
                    unsafe_allow_html=True)
        facts = key_facts(v.lw)
        for row in (facts[:3], facts[3:]):
            for col, (label, value) in zip(st.columns(3), row):
                col.caption(label)
                col.markdown(f"**{value}**")


def render(v: View) -> None:
    lagna = v.lw.chart.sign("Lagna")

    st.title(f"Life Weather · {v.birth.name}")
    _key_facts(v)
    st.caption(
        f"Method: Lahiri ayanamsa, {v.node} node · transits from the Moon · "
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
