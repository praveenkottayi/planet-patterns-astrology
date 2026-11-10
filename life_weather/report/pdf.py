"""Downloadable PDF report of one person's Life Weather (no Streamlit code here).

1  At a glance      what this is, birth details, the chosen date in words, top houses, next events
2  Birth chart      chart with the date's transits, how to read it, planets at birth, roles
3  Planets in motion  the exact events ahead for the slow planets
4  Life Weather     the timeline, how to read it, and every key stretch with its causes
5  Houses           houses over time and the house table on the chosen date
6  Dasa             Maha-dasa timeline, current sub-periods, what each coming dasa lord stands for
7  Method           the model, a glossary, and the disclaimer

Every sentence restates a computed value (see analysis/narrative.py) — description, not prediction.
"""
from __future__ import annotations

import io
from datetime import date, datetime, time, timedelta
from pathlib import Path

import matplotlib
import pandas as pd
from fpdf import FPDF
from fpdf.fonts import FontFace

from ..analysis.dasa_weight import dasa_scale
from ..analysis.houses import house_table
from ..analysis.motion import events
from ..analysis.narrative import (GLOSSARY, chart_guide, dasa_sentence, house_highlights,
                                  house_label, house_reason, key_facts, key_stretches,
                                  planet_role, tone)
from ..analysis.sensitivity import BirthTimeSensitivity
from ..analysis.timeline import LifeWeather, score_of
from ..core.chart import Birth, retrograde, sidereal_longitudes, to_jd
from ..core.constants import GRAHAS, NODES, SIGNS_ML
from ..core.dasa import period_at
from ..core.dignity import dignity, neecha_bhanga
from ..viz.figure import LANE_TITLES
from ..viz.south_chart import chart_cells
from .static_charts import houses_png, life_weather_png, south_chart_png

FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
INK, MUTED = (15, 23, 42), (71, 85, 105)
GOOD_RGB, BAD_RGB = (22, 128, 61), (185, 28, 28)
HEAD = FontFace(emphasis="BOLD", fill_color=(241, 245, 249))
SLOW = ["Jupiter", "Saturn", "Rahu", "Ketu"]
EVENTS_AHEAD_YEARS = 3

DISCLAIMER = (
    "This report applies classical Vedic (Jyotish) rules mechanically and explains each result. "
    "It describes astrological indications, not predictions, and is not medical, financial, legal "
    "or psychological advice. Every result depends on an accurate birth time — see the birth-time "
    "check on page 1."
)
INTRO = (
    "Life Weather reads a birth chart the classical Vedic way and turns it into a timeline of "
    "supportive (green) and challenging (red) stretches across a life. Two things drive it: the "
    "planetary period (dasa) you are in, and where the slow planets — Jupiter, Saturn, Rahu and "
    "Ketu — are moving relative to your Moon. Every number in this report comes from a stated "
    "classical rule, and each one is explained in words. Look for long stretches and recurring "
    "themes rather than single dates."
)
MODEL = [
    "Overall = ½ dasa + ½ (Jupiter + Saturn + Rahu/Ketu), sampled every 5 days, ~3-month average.",
    "Dasa: Vimshottari Maha-dasa / sub-period from the natal Moon. Each planet's weight comes from "
    "its lordship (houses 1/5/9 +1; 3/6/11 −1; 8th −1 unless also Lagna lord), dignity (exalted +1, "
    "own +0.5, debilitated −1, or 0 with neecha bhanga) and placement (1/4/5/7/9/10 +0.5; 6/8/12 "
    f"−0.5). Period = 0.6 × MD + 0.4 × AD on a fixed scale (÷{dasa_scale():g}).",
    "Jupiter from Moon: +1 in 2/5/7/9/11, else −0.5. Saturn from Moon: +1 in 3/6/11; Sade Sati "
    "(12/1/2) −1; 8th −1.5; 4th −0.75; else −0.25. Both adjusted by Ashtakavarga bindus.",
    "Rahu/Ketu from Moon: each +0.5 in 3/6/11, −0.5 in 1/8; the lane is their average.",
    "House score = ½ dasa focus (lord rules or sits there) + ½ transit touch (Jupiter +, "
    "Saturn/Rahu/Ketu − except + in 3/6/11; sitting full, aspect half).",
    "Positions: Swiss Ephemeris, Lahiri ayanamsa, whole-sign houses; independently cross-checked.",
]
OWNER = "Praveen Vijayan"
CONTACT = "praveenkottayi@gmail.com"

