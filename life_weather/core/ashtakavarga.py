"""Bhinnashtakavarga (BPHS): bindus (0–8) each sign gives a planet transiting it."""
from __future__ import annotations

from .chart import Chart

REFS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Lagna"]

# For each planet: per reference point (order of REFS), the houses counted from
# that point which contribute a bindu.
TABLE = {
    "Sun":     [[1, 2, 4, 7, 8, 9, 10, 11], [3, 6, 10, 11], [1, 2, 4, 7, 8, 9, 10, 11],
                [3, 5, 6, 9, 10, 11, 12], [5, 6, 9, 11], [6, 7, 12],
                [1, 2, 4, 7, 8, 9, 10, 11], [3, 4, 6, 10, 11, 12]],
    "Moon":    [[3, 6, 7, 8, 10, 11], [1, 3, 6, 7, 10, 11], [2, 3, 5, 6, 9, 10, 11],
                [1, 3, 4, 5, 7, 8, 10, 11], [1, 4, 7, 8, 10, 11, 12], [3, 4, 5, 7, 9, 10, 11],
                [3, 5, 6, 11], [3, 6, 10, 11]],
    "Mars":    [[3, 5, 6, 10, 11], [3, 6, 11], [1, 2, 4, 7, 8, 10, 11], [3, 5, 6, 11],
                [6, 10, 11, 12], [6, 8, 11, 12], [1, 4, 7, 8, 9, 10, 11], [1, 3, 6, 10, 11]],
    "Mercury": [[5, 6, 9, 11, 12], [2, 4, 6, 8, 10, 11], [1, 2, 4, 7, 8, 9, 10, 11],
                [1, 3, 5, 6, 9, 10, 11, 12], [6, 8, 11, 12], [1, 2, 3, 4, 5, 8, 9, 11],
                [1, 2, 4, 7, 8, 9, 10, 11], [1, 2, 4, 6, 8, 10, 11]],
    "Jupiter": [[1, 2, 3, 4, 7, 8, 9, 10, 11], [2, 5, 7, 9, 11], [1, 2, 4, 7, 8, 10, 11],
                [1, 2, 4, 5, 6, 9, 10, 11], [1, 2, 3, 4, 7, 8, 10, 11], [2, 5, 6, 9, 10, 11],
                [3, 5, 6, 12], [1, 2, 4, 5, 6, 7, 9, 10, 11]],
    "Venus":   [[8, 11, 12], [1, 2, 3, 4, 5, 8, 9, 11, 12], [3, 5, 6, 9, 11, 12],
                [3, 5, 6, 9, 11], [5, 8, 9, 10, 11], [1, 2, 3, 4, 5, 8, 9, 10, 11],
                [3, 4, 5, 8, 9, 10, 11], [1, 2, 3, 4, 5, 8, 9, 11]],
    "Saturn":  [[1, 2, 4, 7, 8, 10, 11], [3, 6, 11], [3, 5, 6, 10, 11, 12],
                [6, 8, 9, 10, 11, 12], [5, 6, 11, 12], [6, 11, 12], [3, 5, 6, 11],
                [1, 3, 4, 6, 10, 11]],
}
# Cross-checked cell by cell against PyJHora (independent open-source Jyotish library).
# Moon (3 cells) and Venus (1 cell) differ between sources — classical texts have variant
# readings — so those rows must not be used until settled against a third source.
VERIFIED = {"Sun", "Mars", "Mercury", "Jupiter", "Saturn"}
UNVERIFIED = {"Moon", "Venus"}

BPHS_TOTALS = {"Sun": 48, "Moon": 49, "Mars": 39, "Mercury": 54,
               "Jupiter": 56, "Venus": 52, "Saturn": 39}
SAV_TOTAL = 337


def bav(planet: str, chart: Chart, allow_unverified: bool = False) -> list[int]:
    """Bindus per sign (index 0 = Aries) for `planet`'s Bhinnashtakavarga."""
    if planet in UNVERIFIED and not allow_unverified:
        raise ValueError(f"{planet} BAV row is unverified (sources disagree); see VERIFIED above")
    out = [0] * 12
    for ref, houses in zip(REFS, TABLE[planet]):
        ref_sign = chart.sign(ref)
        for h in houses:
            out[(ref_sign + h - 1) % 12] += 1
    return out


def sav(chart: Chart) -> list[int]:
    """Sarvashtakavarga: sum of all seven BAVs per sign. Includes the UNVERIFIED rows,
    so per-sign values are provisional (the 337 grand total is unaffected)."""
    rows = [bav(p, chart, allow_unverified=True) for p in TABLE]
    return [sum(r[i] for r in rows) for i in range(12)]
