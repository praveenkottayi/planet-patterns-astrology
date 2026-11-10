"""What the user picked, and the cached computations every tab shares."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime

import pandas as pd
import streamlit as st

from ..analysis.house_timeline import house_timeline
from ..analysis.sensitivity import BirthTimeSensitivity, birth_time_sensitivity
from ..analysis.timeline import LifeWeather, build, combine
from ..core.chart import Birth
from ..report.pdf import build_pdf


@dataclass(frozen=True)
class View:
    birth: Birth
    factors: tuple[str, ...]
    end_year: int
    node: str
    pick: date           # the date driving the 'why' panel, transit chart and marker line
    base: LifeWeather    # all factors on (cached)
    lw: LifeWeather      # overall score recombined from the chosen factors

    @property
    def when_label(self) -> str:
        return f"{self.pick:%d %b %Y}"


# Cache keys are plain values so Streamlit can hash them cheaply.

def _key(b: Birth) -> tuple[str, datetime, float, float, float]:
    return b.name, b.when_local, b.tz_hours, b.lat, b.lon


@st.cache_data(show_spinner="Computing life weather…")
def _build(name, when, tz, lat, lon, end_year, node) -> LifeWeather:
    return build(Birth(name, when, tz, lat, lon), end_year=end_year, node=node)


@st.cache_data(show_spinner="Scoring houses…")
def _houses(name, when, tz, lat, lon, end_year, node, ref) -> pd.DataFrame:
    return house_timeline(_build(name, when, tz, lat, lon, end_year, node), ref)


@st.cache_data(show_spinner=False)
def _sensitivity(name, when, tz, lat, lon, node) -> BirthTimeSensitivity:
    return birth_time_sensitivity(Birth(name, when, tz, lat, lon), node)


def life_weather(birth: Birth, end_year: int, node: str) -> LifeWeather:
    return _build(*_key(birth), end_year, node)


def houses(birth: Birth, end_year: int, node: str, ref: str) -> pd.DataFrame:
    return _houses(*_key(birth), end_year, node, ref)


def sensitivity(birth: Birth, node: str) -> BirthTimeSensitivity:
    return _sensitivity(*_key(birth), node)


@st.cache_data(show_spinner="Preparing PDF…")
def _pdf(name, when, tz, lat, lon, place, end_year, node, factors, pick) -> bytes:
    base = _build(name, when, tz, lat, lon, end_year, node)
    lw = replace(base, frame=combine(base.frame, factors))
    birth = Birth(name, when, tz, lat, lon, place)
    return build_pdf(birth, lw, factors, node, pick,
                     _houses(name, when, tz, lat, lon, end_year, node, "Lagna"),
                     _sensitivity(name, when, tz, lat, lon, node))


def pdf_key(v: View) -> tuple:
    return (*_key(v.birth), v.birth.place, v.end_year, v.node, v.factors, v.pick)


def pdf(v: View) -> bytes:
    return _pdf(*pdf_key(v))
