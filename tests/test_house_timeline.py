"""House scores against values worked out by hand (the derivation and numbers live in the
private fixture, since they reveal a real chart)."""
from types import SimpleNamespace

import pytest

from life_weather.analysis.house_timeline import _dasa_focus, house_scores_at, house_timeline
from life_weather.analysis.timeline import build
from tests.conftest import birth_from, chart_fx


@pytest.fixture(scope="module")
def chart_a(private):
    fx = chart_fx(private, "chart_a")
    return fx, build(birth_from(fx), end_year=2028)


def test_house_scores_by_hand(chart_a):
    fx, lw = chart_a
    check = fx["house_scores"]
    row = SimpleNamespace(**lw.on(check["date"]))
    ref = lw.chart.sign("Lagna")
    scores, why = house_scores_at(lw, row, ref, _dasa_focus(lw, ref))
    for h, expected in enumerate(check["H"], start=1):
        assert scores[h] == pytest.approx(expected), f"H{h}: {why[h]}"


def test_house_timeline_shape(chart_a):
    _, lw = chart_a
    df = house_timeline(lw, "Moon")
    assert len(df) == len(lw.frame)
    assert not df[[f"S{h}" for h in range(1, 13)]].isna().any().any()
