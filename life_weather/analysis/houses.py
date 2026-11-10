"""House table: the universal life-area meaning of each house, mapped onto one person's chart.

The meanings are the same for everyone. What differs per person is computed:
which sign falls in each house (from Lagna), its lord and that lord's condition,
the natal planets there, and the planets transiting it on a given date.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..core.chart import Chart, house_between, sign_of
from ..core.constants import GRAHAS, NODES, SIGN_LORD, SIGNS_EN, SIGNS_ML
from .dasa_weight import PlanetWeight

BODIES = GRAHAS + NODES

# Universal house significations (classical, abbreviated).
HOUSE_AREAS = {
    1:  "Self, body, health, overall direction",
    2:  "Wealth, family, speech, food",
    3:  "Courage, siblings, skills, short travel",
    4:  "Home, mother, property, vehicles, peace of mind",
    5:  "Children, intellect, creativity, romance",
    6:  "Debts, disease, enemies, daily work, service",
    7:  "Marriage, spouse, partnerships",
    8:  "Longevity, sudden events, inheritance, hidden matters",
    9:  "Fortune, father, dharma, higher learning, long journeys",
    10: "Career, status, reputation, authority",
    11: "Income, gains, networks, elder siblings",
    12: "Expenses, losses, foreign lands, sleep, moksha",
}


@dataclass(frozen=True)
class HouseRow:
    house: int              # from Lagna
    house_from_moon: int
    area: str
    sign: int
    lord: str
    lord_house: int         # where the lord sits (from Lagna)
    lord_weight: float
    natal: tuple[str, ...]
    transit: tuple[str, ...]

    @property
    def sign_label(self) -> str:
        return f"{SIGNS_ML[self.sign]} ({SIGNS_EN[self.sign]})"


def _list(bodies, retro=None) -> str:
    names = [b + (" ℞" if retro and retro.get(b) else "") for b in bodies]
    return ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else "".join(names)


def describe_house(row: HouseRow, weights: dict[str, PlanetWeight], when_label: str,
                   retro: dict[str, bool]) -> str:
    """Plain-language markdown walk-through of one house. Descriptive only — no prediction."""
    w = weights[row.lord]
    tone = ("a supportive ruler" if w.total > 0 else "a strained ruler" if w.total < 0
            else "a neutral ruler")
    lines = [
        f"**H{row.house} · {row.area}**",
        f"- **Sign:** {row.sign_label} falls in this house.",
        f"- **Ruler:** {row.lord}, which sits in H{row.lord_house} "
        f"({HOUSE_AREAS[row.lord_house].split(',')[0].lower()}). "
        f"Its weight is **{w.total:+g}** — {tone} ({'; '.join(w.reasons)}).",
        f"- **At birth:** {_list(row.natal)} {'was' if len(row.natal) == 1 else 'were'} here."
        if row.natal else "- **At birth:** no planets here (an empty house is normal; its ruler "
                          "speaks for it).",
        f"- **On {when_label}:** {_list(row.transit, retro)} "
        f"{'is' if len(row.transit) == 1 else 'are'} passing through."
        if row.transit else f"- **On {when_label}:** no planets passing through.",
        f"- **From the Moon** this sign is the {row.house_from_moon}"
        f"{'st' if row.house_from_moon == 1 else 'nd' if row.house_from_moon == 2 else 'rd' if row.house_from_moon == 3 else 'th'}"
        f" house — the count Life Weather uses to score Jupiter, Saturn and Rahu/Ketu.",
    ]
    return "\n".join(lines)


def bodies_by_sign(longitudes: dict[str, float]) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {s: [] for s in range(12)}
    for body in BODIES:
        out[sign_of(longitudes[body])].append(body)
    return out


def house_table(chart: Chart, weights: dict[str, PlanetWeight],
                transit_lons: dict[str, float]) -> list[HouseRow]:
    lagna, moon = chart.sign("Lagna"), chart.sign("Moon")
    natal = bodies_by_sign(chart.longitudes)
    now = bodies_by_sign(transit_lons)
    rows = []
    for h in range(1, 13):
        sign = (lagna + h - 1) % 12
        lord = SIGN_LORD[sign]
        rows.append(HouseRow(
            house=h, house_from_moon=house_between(sign, moon), area=HOUSE_AREAS[h],
            sign=sign, lord=lord, lord_house=chart.house(lord), lord_weight=weights[lord].total,
            natal=tuple(natal[sign]), transit=tuple(now[sign]),
        ))
    return rows
