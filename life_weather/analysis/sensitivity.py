"""How much the chart depends on the exact birth time."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta

from ..core.chart import Birth, natal_chart
from ..core.dasa import maha_dasas, vimshottari

SEARCH_MINUTES = 240


@dataclass(frozen=True)
class BirthTimeSensitivity:
    lagna_earlier: int | None    # minutes earlier at which Lagna changes sign (None = beyond search)
    lagna_later: int | None
    dasa_days_per_10min: int     # how far Maha-dasa boundaries move for a 10-minute later birth


def _lagna_sign(birth: Birth, minutes: int, node: str) -> int:
    shifted = replace(birth, when_local=birth.when_local + timedelta(minutes=minutes))
    return natal_chart(shifted, node).sign("Lagna")


def _first_change(birth: Birth, direction: int, node: str) -> int | None:
    base = _lagna_sign(birth, 0, node)
    for m in range(1, SEARCH_MINUTES + 1):
        if _lagna_sign(birth, direction * m, node) != base:
            return m
    return None


def birth_time_sensitivity(birth: Birth, node: str = "mean") -> BirthTimeSensitivity:
    def first_md_end(b: Birth):
        c = natal_chart(b, node)
        return maha_dasas(vimshottari(c.longitudes["Moon"], c.jd))[0].end

    later = replace(birth, when_local=birth.when_local + timedelta(minutes=10))
    return BirthTimeSensitivity(
        lagna_earlier=_first_change(birth, -1, node),
        lagna_later=_first_change(birth, +1, node),
        dasa_days_per_10min=abs((first_md_end(later) - first_md_end(birth)).days),
    )
