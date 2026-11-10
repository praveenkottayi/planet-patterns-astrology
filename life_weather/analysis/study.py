"""Does Life Weather match one person's own life? A blind, controlled comparison.

Inputs (entered by the person, ideally BEFORE looking at their chart):
  - year ratings, −2 … +2, overall and per life area
  - dated events, each good (+1) or hard (−1)

Every test asks the same question: does YOUR chart fit your ratings better than the charts of
people born on other dates? The ratings stay exactly as entered; only the chart changes. Random
charts share the same planetary cycles in different positions, so this is the fairest control.
Nothing is fitted — the model is used as it stands (its git commit is recorded with each run).

Tests: overall (yearly score vs overall rating), each life area (its house vs its rating),
two fixed hypotheses (Sade Sati years lower; good-Jupiter years higher) and dated events
(good in green, hard in red). p-values are Holm-corrected across all tests.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import swisseph as swe

from ..core.ashtakavarga import bav
from ..core.chart import Chart, house_between, natal_chart, sidereal_longitudes, sign_of
from ..core.constants import SIGN_LORD
from ..core.dasa import vimshottari
from . import assumptions as A
from .dasa_weight import dasa_scale, dasa_score, dasa_weights, ruled_houses
from .gochara import jupiter_score, nodes_score, saturn_score
from .timeline import MAHA_DASAS_COVERED, LifeWeather

AREAS = ["overall", "career", "money", "health", "relationships", "home"]
LIFE_AREAS = AREAS[1:]       # what the person rates; "overall" is computed from these
AREA_HOUSES = {"career": [10], "money": [2, 11], "health": [1], "relationships": [7],
               "home": [4]}
EVENT_CATEGORIES = ["career", "money", "health", "relationships", "family", "home", "other"]
MIN_YEARS = 10
MIN_EVENTS = 5
RANDOM_CHARTS = 500
STEP_DAYS = 10
SMOOTH_SAMPLES = 9          # ≈ 90 days at a 10-day step, like the app's 3-month average
ALPHA = 0.05
SLOW = ("Jupiter", "Saturn", "Rahu", "Ketu")


def with_computed_overall(ratings: pd.DataFrame) -> pd.DataFrame:
    """Overall = the mean of the life areas rated that year (NaN if none). Any typed overall
    value is ignored, so the overall test always reflects the per-area ratings."""
    out = ratings.copy()
    out["overall"] = out[LIFE_AREAS].astype(float).mean(axis=1, skipna=True)
    return out


# ─── Sample dates (the same for every chart) ──────────────────────────────────

@dataclass(frozen=True)
class TransitTable:
    jd: np.ndarray
    year: np.ndarray
    signs: dict[str, np.ndarray]          # Jupiter / Saturn / Rahu / Ketu → sign per sample


def transit_table(first_year: int, last_year: int, node: str = "mean") -> TransitTable:
    jds, years = [], []
    for y in range(first_year, last_year + 1):
        d = date(y, 1, 1)
        while d.year == y:
            jds.append(swe.julday(d.year, d.month, d.day, A.SAMPLE_HOUR_UT))
            years.append(y)
            d += timedelta(days=STEP_DAYS)
    lons = [sidereal_longitudes(jd, node) for jd in jds]
    signs = {p: np.array([sign_of(x[p]) for x in lons]) for p in SLOW}
    return TransitTable(np.array(jds), np.array(years), signs)


# ─── Fast scorers (same formulas as timeline.py and house_timeline.py) ────────

def _dasa_index(chart: Chart, tt: TransitTable):
    periods = vimshottari(chart.longitudes["Moon"], chart.jd, n_maha=MAHA_DASAS_COVERED)
    idx = np.searchsorted(np.array([p.start_jd for p in periods]), tt.jd, side="right") - 1
    return periods, np.clip(idx, 0, None), tt.jd >= chart.jd


def chart_scores(chart: Chart, tt: TransitTable) -> np.ndarray:
    """Overall (unsmoothed) score per sample date — the timeline's formula; NaN before birth."""
    weights = dasa_weights(chart)
    periods, idx, born = _dasa_index(chart, tt)
    dasa = np.array([dasa_score(weights[p.md], weights[p.ad]) for p in periods])[idx]
    moon = chart.sign("Moon")
    bj, bs = bav("Jupiter", chart), bav("Saturn", chart)
    jup = np.array([jupiter_score(s, moon, bj)[0] for s in range(12)])[tt.signs["Jupiter"]]
    sat = np.array([saturn_score(s, moon, bs)[0] for s in range(12)])[tt.signs["Saturn"]]
    nodes = np.array([nodes_score(s, moon)[0] for s in range(12)])[tt.signs["Rahu"]]
    score = A.DASA_SHARE * dasa + A.TRANSIT_SHARE * (jup + sat + nodes)
    return np.where(born, score, np.nan)


def _nature(planet: str, house: int) -> float:
    n = A.NATURE[planet]
    return abs(n) if n < 0 and house in A.MALEFIC_GOOD_HOUSES else n


