"""Plotly Life Weather chart: overall score area + one colour lane per factor."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..analysis import assumptions as A
from ..analysis.timeline import LifeWeather
from .axis import year_dtick

GOOD, BAD = "#27ae60", "#c0392b"
LANE_TITLES = {"dasa": "Dasa", "jupiter": "Jupiter", "saturn": "Saturn", "nodes": "Rahu/Ketu"}
LANE_LIMIT = A.LANE_RANGE   # same colour scale for every lane, so a pale lane really matters less


def build_figure(lw: LifeWeather, factors: tuple[str, ...] = tuple(LANE_TITLES),
                 today: date | None = None, marker: date | None = None) -> go.Figure:
    df = lw.frame
    lanes = list(LANE_TITLES)
    fig = make_subplots(rows=1 + len(lanes), cols=1, shared_xaxes=True, vertical_spacing=0.012,
                        row_heights=[0.64] + [0.09] * len(lanes))

    # ─── Overall score ──────────────────────────────────────────────────
    sm = df["smoothed"].to_numpy()
    for y, colour, name in ((np.clip(sm, 0, None), GOOD, "supportive"),
                            (np.clip(sm, None, 0), BAD, "challenging")):
        fig.add_trace(go.Scatter(x=df["date"], y=y, fill="tozeroy", mode="none",
                                 fillcolor=colour, opacity=0.75, name=name, hoverinfo="skip"),
                      row=1, col=1)

    why_cols = [f"why_{lane}" for lane in LANE_TITLES if lane in factors]
    hover = [
        f"<b>{r.date:%d %b %Y}</b> · overall {s:+.2f} (3-month avg) · this date {r.score:+.2f}<br>"
        + "<br>".join(("Dasa: " if c == "why_dasa" else "") + getattr(r, c) for c in why_cols)
        for r, s in zip(df.itertuples(), sm)
    ]
    fig.add_trace(go.Scatter(
        x=df["date"], y=sm, mode="lines", line=dict(color="#222", width=1), name="overall",
        text=hover, hovertemplate="%{text}<extra></extra>",
    ), row=1, col=1)
    fig.add_hline(y=0, line=dict(color="#222", width=0.8), row=1, col=1)

    # ─── Lanes ──────────────────────────────────────────────────────────
    for i, lane in enumerate(lanes, start=2):
        on = lane in factors
        fig.add_trace(go.Heatmap(
            x=df["date"], z=[df[lane]], text=[df[f"why_{lane}"]],
            colorscale="RdYlGn", zmin=-LANE_LIMIT, zmax=LANE_LIMIT, showscale=False,
            opacity=1.0 if on else 0.15,
            hovertemplate="<b>%{x|%d %b %Y}</b><br>%{text}"
                          + ("" if on else "<br><i>(not in overall)</i>") + "<extra></extra>",
        ), row=i, col=1)
        fig.update_yaxes(showticklabels=False, row=i, col=1,
                         title_text=LANE_TITLES[lane] + ("" if on else " (off)"),
                         title_font=dict(size=11, color="#222" if on else "#aaa"))

    # ─── Maha-dasa starts and today ─────────────────────────────────────
    first, last = df["date"].iloc[0], df["date"].iloc[-1]
    for md in lw.maha_dasas:
        start = np.datetime64(md.start)
        if start > last:
            break
        x = max(start, np.datetime64(first))
        fig.add_vline(x=x, line=dict(color="grey", width=0.8, dash="dash"))
        fig.add_annotation(x=x, y=1, yref="y domain", text=f"{md.md} MD", showarrow=False,
                           xanchor="left", yanchor="top", font=dict(size=10, color="#555"),
                           row=1, col=1)

    today = today or date.today()
    if first <= pd.Timestamp(today) <= last:     # don't stretch the axis to reach today
        fig.add_vline(x=np.datetime64(today), line=dict(color="#2563eb", width=1.5))
        fig.add_annotation(x=np.datetime64(today), y=0, yref="y domain", text="today",
                           showarrow=False, xanchor="left", yanchor="bottom",
                           font=dict(size=10, color="#2563eb"), row=1, col=1)

    if marker and marker != today:   # date chosen for the details / chart tab
        fig.add_vline(x=np.datetime64(marker), line=dict(color="#7c3aed", width=1.2, dash="dot"))

    fig.update_yaxes(title_text="overall", zeroline=False, row=1, col=1)
    fig.update_xaxes(dtick=year_dtick(first, last), tickformat="%Y", row=1 + len(lanes), col=1)
    fig.update_layout(height=640, margin=dict(l=70, r=20, t=20, b=30), showlegend=False,
                      template="plotly_white", hoverlabel=dict(align="left"))
    return fig
