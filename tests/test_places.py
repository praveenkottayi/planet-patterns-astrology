"""Offline city lookup and historical UTC offsets."""
from datetime import datetime

import pytest

from life_weather.places import search_cities, utc_offset_hours
from life_weather.profiles import (example_profiles, parse_env_profile, private_profiles,
                                   read_env_file)


@pytest.mark.parametrize("query,name,country", [
    ("chennai", "Chennai", "India"), ("madras", "Chennai", "India"),
    ("calcutta", "Kolkata", "India"), ("bombay", "Mumbai", "India"), ("london", "London", "United Kingdom"),
])
def test_search_top_hit(query, name, country):
    top = search_cities(query)[0]
    assert (top.name, top.country) == (name, country)


@pytest.mark.parametrize("tz,when,offset", [
    ("Asia/Kolkata", "2000-01-01T12:00", 5.5),
    ("Asia/Kolkata", "1943-06-01T12:00", 6.5),     # wartime IST
    ("Europe/London", "1990-07-01T12:00", 1.0),    # BST
    ("Europe/London", "1990-01-01T12:00", 0.0),
])
def test_historical_offsets(tz, when, offset):
    assert utc_offset_hours(tz, datetime.fromisoformat(when)) == offset


# ─── Profiles: .env (yours) and examples (public) ────────────────────────────

def test_env_profile_city_only():
    b = parse_env_profile("X | 2000-06-15 08:00 | Pune")
    assert (b.name, b.place, round(b.lat, 2), round(b.lon, 2), b.tz_hours) == \
        ("X", "Pune", 18.52, 73.86, 5.5)


def test_env_profile_with_coordinates():
    b = parse_env_profile("Y | 1985-05-05 05:05 | Somewhere | 10.5 | 76.2 | 5.5")
    assert (b.lat, b.lon, b.tz_hours, b.when_local.hour) == (10.5, 76.2, 5.5, 5)


@pytest.mark.parametrize("bad", ["X | 2000-01-01 12:00", "X | 2000-01-01 12:00 | Pune | 1 | 2",
                                 "X | 2000-01-01 12:00 | Zzzqqq"])
def test_env_profile_errors(bad):
    with pytest.raises(ValueError):
        parse_env_profile(bad)


def test_env_file_reader_and_order(tmp_path):
    f = tmp_path / ".env"
    f.write_text('# comment\nexport LW_PROFILE_10="B | 2001-01-01 01:00 | Pune"\n'
                 "LW_PROFILE_2='A | 2000-01-01 00:00 | Pune'\nOTHER=1\n\n")
    env = read_env_file(f)
    assert env["OTHER"] == "1"
    assert [p.birth.name for p in private_profiles(env)] == ["A", "B"]   # numeric order


def test_examples_ship_with_notes():
    examples = example_profiles()
    assert {p.birth.name for p in examples} >= {"Sachin Tendulkar", "Narendra Modi"}
    assert all(p.example and p.note and p.label.endswith("· example") for p in examples)


# ─── Saving people entered in the app ─────────────────────────────────────────

def _person(name="Asha", hour=6):
    from life_weather.core.chart import Birth
    return Birth(name, datetime(2001, 3, 4, hour, 30), 5.5, 9.9312, 76.2673, "Kochi, India")


def test_save_appends_then_updates_same_name(tmp_path):
    from life_weather.profiles import save_profile
    env = tmp_path / ".env"
    env.write_text('# my comment\nOTHER=keep\nLW_PROFILE_7="Old | 1990-01-01 00:00 | Pune"\n')
    assert save_profile(_person(), env) == ("LW_PROFILE_8", False)          # next number
    assert save_profile(_person(hour=7), env) == ("LW_PROFILE_8", True)      # same name → update
    text = env.read_text()
    assert "# my comment" in text and "OTHER=keep" in text and text.count("Asha") == 1
    assert oct(env.stat().st_mode)[-3:] == "600"
    people = {p.birth.name: p.birth for p in private_profiles(read_env_file(env))}
    assert set(people) == {"Old", "Asha"}
    a = people["Asha"]
    assert (a.when_local.hour, a.lat, a.lon, a.tz_hours, a.place) == (7, 9.9312, 76.2673, 5.5,
                                                                       "Kochi, India")


def test_save_creates_env_and_sanitises(tmp_path):
    from life_weather.profiles import format_env_profile, save_profile
    env = tmp_path / ".env"
    key, updated = save_profile(_person(name='A | "B"'), env)
    assert (key, updated) == ("LW_PROFILE_1", False) and env.read_text().startswith("# PRIVATE")
    assert "|" not in format_env_profile(_person(name="A|B")).split(" | ")[0]
    (p,) = private_profiles(read_env_file(env))
    assert p.birth.name == "A / 'B'"


def test_read_only_flag_blocks_saving(monkeypatch):
    from life_weather.profiles import saving_allowed
    monkeypatch.setenv("LW_READ_ONLY", "1")
    assert not saving_allowed()
    monkeypatch.delenv("LW_READ_ONLY")
    assert saving_allowed()