def house_scores(chart: Chart, tt: TransitTable) -> np.ndarray:
    """(samples × 12) house scores from the Lagna — house_timeline's formula, vectorised."""
    lagna = chart.sign("Lagna")
    weights = dasa_weights(chart)
    focus = {}
    for p in weights:
        rules = ruled_houses(p, lagna) if p in SIGN_LORD else []
        focus[p] = set(rules) | {house_between(chart.sign(p), lagna)}

    periods, idx, born = _dasa_index(chart, tt)
    per_period = np.zeros((len(periods), 12))
    for i, p in enumerate(periods):
        for lord, share in ((p.md, A.MD_SHARE), (p.ad, A.AD_SHARE)):
            value = A.HOUSE_DASA_SHARE * A.LANE_RANGE * share * weights[lord].total / dasa_scale()
            for h in focus[lord]:
                per_period[i, h - 1] += value
    out = per_period[idx]

    bavs = {"Jupiter": bav("Jupiter", chart), "Saturn": bav("Saturn", chart)}
    for planet in SLOW:
        table = np.zeros((12, 12))                      # sign → contribution to each house
        for s in range(12):
            h = house_between(s, lagna)
            bindu = (A.BINDU_WEIGHT * (bavs[planet][s] - A.BINDU_NEUTRAL)
                     if planet in bavs else 0.0)
            table[s, h - 1] += A.HOUSE_TRANSIT_SHARE * (_nature(planet, h) * A.SIT_WEIGHT + bindu)
            for n in A.ASPECTS[planet]:
                ha = (h + n - 2) % 12 + 1
                table[s, ha - 1] += A.HOUSE_TRANSIT_SHARE * _nature(planet, ha) * A.ASPECT_WEIGHT
        out = out + table[tt.signs[planet]]
    return np.where(born[:, None], out, np.nan)


# ─── Everything a test needs from one chart ───────────────────────────────────

@dataclass(frozen=True)
class Features:
    overall: pd.Series                  # year → mean score
    houses: pd.DataFrame                # year → 12 house means (columns 1..12)
    sade: pd.Series                     # year → Saturn 12/1/2 from Moon for most of the year
    good_jupiter: pd.Series             # year → Jupiter 2/5/7/9/11 from Moon for most of the year
    smoothed: np.ndarray                # ~3-month average per sample date (for events)


def features(chart: Chart, tt: TransitTable) -> Features:
    score = chart_scores(chart, tt)
    moon = chart.sign("Moon")
    from_moon = np.array([house_between(s, moon) for s in range(12)])
    by_year = pd.Series(tt.year)
    return Features(
        overall=pd.Series(score).groupby(by_year).mean(),
        houses=pd.DataFrame(house_scores(chart, tt), columns=range(1, 13)).groupby(by_year).mean(),
        sade=pd.Series(np.isin(from_moon[tt.signs["Saturn"]], (12, 1, 2)))
        .groupby(by_year).mean() >= 0.5,
        good_jupiter=pd.Series(np.isin(from_moon[tt.signs["Jupiter"]], (2, 5, 7, 9, 11)))
        .groupby(by_year).mean() >= 0.5,
        smoothed=pd.Series(score).rolling(SMOOTH_SAMPLES, center=True, min_periods=1).mean()
        .to_numpy(),
    )


# ─── Statistics ───────────────────────────────────────────────────────────────

def spearman(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = ~(np.isnan(a) | np.isnan(b))
    ra, rb = pd.Series(a[ok]).rank().to_numpy(), pd.Series(b[ok]).rank().to_numpy()
    if len(ra) < 3 or ra.std() == 0 or rb.std() == 0:
        return np.nan
    return float(np.corrcoef(ra, rb)[0, 1])


def holm(pvalues: list[float]) -> list[float]:
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    adjusted, running = [0.0] * len(pvalues), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvalues) - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


# ─── Tests ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Test:
    name: str
    question: str
    n: int
    stat: object          # Features → float, higher = better match; NaN if not computable
    describe: object      # observed value → words


@dataclass(frozen=True)
class TestResult:
    name: str
    question: str
    result: str           # the observed effect in words
    n: int
    beats: float          # share of random charts your chart beats on this test
    p: float              # (1 + random charts ≥ yours) / (1 + random charts)
    p_adjusted: float = 1.0

    @property
    def verdict(self) -> str:
        if self.p_adjusted < ALPHA:
            return "signal beyond chance"
        if self.p < ALPHA:
            return "weak — not significant once corrected for the number of tests"
        return "not distinguishable from chance"


@dataclass(frozen=True)
class StudyReport:
    tests: list[TestResult]
    jitter: dict[int, float]            # birth-time offset (min) → overall ρ
    yearly: pd.DataFrame                # year, model, overall rating
    random_charts: int


