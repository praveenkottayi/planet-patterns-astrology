from __future__ import annotations
from itertools import combinations
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from astro_core import angular_separation

PLOTLY_COLORS = {
    "Jupiter": "#F59E0B", "Saturn": "#8B5CF6", "Rahu": "#A855F7",
    "Ketu": "#06B6D4", "Mars": "#EF4444", "Venus": "#EC4899",
    "Mercury": "#22C55E", "Sun": "#F97316", "Moon": "#3B82F6",
}


HOUSE_COLORS = [
    "#EF4444", "#F97316", "#F59E0B", "#EAB308",
    "#84CC16", "#22C55E", "#06B6D4", "#3B82F6",
    "#8B5CF6", "#A855F7", "#EC4899", "#F43F5E",
]

PLANET_SIGNIFICANCE = {
    "Jupiter": 3.0, "Saturn": 3.0, "Rahu": 2.5, "Ketu": 2.5,
    "Mars": 2.0, "Sun": 1.2, "Mercury": 1.0, "Venus": 1.0, "Moon": 0.8,
}


def _color(planet: str) -> str:
    return PLOTLY_COLORS.get(planet, "#666666")


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def rows_to_frame(rows) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["planet", "when_local"]).reset_index(drop=True)
    return df


def build_motion_figure(df: pd.DataFrame, transit_dt=None,
                        transit_snapshot: pd.DataFrame | None = None,
                        title="Planetary Motion"):
    """
    Two stacked subplots:
      top    — sin(sidereal longitude): smooth oscillating phase, diamonds on retrograde samples
      bottom — raw sidereal longitude 0–360° with translucent fill
    Optional vertical line + star markers pin the transit date on both panels.
    """
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
        subplot_titles=("Phase motion  ·  sin(sidereal longitude)",
                        "Sidereal longitude (0–360°)"),
    )

    for planet, g in df.groupby("planet"):
        col = _color(planet)
        fig.add_trace(go.Scatter(
            x=g["when_local"], y=g["phase_sin"], mode="lines",
            name=planet, legendgroup=planet, line=dict(color=col, width=2),
            hovertemplate=f"<b>{planet}</b><br>%{{x|%d %b %Y}}<br>sin φ = %{{y:.3f}}<extra></extra>",
        ), row=1, col=1)

        retro = g[g["retro"]]
        if not retro.empty:
            fig.add_trace(go.Scatter(
                x=retro["when_local"], y=retro["phase_sin"], mode="markers",
                name=f"{planet} ℞", legendgroup=planet, showlegend=False,
                marker=dict(color=col, symbol="diamond", size=5,
                            line=dict(color="white", width=0.5)),
                hovertemplate=f"<b>{planet} retrograde</b><br>%{{x|%d %b %Y}}<extra></extra>",
            ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=g["when_local"], y=g["longitude"], mode="lines",
            name=planet, legendgroup=planet, showlegend=False,
            line=dict(color=col, width=1.5),
            fill="tozeroy", fillcolor=_rgba(col, 0.06),
            hovertemplate=f"<b>{planet}</b><br>%{{x|%d %b %Y}}<br>%{{y:.1f}}°<extra></extra>",
        ), row=2, col=1)

    if transit_dt is not None:
        for r in (1, 2):
            fig.add_vline(x=transit_dt,
                          line=dict(color="#a0522d", width=1.5, dash="dash"),
                          row=r, col=1)

    if transit_snapshot is not None and not transit_snapshot.empty:
        for _, rr in transit_snapshot.iterrows():
            col = _color(rr["planet"])
            kw = dict(color=col, symbol="star-diamond", size=13,
                      line=dict(color="#3a2410", width=1))
            fig.add_trace(go.Scatter(
                x=[transit_dt], y=[rr["phase_sin"]], mode="markers",
                name=f"{rr['planet']} now", legendgroup=rr["planet"], showlegend=False,
                marker=kw,
                hovertemplate=f"<b>{rr['planet']} (transit)</b><br>{rr['rasi']} {rr['deg_in_rasi']:.1f}°<extra></extra>",
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=[transit_dt], y=[rr["longitude"]], mode="markers",
                name=f"{rr['planet']} now", legendgroup=rr["planet"], showlegend=False,
                marker=kw,
                hovertemplate=f"<b>{rr['planet']} (transit)</b><br>%{{y:.1f}}°<extra></extra>",
            ), row=2, col=1)

    fig.update_xaxes(tickformat="%b %Y")
    fig.update_xaxes(
        rangeslider=dict(visible=True, thickness=0.06), row=2, col=1,
        rangeselector=dict(
            buttons=[
                dict(count=6, label="6m", step="month", stepmode="backward"),
                dict(count=1, label="1y", step="year", stepmode="backward"),
                dict(count=5, label="5y", step="year", stepmode="backward"),
                dict(step="all", label="All"),
            ],
            bgcolor="#f8f8f8", activecolor="#d4a017",
        ),
    )
    fig.update_yaxes(range=[-1.15, 1.15], row=1, col=1)
    fig.update_yaxes(range=[0, 360], dtick=60, row=2, col=1)
    fig.update_layout(
        title=dict(text=title, y=0.98, x=0, xanchor="left", font=dict(size=14)),
        height=620, hovermode="x unified",
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(family="Georgia, serif", color="#3a2410"),
        legend=dict(orientation="h", yanchor="top", y=1.12, xanchor="left", x=0),
        margin=dict(l=50, r=20, t=70, b=20),
    )
    return fig


