"""Slow-planet transit scores, by house counted from the natal Moon. Each returns (score, reason)."""
from __future__ import annotations

from ..core.chart import house_between
from ..core.constants import SIGNS_ML
from . import assumptions as A

SATURN_NAMES = {12: "Sade Sati", 1: "Sade Sati", 2: "Sade Sati",
                8: "Ashtama Shani", 4: "Ardhashtama Shani"}


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _bindu_term(bindus: int) -> float:
    return A.BINDU_WEIGHT * (bindus - A.BINDU_NEUTRAL)


def jupiter_score(sign: int, moon_sign: int, bav_jupiter: list[int]) -> tuple[float, str]:
    h = house_between(sign, moon_sign)
    base = A.JUPITER_HOUSE.get(h, A.JUPITER_ELSE)
    b = bav_jupiter[sign]
    score = base + _bindu_term(b)
    return score, f"Jupiter {ordinal(h)} from Moon in {SIGNS_ML[sign]} ({base:+g}), {b} bindus → {score:+.2f}"


def saturn_score(sign: int, moon_sign: int, bav_saturn: list[int]) -> tuple[float, str]:
    h = house_between(sign, moon_sign)
    base = A.SATURN_HOUSE.get(h, A.SATURN_ELSE)
    b = bav_saturn[sign]
    score = base + _bindu_term(b)
    name = f" — {SATURN_NAMES[h]}" if h in SATURN_NAMES else ""
    return score, f"Saturn {ordinal(h)} from Moon{name} ({base:+g}), {b} bindus → {score:+.2f}"


def nodes_score(rahu_sign: int, moon_sign: int) -> tuple[float, str]:
    ketu_sign = (rahu_sign + 6) % 12
    hr = house_between(rahu_sign, moon_sign)
    hk = house_between(ketu_sign, moon_sign)
    sr = A.NODE_HOUSE.get(hr, A.NODE_ELSE)
    sk = A.NODE_HOUSE.get(hk, A.NODE_ELSE)
    score = (sr + sk) / 2
    return score, f"Rahu {ordinal(hr)} ({sr:+g}) / Ketu {ordinal(hk)} ({sk:+g}) from Moon → {score:+.2f}"
