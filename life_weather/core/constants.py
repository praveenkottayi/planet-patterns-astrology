"""Fixed astronomical / classical tables. Sign and planet indices are 0-based (0 = Aries)."""
from __future__ import annotations

import swisseph as swe

# ─── Signs & nakshatras ───────────────────────────────────────────────────────

SIGNS_ML = [
    "Medam", "Edavam", "Mithunam", "Karkidakam", "Chingam", "Kanni",
    "Thulam", "Vrischikam", "Dhanu", "Makaram", "Kumbham", "Meenam",
]
SIGNS_EN = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
NAKSHATRAS = [
    "Ashwathi", "Bharani", "Karthika", "Rohini", "Makayiram", "Thiruvathira",
    "Punartham", "Pooyam", "Ayilyam", "Makam", "Pooram", "Uthram",
    "Atham", "Chithira", "Chothi", "Vishakham", "Anizham", "Thrikketta",
    "Moolam", "Pooradam", "Uthradam", "Thiruvonam", "Avittam", "Chathayam",
    "Pooruruttathi", "Uthrattathi", "Revathi",
]
NAKSHATRAS_SA = [   # Sanskrit names, same order — for horoscopes written outside Kerala
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]
NAK_SPAN = 360 / 27

# Lunar day: every 12° the Moon gains on the Sun. 1–14 in each half, then Pournami / Amavasya.
TITHIS = ["Prathama", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami",
          "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi"]

# ─── Planets ──────────────────────────────────────────────────────────────────

GRAHAS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]  # the seven bodies
NODES = ["Rahu", "Ketu"]

PLANET_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN,
}
NODE_IDS = {"mean": swe.MEAN_NODE, "true": swe.TRUE_NODE}

# ─── Lordship & dignity ───────────────────────────────────────────────────────

SIGN_LORD = [
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
]
EXALT = {"Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5, "Jupiter": 3, "Venus": 11, "Saturn": 6}
DEBIL = {p: (s + 6) % 12 for p, s in EXALT.items()}
OWN = {p: [s for s, lord in enumerate(SIGN_LORD) if lord == p] for p in GRAHAS}

KENDRAS = (1, 4, 7, 10)

# ─── Vimshottari ──────────────────────────────────────────────────────────────

DASA_SEQUENCE = [
    ("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10), ("Mars", 7),
    ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17),
]
DASA_TOTAL_YEARS = 120
YEAR_DAYS = 365.25
