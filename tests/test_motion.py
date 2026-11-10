"""Exact transit events (checked against astropy-verified ingress times) and the motion graph."""
from datetime import datetime

import numpy as np
import pytest

from life_weather.analysis.motion import _gap, _jd, events, position, series
from life_weather.core.chart import Chart, house_between
from life_weather.core.constants import SIGNS_ML
from life_weather.viz.motion_figure import _break_wraps


def _chart(**lons) -> Chart:
    base = {"Sun": 0, "Moon": 0, "Mars": 0, "Mercury": 0, "Jupiter": 0, "Venus": 0,
            "Saturn": 0, "Rahu": 0, "Ketu": 180, "Lagna": 0}
    base.update(lons)
    return Chart(jd=0, longitudes=base, ayanamsa=0, node="mean")


# Ingress times confirmed independently with astropy (tools/crosscheck.py method), IST.
VERIFIED = [("Jupiter", "Chingam", "2026-10-31 12:02"), ("Mars", "Chingam", "2026-11-12 20:18"),
            ("Rahu", "Makaram", "2026-12-05 22:32"), ("Jupiter", "Thulam", "2029-08-25 01:01")]


@pytest.fixture(scope="module")
def evs():
    return events(_chart(Lagna=95, Moon=245), datetime(2026, 10, 1), datetime(2029, 9, 1), 5.5,
                  ["Jupiter", "Mars", "Rahu", "Saturn"])


@pytest.mark.parametrize("planet,sign,when", VERIFIED)
def test_ingress_times_to_the_minute(evs, planet, sign, when):
    hits = [e for e in evs if e.kind == "ingress" and e.text == f"{planet} enters {sign}"]
    target = datetime.fromisoformat(when)
    assert min(abs((e.when - target).total_seconds()) for e in hits) <= 90


def test_ingress_reports_house_of_the_sign_entered(evs):
    for e in (e for e in evs if e.kind == "ingress"):
        assert SIGNS_ML[e.sign] == e.text.split()[-1]
        assert e.house == house_between(e.sign, 3) and e.moon_house == house_between(e.sign, 8)


def test_stations_alternate_and_flip_speed(evs):
    sat = [e for e in evs if e.kind == "station" and e.planet == "Saturn"]
    turns = ["retrograde" in e.text for e in sat]
    assert len(turns) >= 4 and all(a != b for a, b in zip(turns, turns[1:]))


def test_contact_lands_exactly_on_the_natal_point():
    target = position(2461500.5, "Saturn")[0]          # put a natal Moon where Saturn will be
    chart = _chart(Moon=target, Lagna=(target + 100) % 360)
    hits = [e for e in events(chart, datetime(2026, 1, 1), datetime(2028, 12, 31), 5.5, ["Saturn"])
            if e.kind == "contact" and "birth Moon" in e.text]
    assert hits
    for e in hits:
        assert abs(_gap(position(_jd(e.when, 5.5), "Saturn")[0], target)) < 0.001


def test_series_and_wrap_breaks():
    df = series(datetime(2020, 1, 1), datetime(2022, 1, 1), 5.5, ["Rahu", "Jupiter"])
    assert set(df["body"]) == {"Rahu", "Jupiter"} and not df["retro"][df["body"] == "Rahu"].any()
    y = _break_wraps(np.array([350.0, 355.0, 2.0, 8.0, 3.0]))
    assert np.isnan(y[2]) and y[3] == 8.0 and y[4] == 3.0
