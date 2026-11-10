"""Sidebar: person (saved profile or new, by city), factors, options, and the detail date."""
from __future__ import annotations

from datetime import date, datetime, time

import streamlit as st

from ..core.chart import Birth
from ..places import search_cities, uses_local_mean_time, utc_offset_hours
from ..profiles import load_profiles, save_profile, saving_allowed
from ..viz.figure import LANE_TITLES

NEW = "➕ New person…"
EARLIEST_BIRTH = date(1800, 1, 1)
LIFESPAN_YEARS = 120            # longest "show until" offered after the birth year


def end_year_range(birth_year: int) -> tuple[int, int, int]:
    """(min, max, default) for the 'Show until' slider, following the birth year."""
    lo = birth_year + 1
    hi = max(birth_year + LIFESPAN_YEARS, date.today().year + 20)
    default = min(max(2045, date.today().year + 20, birth_year + 20), hi)
    return lo, hi, default


def _new_person() -> Birth:
    name = st.text_input("Name", "New person")
    d = st.date_input("Birth date", date(2000, 1, 1), min_value=EARLIEST_BIRTH,
                      max_value=date.today(), format="YYYY-MM-DD",
                      help="Any date from 1800 up to today — newborns included.")
    t = st.time_input("Birth time (local)", time(12, 0), step=60)
    when = datetime.combine(d, t)

    query = st.text_input("Birth city", "Chennai",
                          help="Offline city list (GeoNames); old names like Madras or Bombay work too.")
    matches = search_cities(query)
    place = (st.selectbox("Matches", matches, format_func=lambda p: p.label,
                          label_visibility="collapsed") if matches else None)
    if query and not matches:
        st.caption("No city found — set coordinates below.")

    with st.expander("Set coordinates manually", expanded=place is None):
        manual = st.checkbox("Use these instead of the city", value=place is None)
        lat = st.number_input("Latitude (N +)", value=place.lat if place else 10.0,
                              format="%.4f", disabled=not manual)
        lon = st.number_input("Longitude (E +)", value=place.lon if place else 76.0,
                              format="%.4f", disabled=not manual)
        tz_manual = st.number_input("UTC offset at birth (hours)", step=0.5, disabled=not manual,
                                    value=utc_offset_hours(place.tz_name, when, place.lon) if place else 5.5)

    if place and not manual:
        tz = utc_offset_hours(place.tz_name, when, place.lon)
        if uses_local_mean_time(place.tz_name, when):
            st.caption(f"Before standard time: using {place.name}'s local mean time, "
                       f"**{tz:+.3f} h** (longitude ÷ 15).")
        else:
            st.caption(f"UTC offset on that date: **{tz:+g} h** ({place.tz_name}) — "
                       f"includes daylight saving and historical changes.")
        return Birth(name, when, tz, place.lat, place.lon, f"{place.name}, {place.country}")
    return Birth(name, when, tz_manual, lat, lon, query.strip())


def _save_button(birth: Birth) -> None:
    """Save the person being entered into the local .env, then switch to them."""
    if not saving_allowed():
        return
    if not birth.name.strip() or birth.name.strip() == "New person":
        st.caption("Give the person a name to save them to your profiles.")
        return
    if st.button("💾 Save to my profiles", use_container_width=True,
                 help="Adds this person to your local .env (never committed). "
                      "Saving the same name again updates their details."):
        key, updated = save_profile(birth)
        st.session_state["select_profile"] = birth.name.strip()
        st.session_state["saved_note"] = (f"{'Updated' if updated else 'Saved'} "
                                          f"{birth.name.strip()} ({key}) in .env")
        st.rerun()


def person_and_options() -> tuple[Birth, tuple[str, ...], int, str]:
    profiles = load_profiles()
    with st.sidebar:
        st.header("Person")
        options = [p.label for p in profiles] + [NEW]
        wanted = st.session_state.pop("select_profile", None)     # just saved → select them
        choice = st.selectbox("Profile", options,
                              index=options.index(wanted) if wanted in options else 0,
                              help="Your own people come from the local .env file (never "
                                   "committed); '· example' entries are public figures.")
        if note := st.session_state.pop("saved_note", None):
            st.success(note)
        if choice == NEW:
            birth = _new_person()
            _save_button(birth)
        else:
            profile = next(p for p in profiles if p.label == choice)
            birth = profile.birth
            if profile.note:
                st.caption(f"ℹ️ {profile.note}")

        st.header("Factors in the overall line")
        factors = tuple(lane for lane, label in LANE_TITLES.items()
                        if st.checkbox(label, value=True, key=f"f_{lane}"))
        st.caption("Unticked factors count as zero; the formula is not rebalanced.")

        st.header("Options")
        lo, hi, default = end_year_range(birth.when_local.year)
        end_year = st.slider("Show until", lo, hi, default)
        node = st.radio("Rahu/Ketu", ["mean", "true"], horizontal=True,
                        help="Mean node is the classical default and what the reference values use.")
    return birth, factors, end_year, node


def detail_date(first: date, last: date) -> date:
    with st.sidebar:
        st.header("Date for details")
        return st.date_input("Date", min(max(date.today(), first), last),
                             min_value=first, max_value=last,
                             help="Drives the 'why' panel, the transit chart and the purple line.")
