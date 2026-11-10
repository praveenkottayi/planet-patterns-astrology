# Life Weather

A Vedic astrology app (sidereal, Lahiri ayanamsa) that answers one question for a person's whole
life: **when are the supportive and the challenging stretches — and why?**

Every number on screen comes from a stated classical rule or from the Swiss Ephemeris, and every
point carries its reason. No weights are tuned to fit anyone's life story.

## What it shows

| Tab | What you see |
|---|---|
| 🌦️ **Life Weather** | One green/red line from birth to the chosen year (green = supportive, red = challenging), with four lanes explaining it: **Dasa**, **Jupiter**, **Saturn**, **Rahu/Ketu**. Maha-dasa starts as dashed lines; hover any point for the reasons. A "Why" panel lists them for the chosen date. |
| 🏠 **Houses over time** | The same green/red view for each house H1–H12 (Self, Wealth, … Career, Income, Expenses), counted from Lagna or Moon. |
| 🪐 **Chart & houses** | South-Indian chart with birth planets and transits on the chosen date, a reading guide, a plain-language "explain one house", and a table of every house's sign, ruler, birth planets and current transits. |

The sidebar picks the person (saved profile or a new one by **birth city**), which factors count
in the overall line, Rahu/Ketu node type, and the **date for details** that drives the "why"
panel, the transit chart and the purple marker line.

**Download a PDF summary** from the sidebar ("Prepare PDF summary", then "Download PDF"): four
pages — birth details and the chosen date's dasa, score, reasons and chart; the Life Weather
timeline; houses over time with the house table; the dasa timeline, the model and a disclaimer.

Birth dates from **1800 up to today** (newborns included). Before standard time was adopted,
the birthplace's own local mean time is used (longitude ÷ 15), not the tz database's
reference-city time.

A **birth-time check** under the title shows how many minutes of birth-time error would change
the Lagna, and how far dasa dates move per 10 minutes.

## Run it

```bash
uv sync --extra dev
uv run streamlit run life_weather/ui/app.py
```

**Your own people** live in a local `.env` file (gitignored — real birth details never go in git).
Copy `.env.example` to `.env` and add one line per person:

```
LW_PROFILE_1="Name | 1990-01-01 12:00 | Chennai"
LW_PROFILE_2="Name | 1985-05-05 05:05 | Ottapalam | 10.77 | 76.38 | 5.5"   # lat | lon | UTC offset
```

Everyone also sees **public examples** (Sachin Tendulkar, Narendra Modi) from
`life_weather/examples.toml`, each with a note on how reliable its published birth time is.
A city is enough; coordinates and the UTC offset in force
on that date are filled in from an offline city list (GeoNames + IANA tz, so daylight saving and
historical changes such as India's +6:30 in 1942–45 are handled).

## The model

**Overall = ½ dasa + ½ (Jupiter + Saturn + Rahu/Ketu)**, sampled every 5 days, ~3-month average.

- **Dasa** — Vimshottari Maha-dasa / Antardasa from the natal Moon. Each planet gets a weight
  from the chart: lordship from Lagna (1/5/9 +1; 3/6/11 −1; 8th −1 unless also Lagna lord),
  dignity (exalted +1, own +0.5, debilitated −1, or 0 with neecha bhanga), placement
  (1/4/5/7/9/10 +0.5; 6/8/12 −0.5). Period = 0.6 × MD + 0.4 × AD on a **fixed scale** (÷ the
  largest weight the rules can produce, 3.5) so charts are comparable between people.
- **Jupiter** (from Moon) — +1 in 2/5/7/9/11, else −0.5; ± Ashtakavarga bindus.
- **Saturn** (from Moon) — +1 in 3/6/11; Sade Sati (12/1/2) −1; 8th −1.5; 4th −0.75; else
  −0.25; ± bindus.
- **Rahu/Ketu** (from Moon) — each +0.5 in 3/6/11, −0.5 in 1/8; the lane is their average.

**House score = ½ dasa focus + ½ transit touch** — the dasa lord's weight for every house it
rules or sits in, plus Jupiter (+) and Saturn/Rahu/Ketu (−, but + in 3/6/11) sitting in (full)
or aspecting (half) the house. Aspects: Jupiter 5/7/9, Saturn 3/7/10, nodes 7th.

All values live in [`life_weather/analysis/assumptions.py`](life_weather/analysis/assumptions.py).
The few that are our own choices (not classical) are labelled there.

## Accuracy

- `uv run pytest` — reference charts, hand-worked scores and rule tests.
- `uv run --with astropy python tools/crosscheck.py` — recomputes every position, Lagna and dasa
  date **without** Swiss Ephemeris (astropy, textbook ascendant formula, Lahiri from its 1956
  definition, Meeus mean node, dasa by hand). Last run: all positions within 0.011°.
- Jupiter and Saturn Ashtakavarga tables match PyJHora cell for cell. The Moon and Venus rows
  differ between sources and are locked out until settled.

Real birth-data fixtures live in `tests/fixtures_private.toml` (gitignored); those tests skip
when it is absent.

## Layout

```
life_weather/
├── core/        ephemeris, chart, dasa, dignity, ashtakavarga   (pure, no UI)
├── analysis/    assumptions, dasa weights, gochara, timeline, houses, sensitivity
├── viz/         Plotly figures and the SVG South-Indian chart
├── report/      PDF summary (fpdf2) and its static matplotlib charts
├── ui/          Streamlit: app.py wires sidebar, header and one module per tab
├── places.py    offline city → lat/lon/timezone
├── examples.toml public example people
└── profiles.py  your people from .env + the examples
tests/           pytest suite
tools/           crosscheck.py (independent accuracy check)
```
