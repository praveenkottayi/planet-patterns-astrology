"""Per-planet dasa weight computed from the natal chart: lordship + dignity + placement."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..core.chart import Chart, house_between
from ..core.constants import GRAHAS, NODES, SIGN_LORD
from ..core.dignity import dignity, neecha_bhanga
from . import assumptions as A


DIGNITY_LABEL = {"exalted": "exalted", "own": "own sign", "debilitated": "debilitated",
                 "debilitated_cancelled": "debilitated, neecha bhanga"}


@dataclass(frozen=True)
class PlanetWeight:
    planet: str
    lordship: float
    dignity: float
    placement: float
    reasons: tuple[str, ...]

    @property
    def total(self) -> float:
        return self.lordship + self.dignity + self.placement


# ─── Components ───────────────────────────────────────────────────────────────

def ruled_houses(planet: str, lagna_sign: int) -> list[int]:
    return sorted(house_between(s, lagna_sign) for s, lord in enumerate(SIGN_LORD) if lord == planet)


def lordship_score(planet: str, lagna_sign: int) -> tuple[float, str]:
    houses = ruled_houses(planet, lagna_sign)
    score = 0.0
    for h in houses:
        if h == 8 and A.EIGHTH_LORD_EXEMPT_IF_LAGNA_LORD and 1 in houses:
            continue
        score += A.LORDSHIP.get(h, 0.0)
    return score, f"rules H{'+H'.join(map(str, houses))}"


def placement_score(house: int) -> float:
    return A.PLACEMENT.get(house, 0.0)


def _dignity_key(chart: Chart, planet: str) -> str:
    d = dignity(planet, chart.sign(planet))
    if d == "debilitated" and neecha_bhanga(chart, planet):
        return "debilitated_cancelled"
    return d


# ─── Weight per planet ────────────────────────────────────────────────────────

def planet_weight(chart: Chart, planet: str) -> PlanetWeight:
    lagna = chart.sign("Lagna")
    house = chart.house(planet)
    place = placement_score(house)

    if planet in NODES:
        dispositor = SIGN_LORD[chart.sign(planet)]
        lord, lord_why = lordship_score(dispositor, lagna)
        reasons = (f"via dispositor {dispositor} ({lord_why}) {lord:+g}",
                   f"in H{house} {place:+g}")
        return PlanetWeight(planet, lord, 0.0, place, reasons)

    lord, lord_why = lordship_score(planet, lagna)
    key = _dignity_key(chart, planet)
    dig = A.DIGNITY[key]
    reasons = [f"{lord_why} {lord:+g}"]
    if key:
        reasons.append(f"{DIGNITY_LABEL[key]} {dig:+g}")
    reasons.append(f"in H{house} {place:+g}")
    return PlanetWeight(planet, lord, dig, place, tuple(reasons))


def dasa_weights(chart: Chart) -> dict[str, PlanetWeight]:
    return {p: planet_weight(chart, p) for p in GRAHAS + NODES}


# ─── Fixed scale ──────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def dasa_scale() -> float:
    """Largest |weight| the rules can give any planet in any chart (all Lagnas × all signs)."""
    best = 0.0
    for lagna in range(12):
        for sign in range(12):
            place = placement_score(house_between(sign, lagna))
            for p in GRAHAS:
                lord, _ = lordship_score(p, lagna)
                dig = A.DIGNITY[dignity(p, sign)]       # uncancelled debilitation = worst case
                best = max(best, abs(lord + dig + place))
            node_lord, _ = lordship_score(SIGN_LORD[sign], lagna)
            best = max(best, abs(node_lord + place))
    return best


def dasa_score(md: PlanetWeight, ad: PlanetWeight) -> float:
    """Dasa lane value in [−LANE_RANGE, +LANE_RANGE] on the fixed scale."""
    return A.LANE_RANGE * (A.MD_SHARE * md.total + A.AD_SHARE * ad.total) / dasa_scale()
