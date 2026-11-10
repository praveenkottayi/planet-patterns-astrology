"""House table, chart grid, and factor toggles."""
from life_weather.analysis.dasa_weight import dasa_weights
from life_weather.analysis.houses import house_table
from life_weather.analysis.timeline import LANES, build, combine
from life_weather.core.chart import sidereal_longitudes, to_jd
from life_weather.viz.south_chart import GRID
from tests.conftest import birth_from, chart_fx


def test_grid_places_every_sign_once_on_the_border():
    assert sorted(GRID) == list(range(12))
    cells = set(GRID.values())
    assert len(cells) == 12 and not cells & {(1, 1), (1, 2), (2, 1), (2, 2)}


def test_house_table(charts, private):
    fx, chart = charts["chart_a"]
    exp = fx["house_table"]
    t = private["transit"]
    rows = house_table(chart, dasa_weights(chart), sidereal_longitudes(to_jd(t["when"], t["tz"])))
    by_house = {r.house: r for r in rows}
    assert by_house[1].sign == exp["lagna_sign"] and "Lagna" not in by_house[1].natal
    h10 = by_house[10]
    assert (h10.lord, h10.lord_house) == (exp["h10_lord"], exp["h10_lord_house"])
    moon = by_house[exp["moon_house"]]
    assert "Moon" in moon.natal and moon.house_from_moon == 1
    assert sum(len(r.natal) for r in rows) == 9 and sum(len(r.transit) for r in rows) == 9
    assert "Saturn" in by_house[exp["saturn_transit_house"]].transit


def test_dropping_a_factor_only_removes_its_term(private):
    fx = chart_fx(private, "chart_a")
    df = build(birth_from(fx), end_year=2030).frame
    no_sat = combine(df, tuple(lane for lane in LANES if lane != "saturn"))
    assert (no_sat["score"] - (df["score"] - 0.5 * df["saturn"])).abs().max() < 1e-12
    assert (combine(df, ())["score"] == 0).all()
