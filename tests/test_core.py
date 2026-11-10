"""Core engine checked against values verified independently with Swiss Ephemeris (HANDOFF §5)."""
from datetime import datetime

import pytest

from life_weather.core.ashtakavarga import BPHS_TOTALS, SAV_TOTAL, TABLE, bav, sav
from life_weather.core.chart import sidereal_longitudes, to_jd
from life_weather.core.constants import SIGNS_EN
from life_weather.core.dasa import maha_dasas, period_at, vimshottari
from life_weather.core.dignity import neecha_bhanga

DEG_TOL = 0.06   # fixtures are rounded to 0.1°


def assert_position(lon: float, expected: list, label: str):
    sign_name, deg = expected
    assert SIGNS_EN[int(lon // 30)] == sign_name, label
    assert lon % 30 == pytest.approx(deg, abs=DEG_TOL), label


def ym(d) -> str:
    return f"{d.year:04d}-{d.month:02d}"


# ─── Positions ────────────────────────────────────────────────────────────────

def test_natal_positions(charts):
    for cid, (fx, chart) in charts.items():
        for body, expected in fx["positions"].items():
            assert_position(chart.longitudes[body], expected, f"{cid} {body}")


def test_ayanamsa(charts):
    fx, chart = charts["chart_a"]
    assert chart.ayanamsa == pytest.approx(fx["ayanamsa"], abs=1e-3)


def test_moon_nakshatra(charts):
    for cid, (fx, chart) in charts.items():
        assert list(chart.nakshatra("Moon")) == fx["moon_nakshatra"], cid


def test_transit_snapshot(private):
    t = private["transit"]
    lons = sidereal_longitudes(to_jd(t["when"], t["tz"]))
    for body, expected in t["positions"].items():
        assert_position(lons[body], expected, f"transit {body}")


# ─── Dignity ──────────────────────────────────────────────────────────────────

def test_neecha_bhanga(charts):
    for cid, (fx, chart) in charts.items():
        for planet, cancelled in fx.get("neecha_bhanga", {}).items():
            assert bool(neecha_bhanga(chart, planet)) == cancelled, f"{cid} {planet}"


# ─── Dasa ─────────────────────────────────────────────────────────────────────

def _periods(chart):
    return vimshottari(chart.longitudes["Moon"], chart.jd)


def test_maha_dasa_dates(charts):
    for cid, (fx, chart) in charts.items():
        mds = {p.md: p for p in maha_dasas(_periods(chart))}
        for exp in fx.get("maha", []):
            md = mds[exp["lord"]]
            assert (ym(md.start), ym(md.end)) == (exp["start"], exp["end"]), cid


def test_dasa_on_date(charts):
    for cid, (fx, chart) in charts.items():
        for exp in fx.get("dasa_on", []):
            d = exp["date"]
            p = period_at(_periods(chart), to_jd(datetime(d.year, d.month, d.day, 12), 5.5))
            assert (p.md, p.ad, ym(p.end)) == (exp["md"], exp["ad"], exp["ad_end"]), cid


def test_dasa_periods_are_contiguous(charts):
    _, chart = charts["chart_a"]
    ps = _periods(chart)
    assert all(a.end_jd == pytest.approx(b.start_jd) for a, b in zip(ps, ps[1:]))
    first_md = maha_dasas(ps)[0]
    assert first_md.start_jd <= chart.jd < first_md.end_jd   # birth falls inside the first MD


# ─── Ashtakavarga ─────────────────────────────────────────────────────────────

def test_bav_table_totals():
    for planet, rows in TABLE.items():
        assert sum(map(len, rows)) == BPHS_TOTALS[planet], planet


def test_bav_and_sav_totals_on_chart(charts):
    for cid, (_, chart) in charts.items():
        for planet in TABLE:
            assert sum(bav(planet, chart, allow_unverified=True)) == BPHS_TOTALS[planet], f"{cid} {planet}"
        assert sum(sav(chart)) == SAV_TOTAL, cid


def test_bav_cells_against_reference(charts):
    """Cell-level check vs an independent tool (Jagannatha Hora). Filled in once provided."""
    for cid, (fx, chart) in charts.items():
        ref = fx.get("bav_reference")
        if not ref:
            continue
        for planet, row in ref.items():
            assert bav(planet, chart) == row, f"{cid} {planet}"
    if not any(fx.get("bav_reference") for fx, _ in charts.values()):
        pytest.skip("no bav_reference in fixtures yet")


# ─── Neecha bhanga edge case (Moon as the relevant lord) ─────────────────────

def _chart(**lons):
    from life_weather.core.chart import Chart
    base = {"Sun": 45, "Moon": 45, "Mars": 45, "Mercury": 45, "Jupiter": 45, "Venus": 45,
            "Saturn": 45, "Rahu": 45, "Ketu": 225, "Lagna": 15}
    base.update(lons)
    return Chart(jd=0, longitudes=base, ayanamsa=0, node="mean")


def test_mars_in_cancer_not_cancelled_by_moon_from_itself():
    # Mars debilitated in Cancer (its sign lord is the Moon). Lagna Aries; Moon in Taurus = H2
    # from Lagna. Saturn (lord of Mars' exaltation sign) in Gemini = H3 from Lagna, H2 from Moon.
    # Nothing in a kendra — only the old "Moon is H1 from itself" would have cancelled it.
    c = _chart(Mars=95, Moon=45, Saturn=75, Lagna=15)
    assert neecha_bhanga(c, "Mars") == []


def test_mars_in_cancer_cancelled_when_moon_in_kendra_from_lagna():
    c = _chart(Mars=95, Moon=105, Saturn=75, Lagna=15)  # Moon in Cancer = H4 from Lagna
    assert any("Moon" in r and "Lagna" in r for r in neecha_bhanga(c, "Mars"))
