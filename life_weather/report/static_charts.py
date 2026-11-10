"""Static (matplotlib) versions of the on-screen charts, as PNG bytes for the PDF report.
They draw the same data and colours as the Plotly / SVG versions in `viz/`."""
from __future__ import annotations

import io
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from ..analysis import assumptions as A  # noqa: E402
from ..analysis.houses import HOUSE_AREAS  # noqa: E402
from ..analysis.timeline import LifeWeather  # noqa: E402
from ..core.constants import SIGNS_ML  # noqa: E402
from ..viz.figure import BAD, GOOD, LANE_TITLES  # noqa: E402
from ..viz.south_chart import LEGEND, PLANET_COLOURS, Cell  # noqa: E402

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8})
TODAY, MARKER = "#2563eb", "#7c3aed"


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _year_axis(ax, first, last) -> None:
    span = (last - first).days / 365.25
    step = next((y for y in (1, 2, 5, 10, 20, 25, 50) if span / y <= 22), 50)
    ax.xaxis.set_major_locator(mdates.YearLocator(step))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def _markers(axes, lw: LifeWeather, first, last, marker: date | None, label_ax) -> None:
    for md in lw.maha_dasas:
        start = pd.Timestamp(md.start)
        if start > last:
            break
        x = max(start, first)
        for ax in axes:
            ax.axvline(x, color="grey", lw=0.6, ls="--")
        label_ax.text(x, 1.0, f" {md.md} MD", transform=label_ax.get_xaxis_transform(),
                      fontsize=6.5, color="#555", va="bottom")
    today = pd.Timestamp(date.today())
    if first <= today <= last:
        for ax in axes:
            ax.axvline(today, color=TODAY, lw=1.1)
    if marker and pd.Timestamp(marker) != today:
        for ax in axes:
            ax.axvline(pd.Timestamp(marker), color=MARKER, lw=1.0, ls=":")


def life_weather_png(lw: LifeWeather, factors: tuple[str, ...], marker: date | None) -> bytes:
    df = lw.frame
    x = df["date"]
    first, last = x.iloc[0], x.iloc[-1]
    fig, axes = plt.subplots(5, 1, figsize=(10, 5.6), sharex=True,
                             gridspec_kw={"height_ratios": [4, .5, .5, .5, .5], "hspace": .08})
    top = axes[0]
    sm = df["smoothed"].to_numpy()
    top.fill_between(x, sm, 0, where=sm >= 0, color=GOOD, alpha=.75, lw=0, interpolate=True)
    top.fill_between(x, sm, 0, where=sm < 0, color=BAD, alpha=.75, lw=0, interpolate=True)
    top.plot(x, sm, color="#222", lw=.6)
    top.axhline(0, color="#222", lw=.7)
    top.set_ylabel("overall")
    top.spines[["top", "right"]].set_visible(False)

    extent = [mdates.date2num(first), mdates.date2num(last), 0, 1]
    for ax, lane in zip(axes[1:], LANE_TITLES):
        on = lane in factors
        ax.imshow(df[lane].to_numpy()[None, :], aspect="auto", cmap="RdYlGn",
                  vmin=-A.LANE_RANGE, vmax=A.LANE_RANGE, extent=extent, alpha=1 if on else .15)
        ax.set_yticks([])
        ax.set_ylabel(LANE_TITLES[lane] + ("" if on else " (off)"), rotation=0, ha="right",
                      va="center", fontsize=7.5, color="#222" if on else "#999")
    _markers(axes, lw, first, last, marker, top)
    _year_axis(axes[-1], first, last)
    return _png(fig)


def houses_png(lw: LifeWeather, hdf: pd.DataFrame, ref: str, marker: date | None) -> bytes:
    x = hdf["date"]
    first, last = x.iloc[0], x.iloc[-1]
    limit = max(hdf[[f"S{h}" for h in range(1, 13)]].abs().max().max(), 0.5) * 1.05
    prefix = "H" if ref == "Lagna" else "☾"
    fig, axes = plt.subplots(12, 1, figsize=(10, 7.4), sharex=True, gridspec_kw={"hspace": .12})
    for h, ax in enumerate(axes, start=1):
        sm = hdf[f"S{h}"].to_numpy()
        ax.fill_between(x, sm, 0, where=sm >= 0, color=GOOD, alpha=.75, lw=0, interpolate=True)
        ax.fill_between(x, sm, 0, where=sm < 0, color=BAD, alpha=.75, lw=0, interpolate=True)
        ax.axhline(0, color="#999", lw=.5)
        ax.set_ylim(-limit, limit)
        ax.set_yticks([])
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.set_ylabel(f"{prefix}{h} {HOUSE_AREAS[h].split(',')[0]}", rotation=0, ha="right",
                      va="center", fontsize=7)
    _markers(axes, lw, first, last, marker, axes[0])
    _year_axis(axes[-1], first, last)
    return _png(fig)


def south_chart_png(cells: list[Cell], title: str, subtitle: str, legend: bool = True) -> bytes:
    fig, ax = plt.subplots(figsize=(5.2, 5.2))
    ax.set_xlim(0, 4)
    ax.set_ylim(4, 0)
    ax.axis("off")
    for c in cells:
        x, y = c.col, c.row
        ax.add_patch(plt.Rectangle((x, y), 1, 1, facecolor=c.fill, edgecolor="#cbd5e1", lw=.8))
        if c.is_lagna:
            ax.plot([x, x + .18], [y + .18, y], color="#a16207", lw=1.2)
        ax.text(x + .05, y + .28, SIGNS_ML[c.sign], fontsize=6.5, color="#64748b")
        ax.text(x + .95, y + .12, f"H{c.house}", fontsize=8, weight="bold", ha="right")
        ax.text(x + .95, y + .23, f"☾{c.moon_house}", fontsize=6.5, color="#2563eb", ha="right")
        for i, label in enumerate(c.natal):
            ax.text(x + .05, y + .42 + i * .11, label, fontsize=7, weight="bold", color="#0f172a")
        for i, (planet, tag) in enumerate(c.transit):
            ax.text(x + .80, y + .36 + i * .125, tag, fontsize=6.5, weight="bold", color="white",
                    ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.18", fc=PLANET_COLOURS[planet], ec="none"))
    ax.add_patch(plt.Rectangle((1, 1), 2, 2, facecolor="#f8fafc", edgecolor="#cbd5e1", lw=.8))
    ax.add_patch(plt.Rectangle((0, 0), 4, 4, fill=False, edgecolor="#94a3b8", lw=1.5))
    ax.text(2, 1.7, title, fontsize=11, weight="bold", ha="center")
    ax.text(2, 1.92, subtitle, fontsize=8, color="#475569", ha="center")
    for i, (sym, col, text) in enumerate(LEGEND if legend else []):
        ax.text(1.25, 2.25 + i * .14, sym, fontsize=7, weight="bold", color=col)
        ax.text(1.6, 2.25 + i * .14, text, fontsize=7, color="#475569")
    return _png(fig)