def build_tests(ratings: pd.DataFrame, events: pd.DataFrame, tt: TransitTable) -> list[Test]:
    tests: list[Test] = []
    r = ratings.set_index("year")
    sampled = set(tt.year)
    overall = r["overall"].dropna()
    ys = [y for y in overall.index if y in sampled]
    if len(ys) >= MIN_YEARS:
        vals = overall[ys].to_numpy()
        tests.append(Test("Overall", "Do the model's better years match your better years?",
                          len(ys), lambda f, ys=ys, v=vals: spearman(f.overall[ys], v),
                          lambda x: f"ρ = {x:+.2f}"))
        for name, attr, sign, question in (
                ("Sade Sati years", "sade", -1, "Are your Sade Sati years rated lower?"),
                ("Good-Jupiter years", "good_jupiter", +1,
                 "Are years with Jupiter 2/5/7/9/11 from your Moon rated higher?")):
            def stat(f, ys=ys, v=vals, attr=attr, sign=sign):
                flag = getattr(f, attr)[ys].to_numpy()
                if flag.all() or not flag.any():
                    return np.nan
                return sign * (v[flag].mean() - v[~flag].mean())
            tests.append(Test(name, question, len(ys), stat,
                              lambda x, sign=sign: f"{sign * x:+.2f} rating points difference"))
    for area, houses in AREA_HOUSES.items():
        col = r[area].dropna()
        ys_a = [y for y in col.index if y in sampled]
        if len(ys_a) >= MIN_YEARS:
            tests.append(Test(
                area.capitalize(),
                f"Does the {' + '.join(f'H{h}' for h in houses)} score match your {area} ratings?",
                len(ys_a),
                lambda f, ys=ys_a, v=col[ys_a].to_numpy(), hs=houses:
                    spearman(f.houses.loc[ys, hs].mean(axis=1), v),
                lambda x: f"ρ = {x:+.2f}"))
    ev = events.dropna(subset=["date", "valence"])
    if len(ev) >= MIN_EVENTS:
        idx = np.array([int(np.abs(tt.jd - swe.julday(d.year, d.month, d.day, 12)).argmin())
                        for d in pd.to_datetime(ev["date"])])
        good = ev["valence"].to_numpy(float) > 0

        def stat(f, idx=idx, good=good):
            return float(((f.smoothed[idx] > 0) == good).mean())
        tests.append(Test("Events", "Do good events fall in green stretches and hard ones in red?",
                          len(ev), stat, lambda x, n=len(ev): f"{round(x * n)}/{n} match"))
    return tests


def random_charts(birth, n: int, node: str, seed: int = 0) -> list[Chart]:
    """Charts for random birth moments in the 40 years before the real birth, same place."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        when = birth.when_local - timedelta(days=float(rng.uniform(0, 40 * 365.25)))
        when = when.replace(hour=int(rng.integers(0, 24)), minute=int(rng.integers(0, 60)))
        out.append(natal_chart(replace(birth, when_local=when), node))
    return out


def run_study(lw: LifeWeather, ratings: pd.DataFrame, events: pd.DataFrame,
              n_random: int = RANDOM_CHARTS, seed: int = 0) -> StudyReport:
    ratings = with_computed_overall(ratings)
    rated = ratings.dropna(subset=AREAS, how="all")
    if rated.empty:
        raise ValueError("no rated years yet")
    years = [int(y) for y in rated["year"]]
    years += [d.year for d in pd.to_datetime(events["date"].dropna())] if len(events) else []
    tt = transit_table(min(years), max(years), lw.node)
    tests = build_tests(ratings, events, tt)
    mine = features(lw.chart, tt)
    others = [features(c, tt) for c in random_charts(lw.birth, n_random, lw.node, seed)]

    results = []
    for t in tests:
        obs = t.stat(mine)
        null = np.array([t.stat(f) for f in others], dtype=float)
        null = null[~np.isnan(null)]
        if np.isnan(obs) or not len(null):
            continue
        results.append(TestResult(t.name, t.question, t.describe(obs), t.n,
                                  float((null < obs).mean()),
                                  (1 + int((null >= obs).sum())) / (1 + len(null))))
    adjusted = holm([x.p for x in results])
    results = [replace(x, p_adjusted=a) for x, a in zip(results, adjusted)]

    jitter = {}
    overall_test = next((t for t in tests if t.name == "Overall"), None)
    if overall_test:
        for minutes in (-30, -20, -10, 0, 10, 20, 30):
            moved = natal_chart(replace(lw.birth, when_local=lw.birth.when_local
                                        + timedelta(minutes=minutes)), lw.node)
            jitter[minutes] = overall_test.stat(features(moved, tt))

    table = pd.DataFrame({"year": mine.overall.index, "model": mine.overall.to_numpy()}).merge(
        ratings[["year", "overall"]], on="year", how="left")
    return StudyReport(results, jitter, table, n_random)


# ─── Run log ──────────────────────────────────────────────────────────────────

def model_version() -> str:
    """Git commit of the code being tested (the 'frozen' model), if available."""
    root = Path(__file__).resolve().parents[2]
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "life_weather"], cwd=root,
                               capture_output=True, text=True).stdout.strip()
        return sha + (" + uncommitted changes" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def now_stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")
