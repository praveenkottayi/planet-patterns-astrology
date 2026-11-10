"""PDF summary: builds for ordinary, newborn and factor-limited cases; content is right."""
from datetime import date, datetime, timedelta

import pytest

from life_weather.analysis.house_timeline import house_timeline
from life_weather.analysis.sensitivity import birth_time_sensitivity
from life_weather.analysis.timeline import LANES, build, combine
from life_weather.core.chart import Birth
from life_weather.places import search_cities, utc_offset_hours
from life_weather.report.pdf import build_pdf, pdf_filename


def _birth(when: datetime, name="Test Person") -> Birth:
    c = search_cities("Chennai")[0]
    return Birth(name, when, utc_offset_hours(c.tz_name, when, c.lon), c.lat, c.lon, "Chennai, India")


def _pdf(b: Birth, factors=tuple(LANES), pick=None) -> bytes:
    lw = build(b, end_year=b.when_local.year + 40)
    lw.frame = combine(lw.frame, factors)
    pick = pick or b.when_local.date() + timedelta(days=400)
    return build_pdf(b, lw, factors, "mean", pick, house_timeline(lw, "Lagna"),
                     birth_time_sensitivity(b))


def _text(pdf: bytes) -> str:
    import io

    pypdf = pytest.importorskip("pypdf")
    return "".join(page.extract_text() for page in pypdf.PdfReader(io.BytesIO(pdf)).pages)


def test_pdf_is_four_pages_with_key_sections():
    data = _pdf(_birth(datetime(1995, 4, 2, 9, 15)))
    import io

    import pypdf
    assert len(pypdf.PdfReader(io.BytesIO(data)).pages) == 4
    text = _text(data)
    for heading in ("Life Weather · Test Person", "Life Weather timeline", "Houses over time",
                    "Dasa timeline", "Please note", "Chennai, India"):
        assert heading in text


def test_pdf_for_newborn():
    b = _birth(datetime.combine(date.today() - timedelta(days=2), datetime.min.time()))
    assert _pdf(b, pick=date.today()).startswith(b"%PDF")


def test_pdf_notes_factors_left_out():
    text = _text(_pdf(_birth(datetime(1995, 4, 2, 9, 15)), factors=("dasa", "jupiter")))
    assert "Not counted in the overall line for this report: Saturn, Rahu/Ketu" in text


def test_filename_is_safe():
    b = _birth(datetime(1995, 4, 2), name="A. B/C d")
    assert pdf_filename(b, date(2026, 1, 2)) == "life-weather-a--b-c-d-2026-01-02.pdf"
