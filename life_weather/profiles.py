"""People the app offers in its Profile list.

- Your own people come from environment variables, usually kept in the repo's `.env` file
  (gitignored — real birth details never go in git). One variable per person:

      LW_PROFILE_1="Name | 1990-01-01 12:00 | City"
      LW_PROFILE_2="Name | 1990-01-01 12:00 | City | 13.08 | 80.27 | 5.5"   # lat | lon | tz

  lat / lon / tz are optional; without them they come from the offline city list, with the
  UTC offset in force on the birth date. Real environment variables override `.env`.
- Public examples (well-known people, published birth data) ship in `examples.toml`.
"""
from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .core.chart import Birth
from .places import search_cities, utc_offset_hours

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
ENV_PREFIX = "LW_PROFILE_"
EXAMPLES = Path(__file__).resolve().parent / "examples.toml"


@dataclass(frozen=True)
class Profile:
    birth: Birth
    example: bool = False
    note: str = ""        # e.g. how reliable a published birth time is

    @property
    def label(self) -> str:
        return f"{self.birth.name} · example" if self.example else self.birth.name


def _resolve(name: str, when: datetime, place: str, lat=None, lon=None, tz=None) -> Birth:
    """Fill missing lat / lon / tz from the city name."""
    if lat is None or lon is None or tz is None:
        matches = search_cities(place)
        if not matches:
            raise ValueError(f"profile {name!r}: city {place!r} not found; give lat, lon and tz")
        city = matches[0]
        lat = city.lat if lat is None else lat
        lon = city.lon if lon is None else lon
        tz = utc_offset_hours(city.tz_name, when, lon) if tz is None else tz
    return Birth(name, when, float(tz), float(lat), float(lon), place)


# ─── Your people: environment / .env ──────────────────────────────────────────

def read_env_file(path: Path = ENV_FILE) -> dict[str, str]:
    """Minimal KEY=VALUE reader (comments, blank lines, optional quotes, `export` prefix)."""
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        out[key.strip()] = value.strip().strip("'\"")
    return out


def parse_env_profile(value: str) -> Birth:
    """'Name | YYYY-MM-DD HH:MM | City [| lat | lon | tz]' → Birth."""
    parts = [p.strip() for p in value.split("|")]
    if len(parts) not in (3, 6):
        raise ValueError(f"expected 'Name | YYYY-MM-DD HH:MM | City [| lat | lon | tz]', "
                         f"got {value!r}")
    name, when, place = parts[:3]
    lat, lon, tz = (float(x) for x in parts[3:]) if len(parts) == 6 else (None, None, None)
    return _resolve(name, datetime.fromisoformat(when), place, lat, lon, tz)


def private_profiles(env: dict[str, str] | None = None) -> list[Profile]:
    env = {**read_env_file(), **os.environ} if env is None else env
    keys = sorted((k for k in env if k.startswith(ENV_PREFIX)),
                  key=lambda k: int(re.sub(r"\D", "", k) or 0))
    return [Profile(parse_env_profile(env[k])) for k in keys if env[k].strip()]


# ─── Public examples ──────────────────────────────────────────────────────────

def example_profiles(path: Path = EXAMPLES) -> list[Profile]:
    if not path.exists():
        return []
    with path.open("rb") as f:
        people = tomllib.load(f).get("person", [])
    out = []
    for p in people:
        when = p["when"] if isinstance(p["when"], datetime) else datetime.fromisoformat(str(p["when"]))
        birth = _resolve(p["name"], when, p.get("place", ""), p.get("lat"), p.get("lon"), p.get("tz"))
        out.append(Profile(birth, example=True, note=p.get("note", "")))
    return out


def load_profiles() -> list[Profile]:
    """Your people first, then the public examples."""
    return private_profiles() + example_profiles()
