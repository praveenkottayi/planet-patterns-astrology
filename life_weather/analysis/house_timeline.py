"""Houses over time: a green/red score per house (H1–H12), with the reason for each date.

house score = HOUSE_DASA_SHARE × dasa focus + HOUSE_TRANSIT_SHARE × transit touch

- dasa focus:    the MD / AD lord's dasa weight (same weights, shares and fixed scale as the
                 Dasa lane) — counted for every house that lord RULES or SITS IN.
- transit touch: Jupiter, Saturn, Rahu, Ketu sitting in the house (full) or aspecting it
                 (ASPECT_WEIGHT), signed by nature; malefics count + in houses 3/6/11.
                 Jupiter/Saturn sitting also get the Ashtakavarga bindu term.
Houses are counted from the chosen reference (Lagna or Moon).
"""
from __future__ import annotations

import pandas as pd

from ..core.chart import house_between
from ..core.constants import SIGN_LORD
from . import assumptions as A
from .dasa_weight import dasa_scale, ruled_houses
from .gochara import ordinal
from .timeline import LifeWeather

SLOW = ("Jupiter", "Saturn", "Rahu", "Ketu")


def _nature(planet: str, house: int) -> float:
    n = A.NATURE[planet]
    return abs(n) if n < 0 and house in A.MALEFIC_GOOD_HOUSES else n


def _dasa_focus(lw: LifeWeather, ref_sign: int) -> dict[str, list[int]]:
    """Planet → houses it rules or sits in, counted from ref_sign."""
    out = {}
    for planet in lw.weights:
        sits = house_between(lw.chart.sign(planet), ref_sign)
        rules = ruled_houses(planet, ref_sign) if planet in SIGN_LORD else []
        out[planet] = sorted(set(rules) | {sits})
    return out


def house_scores_at(lw: LifeWeather, row, ref_sign: int, focus: dict[str, list[int]]):
    """(scores[1..12], reasons[1..12]) for one timeline row."""
    scores = {h: 0.0 for h in range(1, 13)}
    why: dict[int, list[str]] = {h: [] for h in range(1, 13)}

    # Dasa focus
    for lord, share, label in ((row.md, A.MD_SHARE, "MD"), (row.ad, A.AD_SHARE, "AD")):
        w = lw.weights[lord].total
        value = A.HOUSE_DASA_SHARE * A.LANE_RANGE * share * w / dasa_scale()
        for h in focus[lord]:
            scores[h] += value
            why[h].append(f"{label} {lord} ({w:+g}) rules/sits here {value:+.2f}")

    # Transit touch
    signs = {"Jupiter": row.jup_sign, "Saturn": row.sat_sign,
             "Rahu": row.rahu_sign, "Ketu": (row.rahu_sign + 6) % 12}
    bav = {"Jupiter": lw.bav_jupiter, "Saturn": lw.bav_saturn}
    for planet in SLOW:
        sign = signs[planet]
        h_sit = house_between(sign, ref_sign)
        base = _nature(planet, h_sit) * A.SIT_WEIGHT
        bindu = A.BINDU_WEIGHT * (bav[planet][sign] - A.BINDU_NEUTRAL) if planet in bav else 0.0
        value = A.HOUSE_TRANSIT_SHARE * (base + bindu)
        scores[h_sit] += value
        extra = f", {bav[planet][sign]} bindus" if planet in bav else ""
        why[h_sit].append(f"{planet} sits here{extra} {value:+.2f}")
        for n in A.ASPECTS[planet]:
            h_asp = (h_sit + n - 2) % 12 + 1
            value = A.HOUSE_TRANSIT_SHARE * _nature(planet, h_asp) * A.ASPECT_WEIGHT
            scores[h_asp] += value
            why[h_asp].append(f"{planet} aspects ({ordinal(n)}) {value:+.2f}")
    return scores, why


def house_timeline(lw: LifeWeather, ref: str = "Lagna") -> pd.DataFrame:
    """Columns: date, H1..H12 (raw), S1..S12 (3-month smoothed), why1..why12."""
    ref_sign = lw.chart.sign(ref)
    focus = _dasa_focus(lw, ref_sign)
    rows = []
    for r in lw.frame.itertuples():
        scores, why = house_scores_at(lw, r, ref_sign, focus)
        rows.append({"date": r.date,
                     **{f"H{h}": scores[h] for h in range(1, 13)},
                     **{f"why{h}": " · ".join(why[h]) or "nothing touching" for h in range(1, 13)}})
    df = pd.DataFrame(rows)
    for h in range(1, 13):
        df[f"S{h}"] = df[f"H{h}"].rolling(A.SMOOTH_SAMPLES, center=True, min_periods=1).mean()
    return df
