"""Sidereal (Lahiri) positions from the Swiss Ephemeris, and whole-sign houses."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import swisseph as swe

from .constants import NAK_SPAN, NAKSHATRAS, NODE_IDS, PLANET_IDS, SIGNS_ML

FLAGS = swe.FLG_SIDEREAL


@dataclass(frozen=True)
class Birth:
    name: str
    when_local: datetime
    tz_hours: float       # fixed UTC offset at birth, e.g. 5.5 for IST
    lat: float
    lon: float
    place: str = ""       # display label only; never used in calculations


# ─── Time helpers ─────────────────────────────────────────────────────────────

def to_jd(when_local: datetime, tz_hours: float) -> float:
    hour = when_local.hour + when_local.minute / 60 + when_local.second / 3600
    return swe.julday(when_local.year, when_local.month, when_local.day, hour - tz_hours)


def jd_to_date(jd: float) -> date:
    y, m, d, _ = swe.revjul(jd)
    return date(y, m, d)


# ─── Positions ────────────────────────────────────────────────────────────────

def sidereal_longitudes(jd: float, node: str = "mean") -> dict[str, float]:
    """Sidereal longitude (0–360°) of the seven grahas plus Rahu and Ketu."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    out = {p: swe.calc_ut(jd, pid, FLAGS)[0][0] for p, pid in PLANET_IDS.items()}
    out["Rahu"] = swe.calc_ut(jd, NODE_IDS[node], FLAGS)[0][0]
    out["Ketu"] = (out["Rahu"] + 180) % 360
    return out


def retrograde(jd: float) -> dict[str, bool]:
    """Retrograde flag for the five true planets. Nodes are left out: mean nodes always move backwards."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    return {p: swe.calc_ut(jd, PLANET_IDS[p], FLAGS | swe.FLG_SPEED)[0][3] < 0
            for p in ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")}


def sign_of(longitude: float) -> int:
    return int(longitude // 30) % 12


def house_between(sign: int, ref_sign: int) -> int:
    """Whole-sign house (1–12) of `sign` counted from `ref_sign`."""
    return (sign - ref_sign) % 12 + 1


@dataclass(frozen=True)
class Chart:
    jd: float
    longitudes: dict[str, float]   # grahas, nodes and "Lagna"
    ayanamsa: float
    node: str

    def sign(self, body: str) -> int:
        return sign_of(self.longitudes[body])

    def deg_in_sign(self, body: str) -> float:
        return self.longitudes[body] % 30

    def house(self, body: str, ref: str = "Lagna") -> int:
        return house_between(self.sign(body), self.sign(ref))

    def nakshatra(self, body: str = "Moon") -> tuple[str, int]:
        lon = self.longitudes[body]
        idx = int(lon // NAK_SPAN)
        pada = int((lon % NAK_SPAN) // (NAK_SPAN / 4)) + 1
        return NAKSHATRAS[idx], pada

    def describe(self, body: str) -> str:
        return f"{SIGNS_ML[self.sign(body)]} {self.deg_in_sign(body):.1f}°"


def natal_chart(birth: Birth, node: str = "mean") -> Chart:
    jd = to_jd(birth.when_local, birth.tz_hours)
    lons = sidereal_longitudes(jd, node)
    lons["Lagna"] = swe.houses_ex(jd, birth.lat, birth.lon, b"W", FLAGS)[1][0]
    return Chart(jd=jd, longitudes=lons, ayanamsa=swe.get_ayanamsa_ut(jd), node=node)
