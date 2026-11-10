"""Plain-language sentences built from the computed chart — description, not prediction.

Every sentence restates something the engine computed (a position, a rule, a score) in words;
the only added content is the classical natural significations of the planets below.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date

import pandas as pd

from ..core.chart import Chart
from ..core.constants import SIGN_LORD
from ..core.dignity import dignity, neecha_bhanga
from .dasa_weight import PlanetWeight, ruled_houses
from .houses import HOUSE_AREAS
from .timeline import LifeWeather

# Classical natural significations (karakatva), abbreviated.
SIGNIFIES = {
    "Sun": "the self, father, authority, government, vitality",
    "Moon": "the mind, mother, emotions, comfort, the public",
    "Mars": "energy, courage, property, siblings, conflict",
    "Mercury": "intellect, speech, trade, learning, communication",
    "Jupiter": "wisdom, teachers, children, fortune, dharma",
    "Venus": "love, marriage, comforts, arts, vehicles",
    "Saturn": "discipline, work, delay, endurance, karma",
    "Rahu": "ambition, foreign things, the unconventional, obsession",
    "Ketu": "detachment, spirituality, loss, past karma",
}

GLOSSARY = [
    ("Lagna", "The ascendant: the sign rising in the east at the moment of birth. It is the 1st "
              "house; every other house is counted from it."),
    ("Sign (rasi)", "One of 12 fixed 30° sections of the sidereal zodiac (Medam … Meenam)."),
    ("House", "A life area (H1 self … H12 expenses). Here whole-sign: each sign is one house, "
              "counted from the Lagna — or from the Moon where marked ☾."),
    ("Nakshatra", "One of 27 lunar mansions of 13°20′, each split into 4 padas."),
    ("Dasa", "Vimshottari planetary periods: a Maha-dasa (MD, 6–20 years) ruled by one planet, "
             "divided into sub-periods (antardasa, AD) of all nine planets."),
    ("Gochara", "Transits: where the planets are now, read from the natal Moon."),
    ("Sade Sati", "Saturn passing the 12th, 1st and 2nd signs from the natal Moon (~7½ years)."),
    ("Ashtama Shani", "Saturn in the 8th sign from the natal Moon."),
    ("Bindus", "Ashtakavarga points (0–8) a sign gives a transiting planet; above 4 helps, "
               "below 4 weakens."),
    ("Retrograde (℞)", "A planet appearing to move backwards; it can re-cross the same sign or "
                       "point up to three times."),
    ("Dignity", "Exalted, own sign, or debilitated (weak). Neecha bhanga = a debilitation "
                "cancelled by classical rules."),
    ("Aspect (drishti)", "Every planet looks at the 7th sign from it; Jupiter also the 5th and "
                         "9th, Saturn the 3rd and 10th, Mars the 4th and 8th."),
    ("Upachaya", "Houses 3, 6, 11 — where malefic planets are classically said to do well."),
]


def _area(h: int) -> str:
    return HOUSE_AREAS[h].split(",")[0].lower()


def _houses(hs: list[int]) -> str:
    return " and ".join(f"H{h} ({_area(h)})" for h in hs)


def tone(score: float) -> str:
    if score >= 1.0:
        return "strongly supportive"
    if score >= 0.3:
        return "supportive"
    if score > -0.3:
        return "mixed / neutral"
    if score > -1.0:
        return "challenging"
    return "strongly challenging"


# ─── Planets ──────────────────────────────────────────────────────────────────

def planet_role(chart: Chart, w: PlanetWeight) -> str:
    """What a planet stands for in this chart — not where it is (the table shows that).
    e.g. 'rules H6 (debts), H9 (fortune) · debilitated · stands for wisdom, … · weight −0.5'."""
    p = w.planet
    if p in ("Rahu", "Ketu"):
        parts = [f"acts through its sign lord {SIGN_LORD[chart.sign(p)]}"]
    else:
        ruled = ", ".join(f"H{h} ({_area(h)})" for h in ruled_houses(p, chart.sign("Lagna")))
        parts = [f"rules {ruled}"]
        d = dignity(p, chart.sign(p))
        if d == "debilitated" and neecha_bhanga(chart, p):
            parts.append("debilitated, cancelled (neecha bhanga)")
        elif d:
            parts.append("in its own sign" if d == "own" else d)
    parts += [f"stands for {SIGNIFIES[p]}", f"weight {w.total:+g}"]
    return " · ".join(parts)


def dasa_sentence(chart: Chart, w: PlanetWeight, level: str) -> str:
    """e.g. 'Venus Maha-dasa (weight −0.5, strained): Venus signifies …; here it rules …'."""
    p, lagna = w.planet, chart.sign("Lagna")
    kind = "supportive" if w.total > 0 else "strained" if w.total < 0 else "neutral"
    here = (f"it acts through {SIGN_LORD[chart.sign(p)]} and sits in {_houses([chart.house(p)])}"
            if p in ("Rahu", "Ketu") else
            f"it rules {_houses(ruled_houses(p, lagna))} and sits in {_houses([chart.house(p)])}")
    return (f"{p} {level} (weight {w.total:+g}, {kind}): {p} signifies {SIGNIFIES[p]}; "
            f"in this chart {here}.")


# ─── Key stretches of the Life Weather line ───────────────────────────────────

@dataclass(frozen=True)
class Stretch:
    start: date
    end: date
    mean: float
    drivers: tuple[str, ...]

    @property
    def tone(self) -> str:
        return tone(self.mean)


def clean_reason(text: str) -> str:
    """'Saturn 8th from Moon — Ashtama Shani (-1.5), 3 bindus → -1.75' → 'Saturn 8th from …'."""
    text = text.split(" →")[0]
    text = re.sub(r" \([^)]*\)", "", text)
    return re.sub(r", \d+ bindus", "", text).strip()


def key_stretches(lw: LifeWeather, factors: tuple[str, ...], threshold: float = 0.5,
                  min_days: int = 90, merge_gap_days: int = 60) -> list[Stretch]:
    """Runs where the 3-month average stays beyond ±threshold for at least min_days; runs of the
    same kind separated by less than merge_gap_days are joined into one stretch."""
    df = lw.frame
    sm = df["smoothed"].to_numpy()
    runs: list[tuple[int, int, int]] = []          # (start index, end index exclusive, sign)
    i = 0
    while i < len(df):
        sign = 1 if sm[i] >= threshold else -1 if sm[i] <= -threshold else 0
        j = i
        while j < len(df) and sign and (sm[j] * sign >= threshold):
            j += 1
        if sign:
            gap = (df["date"].iloc[i] - df["date"].iloc[runs[-1][1] - 1]).days if runs else None
            if runs and runs[-1][2] == sign and gap is not None and gap <= merge_gap_days:
                runs[-1] = (runs[-1][0], j, sign)
            else:
                runs.append((i, j, sign))
        i = max(j, i + 1)
    return [_stretch(df.iloc[a:b], factors, sign) for a, b, sign in runs
            if (df["date"].iloc[b - 1] - df["date"].iloc[a]).days >= min_days]


def _stretch(run: pd.DataFrame, factors: tuple[str, ...], sign: int) -> Stretch:
    share = {"dasa": 0.5, "jupiter": 0.5, "saturn": 0.5, "nodes": 0.5}
    contrib = {lane: share[lane] * run[lane].mean() for lane in share if lane in factors}
    pushing = sorted((lane for lane in contrib if contrib[lane] * sign > 0.05),
                     key=lambda lane: -abs(contrib[lane]))[:2]
    drivers = []
    for lane in pushing:
        if lane == "dasa":
            md, ad = Counter(zip(run["md"], run["ad"])).most_common(1)[0][0]
            drivers.append(f"{md}/{ad} dasa")
        else:
            drivers.append(clean_reason(Counter(run[f"why_{lane}"]).most_common(1)[0][0]))
    return Stretch(run["date"].iloc[0].date(), run["date"].iloc[-1].date(),
                   float(run["smoothed"].mean()), tuple(drivers))


# ─── Houses on a date ─────────────────────────────────────────────────────────

def house_highlights(hdf: pd.DataFrame, when: date, n: int = 3) -> tuple[list, list]:
    """([(house, score, why), …] most supported, […] most pressured) on the nearest sample."""
    row = hdf.iloc[(hdf["date"] - pd.Timestamp(when)).abs().argmin()]
    scored = [(h, float(row[f"S{h}"]), row[f"why{h}"]) for h in range(1, 13)]
    up = [s for s in sorted(scored, key=lambda s: -s[1]) if s[1] > 0.05][:n]
    down = [s for s in sorted(scored, key=lambda s: s[1]) if s[1] < -0.05][:n]
    return up, down


def house_label(h: int) -> str:
    return f"H{h} {HOUSE_AREAS[h].split(',')[0]}"


def house_reason(why: str) -> str:
    """'MD Jupiter (-0.5) rules/sits here -0.09 · Saturn aspects (7th) -0.25'
    → 'Maha-dasa lord Jupiter rules or sits here; Saturn aspects it (7th)'."""
    parts = []
    for part in why.split(" · "):
        part = re.sub(r" [+-]\d+\.\d+$", "", part)                     # trailing score
        part = re.sub(r" \(([+-]\d+(\.\d+)?)\)", "", part)             # (weight)
        part = re.sub(r"^MD ", "Maha-dasa lord ", part)
        part = re.sub(r"^AD ", "sub-period lord ", part)
        part = part.replace("rules/sits here", "rules or sits here")
        part = re.sub(r", (\d+) bindus$", r" (\1 bindus)", part)
        part = re.sub(r"aspects \((\w+)\)", r"aspects it (\1)", part)
        parts.append(part)
    return "; ".join(parts)


def chart_guide(name: str, lagna: str, moon: str, when: str,
                in_app: bool = False) -> list[tuple[str, list[str]]]:
    """'How to read this chart' for the South-Indian chart — (heading, points) pairs, shared by
    the app's Chart & houses tab and the PDF so both always say the same thing."""
    move = " Change the date in the sidebar to move them." if in_app else ""
    scores = "the Life Weather tab" if in_app else "the Life Weather timeline"
    return [
        ("The chart is a fixed map of the sky, not of houses.",
         ["Each of the 12 boxes is always the same sign (Medam is always the 2nd box on top, then "
          "the signs run clockwise). What changes from person to person is which house each sign "
          "becomes."]),
        ("1. Find the Lagna (yellow box, diagonal mark).",
         [f"That sign is H1 for {name} — here {lagna}. Count clockwise from it: the next box is "
          "H2, and so on. The H number in each box's corner does this counting for you."]),
        ("2. Read the two numbers in each corner.",
         ["H10 (black) = house counted from the Lagna — the usual \"house\" in a birth chart.",
          f"☾2 (blue) = house counted from the Moon (blue box, {moon}). Classical transit reading "
          f"(gochara) counts from the Moon, and that's what {scores} scores."]),
        ("3. Two kinds of planets in each box.",
         ["Dark text with degrees (e.g. Ju 12°) = where the planet was at birth. Never changes.",
          f"Coloured tag (e.g. a brown Ju) = where the planet is on {when}.{move} "
          "℞ = retrograde (moving backwards)."]),
        ("4. Each house is a life area.",
         ["A house is affected by three things: planets born in it, its ruler (the planet that "
          "owns its sign) and how strong that ruler is, and planets passing through it now. "
          "An empty house is normal — its ruler speaks for it."]),
    ]
