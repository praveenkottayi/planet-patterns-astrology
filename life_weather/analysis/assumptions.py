"""EVERY tunable number in the Life Weather model lives here.

These are assumptions: classical rules turned into numbers (HANDOFF §3). They are
NOT fitted to anyone's life. Change them here and only here.
"""

# ─── Dasa: per-planet weight from the natal chart ─────────────────────────────

# Lordship, by house ruled (counted from Lagna). Unlisted houses (kendras 4/7/10, 2, 12) = 0.
LORDSHIP = {1: +1.0, 5: +1.0, 9: +1.0, 3: -1.0, 6: -1.0, 11: -1.0, 8: -1.0}
EIGHTH_LORD_EXEMPT_IF_LAGNA_LORD = True      # 8th lordship is not counted for the Lagna lord

DIGNITY = {
    "exalted": +1.0,
    "own": +0.5,
    "debilitated": -1.0,
    "debilitated_cancelled": 0.0,            # neecha bhanga
    "": 0.0,
}

# Placement of the planet, house from Lagna. Unlisted (2, 3, 11) = 0.
PLACEMENT = {1: +0.5, 4: +0.5, 5: +0.5, 7: +0.5, 9: +0.5, 10: +0.5,
             6: -0.5, 8: -0.5, 12: -0.5}

# Period score = MD_SHARE × MD-lord weight + AD_SHARE × AD-lord weight
MD_SHARE = 0.6
AD_SHARE = 0.4

# Fixed scale: weights are divided by the largest |weight| these rules can produce
# for ANY chart (computed in dasa_weight.py), so charts are comparable.
LANE_RANGE = 2.0                              # dasa lane spans −2 … +2

# ─── Transits (gochara), house counted from natal Moon ────────────────────────

JUPITER_HOUSE = {2: +1.0, 5: +1.0, 7: +1.0, 9: +1.0, 11: +1.0}
JUPITER_ELSE = -0.5

SATURN_HOUSE = {3: +1.0, 6: +1.0, 11: +1.0,
                12: -1.0, 1: -1.0, 2: -1.0,   # Sade Sati
                8: -1.5,                      # Ashtama Shani
                4: -0.75}                     # Ardhashtama / Kantaka Shani
SATURN_ELSE = -0.25

# Ashtakavarga modifier for Jupiter and Saturn: BINDU_WEIGHT × (bindus − BINDU_NEUTRAL)
BINDU_WEIGHT = 0.25
BINDU_NEUTRAL = 4

# Rahu and Ketu each scored by this rule; the Nodes lane is their average.
NODE_HOUSE = {3: +0.5, 6: +0.5, 11: +0.5, 1: -0.5, 8: -0.5}
NODE_ELSE = 0.0

# ─── Overall line ─────────────────────────────────────────────────────────────

DASA_SHARE = 0.5                              # score = DASA_SHARE × dasa
TRANSIT_SHARE = 0.5                           #       + TRANSIT_SHARE × (jupiter + saturn + nodes)

SAMPLE_DAYS = 5                               # one sample every 5 days
SMOOTH_SAMPLES = 19                           # centred moving average ≈ 95 days
SAMPLE_HOUR_UT = 6.5                          # 06:30 UT = 12:00 IST

# ─── Houses over time (one score per house) ───────────────────────────────────
# house score = HOUSE_DASA_SHARE × dasa focus + HOUSE_TRANSIT_SHARE × transit touch

HOUSE_DASA_SHARE = 0.5          # MD/AD lord rules or sits in the house → its dasa weight
HOUSE_TRANSIT_SHARE = 0.5       # slow planets sitting in / aspecting the house

# Natural nature of the slow planets: benefic +1, malefic −1.
NATURE = {"Jupiter": +1.0, "Saturn": -1.0, "Rahu": -1.0, "Ketu": -1.0}
MALEFIC_GOOD_HOUSES = (3, 6, 11)    # upachaya: malefics here count as + (as in the Saturn rule)

SIT_WEIGHT = 1.0
ASPECT_WEIGHT = 0.5             # ASSUMPTION: an aspect counts half of sitting in the house

# Graha drishti, counted from the planet's own sign (whole-sign). Nodes: 7th only.
ASPECTS = {"Jupiter": (5, 7, 9), "Saturn": (3, 7, 10), "Rahu": (7,), "Ketu": (7,)}
