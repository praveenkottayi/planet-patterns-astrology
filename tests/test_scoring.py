"""Scoring rules: computed dasa weights, transit rules, fixed scale, and timeline sanity."""

import pandas as pd
import pytest

from life_weather.analysis import assumptions as A
from life_weather.analysis.dasa_weight import dasa_scale, dasa_weights
from life_weather.analysis.gochara import jupiter_score, nodes_score, saturn_score
from life_weather.analysis.timeline import build
from tests.conftest import birth_from, chart_fx

FLAT_BAV = [A.BINDU_NEUTRAL] * 12   # removes the bindu term so only the house rule shows


# ─── Dasa weights ─────────────────────────────────────────────────────────────

def test_dasa_weights_match_brief(charts):
    for cid, (fx, chart) in charts.items():
        w = dasa_weights(chart)
        for planet, expected in fx.get("dasa_weights", {}).items():
            assert w[planet].total == pytest.approx(expected), f"{cid} {planet} {w[planet].reasons}"


def test_fixed_scale_bounds_every_chart(charts):
    scale = dasa_scale()
    for _, chart in charts.values():
        assert all(abs(pw.total) <= scale for pw in dasa_weights(chart).values())


# ─── Transit rules (house from Moon; moon_sign = 0 so sign index = house − 1) ──

def test_jupiter_over_moon_is_unfavourable():          # HANDOFF §6 bug 2
    score, why = jupiter_score(0, 0, FLAT_BAV)
    assert score == A.JUPITER_ELSE < 0 and "1st" in why


@pytest.mark.parametrize("house", [2, 5, 7, 9, 11])
def test_jupiter_good_houses(house):
    assert jupiter_score(house - 1, 0, FLAT_BAV)[0] == 1.0


@pytest.mark.parametrize("house,expected,name", [
    (8, -1.5, "Ashtama"), (12, -1.0, "Sade Sati"), (1, -1.0, "Sade Sati"),
    (2, -1.0, "Sade Sati"), (4, -0.75, "Ardhashtama"), (3, 1.0, ""), (9, -0.25, ""),
])
def test_saturn_houses(house, expected, name):
    score, why = saturn_score(house - 1, 0, FLAT_BAV)
    assert score == expected and name in why


def test_bindus_shift_score():
    bav = FLAT_BAV.copy()
    bav[1] = 7
    assert jupiter_score(1, 0, bav)[0] == pytest.approx(1.0 + 0.25 * 3)


def test_nodes_average_rahu_and_ketu():
    # Rahu 3rd (+0.5) ⇒ Ketu 9th (0) → +0.25 ; Rahu 8th (−0.5) ⇒ Ketu 2nd (0) → −0.25
    assert nodes_score(2, 0)[0] == 0.25
    assert nodes_score(7, 0)[0] == -0.25


# ─── Timeline ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def chart_b_lw(private):
    return build(birth_from(chart_fx(private, "chart_b")), end_year=2045)


def test_timeline_is_complete(chart_b_lw):
    df = chart_b_lw.frame
    assert not df[["dasa", "jupiter", "saturn", "nodes", "score", "smoothed"]].isna().any().any()
    assert df["dasa"].abs().max() <= A.LANE_RANGE
    assert all(df[c].str.len().gt(0).all() for c in ["why_dasa", "why_jupiter", "why_saturn", "why_nodes"])


def test_dasa_lane_follows_md_weights(chart_b_lw):
    """Regression on the rules (not a fit): among Maha-dasas fully inside the timeline, the one
    with the highest computed weight averages higher on the Dasa lane than the lowest."""
    lw = chart_b_lw
    df = lw.frame.set_index("date")
    first, last = df.index[0], df.index[-1]
    inside = [md for md in lw.maha_dasas
              if first <= pd.Timestamp(md.start) and pd.Timestamp(md.end) <= last]
    best = max(inside, key=lambda md: lw.weights[md.md].total)
    worst = min(inside, key=lambda md: lw.weights[md.md].total)
    mean = lambda md: df.loc[str(md.start):str(md.end), "dasa"].mean()  # noqa: E731
    assert lw.weights[best.md].total > lw.weights[worst.md].total
    assert mean(best) > mean(worst)


# ─── Exact-date reasons & birth-time sensitivity ─────────────────────────────

def test_exact_date_matches_timeline_on_sample_dates(chart_b_lw):
    for _, row in chart_b_lw.frame.iloc[::400].iterrows():
        exact = chart_b_lw.on(row["date"].date())
        assert exact["why_saturn"] == row["why_saturn"] and exact["dasa"] == row["dasa"]


def test_exact_date_sees_ingress_between_samples(private):
    """Jupiter enters Chingam on 31 Oct 2026 ~12:00 IST (checked against astropy)."""
    from datetime import date
    lw = build(birth_from(chart_fx(private, "chart_a")), end_year=2027)
    assert "Karkidakam" in lw.on(date(2026, 10, 30))["why_jupiter"]
    assert "Chingam" in lw.on(date(2026, 11, 1))["why_jupiter"]


def test_birth_time_sensitivity(private):
    from life_weather.analysis.sensitivity import birth_time_sensitivity
    fx = chart_fx(private, "chart_a")
    s = birth_time_sensitivity(birth_from(fx))
    assert [s.lagna_earlier, s.lagna_later] == fx["lagna_margin_minutes"]
    assert 30 <= s.dasa_days_per_10min <= 60     # Moon moves ~0.08° per 10 min