EVENT_KINDS = (
    "Sign change (ingress): the planet moves into a new sign — and so a new house for you. "
    "Turns retrograde / direct (station): the planet stands still and reverses; retrograde "
    "planets revisit the same ground. Passes over a birth point (contact): the moving planet is "
    "exactly over your birth Moon, Lagna, or its own birth position — classically a time when "
    "that planet's themes are switched on."
)


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
    def section(self, need_mm: float):
        """Start a section on this page if `need_mm` fits below, else on a new page."""
        if self.page == 0 or self.get_y() + need_mm > self.h - self.b_margin:
            self.add_page()
        else:
            self.ln(4)
            self.set_draw_color(203, 213, 225)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(5)

    def h1(self, text: str, sub: str = ""):
        self.set_font("DejaVu", "B", 17)
        self.set_text_color(*INK)
        self.cell(0, 9, text, new_x="LMARGIN", new_y="NEXT")
        if sub:
            self.para(sub)

    def h2(self, text: str):
        self.ln(2)
        self.set_font("DejaVu", "B", 11.5)
        self.set_text_color(*INK)
        self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")

    def para(self, text: str, size: float = 9, color=MUTED):
        self.set_font("DejaVu", "", size)
        self.set_text_color(*color)
        self.multi_cell(0, size * 0.5, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1.5)

    def bullets(self, items: list[str], size: float = 9, color=INK):
        self.set_font("DejaVu", "", size)
        self.set_text_color(*color)
        for item in items:
            self.multi_cell(0, size * 0.5, f"•  {item}", new_x="LMARGIN", new_y="NEXT")
            self.ln(0.6)
        self.ln(1)

    def guide(self, steps: list[tuple[str, list[str]]], size: float = 8.6):
        """Bold heading per step, then its points (bulleted when there are several)."""
        for heading, points in steps:
            self.set_font("DejaVu", "B", size)
            self.set_text_color(*INK)
            self.multi_cell(0, size * 0.52, heading, new_x="LMARGIN", new_y="NEXT")
            self.set_font("DejaVu", "", size)
            self.set_text_color(*MUTED)
            for pt in points:
                self.multi_cell(0, size * 0.52, pt if len(points) == 1 else f"•  {pt}",
                                new_x="LMARGIN", new_y="NEXT")
            self.ln(1.2)

    def callout(self, text: str, rgb):
        self.set_font("DejaVu", "B", 10)
        self.set_text_color(*rgb)
        self.multi_cell(0, 5.2, text, new_x="LMARGIN", new_y="NEXT")
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


def _rgb(score: float):
    return GOOD_RGB if score >= 0.3 else BAD_RGB if score <= -0.3 else INK


