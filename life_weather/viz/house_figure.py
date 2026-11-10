"""Houses over time: 12 stacked green/red score strips on one shared time axis and scale."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..analysis.houses import HOUSE_AREAS
from ..analysis.timeline import LifeWeather
from .axis import year_dtick
from .figure import BAD, GOOD


def build_house_figure(lw: LifeWeather, hdf: pd.DataFrame, houses: list[int],
                       ref: str, marker: date | None = None) -> go.Figure:
    n = len(houses)
    fig = make_subplots(rows=n, cols=1, shared_xaxes=True, vertical_spacing=0.006)
    limit = max(hdf[[f"S{h}" for h in houses]].abs().max().max(), 0.5) * 1.05
    prefix = "H" if ref == "Lagna" else "☾"

    for i, h in enumerate(houses, start=1):
        sm = hdf[f"S{h}"].to_numpy()
        for y, colour in ((np.clip(sm, 0, None), GOOD), (np.clip(sm, None, 0), BAD)):
            fig.add_trace(go.Scatter(x=hdf["date"], y=y, fill="tozeroy", mode="none",
                                     fillcolor=colour, opacity=0.75, hoverinfo="skip"),
                          row=i, col=1)
        hover = [f"<b>{prefix}{h} · {HOUSE_AREAS[h].split(',')[0]}</b> · {d:%d %b %Y}<br>"
                 f"3-month avg {s:+.2f} · this date {raw:+.2f}<br>{why.replace(' · ', '<br>')}"
                 for d, s, raw, why in zip(hdf["date"], sm, hdf[f"H{h}"], hdf[f"why{h}"])]
        fig.add_trace(go.Scatter(x=hdf["date"], y=sm, mode="lines",
                                 line=dict(color="#222", width=0.7), text=hover,
                                 hovertemplate="%{text}<extra></extra>"), row=i, col=1)
        short = HOUSE_AREAS[h].split(",")[0]
        fig.update_yaxes(range=[-limit, limit], showticklabels=False, zeroline=True,
                         zerolinecolor="#999", zerolinewidth=0.6, showgrid=False, row=i, col=1)
        fig.add_annotation(x=0, xref="paper", y=0.5, yref=f"y{'' if i == 1 else i} domain",
                           text=f"<b>{prefix}{h}</b> {short}", showarrow=False, xanchor="right",
                           xshift=-6, font=dict(size=11, color="#334155"))

    first, last = hdf["date"].iloc[0], hdf["date"].iloc[-1]
    for md in lw.maha_dasas:
        start = np.datetime64(md.start)
        if start > last:
            break
        x = max(start, np.datetime64(first))
        fig.add_vline(x=x, line=dict(color="grey", width=0.7, dash="dash"))
        fig.add_annotation(x=x, y=1, yref="y domain", text=f"{md.md} MD", showarrow=False,
                           xanchor="left", yanchor="bottom", font=dict(size=9, color="#555"),
                           row=1, col=1)
    if first <= pd.Timestamp(date.today()) <= last:
        fig.add_vline(x=np.datetime64(date.today()), line=dict(color="#2563eb", width=1.3))
    if marker and marker != date.today():
        fig.add_vline(x=np.datetime64(marker), line=dict(color="#7c3aed", width=1.1, dash="dot"))

    fig.update_xaxes(dtick=year_dtick(first, last), tickformat="%Y", row=n, col=1)
    fig.update_layout(height=70 * n + 70, margin=dict(l=120, r=20, t=24, b=30),
                      showlegend=False, template="plotly_white", hoverlabel=dict(align="left"))
    return fig