def build_interaction_figure(df: pd.DataFrame, transit_dt=None,
                             title="Pairwise Angular Separation"):
    """
    Angular separation (0–180°) for every planet pair.
    Gold band = conjunction zone (≤12°), orange band = opposition (≥168°).
    """
    planets = sorted(df["planet"].unique())
    fig = go.Figure()

    fig.add_hrect(y0=0, y1=12, fillcolor="#d4a017", opacity=0.15,
                  line_width=0, annotation_text="conjunction",
                  annotation_position="top left")
    fig.add_hrect(y0=168, y1=180, fillcolor="#e8772e", opacity=0.15,
                  line_width=0, annotation_text="opposition",
                  annotation_position="bottom left")

    wide = df.pivot_table(index="when_local", columns="planet", values="longitude")
    for a, b in combinations(planets, 2):
        if a not in wide or b not in wide:
            continue
        sep = wide.apply(lambda r: angular_separation(r[a], r[b]), axis=1)
        fig.add_trace(go.Scatter(
            x=wide.index, y=sep.values, mode="lines", name=f"{a}–{b}",
            line=dict(width=1.8),
            hovertemplate=f"<b>{a}–{b}</b><br>%{{x|%d %b %Y}}<br>%{{y:.1f}}°<extra></extra>",
        ))

    if transit_dt is not None:
        fig.add_vline(x=transit_dt,
                      line=dict(color="#a0522d", width=1.5, dash="dash"))

    fig.update_yaxes(range=[0, 180], dtick=30, title="separation (°)")
    fig.update_layout(
        title=title, height=420, hovermode="x unified",
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(family="Georgia, serif", color="#3a2410"),
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="left", x=0),
        margin=dict(l=50, r=20, t=70, b=20),
    )
    return fig


def closest_passes(df: pd.DataFrame, top_n=3) -> pd.DataFrame:
    """Top-N closest-approach dates per planet pair (minimum angular separation)."""
    planets = sorted(df["planet"].unique())
    wide = df.pivot_table(index="when_local", columns="planet", values="longitude")
    out = []
    for a, b in combinations(planets, 2):
        if a not in wide or b not in wide:
            continue
        sep = wide.apply(lambda r: angular_separation(r[a], r[b]), axis=1)
        for when, val in sep.nsmallest(top_n).items():
            out.append({"Pair": f"{a}–{b}", "Date": when.strftime("%d %b %Y"),
                        "Separation": f"{val:.1f}°", "_sortval": val})
    res = pd.DataFrame(out)
    if not res.empty:
        res = res.sort_values(["Pair", "_sortval"]).drop(columns="_sortval")
    return res


def build_house_activation_figure(house_planet_map: dict, house_keywords: dict):
    """
    Horizontal bar chart showing each house's current activation weight.
    house_planet_map: {house_number (1-12): [planet_name, ...]}
    """
    houses = list(range(12, 0, -1))  # H12 at top so H1 ends up at the bottom-left
    weights = [
        sum(PLANET_SIGNIFICANCE.get(p, 1) for p in house_planet_map.get(h, []))
        for h in houses
    ]
    labels = [", ".join(house_planet_map.get(h, [])) or "·" for h in houses]
    y_labels = [f"H{h} · {house_keywords.get(h, '')}" for h in houses]
    bar_colors = [HOUSE_COLORS[(h - 1) % 12] for h in houses]

    fig = go.Figure(go.Bar(
        x=weights,
        y=y_labels,
        orientation="h",
        text=labels,
        textposition="auto",
        marker_color=bar_colors,
        marker_opacity=0.85,
        hovertemplate="<b>%{y}</b><br>Planets: %{text}<br>Score: %{x:.1f}<extra></extra>",
    ))
    fig.update_layout(
        title="Current house activation (weighted by planet significance)",
        height=420,
        xaxis=dict(title="Activation score", showgrid=True, gridcolor="#eeeeee", zeroline=True),
        yaxis=dict(showgrid=False, tickfont=dict(size=11)),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(family="Georgia, serif", color="#3a2410"),
        margin=dict(l=175, r=20, t=55, b=40),
    )
    return fig


