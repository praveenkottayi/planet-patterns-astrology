"""Independent accuracy check of the life_weather engine.

Recomputes positions with astropy (no Swiss Ephemeris), the ascendant from the textbook
formula, Lahiri ayanamsa from its 1956 definition + IAU precession, the mean node from
Meeus, and Vimshottari dasa by hand — then compares with the app.

    uv run --with astropy python tools/crosscheck.py

Uses your people from .env (gitignored), the public examples, and fixed transit dates.
Exits non-zero if any position differs by more than TOL_DEG or any sign/dasa disagrees.
"""
from __future__ import annotations

import math
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import astropy.units as u
import erfa
from astropy.coordinates import GeocentricTrueEcliptic, get_body, solar_system_ephemeris
from astropy.time import Time

from life_weather.core.chart import Birth, natal_chart, sidereal_longitudes, to_jd
from life_weather.core.dasa import maha_dasas, vimshottari
from life_weather.profiles import load_profiles

REPO = Path(__file__).resolve().parents[1]

warnings.filterwarnings("ignore", module="erfa")
solar_system_ephemeris.set("builtin")
TOL_DEG = 0.05
TRANSITS = ["2026-11-01T12:00:00", "2035-06-15T12:00:00"]   # IST

# ─── Independent astronomy ────────────────────────────────────────────────────

def _T(t: Time) -> float:
    return (t.tt.jd - 2451545.0) / 36525


def lahiri(t: Time) -> float:
    p_a = lambda tc: (5028.796195 * tc + 1.1054348 * tc ** 2) / 3600  # noqa: E731
    t0 = (2435553.5 - 2451545.0) / 36525                               # 1956-03-21
    return 23 + 15 / 60 + 0.658 / 3600 + p_a(_T(t)) - p_a(t0)


def mean_node(t: Time) -> float:   # Meeus 47.7
    tc = _T(t)
    return (125.0445479 - 1934.1362891 * tc + 0.0020754 * tc ** 2
            + tc ** 3 / 467441 - tc ** 4 / 60616000) % 360


def ascendant(t: Time, lat: float, lon: float) -> float:
    ramc = t.sidereal_time("apparent", longitude=lon * u.deg).deg
    eps = math.degrees(erfa.obl06(t.tt.jd1, t.tt.jd2) + erfa.nut06a(t.tt.jd1, t.tt.jd2)[1])
    r, e, f = map(math.radians, (ramc, eps, lat))
    return math.degrees(math.atan2(math.cos(r),
                                   -(math.sin(r) * math.cos(e) + math.tan(f) * math.sin(e)))) % 360


def independent(when_local: datetime, tz: float, lat=None, lon=None) -> dict[str, float]:
    t = Time(when_local.isoformat()) - tz * u.hour
    ay = lahiri(t)
    out = {b.capitalize(): (get_body(b, t).transform_to(GeocentricTrueEcliptic(equinox=t))
                            .lon.deg - ay) % 360
           for b in ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn")}
    out["Rahu"] = (mean_node(t) - ay) % 360
    if lat is not None:
        out["Lagna"] = (ascendant(t, lat, lon) - ay) % 360
    return out


# ─── Compare ──────────────────────────────────────────────────────────────────

def main() -> int:
    failures = 0
    people = [p.birth for p in load_profiles()]
    cases = [(b.name, b.when_local, b.tz_hours, b.lat, b.lon) for b in people]
    cases += [(f"transit {w[:10]}", datetime.fromisoformat(w), 5.5, None, None) for w in TRANSITS]

    for name, when, tz, lat, lon in cases:
        ind = independent(when, tz, lat, lon)
        app = (natal_chart(Birth(name, when, tz, lat, lon)).longitudes if lat is not None
               else sidereal_longitudes(to_jd(when, tz)))
        print(f"\n{name}")
        for body, v in ind.items():
            d = (app[body] - v + 180) % 360 - 180
            bad = abs(d) > TOL_DEG or int(app[body] // 30) != int(v // 30)
            failures += bad
            print(f"  {body:8} app {app[body]:8.3f}  independent {v:8.3f}  Δ {d:+.3f}°"
                  f"{'  ✗' if bad else ''}")

    span, years = 360 / 27, [("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10), ("Mars", 7),
                             ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17)]
    for b in people:
        moon = independent(b.when_local, b.tz_hours)["Moon"]
        i, frac = int(moon // span) % 9, (moon % span) / span
        end = b.when_local + timedelta(days=(1 - frac) * years[i][1] * 365.25)
        c = natal_chart(b)
        app = maha_dasas(vimshottari(c.longitudes["Moon"], c.jd))
        print(f"\nDasa {b.name}")
        for k, a in enumerate(app[:5]):
            lord = years[(i + k) % 9][0]
            if k:
                end += timedelta(days=years[(i + k) % 9][1] * 365.25)
            bad = a.md != lord or abs((a.end - end.date()).days) > 5
            failures += bad
            print(f"  {lord:8} ends by hand {end.date()}  app {a.end}{'  ✗' if bad else ''}")

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
