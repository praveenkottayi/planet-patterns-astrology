"""Tab: your life events set against the chart (dasa, transits, named conditions), with an
optional blind check of year ratings against chance."""
from __future__ import annotations

import re
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .. import study_store
from ..analysis.study import (AREAS, EVENT_CATEGORIES, LIFE_AREAS, MIN_EVENTS, MIN_YEARS,
                              model_version, now_stamp, run_study, with_computed_overall)
from ..analysis.events_explained import explain, themes
from ..profiles import private_profiles
from .state import View

RULES = """
For the check against chance, **fill this in before you look at your Life Weather chart** — once you've seen the green and red
stretches, memory starts bending to fit them. Use diaries, photos, old messages; ask family.

- Rate each year's life areas from **−2** (very hard) to **+2** (very good). **Leave a cell
  blank if unsure** — a blank is better than a guess. Overall is computed from these.
- Rate what the year was *like for you*, not what you think the planets were doing.
**What the check does:** it asks whether *your* chart fits your ratings better than the charts
of people born on other dates (500 random charts, same ratings). Nothing in the model is
adjusted to fit you. A "not distinguishable from chance" result is a real, useful answer.
"""

HOW_TO_READ = """
- **Beats random charts** — how many of 500 random birth charts your own chart beats on that
  test. Around 50% is what luck gives; 95%+ is unusual.
- **Chance p** — the probability of doing this well by luck. **Corrected p** adjusts for running
  several tests at once (otherwise one test would "pass" by luck about a third of the time).
- **Verdict** — "signal beyond chance" only when the corrected p is below 0.05.
- **Birth-time check** — the overall result recomputed with the birth time moved by up to
  ±30 minutes. A real effect shouldn't vanish or flip within that range.
- One life is a small sample: 30 rated years can show a strong pattern, but can't rule out
  a weak one.
"""


# A rating from −2 to +2, decimals allowed: "-1", "1.5", "+2", ".5", "−0.5" (Unicode minus).
RATING_PATTERN = r"^\s*$|^\s*[+\-−]?\s*(2(\.0*)?|[01](\.\d*)?|\.\d+)\s*$"   # blank allowed


def parse_rating(text) -> float:
    """'−1.5' → -1.5; blank or invalid → NaN. Values are clipped to −2 … +2."""
    if text is None or (isinstance(text, float) and np.isnan(text)):
        return np.nan
    cleaned = str(text).strip().replace("−", "-").replace(" ", "")
    if not cleaned or not re.fullmatch(RATING_PATTERN, cleaned):
        return np.nan
    return float(np.clip(float(cleaned), -2, 2))


def _as_text(value) -> str | None:
    return None if pd.isna(value) else f"{value:+g}" if value else "0"


def _empty_ratings(first: int, last: int) -> pd.DataFrame:
    return pd.DataFrame({"year": range(first, last + 1), **{a: float("nan") for a in AREAS}})


def render(v: View) -> None:
    mine = {p.birth.name for p in private_profiles()}
    if v.birth.name not in mine:
        st.info("This tab is for your own life: pick your own profile (from your local .env) "
                "in the sidebar.")
        return

    data = study_store.load(v.birth.name)
    st.subheader(f"Your life events and the chart · {v.birth.name}")
    st.caption("List events you can date; each one is set against what the dasa and the slow "
               "planets were doing at the time. Saved on this computer only (study/ folder).")

    # ── Events ──
    st.markdown("#### Your events")
    events = data["events"].copy()
    events["valence"] = events["valence"].map({1: "good", -1: "hard"})
    events = st.data_editor(
        events, num_rows="dynamic", hide_index=True, use_container_width=True, key="study_events",
        column_config={
            "date": st.column_config.DateColumn("Date", min_value=v.birth.when_local.date(),
                                                max_value=date.today()),
            "category": st.column_config.SelectboxColumn("Category", options=EVENT_CATEGORIES),
            "valence": st.column_config.SelectboxColumn("Good or hard", options=["good", "hard"]),
            "note": st.column_config.TextColumn("Note (optional)")})
    events = events.assign(valence=events["valence"].map({"good": 1, "hard": -1}))
    if st.button("💾 Save events"):
        study_store.save(v.birth.name, data["ratings"], events, data["runs"])
        st.toast("Events saved on this computer.")

    explained = explain(v.base, events)
    if explained:
        _explain_section(explained)
    else:
        st.info("Add a few events above (date, category, good or hard) to see them explained.")

    # ── Optional: year ratings and the check against chance ──
    with st.expander("Optional · rate your years and check against chance"):
        _ratings_and_study(v, data, events)


