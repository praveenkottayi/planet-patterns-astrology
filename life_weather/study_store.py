"""Local storage for one person's study data: year ratings, events and a log of runs.

Kept in the repo's `study/` folder (gitignored) — this is private life data and never committed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from .analysis.study import AREAS

STUDY_DIR = Path(__file__).resolve().parent.parent / "study"
EVENT_COLUMNS = ["date", "category", "valence", "note"]


def _path(name: str, root: Path = STUDY_DIR) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "person"
    return root / f"{slug}.json"


def load(name: str, root: Path = STUDY_DIR) -> dict:
    p = _path(name, root)
    data = json.loads(p.read_text()) if p.exists() else {}
    ratings = pd.DataFrame(data.get("ratings", []), columns=["year"] + AREAS)
    events = pd.DataFrame(data.get("events", []), columns=EVENT_COLUMNS)
    if len(events):
        events["date"] = pd.to_datetime(events["date"]).dt.date
    return {"ratings": ratings, "events": events, "runs": data.get("runs", [])}


def save(name: str, ratings: pd.DataFrame, events: pd.DataFrame, runs: list[dict],
         root: Path = STUDY_DIR) -> Path:
    root.mkdir(exist_ok=True)
    rated = ratings.dropna(subset=AREAS, how="all")
    ev = events.dropna(subset=["date"]).copy()
    ev["date"] = pd.to_datetime(ev["date"]).dt.strftime("%Y-%m-%d")
    data = {
        "ratings": [{k: (None if pd.isna(v) else (int(v) if k == "year" else float(v)))
                     for k, v in row.items()} for row in rated.to_dict("records")],
        "events": [{k: (None if pd.isna(v) else v) for k, v in row.items()}
                   for row in ev[EVENT_COLUMNS].to_dict("records")],
        "runs": runs,
    }
    p = _path(name, root)
    p.write_text(json.dumps(data, indent=2, default=str))
    p.chmod(0o600)
    return p
