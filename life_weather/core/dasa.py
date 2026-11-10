"""Vimshottari dasa: Maha-dasa (MD) and Antardasa (AD) periods from the natal Moon."""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date

from .chart import jd_to_date
from .constants import DASA_SEQUENCE, DASA_TOTAL_YEARS, NAK_SPAN, YEAR_DAYS


@dataclass(frozen=True)
class DasaPeriod:
    md: str
    ad: str
    start_jd: float
    end_jd: float

    @property
    def start(self) -> date:
        return jd_to_date(self.start_jd)

    @property
    def end(self) -> date:
        return jd_to_date(self.end_jd)


def vimshottari(moon_lon: float, birth_jd: float, n_maha: int = 10) -> list[DasaPeriod]:
    """All MD/AD periods, starting with the MD running at birth.

    The first MD is back-dated by the fraction of the Moon's nakshatra already
    traversed, so the AD boundaries inside it land on their true dates.
    """
    first = int(moon_lon // NAK_SPAN) % 9
    elapsed = (moon_lon % NAK_SPAN) / NAK_SPAN
    t = birth_jd - elapsed * DASA_SEQUENCE[first][1] * YEAR_DAYS

    periods = []
    for i in range(n_maha):
        md, md_years = DASA_SEQUENCE[(first + i) % 9]
        for j in range(9):
            ad, ad_years = DASA_SEQUENCE[(first + i + j) % 9]
            length = md_years * ad_years / DASA_TOTAL_YEARS * YEAR_DAYS
            periods.append(DasaPeriod(md, ad, t, t + length))
            t += length
    return periods


def period_at(periods: list[DasaPeriod], jd: float) -> DasaPeriod | None:
    i = bisect_right([p.start_jd for p in periods], jd) - 1
    if i < 0 or jd >= periods[i].end_jd:
        return None
    return periods[i]


def maha_dasas(periods: list[DasaPeriod]) -> list[DasaPeriod]:
    """One entry per MD (ad field = md), spanning all its ADs."""
    out: list[DasaPeriod] = []
    for p in periods:
        if out and out[-1].md == p.md:
            out[-1] = DasaPeriod(p.md, p.md, out[-1].start_jd, p.end_jd)
        else:
            out.append(DasaPeriod(p.md, p.md, p.start_jd, p.end_jd))
    return out