def _explain_section(explained) -> None:
    st.markdown("#### Each event, explained")
    st.dataframe(pd.DataFrame([{
        "Date": f"{e.when:%d %b %Y}",
        "Event": f"{e.category} · {'good' if e.good else 'hard'}",
        "Note": e.note,
        "Life Weather": f"{e.reading:+.2f} {'✓' if e.matches else '✗'}",
        "Dasa": e.dasa_text,
        "Saturn": e.where("Saturn"), "Jupiter": e.where("Jupiter"), "Rahu": e.where("Rahu"),
        "Conditions": "; ".join(e.conditions) or "—",
    } for e in explained]), hide_index=True, use_container_width=True,
        height=min(38 + 35 * len(explained), 460),
        column_config={"Conditions": st.column_config.TextColumn(width="large")})
    st.caption("Planets: sign · house from your Lagna (H) · house from your Moon (☾). "
               "Life Weather ✓ = its green/red reading agrees with the event being good/hard.")
    with st.expander("In words — one line per event", expanded=False):
        st.markdown("\n".join(f"- **{e.when:%d %b %Y} · {e.category}, "
                               f"{'good' if e.good else 'hard'}"
                               f"{' — ' + e.note if e.note else ''}:** {e.summary}"
                               for e in explained))

    table = themes(explained)
    if len(table):
        st.markdown("#### Recurring themes")
        st.dataframe(table, hide_index=True, use_container_width=True)
        st.caption("Dasas and conditions present around at least two of your events, split by "
                   "good and hard. This describes your history — add more events, especially "
                   "older ones, to see which themes keep holding.")


def _ratings_and_study(v: View, data: dict, events: pd.DataFrame) -> None:
    st.markdown(RULES)
    st.markdown("##### Rate your years")
    first = v.birth.when_local.year + st.number_input("Start from age", 5, 30, 12, step=1)
    base = _empty_ratings(first, date.today().year)
    saved = data["ratings"].set_index("year").astype(float)
    base = base.set_index("year")
    base.update(saved)
    shown = base.reset_index()[["year"] + LIFE_AREAS]
    for a in LIFE_AREAS:
        shown[a] = shown[a].map(_as_text).astype(object)
    edited = st.data_editor(
        shown, hide_index=True, use_container_width=True, height=420, key="study_ratings",
        column_config={"year": st.column_config.NumberColumn("Year", disabled=True, format="%d"),
                       **{a: st.column_config.TextColumn(
                           a.capitalize(), validate=RATING_PATTERN,
                           help="−2 (very hard) … +2 (very good); decimals like 1.5 are fine; "
                                "leave blank if unsure")
                          for a in LIFE_AREAS}})
    st.caption("Type a value from −2 to +2 — e.g. -1, 0.5, 1.5, +2. Leave blank if unsure. "
               "**Overall is worked out for you** as the average of the areas you rated that "
               "year.")
    ratings = edited.copy()
    for a in LIFE_AREAS:
        ratings[a] = ratings[a].map(parse_rating)
    ratings = with_computed_overall(ratings)
    if st.button("💾 Save ratings"):
        study_store.save(v.birth.name, ratings, events, data["runs"])
        st.toast("Ratings saved on this computer.")

    counts = {a: int(ratings[a].notna().sum()) for a in AREAS}
    n_events = int(events.dropna(subset=["date", "valence"]).shape[0])
    st.markdown("##### Check against chance")
    st.markdown(_readiness(counts, n_events))
    ready = any(c >= MIN_YEARS for c in counts.values()) or n_events >= MIN_EVENTS
    blind = st.checkbox("I filled in my ratings and events before looking at my Life Weather "
                        "chart", value=False)
    if st.button("🔬 Run the check", type="primary", disabled=not ready):
        with st.spinner("Comparing your chart with 500 random charts…"):
            report = run_study(v.base, ratings, events)
        runs = data["runs"] + [{
            "when": now_stamp(), "model": model_version(), "blind": blind,
            "years": counts["overall"], "rated": counts, "events": n_events,
            "results": {t.name: {"result": t.result, "beats": round(t.beats, 3),
                                 "p": round(t.p, 4), "p_adjusted": round(t.p_adjusted, 4)}
                        for t in report.tests}}]
        study_store.save(v.birth.name, ratings, events, runs)
        st.session_state["study_report"] = (v.birth.name, report)
    if not ready:
        st.caption(f"Rate at least {MIN_YEARS} years in any column, or list {MIN_EVENTS}+ "
                   "events, to run the check.")

    saved_report = st.session_state.get("study_report")
    if saved_report and saved_report[0] == v.birth.name:
        _show(saved_report[1])

    if data["runs"]:
        st.markdown(f"##### Run history ({len(data['runs'])})")
        st.dataframe(pd.DataFrame([{
            "When": r["when"], "Model version": r["model"],
            "Rated blind": "yes" if r.get("blind") else "no",
            "Years (overall)": r["years"], "Events": r["events"],
            "Overall": r["results"].get("Overall", {}).get("result", "—"),
            "Beats random": f"{r['results'].get('Overall', {}).get('beats', 0):.0%}"
            if "Overall" in r["results"] else "—",
        } for r in reversed(data["runs"])]), hide_index=True, use_container_width=True)