def build_house_journey_figure(df: pd.DataFrame, asc_rasi_index: int,
                                transit_dt=None, house_keywords: dict | None = None):
    """
    Step chart: which house (1-12) each planet occupies over time.
    Each planet is a colored step line; dashed vertical = transit date.
    """
    house_keywords = house_keywords or {}
    fig = go.Figure()

    for h in range(1, 13):
        fig.add_hrect(
            y0=h - 0.45, y1=h + 0.45,
            fillcolor=HOUSE_COLORS[(h - 1) % 12],
            opacity=0.07, line_width=0,
        )

    for planet, g in df.groupby("planet"):
        col = PLOTLY_COLORS.get(planet, "#666")
        g = g.sort_values("when_local")
        house_series = ((g["longitude"] // 30).astype(int) - asc_rasi_index) % 12 + 1
        fig.add_trace(go.Scatter(
            x=g["when_local"], y=house_series,
            mode="lines",
            name=planet,
            line=dict(color=col, width=3, shape="hv"),
            hovertemplate=f"<b>{planet}</b><br>%{{x|%d %b %Y}}<br>House %{{y}}<extra></extra>",
        ))

    if transit_dt is not None:
        fig.add_vline(x=transit_dt, line=dict(color="#a0522d", width=1.5, dash="dash"),
                      annotation_text="today", annotation_position="top right",
                      annotation_font_color="#a0522d")

    y_tick_labels = [f"H{h} · {house_keywords.get(h, '')}" for h in range(1, 13)]
    fig.update_yaxes(
        tickmode="array",
        tickvals=list(range(1, 13)),
        ticktext=y_tick_labels,
        range=[0.5, 12.5],
        autorange="reversed",
    )
    fig.update_layout(
        title="Planet journeys through your 12 houses",
        height=520,
        hovermode="x unified",
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(family="Georgia, serif", color="#3a2410"),
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="left", x=0),
        margin=dict(l=185, r=20, t=70, b=40),
    )
    return fig


def build_sinwave_house_figure(df: pd.DataFrame, planet_name: str,
                                asc_rasi_index: int, transit_dt=None,
                                house_keywords: dict | None = None):
    """
    Phase wave sin(longitude) for one planet with colored vertical bands
    showing which of the user's houses the planet occupies at each time.
    """
    house_keywords = house_keywords or {}
    g = df[df["planet"] == planet_name].sort_values("when_local").copy()
    if g.empty:
        return go.Figure()

    col = PLOTLY_COLORS.get(planet_name, "#666")
    g["house"] = ((g["longitude"] // 30).astype(int) - asc_rasi_index) % 12 + 1

    fig = go.Figure()

    # Colored vertical bands per house occupancy period
    prev_h: int | None = None
    seg_start = None
    for _, row in g.iterrows():
        h = int(row["house"])
        t = row["when_local"]
        if h != prev_h:
            if prev_h is not None:
                fig.add_vrect(
                    x0=seg_start, x1=t,
                    fillcolor=HOUSE_COLORS[(prev_h - 1) % 12],
                    opacity=0.18, line_width=0,
                    annotation_text=f"H{prev_h}",
                    annotation_position="top left",
                    annotation_font_size=8,
                    annotation_font_color=HOUSE_COLORS[(prev_h - 1) % 12],
                )
            seg_start = t
            prev_h = h
    if prev_h is not None and seg_start is not None:
        fig.add_vrect(
            x0=seg_start, x1=g["when_local"].iloc[-1],
            fillcolor=HOUSE_COLORS[(prev_h - 1) % 12],
            opacity=0.18, line_width=0,
            annotation_text=f"H{prev_h}",
            annotation_position="top left",
            annotation_font_size=8,
            annotation_font_color=HOUSE_COLORS[(prev_h - 1) % 12],
        )

    fig.add_trace(go.Scatter(
        x=g["when_local"], y=g["phase_sin"],
        mode="lines", name=planet_name,
        line=dict(color=col, width=2.5),
        hovertemplate=(
            f"<b>{planet_name}</b><br>%{{x|%d %b %Y}}<br>"
            "sin φ = %{y:.3f}<extra></extra>"
        ),
    ))

    retro = g[g["retro"]]
    if not retro.empty:
        fig.add_trace(go.Scatter(
            x=retro["when_local"], y=retro["phase_sin"],
            mode="markers", name="℞ periods",
            marker=dict(color=col, symbol="diamond", size=7,
                        line=dict(color="white", width=1)),
        ))

    if transit_dt is not None:
        fig.add_vline(x=transit_dt, line=dict(color="#a0522d", width=1.5, dash="dash"),
                      annotation_text="today", annotation_position="top right",
                      annotation_font_color="#a0522d")

    fig.update_yaxes(range=[-1.15, 1.15], title="sin(sidereal longitude)",
                     zeroline=True, zerolinecolor="#dddddd")
    fig.update_layout(
        title=f"{planet_name} · phase wave coloured by your house",
        height=380,
        hovermode="x",
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(family="Georgia, serif", color="#3a2410"),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="left", x=0),
        margin=dict(l=60, r=20, t=65, b=40),
    )
    return fig
