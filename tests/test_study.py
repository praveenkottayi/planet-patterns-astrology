"""The personal study: exact fast scorers, signal vs noise, multiple-test correction, storage."""
from datetime import date, datetime
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import swisseph as swe

from life_weather.analysis.house_timeline import _dasa_focus, house_scores_at
from life_weather.analysis.study import (AREAS, chart_scores, features, holm, house_scores,
                                         run_study, transit_table)
from life_weather.analysis.timeline import build, score_of
from life_weather.core.chart import Birth

YEARS = list(range(1988, 2026))
NO_EVENTS = pd.DataFrame(columns=["date", "category", "valence", "note"])


@pytest.fixture(scope="module")
def lw():
    return build(Birth("t", datetime(1975, 6, 1, 8, 30), 5.5, 13.08, 80.27), end_year=2026)


@pytest.fixture(scope="module")
def feats(lw):
    return features(lw.chart, transit_table(YEARS[0], YEARS[-1]))


def _ratings(overall, career=None) -> pd.DataFrame:
    """Every life area rated `overall` (so the computed overall equals it); career optional."""
    r = pd.DataFrame({"year": YEARS, "overall": np.nan})
    for a in AREAS[1:]:
        r[a] = np.asarray(overall, float)
    if career is not None:
        r["career"] = career
    return r


def test_fast_scorers_equal_the_app(lw):
    tt = transit_table(1990, 1993)
    fast_overall, fast_houses = chart_scores(lw.chart, tt), house_scores(lw.chart, tt)
    ref, focus = lw.chart.sign("Lagna"), _dasa_focus(lw, lw.chart.sign("Lagna"))
    for i, jd in enumerate(tt.jd):
        d = date(*swe.revjul(jd)[:3])
        row = lw.on(d)
        assert fast_overall[i] == pytest.approx(score_of(row))
        scores, _ = house_scores_at(lw, SimpleNamespace(**row), ref, focus)
        assert fast_houses[i] == pytest.approx([scores[h] for h in range(1, 13)])


def test_detects_ratings_that_follow_the_model(lw, feats):
    rng = np.random.default_rng(1)
    overall = np.clip(np.round(feats.overall[YEARS].to_numpy() * 2 + rng.normal(0, .3, len(YEARS))),
                      -2, 2)
    career = np.clip(np.round(feats.houses.loc[YEARS, 10].to_numpy() * 3
                              + rng.normal(0, .3, len(YEARS))), -2, 2)
    report = run_study(lw, _ratings(overall, career), NO_EVENTS, n_random=200)
    by = {t.name: t for t in report.tests}
    assert by["Overall"].verdict == "signal beyond chance" and by["Overall"].beats > 0.95
    assert by["Career"].verdict == "signal beyond chance"
    assert set(report.jitter) == {-30, -20, -10, 0, 10, 20, 30}


def test_random_ratings_are_chance(lw):
    rng = np.random.default_rng(7)
    report = run_study(lw, _ratings(rng.integers(-2, 3, len(YEARS)).astype(float)), NO_EVENTS,
                       n_random=200)
    assert all(t.verdict != "signal beyond chance" for t in report.tests)


def test_events_in_matching_stretches_count_as_hits(lw, feats):
    tt = transit_table(YEARS[0], YEARS[-1])
    green = np.where(feats.smoothed > 0.3)[0][::40][:4]
    red = np.where(feats.smoothed < -0.3)[0][::40][:4]
    rows = [(date(*swe.revjul(tt.jd[i])[:3]), 1) for i in green] + \
           [(date(*swe.revjul(tt.jd[i])[:3]), -1) for i in red]
    events = pd.DataFrame({"date": [d for d, _ in rows], "category": "other",
                           "valence": [v for _, v in rows], "note": ""})
    report = run_study(lw, _ratings([0.0] * len(YEARS)), events, n_random=100)
    ev = next(t for t in report.tests if t.name == "Events")
    assert ev.result == f"{len(rows)}/{len(rows)} match"


def test_holm_correction():
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


def test_store_round_trip(tmp_path):
    from life_weather import study_store
    ratings = _ratings([1.0, -2.0] + [np.nan] * (len(YEARS) - 2))
    events = pd.DataFrame({"date": [date(2001, 5, 1)], "category": ["career"], "valence": [1],
                           "note": ["new job"]})
    p = study_store.save("Test Person", ratings, events, [{"when": "x"}], root=tmp_path)
    assert p.name == "test-person.json" and oct(p.stat().st_mode)[-3:] == "600"
    back = study_store.load("Test Person", root=tmp_path)
    assert list(back["ratings"]["health"]) == [1.0, -2.0]
    assert back["events"].iloc[0]["date"] == date(2001, 5, 1) and back["runs"] == [{"when": "x"}]


@pytest.mark.parametrize("typed,value", [
    ("-1", -1.0), ("1.5", 1.5), ("+2", 2.0), (".5", 0.5), ("−0.5", -0.5), (" -2 ", -2.0),
    ("0", 0.0), ("-1.25", -1.25)])
def test_rating_cells_accept_negatives_and_decimals(typed, value):
    import re

    from life_weather.ui.tab_study import RATING_PATTERN, parse_rating
    assert re.fullmatch(RATING_PATTERN, typed) and parse_rating(typed) == value


@pytest.mark.parametrize("typed", ["3", "-2.5", "abc", "1-"])
def test_rating_cells_reject_out_of_range(typed):
    import re

    from life_weather.ui.tab_study import RATING_PATTERN, parse_rating
    assert not re.fullmatch(RATING_PATTERN, typed) and np.isnan(parse_rating(typed))


def test_blank_rating_is_allowed_and_means_unrated():
    import re

    from life_weather.ui.tab_study import RATING_PATTERN, parse_rating
    assert re.fullmatch(RATING_PATTERN, "") and np.isnan(parse_rating(""))


def test_overall_is_computed_from_areas_and_typed_overall_is_ignored(lw):
    from life_weather.analysis.study import with_computed_overall
    r = pd.DataFrame({"year": [2000, 2001, 2002], "overall": [2.0, 2.0, 2.0],
                      "career": [1.0, np.nan, np.nan], "money": [np.nan, np.nan, np.nan],
                      "health": [-1.0, -1.5, np.nan], "relationships": [np.nan] * 3,
                      "home": [np.nan] * 3})
    out = with_computed_overall(r)
    assert out["overall"].iloc[0] == 0.0 and out["overall"].iloc[1] == -1.5
    assert np.isnan(out["overall"].iloc[2])


def test_area_ratings_alone_drive_the_overall_test(lw):
    """Regression: with only health rated (and a contradictory typed overall), the overall test
    uses the health ratings."""
    rng = np.random.default_rng(3)
    r = pd.DataFrame({"year": YEARS, **{a: np.nan for a in AREAS}})
    r["overall"] = 2.0                                           # typed — must be ignored
    r.loc[:22, "health"] = rng.integers(-2, 3, 23)
    events = pd.DataFrame({"date": [date(2000 + i, 6, 1) for i in range(6)], "category": "other",
                           "valence": [1, -1] * 3, "note": ""})
    report = run_study(lw, r, events, n_random=50)
    names = [t.name for t in report.tests]
    assert names[0] == "Overall" and "Health" in names and "Events" in names
    assert report.tests[0].n == 23 and report.jitter
