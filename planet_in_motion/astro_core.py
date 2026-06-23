from __future__ import annotations
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
import swisseph as swe

# ─── Zodiac & nakshatra constants ─────────────────────────────────────────────

RASIS = [
    "Medam", "Edavam", "Mithuna", "Karkata", "Chingam", "Kanni",
    "Tula", "Vrischika", "Dhanu", "Makara", "Kumba", "Meena",
]
RASIS_EN = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
NAKSHATRAS = [
    "Aswati", "Bharani", "Karthika", "Rohini", "Makiryam", "Thiruvathira",
    "Punartham", "Pooyam", "Ayilyam", "Makam", "Pooram", "Uthram",
    "Atham", "Chithira", "Chothi", "Vishakham", "Anizham", "Thriketta",
    "Moolam", "Pooradam", "Uthradam", "Thiruvonam", "Avittam", "Chathayam",
    "Pooruruttathi", "Uthrattathi", "Revathi",
]

# ─── Vimshottari Dasa ─────────────────────────────────────────────────────────

# 120-year cycle; each nakshatra group of 9 repeats in the same order
DASA_SEQUENCE = [
    ("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10), ("Mars", 7),
    ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17),
]
NAK_LORDS = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
] * 3

# ─── Planet identifiers ───────────────────────────────────────────────────────

PLANETS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
    "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE,
}
SHORT = {
    "Lagna": "Lag", "Sun": "Sun", "Moon": "Moo", "Mercury": "Mer",
    "Venus": "Ven", "Mars": "Mar", "Jupiter": "Jup", "Saturn": "Sat",
    "Rahu": "Rah", "Ketu": "Ket",
}

YEAR_DAYS = 365.25

# ─── Dignity tables ───────────────────────────────────────────────────────────

EXALT  = {"Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5, "Jupiter": 3, "Venus": 11, "Saturn": 6}
DEBIL  = {"Sun": 6, "Moon": 7, "Mars": 3, "Mercury": 11, "Jupiter": 9, "Venus": 5, "Saturn": 0}
OWN    = {
    "Sun": [4], "Moon": [3], "Mars": [0, 7], "Mercury": [2, 5],
    "Jupiter": [8, 11], "Venus": [1, 6], "Saturn": [9, 10],
}

# ─── House meanings ───────────────────────────────────────────────────────────

HOUSE_SIGNIFICATIONS = {
    1:  "Self, body, personality, vitality, overall life direction",
    2:  "Wealth & savings, family, speech, food, values",
    3:  "Courage, siblings, skills, short travel, effort & initiative",
    4:  "Home, mother, property, vehicles, education, inner peace",
    5:  "Children, intelligence, creativity, romance, speculation",
    6:  "Enemies, debts, disease, daily work, obstacles, service",
    7:  "Marriage, spouse, partnerships, business dealings",
    8:  "Longevity, sudden events, inheritance, transformation, hidden matters",
    9:  "Fortune, luck, father, dharma, higher learning, long journeys",
    10: "Career, status, reputation, authority, public life",
    11: "Income, gains, fulfilled ambitions, networks, elder siblings",
    12: "Expenses, losses, foreign lands, isolation, spirituality, sleep",
}
HOUSE_KEYWORDS = {
    1: "Self", 2: "Wealth", 3: "Courage", 4: "Home", 5: "Children",
    6: "Health/Enemies", 7: "Marriage", 8: "Longevity", 9: "Fortune",
    10: "Career", 11: "Income", 12: "Loss/Moksha",
}

# ─── Planet significations ────────────────────────────────────────────────────

PLANET_KARAKA = {
    "Sun":     "soul, father, authority, vitality, status",
    "Moon":    "mind, mother, emotions, comfort, the public",
    "Mars":    "energy, courage, drive, conflict, property, siblings",
    "Mercury": "intellect, speech, commerce, communication, learning",
    "Jupiter": "wisdom, fortune, expansion, children, dharma, teachers",
    "Venus":   "love, marriage, beauty, arts, comforts, luxury",
    "Saturn":  "discipline, delay, hard work, longevity, structure, karma",
    "Rahu":    "obsession, ambition, foreign things, sudden rise, illusion",
    "Ketu":    "detachment, spirituality, loss, past karma, liberation",
}

# Goal → houses to watch for timing (used by the forward scanner)
GOAL_HOUSES = {
    "Career & Status":         [10, 2, 11],
    "Marriage & Partnership":  [7, 2, 11],
    "Children & Creativity":   [5, 9, 1],
    "Wealth & Income":         [2, 11, 9],
    "Health & Vitality":       [1, 6, 8],
    "Home & Property":         [4, 2, 7],
    "Fortune & Luck":          [9, 5, 11],
    "Spirituality & Moksha":   [9, 12, 8],
    "Foreign Travel":          [12, 9, 3],
    "Education & Knowledge":   [5, 4, 9],
}

# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class PlanetPos:
    name: str
    longitude: float      # 0–360 sidereal
    rasi_index: int       # 0–11
    deg_in_rasi: float
    nakshatra: str
    pada: int
    retro: bool

    @property
    def rasi(self) -> str:
        return RASIS[self.rasi_index]


@dataclass
class Chart:
    when_utc: datetime
    lat: float
    lon: float
    ascendant: float      # sidereal longitude of lagna
    asc_rasi_index: int
    planets: dict         # name -> PlanetPos
    ayanamsa: float

    def planets_in_rasi(self, idx: int):
        out = []
        if self.asc_rasi_index == idx:
            out.append(("Lag", False))
        for name, p in self.planets.items():
            if p.rasi_index == idx:
                out.append((SHORT[name], p.retro))
        return out

    def house_of(self, rasi_index: int) -> int:
        return ((rasi_index - self.asc_rasi_index) % 12) + 1


# ─── Ephemeris helpers ────────────────────────────────────────────────────────

def local_to_jd(dt_local: datetime, tz_offset_hours: float) -> float:
    dt_utc = dt_local - timedelta(hours=tz_offset_hours)
    hour = dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, hour)


