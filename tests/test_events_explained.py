"""Life events set against the chart: dasa, positions, named conditions, themes."""
from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from life_weather.analysis.events_explained import explain, themes
from life_weather.analysis.timeline import build
from life_weather.core.chart import Birth, house_between


@pytest.fixture(scope="module")
def lw():
    return build(Birth("t", datetime(1985, 3, 10, 7, 45), 5.5, 13.08, 80.27), end_year=2026)


def _events(rows):
    return pd.DataFrame([{"date": d, "category": c, "valence": v, "note": ""} for d, c, v in rows])


def test_positions_and_dasa_match_the_engine(lw):
    d = date(2010, 6, 1)
    (e,) = explain(lw, _events([(d, "career", 1)]))
    on = lw.on(d)
    assert (e.md, e.ad) == (on["md"], on["ad"]) and e.ad_start <= d < e.ad_end
    sign, h_lagna, h_moon = e.positions["Saturn"]
    assert h_lagna == house_between(sign, lw.chart.sign("Lagna"))
    assert h_moon == house_between(sign, lw.chart.sign("Moon"))


def test_new_sub_period_is_flagged(lw):
    start = next(p for p in lw.periods if p.start > date(2005, 1, 1)).start
    (e,) = explain(lw, _events([(start + timedelta(days=10), "other", -1)]))
    assert e.conditions[0].endswith("sub-period had just begun (10 days before)")


def test_sade_sati_is_named(lw):
    moon = lw.chart.sign("Moon")
    for y in range(1990, 2026):
        (e,) = explain(lw, _events([(date(y, 7, 1), "other", 1)]))
        if e.positions["Saturn"][2] == 1:
            assert any(c.startswith("Sade Sati, peak phase") for c in e.conditions)
            return
    pytest.skip(f"Saturn never over Moon sign {moon} in the sampled years")


def test_events_before_birth_are_ignored_and_order_is_by_date(lw):
    out = explain(lw, _events([(date(2020, 1, 1), "home", 1), (date(1980, 1, 1), "home", 1),
                               (date(2001, 1, 1), "home", -1)]))
    assert [e.when.year for e in out] == [2001, 2020]


def test_themes_count_good_and_hard(lw):
    ev = explain(lw, _events([(date(2011, 3, 1), "career", 1), (date(2011, 4, 1), "health", -1),
                              (date(2011, 5, 1), "home", -1)]))
    table = themes(ev).set_index("Condition")
    md = f"{ev[0].md} Maha-dasa"
    assert (table.loc[md, "Good events"], table.loc[md, "Hard events"]) == (1, 2)
