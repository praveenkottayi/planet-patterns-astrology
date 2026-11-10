"""Births anywhere from 1800 to today (newborns included) build a full timeline."""
from datetime import date, datetime, timedelta

import pytest

from life_weather.analysis.house_timeline import house_timeline
from life_weather.analysis.sensitivity import birth_time_sensitivity
from life_weather.analysis.timeline import build
from life_weather.core.chart import Birth
from life_weather.places import search_cities, utc_offset_hours
from life_weather.ui.sidebar import end_year_range
from life_weather.viz.axis import year_dtick


def _birth(when: datetime) -> Birth:
    city = search_cities("Chennai")[0]
    return Birth("test", when, utc_offset_hours(city.tz_name, when, city.lon), city.lat, city.lon)


@pytest.mark.parametrize("when", [
    datetime.combine(date.today() - timedelta(days=1), datetime.min.time()),   # newborn
    datetime(1850, 3, 1, 6, 0),                                                 # historical
])
def test_full_pipeline_for_extreme_births(when):
    b = _birth(when)
    lo, hi, default = end_year_range(when.year)
    lw = build(b, end_year=default)
    assert lw.frame["date"].iloc[0].date() == when.date()
    assert not lw.frame[["dasa", "score", "smoothed"]].isna().any().any()
    assert not house_timeline(lw, "Lagna").isna().any().any()
    assert lw.on(when.date())["md"]
    birth_time_sensitivity(b)


def test_end_year_range_follows_birth():
    assert end_year_range(1850)[0] == 1851
    lo, hi, default = end_year_range(date.today().year)
    assert lo == date.today().year + 1 and hi >= date.today().year + 100 and lo <= default <= hi


def test_before_standard_time_uses_birthplace_local_mean_time():
    # tz database alone gives Kolkata's LMT (+5:53) for all of India before 1854.
    chennai = search_cities("Chennai")[0]
    when = datetime(1850, 3, 1, 6)
    assert utc_offset_hours(chennai.tz_name, when) == pytest.approx(5 + 53 / 60 + 28 / 3600)
    assert utc_offset_hours(chennai.tz_name, when, chennai.lon) == pytest.approx(chennai.lon / 15)
    assert utc_offset_hours(chennai.tz_name, datetime(2000, 1, 1), chennai.lon) == 5.5


@pytest.mark.parametrize("years,step", [(5, "M12"), (45, "M24"), (120, "M60")])
def test_year_ticks_thin_out(years, step):
    import pandas as pd
    first = pd.Timestamp("1900-01-01")
    assert year_dtick(first, first + pd.Timedelta(days=365.25 * years)) == step
