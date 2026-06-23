"""
South-Indian style (fixed-sign) Vedic chart rendered as inline SVG.

Grid layout (signs fixed, not house-relative):
   Meena(11)  Medam(0)   Edavam(1)  Mithuna(2)
   Kumba(10)  ┌──────────────────┐  Karkata(3)
   Makara(9)  │      CENTER      │  Chingam(4)
   Dhanu(8)   Vrischika(7) Tula(6)  Kanni(5)
"""

from astro_core import RASIS

GRID_POS = {
    11: (0, 0), 0: (0, 1), 1: (0, 2), 2: (0, 3),
    10: (1, 0),                         3: (1, 3),
     9: (2, 0),                         4: (2, 3),
     8: (3, 0), 7: (3, 1), 6: (3, 2), 5: (3, 3),
}

PLANET_COLORS = {
    "Lag": "#7C3AED", "Moo": "#3B82F6", "Sun": "#F97316", "Mer": "#22C55E",
    "Ven": "#EC4899", "Mar": "#EF4444", "Jup": "#F59E0B", "Sat": "#8B5CF6",
    "Rah": "#A855F7", "Ket": "#06B6D4",
}


def render_chart_svg(chart, title="Rasi", highlight=None, transit=None, cell=86):
    """
    chart     : astro_core.Chart (natal)
    highlight : set of rasi indices to tint gold
    transit   : {rasi_index: [(tag, retro), ...]} overlay in boxed style
    Returns an SVG string suitable for st.markdown(..., unsafe_allow_html=True).
    """
    highlight = highlight or set()
    transit = transit or {}
    gap = 2
    size = cell * 4 + gap * 5

    parts = [
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
        f'xmlns="http://www.w3.org/2000/svg" style="font-family:Georgia,serif;">'
    ]
    parts.append(
        f'<rect x="1" y="1" width="{size-2}" height="{size-2}" '
        f'fill="#ffffff" stroke="#d4a017" stroke-width="3"/>'
    )

    def xy(r, c):
        return gap + c * (cell + gap), gap + r * (cell + gap)

    cx, cy = xy(1, 1)
    cw = cell * 2 + gap
    parts.append(
        f'<rect x="{cx}" y="{cy}" width="{cw}" height="{cw}" '
        f'fill="#f9f9f9" stroke="#e8d9a8" stroke-width="1"/>'
    )
    parts.append(
        f'<text x="{cx+cw/2}" y="{cy+cw/2-6}" text-anchor="middle" '
        f'fill="#a0522d" font-size="15" font-weight="bold">{title}</text>'
    )
    parts.append(
        f'<text x="{cx+cw/2}" y="{cy+cw/2+14}" text-anchor="middle" '
        f'fill="#bfa055" font-size="9">South Indian Chart</text>'
    )

    for idx, (r, c) in GRID_POS.items():
        x, y = xy(r, c)
        fill = "#FEF9C3" if idx in highlight else "#ffffff"
        parts.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
            f'fill="{fill}" stroke="#d9b870" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x+cell-4}" y="{y+11}" text-anchor="end" '
            f'fill="#bfa055" font-size="7.5">{RASIS[idx]}</text>'
        )
        parts.append(
            f'<text x="{x+4}" y="{y+11}" fill="#cbb06a" '
            f'font-size="7.5" font-weight="bold">{idx+1}</text>'
        )

        ty = y + 24
        for tag, retro in chart.planets_in_rasi(idx):
            col = PLANET_COLORS.get(tag, "#333")
            label = tag + ("℞" if retro else "")
            parts.append(
                f'<text x="{x+5}" y="{ty}" fill="{col}" '
                f'font-size="11" font-weight="bold">{label}</text>'
            )
            ty += 13

        for tag, retro in transit.get(idx, []):
            col = PLANET_COLORS.get(tag, "#333")
            label = "→" + tag + ("℞" if retro else "")
            parts.append(
                f'<text x="{x+cell-5}" y="{y+cell-6}" text-anchor="end" '
                f'fill="#fff" font-size="10" font-weight="bold" '
                f'style="paint-order:stroke;stroke:{col};stroke-width:7px;'
                f'stroke-linejoin:round;">{label}</text>'
            )

    parts.append("</svg>")
    return "".join(parts)
