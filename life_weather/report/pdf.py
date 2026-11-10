"""Downloadable PDF summary of one person's Life Weather (no Streamlit code here).

Page 1  Summary — birth details, birth-time check, the chosen date (dasa, score, reasons), chart
Page 2  Life Weather chart and how to read it
Page 3  Houses over time (from Lagna) and the house table on the chosen date
Page 4  Dasa timeline, dasa weights, the model in brief, disclaimer
"""
from __future__ import annotations

import io
from datetime import date, datetime, time
from pathlib import Path

import matplotlib
import pandas as pd
from fpdf import FPDF
from fpdf.fonts import FontFace

from ..analysis.dasa_weight import dasa_scale
from ..analysis.houses import house_table
from ..analysis.sensitivity import BirthTimeSensitivity
from ..analysis.timeline import LifeWeather, score_of
from ..core.chart import Birth, retrograde, sidereal_longitudes, to_jd
from ..core.constants import SIGNS_EN, SIGNS_ML
from ..core.dasa import period_at
from ..viz.figure import LANE_TITLES
from ..viz.south_chart import chart_cells
from .static_charts import houses_png, life_weather_png, south_chart_png

FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
INK, MUTED, ACCENT = (15, 23, 42), (71, 85, 105), (37, 99, 235)
HEAD = FontFace(emphasis="BOLD", fill_color=(241, 245, 249))

DISCLAIMER = (
    "This report applies classical Vedic (Jyotish) rules mechanically. It describes astrological "
    "indications, not predictions, and is not medical, financial, legal or psychological advice. "
    "Results depend on an accurate birth time — see the birth-time check on page 1."
)
MODEL = [
    "Overall = ½ dasa + ½ (Jupiter + Saturn + Rahu/Ketu), sampled every 5 days, ~3-month average.",
    "Dasa: Vimshottari Maha-dasa / sub-period from the natal Moon. Each planet's weight comes from "
    "its lordship (houses 1/5/9 +1; 3/6/11 −1; 8th −1 unless also Lagna lord), dignity (exalted +1, "
    "own +0.5, debilitated −1 or 0 with neecha bhanga) and placement (1/4/5/7/9/10 +0.5; 6/8/12 "
    f"−0.5). Period = 0.6 × MD + 0.4 × AD on a fixed scale (÷{dasa_scale():g}).",
    "Jupiter from Moon: +1 in 2/5/7/9/11, else −0.5. Saturn from Moon: +1 in 3/6/11; Sade Sati "
    "(12/1/2) −1; 8th −1.5; 4th −0.75; else −0.25. Both adjusted by Ashtakavarga bindus.",
    "Rahu/Ketu from Moon: each +0.5 in 3/6/11, −0.5 in 1/8; the lane is their average.",
    "House score = ½ dasa focus (lord rules or sits there) + ½ transit touch (Jupiter +, "
    "Saturn/Rahu/Ketu − except + in 3/6/11; sitting full, aspect half).",
    "Positions: Swiss Ephemeris, Lahiri ayanamsa, whole-sign houses.",
]


