"""City → coordinates and historical UTC offset. Fully offline (GeoNames via geonamescache +
the IANA tz database), so no birth details or places are sent anywhere."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

import geonamescache


@dataclass(frozen=True)
class Place:
    name: str
    country: str
    lat: float
    lon: float
    tz_name: str
    population: int

    @property
    def label(self) -> str:
        return f"{self.name}, {self.country}  ({self.lat:.2f}, {self.lon:.2f})"


@lru_cache(maxsize=1)
def _index() -> list[tuple[str, tuple[str, ...], Place]]:
    gc = geonamescache.GeonamesCache()
    countries = {code: c["name"] for code, c in gc.get_countries().items()}
    out = []
    for c in gc.get_cities().values():
        place = Place(c["name"], countries.get(c["countrycode"], c["countrycode"]),
                      float(c["latitude"]), float(c["longitude"]), c["timezone"],
                      int(c["population"]))
        alts = tuple(a.lower() for a in c.get("alternatenames", []) if a)
        out.append((c["name"].lower(), alts, place))
    return out


def search_cities(query: str, limit: int = 15) -> list[Place]:
    """Exact name or exact other name (e.g. Calcutta → Kolkata) > name prefix > partial match;
    ties go to the larger city, so a big city's old name beats a small town of that name."""
    q = query.strip().lower()
    if len(q) < 2:
        return []
    ranked = []
    for name, alts, place in _index():
        if name == q or q in alts:
            rank = 0
        elif name.startswith(q):
            rank = 1
        elif q in name or any(a.startswith(q) for a in alts):
            rank = 2
        else:
            continue
        ranked.append((rank, -place.population, place))
    ranked.sort(key=lambda r: (r[0], r[1]))
    return [p for _, _, p in ranked[:limit]]


def utc_offset_hours(tz_name: str, when_local: datetime, lon: float | None = None) -> float:
    """UTC offset in force at that local date and time (handles DST and historical changes).

    Before a region adopted standard time the tz database gives "LMT" — the local mean time of
    the zone's reference city (e.g. Kolkata, +5:53 for all of India before 1854). Births then
    were recorded in the birthplace's own local mean time, so with `lon` given we use lon / 15.
    """
    zone = ZoneInfo(tz_name)
    naive = when_local.replace(tzinfo=None)
    if lon is not None and zone.tzname(naive) == "LMT":
        return lon / 15
    return zone.utcoffset(naive).total_seconds() / 3600


def uses_local_mean_time(tz_name: str, when_local: datetime) -> bool:
    return ZoneInfo(tz_name).tzname(when_local.replace(tzinfo=None)) == "LMT"
