"""Plain-language sentences restate computed values correctly."""
from datetime import datetime

import pandas as pd

from life_weather.analysis.dasa_weight import dasa_weights
from life_weather.analysis.narrative import (clean_reason, dasa_sentence, house_reason,
                                             key_stretches, planet_role, tone)
from life_weather.analysis.timeline import LANES, LifeWeather
from life_weather.core.chart import Birth, natal_chart


def test_reason_cleaners():
    assert clean_reason("Saturn 8th from Moon — Ashtama Shani (-1.5), 3 bindus → -1.75") == \
        "Saturn 8th from Moon — Ashtama Shani"
    assert house_reason("MD Jupiter (-0.5) rules/sits here -0.09 · Saturn sits here, 3 bindus "
                        "-0.62 · Ketu aspects (7th) -0.25") == \
        "Maha-dasa lord Jupiter rules or sits here; Saturn sits here (3 bindus); Ketu aspects it (7th)"


def test_tone_bands():
    assert [tone(x) for x in (1.2, 0.5, 0.0, -0.5, -1.5)] == [
        "strongly supportive", "supportive", "mixed / neutral", "challenging",
        "strongly challenging"]


def test_planet_and_dasa_sentences_restate_the_chart():
    c = natal_chart(Birth("t", datetime(2000, 1, 1, 12), 5.5, 13.08, 80.27))
    w = dasa_weights(c)
    s = planet_role(c, w["Saturn"])
    assert s.startswith("rules H") and s.endswith(f"weight {w['Saturn'].total:+g}")
    assert "from the Lagna" not in s and "°" not in s          # no location: the table has it
    assert planet_role(c, w["Rahu"]).startswith("acts through its sign lord")
    assert dasa_sentence(c, w["Jupiter"], "Maha-dasa").startswith("Jupiter Maha-dasa (weight")


def _lw(values: list[float]) -> LifeWeather:
    dates = pd.date_range("2000-01-01", periods=len(values), freq="5D")
    df = pd.DataFrame({"date": dates, "smoothed": values, "md": "Venus", "ad": "Sun",
                       **{lane: values for lane in LANES},
                       **{f"why_{lane}": f"{lane} reason (+1) → +1" for lane in LANES}})
    return LifeWeather(None, None, {}, [], df, [], [], "mean")


def test_key_stretches_threshold_length_and_merge():
    # 30 samples (150 d) good, 8 samples (40 d) neutral gap, 30 good again → merged into one;
    # then 10 samples (50 d) bad → too short to count.
    vals = [1.0] * 30 + [0.0] * 8 + [1.0] * 30 + [0.0] * 5 + [-1.0] * 10
    st = key_stretches(_lw(vals), tuple(LANES))
    assert len(st) == 1                              # merged across the gap; bad run too short
    assert 0.8 < st[0].mean < 1.0                    # the merged span includes the neutral gap
    assert st[0].start == datetime(2000, 1, 1).date()
    assert st[0].end == (pd.Timestamp("2000-01-01") + pd.Timedelta(days=5 * 67)).date()


# ─── Key facts ────────────────────────────────────────────────────────────────

def _chart_at(when: datetime):
    return natal_chart(Birth("t", when, 5.5, 13.08, 80.27))


def test_tithi_on_known_full_and_new_moons():
    from life_weather.analysis.narrative import tithi
    assert tithi(_chart_at(datetime(2024, 4, 23, 12))) == "Pournami (full moon)"    # Chaitra Purnima
    assert tithi(_chart_at(datetime(2024, 11, 1, 12))) == "Amavasya (new moon)"     # Diwali
    assert tithi(_chart_at(datetime(2024, 4, 27, 12))).startswith("Krishna")         # waning after


def test_key_facts_are_consistent_with_the_chart():
    from datetime import timedelta

    from life_weather.analysis.narrative import key_facts
    from life_weather.analysis.timeline import build
    b = Birth("t", datetime(1995, 4, 2, 9, 15), 5.5, 13.08, 80.27)
    lw = build(b, end_year=2000)
    facts = dict(key_facts(lw))
    assert list(facts) == ["Lagna", "Rasi (Moon sign)", "Naal (birth star)", "Sun sign", "Tithi",
                           "Dasa balance at birth"]
    nak, pada = lw.chart.nakshatra("Moon")
    assert facts["Naal (birth star)"].startswith(f"{nak}, pada {pada} (")
    # On 2 April the Sun is ~12° tropical Aries, i.e. ~18° sidereal Pisces (Meenam).
    assert facts["Sun sign"] == "Meenam (Pisces) · Western (tropical): Aries"
    lord, y, _, m, _, d, _ = facts["Dasa balance at birth"].split()
    first = next(md for md in lw.maha_dasas if md.end_jd > lw.chart.jd)
    left = timedelta(days=int(y) * 365.25 + int(m) * 30.4375 + int(d))
    assert lord == first.md and abs((b.when_local + left).date() - first.end).days <= 1
