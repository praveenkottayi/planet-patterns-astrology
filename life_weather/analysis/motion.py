"""Planet motion over a time window, and exact transit events within it.

Events (all times found by bisection to within ~1 minute, not by sampling):
- ingress    a planet enters a new sign
- station    a planet turns retrograde or direct (not for the Sun, Moon or the mean nodes)
- contact    a slow planet passes over a natal point (Moon, Lagna) or its own natal position
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd
import swisseph as swe

from ..core.chart import Chart, house_between, sign_of
from ..core.constants import NODE_IDS, PLANET_IDS, SIGNS_ML

SLOW = ("Jupiter", "Saturn", "Rahu", "Ketu")
STATION_PLANETS = ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")
NATAL_POINTS = ("Moon", "Lagna")
BISECT_STEPS = 18                 # 1 day / 2^18 ≈ 0.3 s


def _jd(when_local: datetime, tz: float) -> float:
    h = when_local.hour + when_local.minute / 60 + when_local.second / 3600
    return swe.julday(when_local.year, when_local.month, when_local.day, h - tz)


def _local(jd: float, tz: float) -> datetime:
    y, m, d, h = swe.revjul(jd + tz / 24)
    return datetime(y, m, d) + timedelta(hours=h)


def position(jd: float, body: str, node: str = "mean") -> tuple[float, float]:
    """(sidereal longitude, speed °/day)."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    if body in ("Rahu", "Ketu"):
        lon, _, _, speed, *_ = swe.calc_ut(jd, NODE_IDS[node], swe.FLG_SIDEREAL | swe.FLG_SPEED)[0]
        return ((lon + 180) % 360 if body == "Ketu" else lon), speed
    lon, _, _, speed, *_ = swe.calc_ut(jd, PLANET_IDS[body], swe.FLG_SIDEREAL | swe.FLG_SPEED)[0]
    return lon, speed


def _gap(a: float, b: float) -> float:
    """Signed angular gap a − b in (−180, 180]."""
    return (a - b + 180) % 360 - 180


def _bisect(f, lo: float, hi: float) -> float:
    """f changes truth value between lo and hi; return the switch point."""
    f_lo = f(lo)
    for _ in range(BISECT_STEPS):
        mid = (lo + hi) / 2
        if f(mid) == f_lo:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ─── Series for the graph ─────────────────────────────────────────────────────

def series(start: datetime, end: datetime, tz: float, bodies: list[str], node: str = "mean",
           step_days: float | None = None) -> pd.DataFrame:
    """Columns: date, body, lon, retro. Step defaults to ~600 samples per body."""
    jd0, jd1 = _jd(start, tz), _jd(end, tz)
    step = step_days or max((jd1 - jd0) / 600, 0.25)
    rows = []
    jd = jd0
    while jd <= jd1:
        when = _local(jd, tz)
        for b in bodies:
            lon, speed = position(jd, b, node)
            rows.append((when, b, lon, speed < 0 and b in STATION_PLANETS))
        jd += step
    return pd.DataFrame(rows, columns=["date", "body", "lon", "retro"])


# ─── Events ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Event:
    when: datetime          # local time (birth time zone)
    planet: str
    kind: str               # ingress | station | contact
    text: str
    sign: int
    house: int              # from Lagna
    moon_house: int


def events(chart: Chart, start: datetime, end: datetime, tz: float, planets: list[str],
           node: str = "mean") -> list[Event]:
    jd0, jd1 = _jd(start, tz), _jd(end, tz)
    lagna, moon = chart.sign("Lagna"), chart.sign("Moon")
    out: list[Event] = []

    def add(jd: float, planet: str, kind: str, text: str, sign: int | None = None) -> None:
        s = sign_of(position(jd, planet, node)[0]) if sign is None else sign
        out.append(Event(_local(jd, tz), planet, kind, text, s,
                         house_between(s, lagna), house_between(s, moon)))

    for planet in planets:
        targets = []
        if planet in SLOW:
            targets = [(p, chart.longitudes[p]) for p in NATAL_POINTS]
            if planet not in ("Rahu", "Ketu"):
                targets.append(("its own birth position", chart.longitudes[planet]))
        jd = jd0
        prev_lon, prev_speed = position(jd, planet, node)
        while jd < jd1:
            nxt = min(jd + 1, jd1)
            lon, speed = position(nxt, planet, node)

            if sign_of(lon) != sign_of(prev_lon):
                t = _bisect(lambda x: sign_of(position(x, planet, node)[0]), jd, nxt)
                add(t, planet, "ingress", f"{planet} enters {SIGNS_ML[sign_of(lon)]}", sign_of(lon))

            if planet in STATION_PLANETS and (speed < 0) != (prev_speed < 0):
                t = _bisect(lambda x: position(x, planet, node)[1] < 0, jd, nxt)
                add(t, planet, "station",
                    f"{planet} turns {'retrograde' if speed < 0 else 'direct'}")

            for name, natal_lon in targets:
                a, b = _gap(prev_lon, natal_lon), _gap(lon, natal_lon)
                if (a < 0) != (b < 0) and abs(a - b) < 90:      # crossed, not wrapped
                    t = _bisect(lambda x: _gap(position(x, planet, node)[0], natal_lon) < 0,
                                jd, nxt)
                    what = name if name.startswith("its") else f"your birth {name}"
                    add(t, planet, "contact", f"{planet} passes over {what}")

            jd, prev_lon, prev_speed = nxt, lon, speed
    return sorted(out, key=lambda e: e.when)
