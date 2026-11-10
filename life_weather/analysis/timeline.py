"""Life Weather timeline: one row per sample date, every lane with its reason."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import swisseph as swe

from ..core.ashtakavarga import bav
from ..core.chart import Birth, Chart, natal_chart, sign_of, sidereal_longitudes
from ..core.dasa import DasaPeriod, maha_dasas, period_at, vimshottari
from . import assumptions as A
from .dasa_weight import PlanetWeight, dasa_score, dasa_weights
from .gochara import jupiter_score, nodes_score, saturn_score

LANES = ["dasa", "jupiter", "saturn", "nodes"]
TRANSIT_LANES = ["jupiter", "saturn", "nodes"]
MAHA_DASAS_COVERED = 20     # two full 120-year Vimshottari cycles, enough for any timeline


@dataclass
class LifeWeather:
    birth: Birth
    chart: Chart
    weights: dict[str, PlanetWeight]
    periods: list[DasaPeriod]
    frame: pd.DataFrame
    bav_jupiter: list[int]
    bav_saturn: list[int]
    node: str

    @property
    def maha_dasas(self) -> list[DasaPeriod]:
        return maha_dasas(self.periods)

    def on(self, d: date) -> dict:
        """All lanes and reasons for one exact date (not the nearest sample)."""
        jd = swe.julday(d.year, d.month, d.day, A.SAMPLE_HOUR_UT)
        return _score_at(jd, self.chart.sign("Moon"), self.weights, self.periods,
                         self.bav_jupiter, self.bav_saturn, self.node)


def _sample_dates(start: date, end: date) -> list[date]:
    return [start + timedelta(days=k) for k in range(0, (end - start).days + 1, A.SAMPLE_DAYS)]


def _score_at(jd: float, moon: int, weights: dict[str, PlanetWeight],
              periods: list[DasaPeriod], bav_jup: list[int], bav_sat: list[int],
              node: str) -> dict:
    """Every lane and its reason at one instant. The single source for the timeline AND
    the exact-date 'why' panel, so they can never disagree."""
    lons = sidereal_longitudes(jd, node)
    p = period_at(periods, jd)
    if p is None:
        raise ValueError("date outside the computed dasa periods")
    md, ad = weights[p.md], weights[p.ad]

    j, j_why = jupiter_score(sign_of(lons["Jupiter"]), moon, bav_jup)
    s, s_why = saturn_score(sign_of(lons["Saturn"]), moon, bav_sat)
    n, n_why = nodes_score(sign_of(lons["Rahu"]), moon)
    ds = dasa_score(md, ad)
    return {
        "md": p.md, "ad": p.ad,
        "jup_sign": sign_of(lons["Jupiter"]), "sat_sign": sign_of(lons["Saturn"]),
        "rahu_sign": sign_of(lons["Rahu"]),
        "dasa": ds, "jupiter": j, "saturn": s, "nodes": n,
        "why_dasa": f"{p.md}/{p.ad} (MD {md.total:+g}, AD {ad.total:+g}) → {ds:+.2f}",
        "why_jupiter": j_why, "why_saturn": s_why, "why_nodes": n_why,
    }


def score_of(row: dict, factors: tuple[str, ...] = tuple(LANES)) -> float:
    """Overall (unsmoothed) score of one row — same formula as combine()."""
    transit = sum(row[lane] for lane in TRANSIT_LANES if lane in factors)
    dasa = row["dasa"] if "dasa" in factors else 0.0
    return A.DASA_SHARE * dasa + A.TRANSIT_SHARE * transit


def build(birth: Birth, end_year: int = 2045, node: str = "mean") -> LifeWeather:
    chart = natal_chart(birth, node)
    moon = chart.sign("Moon")
    weights = dasa_weights(chart)
    periods = vimshottari(chart.longitudes["Moon"], chart.jd, n_maha=MAHA_DASAS_COVERED)
    bav_jup, bav_sat = bav("Jupiter", chart), bav("Saturn", chart)

    rows = []
    for d in _sample_dates(birth.when_local.date(), date(end_year, 12, 31)):
        jd = swe.julday(d.year, d.month, d.day, A.SAMPLE_HOUR_UT)
        rows.append({"date": d, **_score_at(jd, moon, weights, periods, bav_jup, bav_sat, node)})

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return LifeWeather(birth, chart, weights, periods, combine(df), bav_jup, bav_sat, node)


def combine(df: pd.DataFrame, factors: tuple[str, ...] = tuple(LANES)) -> pd.DataFrame:
    """(Re)compute the overall score from the chosen lanes. Unchosen lanes count as 0 —
    the formula is not rebalanced, so dropping a factor visibly changes the balance."""
    df = df.copy()

    def use(lane):
        return df[lane] if lane in factors else 0.0

    df["transit"] = sum(use(lane) for lane in TRANSIT_LANES)
    df["score"] = A.DASA_SHARE * use("dasa") + A.TRANSIT_SHARE * df["transit"]
    df["smoothed"] = df["score"].rolling(A.SMOOTH_SAMPLES, center=True, min_periods=1).mean()
    return df