class _Report(FPDF):
    def __init__(self, footer_note: str):
        super().__init__(format="A4")
        self.footer_note = footer_note
        self.add_font("DejaVu", "", FONT_DIR / "DejaVuSans.ttf")
        self.add_font("DejaVu", "B", FONT_DIR / "DejaVuSans-Bold.ttf")
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(True, margin=16)

    def footer(self):
        self.set_y(-11)
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*MUTED)
        self.cell(0, 5, f"{self.footer_note}   ·   page {self.page_no()}", align="C")

    # ── building blocks ──
    def h1(self, text: str):
        self.set_font("DejaVu", "B", 17)
        self.set_text_color(*INK)
        self.cell(0, 9, text, new_x="LMARGIN", new_y="NEXT")

    def h2(self, text: str):
        self.ln(2)
        self.set_font("DejaVu", "B", 11.5)
        self.set_text_color(*INK)
        self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")

    def para(self, text: str, size: float = 9, color=MUTED):
        self.set_font("DejaVu", "", size)
        self.set_text_color(*color)
        self.multi_cell(0, size * 0.5, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def bullets(self, items: list[str], size: float = 9):
        self.set_font("DejaVu", "", size)
        self.set_text_color(*INK)
        for item in items:
            self.multi_cell(0, size * 0.5, f"•  {item}", new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def kv(self, rows: list[tuple[str, str]]):
        self.set_font("DejaVu", "", 9)
        self.set_text_color(*INK)
        with self.table(col_widths=(40, 140), first_row_as_headings=False, line_height=5,
                        text_align="LEFT", borders_layout="HORIZONTAL_LINES") as t:
            for k, v in rows:
                r = t.row()
                r.cell(k, style=FontFace(emphasis="BOLD"))
                r.cell(v)
        self.ln(2)

    def grid(self, header: list[str], rows: list[list[str]], widths: tuple, size: float = 7.5):
        self.set_font("DejaVu", "", size)
        self.set_text_color(*INK)
        with self.table(col_widths=widths, headings_style=HEAD, line_height=size * 0.55,
                        text_align="LEFT", borders_layout="HORIZONTAL_LINES") as t:
            t.row(header)
            for row in rows:
                t.row([str(c) for c in row])
        self.ln(2)

    def png(self, data: bytes, width: float):
        self.image(io.BytesIO(data), w=width, x=(self.w - width) / 2)
        self.ln(2)


def _hours(h: float) -> str:
    sign = "+" if h >= 0 else "−"
    m = round(abs(h) * 60)
    return f"UTC {sign}{m // 60}:{m % 60:02d}"


def _minutes(m: int | None) -> str:
    return f"{m} min" if m is not None else "more than 4 h"


def build_pdf(birth: Birth, lw: LifeWeather, factors: tuple[str, ...], node: str, pick: date,
              houses_from_lagna: pd.DataFrame, sens: BirthTimeSensitivity) -> bytes:
    chart = lw.chart
    lagna, moon = chart.sign("Lagna"), chart.sign("Moon")
    nak, pada = chart.nakshatra("Moon")
    when = f"{pick:%d %b %Y}"
    jd = to_jd(datetime.combine(pick, time(12)), birth.tz_hours)
    transit, retro = sidereal_longitudes(jd, node), retrograde(jd)
    period = period_at(lw.periods, jd)
    exact = lw.on(pick)
    nearest = lw.frame.iloc[(lw.frame["date"] - pd.Timestamp(pick)).abs().argmin()]
    rows = house_table(chart, lw.weights, transit)

    pdf = _Report(f"Life Weather · {birth.name} · generated {date.today():%d %b %Y}")

    # ── Page 1: summary ──
    pdf.add_page()
    pdf.h1(f"Life Weather · {birth.name}")
    pdf.para(f"Summary for {when}. Sidereal (Lahiri), {node} node, transits counted from the Moon.")
    place = birth.place or "—"
    pdf.kv([
        ("Born", f"{birth.when_local:%d %b %Y, %H:%M} local ({_hours(birth.tz_hours)})"),
        ("Place", f"{place}  ({abs(birth.lat):.2f}°{'N' if birth.lat >= 0 else 'S'}, "
                  f"{abs(birth.lon):.2f}°{'E' if birth.lon >= 0 else 'W'})"),
        ("Lagna", f"{SIGNS_ML[lagna]} ({SIGNS_EN[lagna]}) {chart.deg_in_sign('Lagna'):.1f}°"),
        ("Moon", f"{SIGNS_ML[moon]} ({SIGNS_EN[moon]}), nakshatra {nak} pada {pada}"),
        ("Birth-time check", f"Lagna holds if the birth time is right to within "
                             f"{_minutes(sens.lagna_earlier)} earlier / "
                             f"{_minutes(sens.lagna_later)} later; dasa dates move about "
                             f"{sens.dasa_days_per_10min} days per 10 minutes of error."),
    ])
    pdf.h2(f"On {when}")
    pdf.kv([
        ("Dasa", f"{period.md} Maha-dasa / {period.ad} sub-period (until {period.end:%b %Y})"),
        ("Overall", f"{nearest.smoothed:+.2f} (3-month average) · {score_of(exact, factors):+.2f} "
                    f"on this date — positive = supportive, negative = challenging"),
    ])
    pdf.bullets([("Dasa: " if lane == "dasa" else "") + exact[f"why_{lane}"]
                 + ("" if lane in factors else "  (not counted)") for lane in LANE_TITLES])
    pdf.png(south_chart_png(chart_cells(chart, transit, retro), birth.name, f"transits {when}"),
            width=108)

    # ── Page 2: Life Weather ──
    pdf.add_page()
    pdf.h1("Life Weather timeline")
    pdf.png(life_weather_png(lw, factors, pick), width=180)
    pdf.para("Green = supportive, red = challenging (3-month average). The four lanes below the "
             "line show why: Dasa, Jupiter, Saturn and Rahu/Ketu, all on one colour scale — a pale "
             "lane contributes little. Dashed lines mark each Maha-dasa start; blue = today; dotted "
             f"purple = {when}. Look for long stretches rather than single spikes.")
    off = [LANE_TITLES[f] for f in LANE_TITLES if f not in factors]
    if off:
        pdf.para(f"Not counted in the overall line for this report: {', '.join(off)}.",
                 color=INK)

    # ── Page 3: Houses ──
    pdf.add_page()
    pdf.h1("Houses over time")
    pdf.png(houses_png(lw, houses_from_lagna, "Lagna", pick), width=180)
    pdf.para("Each strip is one house (life area), counted from the Lagna, on one shared scale. "
             "Score = ½ dasa focus (the running dasa lord rules or sits in the house) + ½ transit "
             "touch (Jupiter adds; Saturn, Rahu, Ketu subtract except in houses 3, 6, 11; sitting "
             "counts fully, an aspect half).")
    pdf.h2(f"Houses on {when}")
    pdf.grid(["House", "Life area", "Sign", "Ruler (sits in, weight)", "Born with",
              "Passing through", "☾"],
             [[f"H{r.house}", r.area, SIGNS_ML[r.sign], f"{r.lord} (H{r.lord_house}, "
               f"{r.lord_weight:+g})", ", ".join(r.natal) or "—",
               ", ".join(p + (" ℞" if retro.get(p) else "") for p in r.transit) or "—",
               str(r.house_from_moon)] for r in rows],
             widths=(13, 50, 21, 34, 24, 29, 9))

    # ── Page 4: Dasa & method ──
    pdf.add_page()
    pdf.h1("Dasa timeline")
    mds = [md for md in lw.maha_dasas if md.end > birth.when_local.date()]
    pdf.grid(["Maha-dasa", "From", "To", "Weight", "Why"],
             [[md.md, f"{max(md.start, birth.when_local.date()):%b %Y}", f"{md.end:%b %Y}",
               f"{lw.weights[md.md].total:+g}", "; ".join(lw.weights[md.md].reasons)]
              for md in mds[:10]],
             widths=(22, 20, 20, 16, 102))
    current = [md for md in mds if md.start <= pick < md.end]
    if current:
        cur = current[0]
        nxt = mds[mds.index(cur) + 1] if mds.index(cur) + 1 < len(mds) else None
        subs = [p for p in lw.periods if p.md in {cur.md, nxt.md if nxt else ""}
                and p.end >= pick and p.start < (nxt.end if nxt else cur.end)]
        pdf.h2(f"Sub-periods — {cur.md}" + (f" and {nxt.md}" if nxt else "") + " Maha-dasa")
        pdf.grid(["Maha-dasa / sub-period", "From", "To", "Sub-period lord weight"],
                 [[f"{p.md} / {p.ad}", f"{p.start:%d %b %Y}", f"{p.end:%d %b %Y}",
                   f"{lw.weights[p.ad].total:+g}"] for p in subs],
                 widths=(60, 35, 35, 50))
    pdf.h2("The model in brief")
    pdf.bullets(MODEL, size=8)
    pdf.para("Houses here are whole-sign, counted from the Lagna unless marked ☾ (from the Moon). "
             f"Birth time is taken as {_hours(birth.tz_hours)}.", size=8)
    pdf.h2("Please note")
    pdf.para(DISCLAIMER, size=8.5, color=INK)
    return bytes(pdf.output())


def pdf_filename(birth: Birth, pick: date) -> str:
    safe = "".join(ch if ch.isalnum() else "-" for ch in birth.name).strip("-").lower() or "person"
    return f"life-weather-{safe}-{pick:%Y-%m-%d}.pdf"
