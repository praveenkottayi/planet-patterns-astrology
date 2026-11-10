"""Sign dignity and neecha bhanga (cancellation of debilitation)."""
from __future__ import annotations

from .chart import Chart
from .constants import DEBIL, EXALT, KENDRAS, OWN, SIGN_LORD


def dignity(planet: str, sign: int) -> str:
    """'exalted' | 'debilitated' | 'own' | '' (nodes always '')."""
    if planet not in EXALT:
        return ""
    if sign == EXALT[planet]:
        return "exalted"
    if sign == DEBIL[planet]:
        return "debilitated"
    if sign in OWN[planet]:
        return "own"
    return ""


def neecha_bhanga(chart: Chart, planet: str) -> list[str]:
    """Reasons the planet's debilitation is cancelled; empty list = not cancelled.

    Rules (any one is enough):
      1. lord of the debilitation sign is in a kendra from Lagna or Moon
      2. lord of the exaltation sign is in a kendra from Lagna or Moon
      3. lord of the debilitation sign is conjunct (same sign as) the planet

    When the lord in question IS the Moon (Mars debilitated in Karkidakam, Jupiter in
    Makaram), "in a kendra from the Moon" is skipped: the Moon is trivially in the 1st
    from itself, which would cancel every such debilitation automatically.
    """
    sign = chart.sign(planet)
    if dignity(planet, sign) != "debilitated":
        return []

    debil_lord = SIGN_LORD[sign]
    exalt_lord = SIGN_LORD[EXALT[planet]]
    reasons = []
    for role, lord in (("debilitation-sign lord", debil_lord),
                       ("exaltation-sign lord", exalt_lord)):
        for ref in ("Lagna", "Moon"):
            if lord == ref:
                continue
            h = chart.house(lord, ref)
            if h in KENDRAS:
                reasons.append(f"{lord} ({role}) in house {h} from {ref}")
    if debil_lord != planet and chart.sign(debil_lord) == sign:
        reasons.append(f"{debil_lord} (debilitation-sign lord) conjunct {planet}")
    return reasons
