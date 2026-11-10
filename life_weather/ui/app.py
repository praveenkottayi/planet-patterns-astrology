"""Life Weather — Streamlit entry point.   Run:  streamlit run life_weather/ui/app.py"""
from __future__ import annotations

from dataclasses import replace

import streamlit as st

from life_weather.analysis.timeline import combine
from life_weather.ui import (download, header, sidebar, state, tab_chart, tab_houses, tab_motion,
                             tab_weather)
from life_weather.ui.state import View

st.set_page_config(page_title="Life Weather", page_icon="🌦️", layout="wide")

birth, factors, end_year, node = sidebar.person_and_options()
base = state.life_weather(birth, end_year, node)
dates = base.frame["date"]
pick = sidebar.detail_date(dates.iloc[0].date(), dates.iloc[-1].date())

view = View(birth, factors, end_year, node, pick, base,
            lw=replace(base, frame=combine(base.frame, factors)))

download.render(view)
header.render(view)
motion, weather, houses, chart = st.tabs(
    ["🌀 Planets in motion", "🌦️ Life Weather", "🏠 Houses over time", "🪐 Chart & houses"])
with motion:
    tab_motion.render(view)
with weather:
    tab_weather.render(view)
with houses:
    tab_houses.render(view)
with chart:
    tab_chart.render(view)