def _nak_pada(longitude: float):
    span = 360 / 27  # each nakshatra spans 13°20'
    n_index = int(longitude // span)
    within = longitude - n_index * span
    pada = int(within // (span / 4)) + 1
    return NAKSHATRAS[n_index % 27], pada


def build_chart(dt_local: datetime, tz_offset_hours: float,
                lat: float, lon: float) -> Chart:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    jd = local_to_jd(dt_local, tz_offset_hours)
    flag = swe.FLG_SIDEREAL | swe.FLG_SPEED

    planets: dict[str, PlanetPos] = {}
    for name, pid in PLANETS.items():
        pos, _ = swe.calc_ut(jd, pid, flag)
        lon_p = pos[0] % 360
        nak, pada = _nak_pada(lon_p)
        planets[name] = PlanetPos(
            name=name,
            longitude=lon_p,
            rasi_index=int(lon_p // 30),
            deg_in_rasi=lon_p % 30,
            nakshatra=nak,
            pada=pada,
            # Rahu's speed is always negative in Swiss Eph; treat as always retrograde
            retro=(pos[3] < 0 and name != "Rahu") or (name == "Rahu"),
        )

    # Ketu is always exactly opposite Rahu
    rahu = planets["Rahu"]
    ketu_lon = (rahu.longitude + 180) % 360
    nak, pada = _nak_pada(ketu_lon)
    planets["Ketu"] = PlanetPos("Ketu", ketu_lon, int(ketu_lon // 30),
                                ketu_lon % 30, nak, pada, True)

    cusps, ascmc = swe.houses_ex(jd, lat, lon, b"P", swe.FLG_SIDEREAL)
    asc = ascmc[0] % 360
    dt_utc = dt_local - timedelta(hours=tz_offset_hours)
    return Chart(
        when_utc=dt_utc, lat=lat, lon=lon,
        ascendant=asc, asc_rasi_index=int(asc // 30),
        planets=planets, ayanamsa=swe.get_ayanamsa_ut(jd),
    )


# ─── Vimshottari Dasa ─────────────────────────────────────────────────────────

def vimshottari_periods(moon_longitude: float, birth_local: datetime):
    """Maha-dasa periods covering the full 120-year Vimshottari cycle from birth."""
    span = 360 / 27
    n_index = int(moon_longitude // span)
    lord = NAK_LORDS[n_index]
    frac_elapsed = (moon_longitude - n_index * span) / span

    seq = DASA_SEQUENCE
    start_i = next(i for i, (l, _) in enumerate(seq) if l == lord)
    first_lord, first_len = seq[start_i]
    balance_years = first_len * (1 - frac_elapsed)

    periods = []
    cursor = birth_local
    end = cursor + timedelta(days=balance_years * YEAR_DAYS)
    periods.append(dict(lord=first_lord, start=cursor, end=end,
                        years=balance_years, partial=True))
    cursor = end

    for k in range(1, 9):
        l, yrs = seq[(start_i + k) % 9]
        end = cursor + timedelta(days=yrs * YEAR_DAYS)
        periods.append(dict(lord=l, start=cursor, end=end, years=yrs, partial=False))
        cursor = end

    return periods


def sub_periods(maha_lord: str, maha_start: datetime, maha_years: float):
    """Antardasa (bhukti) breakdown within a maha-dasa."""
    seq = DASA_SEQUENCE
    start_i = next(i for i, (l, _) in enumerate(seq) if l == maha_lord)
    out = []
    cursor = maha_start
    for k in range(9):
        l, yrs = seq[(start_i + k) % 9]
        sub_years = maha_years * (yrs / 120)
        end = cursor + timedelta(days=sub_years * YEAR_DAYS)
        out.append(dict(lord=l, start=cursor, end=end, years=sub_years))
        cursor = end
    return out


def current_dasa(periods, on_date: datetime):
    for p in periods:
        if p["start"] <= on_date < p["end"]:
            subs = sub_periods(p["lord"], p["start"], p["years"])
            cur_sub = next((s for s in subs if s["start"] <= on_date < s["end"]), None)
            return p, cur_sub, subs
    return None, None, []


# ─── Dignity & functional nature ──────────────────────────────────────────────

def dignity(planet_name: str, rasi_index: int) -> str:
    if planet_name in EXALT and EXALT[planet_name] == rasi_index:
        return "Exalted"
    if planet_name in DEBIL and DEBIL[planet_name] == rasi_index:
        return "Debilitated"
    if planet_name in OWN and rasi_index in OWN[planet_name]:
        return "Own sign"
    return ""


def house_from_lagna(rasi_index: int, asc_rasi_index: int) -> int:
    return ((rasi_index - asc_rasi_index) % 12) + 1


def functional_nature(planet: str, asc_rasi_index: int) -> dict:
    """
    Classifies a planet's functional role for a given Lagna.

    Returns {"label", "color", "explanation"} based on simplified classical rules:
    - Yogakaraka: owns a pure trikona (5/9) AND a kendra (1/4/7/10) — highest quality
    - Lagna Lord: owns house 1 — always auspicious regardless of second sign
    - Benefic: owns 5th or 9th without dusthana
    - Mixed: owns a trikona+dusthana or kendra+dusthana
    - Malefic: owns only dusthana (6/8/12)
    - Neutral: neither trikona nor dusthana
    - Shadowy: Rahu/Ketu (no sign ownership; adopt the lord they occupy)
    """
    if planet in ("Rahu", "Ketu"):
        return {"label": "Shadowy", "color": "#8B5CF6",
                "explanation": "Act as the sign lord they occupy; inherently unpredictable."}

    houses = {house_from_lagna(s, asc_rasi_index) for s in OWN.get(planet, [])}
    tri  = houses & {5, 9}         # pure trikonas (5th/9th; Lagna is handled separately)
    ken  = houses & {1, 4, 7, 10}  # kendras (angles)
    dust = houses & {6, 8, 12}     # dusthanas (difficult houses)

    if tri and ken:
        label, color = "Yogakaraka", "#15803d"
        exp = (f"Rules H{min(tri)} (trine) and H{min(ken)} (angle) — "
               f"most powerful dasa lord for {RASIS[asc_rasi_index]} Lagna.")
    elif 1 in houses:
        label, color = "Lagna Lord", "#16a34a"
        note = " Also rules a dusthana; themes may be mixed." if dust else ""
        exp = f"Rules the 1st house — its dasa reinforces your chart's core direction.{note}"
    elif tri and not dust:
        label, color = "Benefic", "#22C55E"
        exp = f"Trikona lord (H{min(tri)}) — dasa periods tend toward growth and auspiciousness."
    elif tri and dust:
        label, color = "Mixed", "#D97706"
        exp = (f"Rules H{min(tri)} (trine) and H{min(dust)} (dusthana) — "
               "growth and challenge intertwined; natal strength of the planet matters.")
    elif dust and not ken:
        label, color = "Malefic", "#DC2626"
        exp = (f"Rules only H{min(dust)} (dusthana) — "
               "dasa may bring obstacles, delays, or karmic pressure.")
    elif dust and ken:
        label, color = "Mixed", "#D97706"
        exp = "Rules both an angle and a dusthana — outcomes depend on natal placement and strength."
    else:
        label, color = "Neutral", "#64748b"
        exp = "Neither trikona nor dusthana lord — moderate results per natural significations."

    return {"label": label, "color": color, "explanation": exp}


# ─── House maps & lordships ───────────────────────────────────────────────────

def lagna_house_map(asc_rasi_index: int):
    return [
        {
            "house": h,
            "rasi": RASIS[(asc_rasi_index + h - 1) % 12],
            "rasi_en": RASIS_EN[(asc_rasi_index + h - 1) % 12],
            "keyword": HOUSE_KEYWORDS[h],
            "significations": HOUSE_SIGNIFICATIONS[h],
        }
        for h in range(1, 13)
    ]


def planet_lordships(asc_rasi_index: int):
    out = []
    for planet, ruled_signs in OWN.items():
        houses = sorted(house_from_lagna(s, asc_rasi_index) for s in ruled_signs)
        out.append({
            "planet": planet,
            "houses_ruled": houses,
            "houses_label": " & ".join(str(h) for h in houses),
            "karaka": PLANET_KARAKA.get(planet, ""),
        })
    # Nodes have no sign-rulership; listed for completeness
    for node in ("Rahu", "Ketu"):
        out.append({"planet": node, "houses_ruled": [], "houses_label": "—",
                    "karaka": PLANET_KARAKA.get(node, "")})
    return out


# ─── Motion timeseries ────────────────────────────────────────────────────────

def angular_separation(longitude_a: float, longitude_b: float) -> float:
    """Shortest arc between two sidereal longitudes (0–180°)."""
    return abs((longitude_a - longitude_b + 180) % 360 - 180)


def planetary_timeseries(start_local, end_local, tz_offset_hours, lat, lon,
                         planet_names=None, step_days=1):
    """
    Sample sidereal positions at step_days intervals over a date range.
    Returns one dict per (date, planet) with longitude, rasi, retro flag,
    and phase_sin/phase_cos for smooth motion curves.
    """
    selected = planet_names or (list(PLANETS.keys()) + ["Ketu"])
    step = timedelta(days=step_days)
    cursor = start_local
    rows = []
    while cursor <= end_local:
        chart = build_chart(cursor, tz_offset_hours, lat, lon)
        for name in selected:
            pos = chart.planets[name]
            rad = math.radians(pos.longitude)
            rows.append({
                "when_local": cursor,
                "planet": name,
                "longitude": pos.longitude,
                "deg_in_rasi": pos.deg_in_rasi,
                "rasi": pos.rasi,
                "retro": pos.retro,
                "phase_sin": math.sin(rad),
                "phase_cos": math.cos(rad),
            })
        cursor += step
    return rows