def build_pdf(birth: Birth, lw: LifeWeather, factors: tuple[str, ...], node: str, pick: date,
              houses_from_lagna: pd.DataFrame, sens: BirthTimeSensitivity) -> bytes:
    chart = lw.chart
    lagna, moon = chart.sign("Lagna"), chart.sign("Moon")
    when = f"{pick:%d %b %Y}"
    jd = to_jd(datetime.combine(pick, time(12)), birth.tz_hours)
    transit, retro_now = sidereal_longitudes(jd, node), retrograde(jd)
    retro_birth = retrograde(chart.jd)
    period = period_at(lw.periods, jd)
    exact = lw.on(pick)
    nearest = lw.frame.iloc[(lw.frame["date"] - pd.Timestamp(pick)).abs().argmin()]
    overall = float(nearest.smoothed)
    rows = house_table(chart, lw.weights, transit)
    up, down = house_highlights(houses_from_lagna, pick)
    centre = datetime.combine(pick, time(12))
    ahead = events(chart, centre, centre + timedelta(days=365.25 * EVENTS_AHEAD_YEARS),
                   birth.tz_hours, SLOW, node)
    stretches = key_stretches(lw, factors)

    pdf = _Report(f"Life Weather · {birth.name} · generated {date.today():%d %b %Y}")

    # ── 1. At a glance ──────────────────────────────────────────────────────
    pdf.add_page()
    pdf.h1(f"Life Weather · {birth.name}", f"Report for {when}")
    place = birth.place or "—"
    pdf.h2("Key facts — check these against your horoscope first")
    pdf.kv([
        ("Born", f"{birth.when_local:%d %b %Y, %H:%M} local ({_hours(birth.tz_hours)})"),
        ("Place", f"{place}  ({abs(birth.lat):.2f}°{'N' if birth.lat >= 0 else 'S'}, "
                  f"{abs(birth.lon):.2f}°{'E' if birth.lon >= 0 else 'W'})"),
        *key_facts(lw),
        ("Birth-time check", f"The Lagna holds only if the birth time is right to within "
                             f"{_minutes(sens.lagna_earlier)} earlier / "
                             f"{_minutes(sens.lagna_later)} later; dasa dates move about "
                             f"{sens.dasa_days_per_10min} days per 10 minutes of error."),
    ])
    pdf.para("If any of these differ from your horoscope, check the birth time and place before "
             "reading further — everything below depends on them.", size=8.3)
    pdf.para(INTRO)

    pdf.h2(f"At a glance — {when}")
    pdf.callout(f"Overall: {tone(overall)} ({overall:+.2f}, 3-month average; this date "
                f"{score_of(exact, factors):+.2f}).", _rgb(overall))
    pdf.para(f"You are in the {period.md} Maha-dasa, {period.ad} sub-period, until "
             f"{period.end:%B %Y}.", color=INK)
    pdf.bullets([dasa_sentence(chart, lw.weights[period.md], "Maha-dasa"),
                 dasa_sentence(chart, lw.weights[period.ad], "sub-period")])
    pdf.para("Why the line sits where it does today:", color=INK)
    pdf.bullets([("Dasa: " if lane == "dasa" else "") + exact[f"why_{lane}"]
                 + ("" if lane in factors else "  (not counted in this report)")
                 for lane in LANE_TITLES])
    if up:
        pdf.para("Life areas most supported now (houses from the Lagna):", color=INK)
        pdf.bullets([f"{house_label(h)} ({s:+.2f}) — {house_reason(w)}"
                     for h, s, w in up])
    if down:
        pdf.para("Life areas under most pressure now:", color=INK)
        pdf.bullets([f"{house_label(h)} ({s:+.2f}) — {house_reason(w)}"
                     for h, s, w in down])
    major = [e for e in ahead if e.kind in ("ingress", "contact")][:6]
    if major:
        pdf.para(f"Next changes among the slow planets (to {EVENTS_AHEAD_YEARS} years ahead):",
                 color=INK)
        pdf.bullets([f"{e.when:%d %b %Y} — {e.text} (H{e.house} from Lagna, ☾{e.moon_house} "
                     f"from Moon)" for e in major])

    # ── 2. Birth chart ─────────────────────────────────────────────────────
    pdf.section(110)
    pdf.h1("Birth chart", f"Birth planets, with the planets' positions on {when} as tags.")
    pdf.png(south_chart_png(chart_cells(chart, transit, retro_now), birth.name, f"transits {when}"),
            width=92)
    pdf.h2("How to read this chart")
    pdf.guide(chart_guide(birth.name, SIGNS_ML[lagna], SIGNS_ML[moon], when))
    pdf.h2("Planets at birth")
    table = []
    for p in ["Lagna"] + GRAHAS + NODES:
        n, pd_ = chart.nakshatra(p)
        d = dignity(p, chart.sign(p)) if p != "Lagna" else ""
        if d == "debilitated" and neecha_bhanga(chart, p):
            d = "neecha bhanga"
        table.append([p, SIGNS_ML[chart.sign(p)], f"{chart.deg_in_sign(p):.1f}°", f"{n}-{pd_}",
                      "—" if p == "Lagna" else f"H{chart.house(p)}",
                      "—" if p in ("Lagna", "Moon") else f"☾{chart.house(p, 'Moon')}",
                      d or "—", "℞" if retro_birth.get(p) else "",
                      "—" if p == "Lagna" else f"{lw.weights[p].total:+g}"])
    pdf.grid(["", "Sign", "Degree", "Nakshatra", "House", "☾", "Dignity", "℞", "Dasa wt"], table,
             widths=(18, 24, 16, 30, 14, 12, 30, 8, 18))
    pdf.h2("What each planet stands for here")
    pdf.bullets([f"{p} — {planet_role(chart, lw.weights[p])}" for p in GRAHAS + NODES], size=8.3)

    # ── 3. Planets in motion ───────────────────────────────────────────────
    pdf.section(70)
    pdf.h1("Planets in motion", f"Exact events for Jupiter, Saturn, Rahu and Ketu over the "
                                f"{EVENTS_AHEAD_YEARS} years from {when}.")
    pdf.para(EVENT_KINDS, size=8.3)
    if ahead:
        pdf.grid(["When (local)", "Event", "Sign", "House", "☾"],
                 [[f"{e.when:%d %b %Y, %H:%M}", e.text, SIGNS_ML[e.sign], f"H{e.house}",
                   f"☾{e.moon_house}"] for e in ahead],
                 widths=(34, 86, 26, 17, 17))

    # ── 4. Life Weather ────────────────────────────────────────────────────
    pdf.section(125)
    pdf.h1("Life Weather timeline")
    pdf.png(life_weather_png(lw, factors, pick), width=180)
    pdf.para("The top line is the overall reading (3-month average): green = supportive, red = "
             "challenging. The four lanes below explain it — Dasa, Jupiter, Saturn and Rahu/Ketu "
             "— on one colour scale, so a pale lane contributes little. Dashed lines mark each "
             f"Maha-dasa start; blue = today; dotted purple = {when}.")
    off = [LANE_TITLES[f] for f in LANE_TITLES if f not in factors]
    if off:
        pdf.para(f"Not counted in the overall line for this report: {', '.join(off)}.", color=INK)
    pdf.h2("Key stretches")
    pdf.para("Every period of three months or more where the overall line stays clearly "
             "supportive (≥ +0.5) or challenging (≤ −0.5), with the two factors pushing it "
             "most. Shorter dips and peaks are left out.", size=8.3)
    if stretches:
        pdf.grid(["From", "To", "Reading", "Mainly because of"],
                 [[f"{s.start:%b %Y}", f"{s.end:%b %Y}", f"{s.tone} ({s.mean:+.2f})",
                   "; ".join(s.drivers) or "—"] for s in stretches],
                 widths=(19, 19, 44, 98), size=7.3)

    # ── 5. Houses ──────────────────────────────────────────────────────────
    pdf.section(150)
    pdf.h1("Houses over time", "Each strip is one life area (house), counted from the Lagna, on "
                               "one shared scale.")
    pdf.png(houses_png(lw, houses_from_lagna, "Lagna", pick), width=180)
    pdf.para("Score = ½ dasa focus (the running dasa lord rules or sits in the house) + ½ transit "
             "touch (Jupiter adds; Saturn, Rahu and Ketu subtract except in houses 3, 6 and 11; "
             "sitting in a house counts fully, an aspect half).")
    pdf.h2(f"Houses on {when}")
    pdf.grid(["House", "Life area", "Sign", "Ruler (sits in, weight)", "Born with",
              "Passing through", "☾"],
             [[f"H{r.house}", r.area, SIGNS_ML[r.sign], f"{r.lord} (H{r.lord_house}, "
               f"{r.lord_weight:+g})", ", ".join(r.natal) or "—",
               ", ".join(p + (" ℞" if retro_now.get(p) else "") for p in r.transit) or "—",
               str(r.house_from_moon)] for r in rows],
             widths=(13, 50, 21, 34, 24, 29, 9))

    # ── 6. Dasa ────────────────────────────────────────────────────────────
    pdf.section(70)
    pdf.h1("Dasa timeline", "Vimshottari periods from the birth Moon. The weight says how "
                            "supportive each planet's period is for this chart.")
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
        coming = [md for md in mds if md.end > pick][:3]
        pdf.h2("What the current and coming Maha-dasa lords stand for here")
        pdf.bullets([f"{md.start:%b %Y} – {md.end:%b %Y}: "
                     + dasa_sentence(chart, lw.weights[md.md], "Maha-dasa") for md in coming],
                    size=8.3)

    # ── 7. Method & glossary ───────────────────────────────────────────────
    pdf.section(70)
    pdf.h1("How this report is made")
    pdf.bullets(MODEL, size=8.3)
    pdf.para("All weights are listed in life_weather/analysis/assumptions.py; the few that are "
             "the app's own choices rather than classical rules are labelled there. Birth time is "
             f"taken as {_hours(birth.tz_hours)}.", size=8.3)
    pdf.h2("Glossary")
    pdf.grid(["Term", "Meaning"], [[t, m] for t, m in GLOSSARY], widths=(32, 148), size=8)
    pdf.h2("Please note")
    pdf.para(DISCLAIMER, size=8.5, color=INK)
    pdf.ln(4)
    pdf.set_font("DejaVu", "B", 8.5)
    pdf.set_text_color(*INK)
    pdf.cell(0, 5, f"© {date.today():%Y} {OWNER}. All rights reserved.",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 8.5)
    pdf.cell(0, 5, f"Contact: {CONTACT}", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def pdf_filename(birth: Birth, pick: date) -> str:
    safe = "".join(ch if ch.isalnum() else "-" for ch in birth.name).strip("-").lower() or "person"
    return f"life-weather-{safe}-{pick:%Y-%m-%d}.pdf"
