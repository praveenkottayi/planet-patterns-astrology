"""Shared axis helpers."""
from __future__ import annotations

import pandas as pd

NICE_YEARS = (1, 2, 5, 10, 20, 25, 50)
MAX_TICKS = 30


def year_dtick(first: pd.Timestamp, last: pd.Timestamp) -> str:
    """Plotly month dtick giving at most ~MAX_TICKS year labels over the span."""
    span = max((last - first).days / 365.25, 1)
    step = next((y for y in NICE_YEARS if span / y <= MAX_TICKS), NICE_YEARS[-1])
    return f"M{12 * step}"
