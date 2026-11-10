"""South-Indian chart (signs fixed in the grid) with natal planets and a transit overlay.

`chart_cells` decides what goes in each box; the SVG here and the matplotlib version in
`report/static_charts.py` only draw it, so screen and PDF always show the same chart.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape

from ..analysis.houses import BODIES
from ..core.chart import Chart, house_between, sign_of
from ..core.constants import SIGNS_ML

# sign index → (row, col) in the fixed 4×4 South-Indian grid
GRID = {11: (0, 0), 0: (0, 1), 1: (0, 2), 2: (0, 3), 3: (1, 3), 4: (2, 3),
        5: (3, 3), 6: (3, 2), 7: (3, 1), 8: (3, 0), 9: (2, 0), 10: (1, 0)}

ABBR = {"Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me", "Jupiter": "Ju",
        "Venus": "Ve", "Saturn": "Sa", "Rahu": "Ra", "Ketu": "Ke"}
PLANET_COLOURS = {   # one distinct colour per planet (Rahu ≠ Saturn)
    "Sun": "#d97706", "Moon": "#2563eb", "Mars": "#dc2626", "Mercury": "#16a34a",
    "Jupiter": "#a16207", "Venus": "#db2777", "Saturn": "#334155", "Rahu": "#7c3aed",
    "Ketu": "#0891b2",
}
LAGNA_FILL, MOON_FILL, PLAIN_FILL = "#fef9c3", "#e0f2fe", "#ffffff"
LEGEND = [("Ju 12°", "#0f172a", "birth planet"), ("Ju", PLANET_COLOURS["Jupiter"], "transit"),
          ("H10", "#0f172a", "house from Lagna"), ("☾2", "#2563eb", "house from Moon")]


@dataclass(frozen=True)
class Cell:
    sign: int
    row: int
    col: int
    house: int                          # from Lagna
    moon_house: int
    natal: tuple[str, ...]              # e.g. "Asc 26°", "Ju 12°"
    transit: tuple[tuple[str, str], ...]  # (planet, tag) e.g. ("Saturn", "Sa℞")
    is_lagna: bool
    is_moon: bool

    @property
    def fill(self) -> str:
        return LAGNA_FILL if self.is_lagna else MOON_FILL if self.is_moon else PLAIN_FILL


def chart_cells(chart: Chart, transit_lons: dict[str, float] | None,
                retro: dict[str, bool]) -> list[Cell]:
    """transit_lons=None draws the birth chart alone; a partial dict overlays only those planets."""
    lagna, moon = chart.sign("Lagna"), chart.sign("Moon")
    natal: dict[int, list[str]] = {s: [] for s in range(12)}
    for b in BODIES:
        natal[chart.sign(b)].append(f"{ABBR[b]} {chart.deg_in_sign(b):.0f}°")
    natal[lagna].insert(0, f"Asc {chart.deg_in_sign('Lagna'):.0f}°")
    now: dict[int, list[tuple[str, str]]] = {s: [] for s in range(12)}
    for b in (b for b in BODIES if transit_lons and b in transit_lons):
        now[sign_of(transit_lons[b])].append((b, ABBR[b] + ("℞" if retro.get(b) else "")))
    return [Cell(sign, r, c, house_between(sign, lagna), house_between(sign, moon),
                 tuple(natal[sign]), tuple(now[sign]), sign == lagna, sign == moon)
            for sign, (r, c) in GRID.items()]


def render_south_chart(chart: Chart, transit_lons: dict[str, float] | None,
                       retro: dict[str, bool], title: str, subtitle: str, cell: int = 120,
                       legend: bool = True) -> str:
    size = cell * 4
    parts = [f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg" '
             f'style="max-width:{size}px;width:100%;font-family:system-ui,sans-serif">',
             f'<rect width="{size}" height="{size}" fill="#fff" stroke="#94a3b8" stroke-width="2"/>']

    for c in chart_cells(chart, transit_lons, retro):
        x, y = c.col * cell, c.row * cell
        parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{c.fill}" '
                     f'stroke="#cbd5e1"/>')
        if c.is_lagna:   # classical Lagna marker: diagonal in the corner
            parts.append(f'<line x1="{x}" y1="{y + 22}" x2="{x + 22}" y2="{y}" stroke="#a16207" '
                         f'stroke-width="1.5"/>')
        parts.append(f'<text x="{x + 6}" y="{y + 34}" font-size="10" fill="#64748b">'
                     f'{SIGNS_ML[c.sign]}</text>')
        parts.append(f'<text x="{x + cell - 6}" y="{y + 15}" font-size="12" font-weight="700" '
                     f'text-anchor="end" fill="#0f172a">H{c.house}</text>')
        parts.append(f'<text x="{x + cell - 6}" y="{y + 28}" font-size="9.5" text-anchor="end" '
                     f'fill="#2563eb">☾{c.moon_house}</text>')

        for i, label in enumerate(c.natal):              # natal: left column, dark text
            parts.append(f'<text x="{x + 6}" y="{y + 50 + i * 13}" font-size="11" '
                         f'font-weight="600" fill="#0f172a">{escape(label)}</text>')
        for i, (planet, tag) in enumerate(c.transit):    # transit: right column, coloured chips
            cx, cy = x + cell - 40, y + 39 + i * 15
            parts.append(f'<rect x="{cx}" y="{cy}" width="34" height="13" rx="3" '
                         f'fill="{PLANET_COLOURS[planet]}"/>'
                         f'<text x="{cx + 17}" y="{cy + 10}" font-size="9.5" font-weight="700" '
                         f'text-anchor="middle" fill="#fff">{escape(tag)}</text>')

    m = cell
    parts.append(f'<rect x="{m}" y="{m}" width="{2 * m}" height="{2 * m}" fill="#f8fafc" '
                 f'stroke="#cbd5e1"/>')
    parts.append(f'<text x="{2 * m}" y="{1.75 * m}" font-size="17" font-weight="700" '
                 f'text-anchor="middle" fill="#0f172a">{escape(title)}</text>')
    parts.append(f'<text x="{2 * m}" y="{1.75 * m + 22}" font-size="12" text-anchor="middle" '
                 f'fill="#475569">{escape(subtitle)}</text>')
    for i, (sym, col, text) in enumerate(LEGEND if legend else []):
        ly = 2.25 * m + i * 16
        parts.append(f'<text x="{1.25 * m}" y="{ly}" font-size="10.5" font-weight="700" '
                     f'fill="{col}">{escape(sym)}</text><text x="{1.25 * m + 38}" y="{ly}" '
                     f'font-size="10.5" fill="#475569">{text}</text>')
    parts.append("</svg>")
    return "".join(parts)
