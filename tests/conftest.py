import tomllib
from datetime import datetime
from pathlib import Path

import pytest

from life_weather.core.chart import Birth, natal_chart

PRIVATE = Path(__file__).parent / "fixtures_private.toml"


def _load_private() -> dict:
    if not PRIVATE.exists():
        pytest.skip("tests/fixtures_private.toml not present (real birth data is never committed)")
    with PRIVATE.open("rb") as f:
        return tomllib.load(f)


@pytest.fixture(scope="session")
def private() -> dict:
    return _load_private()


def birth_from(fx: dict) -> Birth:
    when = fx["when"]
    if not isinstance(when, datetime):
        when = datetime.fromisoformat(str(when))
    return Birth(fx["id"], when, fx["tz"], fx["lat"], fx["lon"])


@pytest.fixture(scope="session")
def charts(private) -> dict:
    """id → (fixture dict, Chart)"""
    return {fx["id"]: (fx, natal_chart(birth_from(fx))) for fx in private["chart"]}


def chart_fx(private: dict, cid: str) -> dict:
    """One chart's fixture block by its anonymous id."""
    return next(c for c in private["chart"] if c["id"] == cid)
