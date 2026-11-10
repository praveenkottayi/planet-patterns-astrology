# Life Weather (v2) — plan

Branch: `v2` · Brief: `handoff/life_weather/HANDOFF.md` (local only, gitignored)

v2 is a standalone rebuild. v1 (`planet_in_motion/`) has been removed from this branch; it stays
on `main` until `v2` is merged to replace it.

## Design rules

1. **Pure computation.** Every number comes from a classical rule or the ephemeris; nothing is
   fitted to anyone's life.
2. **One assumptions block** (`analysis/assumptions.py`); non-classical choices are labelled.
3. **Every score explains itself** — each point carries its reason.
4. **Verified before shown** — tests + `tools/crosscheck.py` (independent ephemeris).
5. **No personal data in git** — `.env`, `tests/fixtures_private.toml`, `handoff/`.

## Done

- ☑ Core engine: Lahiri positions, whole-sign houses, Vimshottari MD/AD, dignity + neecha bhanga,
  Ashtakavarga (Jupiter/Saturn verified; Moon/Venus locked).
- ☑ Life Weather: dasa weights (fixed scale ÷3.5), Jupiter/Saturn/Nodes lanes from Moon, reasons,
  factor toggles, exact-date "why" panel.
- ☑ Houses over time: green/red score per house, Lagna/Moon reference.
- ☑ Chart & houses: South-Indian chart with transit overlay, reading guide, house explainer,
  house table.
- ☑ Birth city input (offline GeoNames + historical tz); city-only profiles.
- ☑ Birth-time sensitivity warning.
- ☑ Independent cross-check (positions ≤0.011°, dasa ±3 days); brief's ingress dates found 1 day late.
- ☑ Refactor: v1 removed, installable package, UI split per tab.
- ☑ Birth dates 1800 → today (newborns); birthplace local mean time before standard time.
- ☑ PDF summary download (4 pages).
- ☑ Your people from local `.env`; public examples (Tendulkar, Modi) with birth-time reliability notes.
- ☑ Privacy pass: tests use anonymous ids; chart-specific values only in the private fixture.

## Next (pick one at a time)

- ☐ Aspect highlight on the chart (pick a house → arrows from planets aspecting it)
- ☐ Rate past years → honest check whether the model beats chance (`tune.py` idea)
- ☐ Exact ingress list / "next changes" card (v1's forward scanner, done accurately)
- ☐ Dasa timeline table (MD/AD list with dates)
- ☐ Fast-planet monthly strip (Sun, Mars, Moon from Moon; Chandrashtama)
- ☐ Settle Moon/Venus Ashtakavarga rows against a third source
- ☐ Vedha, Kakshya, Shadbala (brief §8)

## Cut over

- ☐ Merge `v2` → `main` (replaces v1)