def _readiness(counts: dict[str, int], n_events: int) -> str:
    """Which tests will run with the data entered so far."""
    def line(label: str, have: int, need: int, tests: str) -> str:
        mark = "✅" if have >= need else "⏳"
        more = "" if have >= need else f" — {need - have} more needed"
        return f"- {mark} **{label}**: {have} {'events' if label == 'Events' else 'years'}" \
               f"{more} → {tests}"
    rows = [line("Overall (auto: years with any area rated)", counts["overall"], MIN_YEARS,
                 "overall match, Sade Sati years, good-Jupiter years, birth-time check")]
    rows += [line(a.capitalize(), counts[a], MIN_YEARS, f"{a} test") for a in AREAS[1:]]
    rows.append(line("Events", n_events, MIN_EVENTS, "events test"))
    return "Tests that will run with what you've entered (25+ years makes them much stronger):" \
           "\n\n" + "\n".join(rows)


def _show(report) -> None:
    overall = next((t for t in report.tests if t.name == "Overall"), None)
    if not report.tests:
        st.warning("No test had enough data to run.")
        return
    if not overall:
        st.info(f"The overall test was skipped — rate at least {MIN_YEARS} years (any area) "
                "to add it, along with the Sade Sati / Jupiter / birth-time checks.")
    else:
        good = overall.verdict == "signal beyond chance"
        (st.success if good else st.info)(
            f"**Overall: your chart matches your ratings better than {overall.beats:.0%} of "
            f"{report.random_charts} random charts ({overall.result}) — {overall.verdict}.**")
    st.dataframe(pd.DataFrame([{
        "Test": t.name, "Question": t.question, "Your result": t.result, "n": t.n,
        "Beats random charts": f"{t.beats:.0%}", "Chance p": f"{t.p:.3f}",
        "Corrected p": f"{t.p_adjusted:.3f}", "Verdict": t.verdict,
    } for t in report.tests]), hide_index=True, use_container_width=True)

    df = report.yearly.dropna(subset=["overall"])
    if len(df):
        fig = go.Figure()
        fig.add_bar(x=df["year"], y=df["overall"], name="your rating",
                    marker_color=["#27ae60" if v >= 0 else "#c0392b" for v in df["overall"]],
                    opacity=0.55)
        fig.add_scatter(x=df["year"], y=df["model"] * 2, name="model (scaled ×2)",
                        mode="lines+markers", line=dict(color="#222", width=1.5))
        fig.update_layout(height=320, template="plotly_white", margin=dict(l=40, r=20, t=30, b=30),
                          title=dict(text="Your ratings (bars) and the model (line), by year",
                                     font=dict(size=13)),
                          legend=dict(orientation="h", y=1.15, x=1, xanchor="right"))
        st.plotly_chart(fig, use_container_width=True)

    if report.jitter:
        st.caption("Birth-time check — overall ρ with the birth time moved: " + " · ".join(
            f"{m:+d} min {r:+.2f}" for m, r in report.jitter.items()))
    with st.expander("How to read these results"):
        st.markdown(HOW_TO_READ)
