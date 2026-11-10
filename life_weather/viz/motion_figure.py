"""Planets in motion — phase motion, sin(sidereal longitude): each planet's orbit as a wave.

+1 = 90° (start of Karkidakam), −1 = 270° (start of Makaram). Diamonds mark retrograde samples;
stars pin each planet's position on the chosen date, with a dashed line at that date.
"""
from __future__ import annotations

from datetime import date, datetime, time

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..core.chart import sign_of
from ..core.constants import SIGNS_ML
from .south_chart import PLANET_COLOURS

DATE_LINE = "#a0522d"


def _break_wraps(lon: np.ndarray) -> np.ndarray:
    """NaN where a planet wraps 360°→0° (or back), so a longitude line doesn't streak across."""
    y = lon.astype(float).copy()
    jumps = np.abs(np.diff(y)) > 180
    y[1:][jumps] = np.nan
    return y


def phase(lon) -> np.ndarray:
    return np.sin(np.radians(np.asarray(lon, dtype=float)))


def build_motion_figure(sdf: pd.DataFrame, pick: date, now: dict[str, float],
                        retro_now: dict[str, bool]) -> go.Figure:
    fig = go.Figure()
    for body, g in sdf.groupby("body", sort=False):
        g = g.sort_values("date")
        col = PLANET_COLOURS[body]
        signs = [SIGNS_ML[int(v // 30)] for v in g["lon"]]
        fig.add_trace(go.Scatter(
            x=g["date"], y=phase(g["lon"]), mode="lines", name=body, legendgroup=body,
            line=dict(color=col, width=2), customdata=signs,
            hovertemplate=f"{body} · %{{customdata}}<extra></extra>",
        ))
        retro = g[g["retro"]]
        if not retro.empty:
            fig.add_trace(go.Scatter(
                x=retro["date"], y=phase(retro["lon"]), mode="markers", legendgroup=body,
                showlegend=False, hoverinfo="skip",
                marker=dict(color=col, symbol="diamond", size=5,
                            line=dict(color="white", width=0.5)),
            ))

    x0 = datetime.combine(pick, time(12))
    fig.add_vline(x=x0, line=dict(color=DATE_LINE, width=1.5, dash="dash"))
    for body, lon in now.items():
        fig.add_trace(go.Scatter(
            x=[x0], y=[float(phase(lon))], mode="markers", legendgroup=body, showlegend=False,
            marker=dict(color=PLANET_COLOURS[body], symbol="star-diamond", size=13,
                        line=dict(color="#3a2410", width=1)),
            hovertemplate=f"★ {body} · {SIGNS_ML[sign_of(lon)]}"
                          + (" ℞" if retro_now.get(body) else "") + "<extra></extra>",
        ))

    fig.update_xaxes(tickformat="%b %Y", rangeslider=dict(visible=True, thickness=0.06),
                     rangeselector=dict(buttons=[
                         dict(count=6, label="6m", step="month", stepmode="backward"),
                         dict(count=1, label="1y", step="year", stepmode="backward"),
                         dict(count=5, label="5y", step="year", stepmode="backward"),
                         dict(step="all", label="All"),
                     ], bgcolor="#f8f8f8", activecolor="#d4a017"))
    fig.update_yaxes(range=[-1.15, 1.15], tickvals=[-1, -0.5, 0, 0.5, 1])
    fig.update_layout(
        title=dict(text="Phase motion  ·  sin(sidereal longitude)  ·  ★ = chosen date",
                   x=0, xanchor="left", font=dict(size=14)),
        height=520, hovermode="x unified", template="plotly_white",
        font=dict(family="Georgia, serif", color="#3a2410"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=20, t=80, b=20),
    )
    return fig
