"""Tab: transit + motion — the gochara chart with the selected planets, their positions on the
chosen date, the phase / longitude motion graph, exact events, and the planets at birth."""
from __future__ import annotations

from datetime import datetime, time, timedelta

import pandas as pd
import streamlit as st

from ..core.chart import house_between, retrograde, sidereal_longitudes, sign_of, to_jd
from ..core.constants import GRAHAS, NODES, SIGNS_ML
from ..core.dignity import dignity, neecha_bhanga
from ..viz.motion_figure import build_motion_figure
from ..viz.south_chart import render_south_chart
from . import state
from .state import View

ALL = GRAHAS + NODES
DEFAULT = ["Jupiter", "Saturn", "Ketu"]
WINDOWS = [0.5, 1, 2, 5, 10, 15, 30]
HOW_TO_READ = """
**Each line is one planet travelling round the zodiac. One full wave = one full orbit**
(Jupiter ≈ 12 years, Saturn ≈ 29½, Rahu/Ketu ≈ 18½ — the nodes move backwards, so their
waves run the other way).

**The height tells you roughly where the planet is:**

| Line is… | Planet is moving through |
|---|---|
| going **up** | Makaram → Kumbham → Meenam → Medam → Edavam → Mithunam |
| at the **top** (+1) | entering Karkidakam |
| going **down** | Karkidakam → Chingam → Kanni → Thulam → Vrischikam → Dhanu |
| at the **bottom** (−1) | entering Makaram |

*Rahu and Ketu always move backwards, so for them read the direction the other way round
(going up = Mithunam → … → Makaram).*

**Small wiggles with diamonds** = retrograde: the planet slows, backs up a little, then moves on.

**★ and the dashed line** = where each planet is on the chosen date (set in the sidebar).

**Lines crossing does not mean the planets meet** — the same height comes twice per orbit.
For the exact sign and house use the table above; for exact dates use the events below.

**Zoom** with 6m / 1y / 5y / All, or drag the slider under the chart.
"""
KIND_LABEL = {"ingress": "enters a sign", "station": "turns retrograde / direct",
              "contact": "passes over a birth point"}


def _birth_table(v: View) -> pd.DataFrame:
    chart = v.lw.chart
    retro = retrograde(chart.jd)
    rows = []
    for p in ["Lagna"] + ALL:
        nak, pada = chart.nakshatra(p)
        d = dignity(p, chart.sign(p)) if p != "Lagna" else ""
        if d == "debilitated" and neecha_bhanga(chart, p):
            d = "neecha bhanga"
        rows.append({"": p, "Sign": SIGNS_ML[chart.sign(p)],
                     "Degree": f"{chart.deg_in_sign(p):.1f}°", "Nakshatra": f"{nak}-{pada}",
                     "House": "—" if p == "Lagna" else f"H{chart.house(p)}",
                     "☾": "—" if p in ("Lagna", "Moon") else f"☾{chart.house(p, 'Moon')}",
                     "Dignity": d or "—", "℞": "℞" if retro.get(p) else ""})
    return pd.DataFrame(rows)


def render(v: View) -> None:
    chart = v.lw.chart
    lagna, moon = chart.sign("Lagna"), chart.sign("Moon")
    st.subheader(f"Transit + motion · {v.when_label}")

    c1, c2 = st.columns([2, 1])
    bodies = c1.multiselect("Planets", ALL, default=DEFAULT, key="motion_planets",
                            help="Slow planets shape years; add Mars or the Sun for months. "
                                 "The Moon circles the chart every 27 days.")
    window = c2.selectbox("Window (± years)", WINDOWS, index=WINDOWS.index(30),
                          help=f"Centred on the sidebar date ({v.when_label}).")
    if not bodies:
        st.info("Pick at least one planet.")
        return

    jd = to_jd(datetime.combine(v.pick, time(12)), v.birth.tz_hours)
    all_now = sidereal_longitudes(jd, v.node)
    now = {b: all_now[b] for b in bodies}
    retro_now = retrograde(jd)

    left, right = st.columns(2)
    with left:
        st.markdown(render_south_chart(chart, now, retro_now, "Gochara", f"transits {v.when_label}"),
                    unsafe_allow_html=True)
        st.caption("Dark text = birth planets · coloured tags = the selected planets on the "
                   "chosen date · yellow = Lagna, blue = Moon sign.")
    with right:
        st.dataframe(pd.DataFrame([{
            "Planet": b, "Sign": SIGNS_ML[sign_of(lon)], "Degree": f"{lon % 30:.1f}°",
            "R": "℞" if retro_now.get(b) else "",
            "House": house_between(sign_of(lon), lagna),
            "From Moon": house_between(sign_of(lon), moon),
        } for b, lon in now.items()]), hide_index=True, use_container_width=True)

    centre = datetime.combine(v.pick, time(12))
    start = max(centre - timedelta(days=365.25 * window), v.birth.when_local)
    end = centre + timedelta(days=365.25 * window)
    sdf, evs = state.motion(v.birth, v.node, start, end, tuple(bodies))

    st.plotly_chart(build_motion_figure(sdf, v.pick, now, retro_now), use_container_width=True)
    with st.expander("📖 How to read this chart", expanded=True):
        st.markdown(HOW_TO_READ)

    st.subheader("Events")
    k1, k2 = st.columns([3, 1])
    kinds = k1.multiselect("Show", list(KIND_LABEL), default=list(KIND_LABEL),
                           format_func=KIND_LABEL.get, label_visibility="collapsed")
    only_ahead = k2.toggle(f"From {v.when_label} on", value=True)
    rows = [e for e in evs if e.kind in kinds and (not only_ahead or e.when.date() >= v.pick)]
    if rows:
        st.dataframe(pd.DataFrame([{
            "When (local)": f"{e.when:%d %b %Y, %H:%M}", "Event": e.text,
            "Sign": SIGNS_ML[e.sign], "House": f"H{e.house}", "From Moon": f"☾{e.moon_house}",
        } for e in rows]), hide_index=True, use_container_width=True,
            height=min(38 + 35 * len(rows), 420))
        st.caption(f"Exact times (to the minute) in the birth time zone, UTC "
                   f"{v.birth.tz_hours:+g} h. Retrograde planets can enter the same sign, or pass "
                   "the same point, up to three times — each pass is listed. The Moon is left out.")
    else:
        st.caption("No events of these kinds in the window.")

    with st.expander("Planets at birth"):
        st.caption("House = from Lagna · ☾ = from Moon · neecha bhanga = debilitation cancelled")
        st.dataframe(_birth_table(v), hide_index=True, use_container_width=True)
