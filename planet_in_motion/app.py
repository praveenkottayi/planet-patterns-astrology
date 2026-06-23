from datetime import datetime, date, time, timedelta
import math
import tomllib
from pathlib import Path
import pandas as pd
import requests
import streamlit as st

from astro_core import (
    build_chart, vimshottari_periods, current_dasa,
    dignity, functional_nature, planetary_timeseries,
    lagna_house_map, planet_lordships,
    RASIS, RASIS_EN, SHORT, PLANETS,
    HOUSE_KEYWORDS, HOUSE_SIGNIFICATIONS, GOAL_HOUSES,
)
from chart_render import render_chart_svg
from motion_viz import (
    rows_to_frame, build_motion_figure, build_interaction_figure,
    closest_passes,
    build_house_activation_figure, build_house_journey_figure,
    build_sinwave_house_figure,
)

# ─── Config ───────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    cfg_path = Path(__file__).parent / "config.toml"
    if cfg_path.exists():
        with open(cfg_path, "rb") as f:
            return tomllib.load(f)
    return {}


_CFG    = _load_config()
_PERSON = _CFG.get("person", {})
_BIRTH  = _CFG.get("birth", {})

APP_MIN_DATE = date(1900, 1, 1)
APP_MAX_DATE = date(2100, 12, 31)
ALL_PLANETS  = list(PLANETS.keys()) + ["Ketu"]

# Slow movers are the most useful for timing windows; fast planets complete
# all 12 houses in under a year so they're less meaningful for the scanner.
SLOW_PLANETS = ["Jupiter", "Saturn", "Rahu", "Ketu"]

# Quality label → light background tint for dasa table rows
_QUALITY_BG = {
    "Yogakaraka": "#bbf7d0",
    "Lagna Lord": "#d1fae5",
    "Benefic":    "#dcfce7",
    "Mixed":      "#fef3c7",
    "Neutral":    "#f1f5f9",
    "Malefic":    "#fee2e2",
    "Shadowy":    "#ede9fe",
}

# ─── Utility functions ────────────────────────────────────────────────────────

def ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1:'st', 2:'nd', 3:'rd'}.get(n % 10, 'th')}"


@st.cache_data(show_spinner=False)
def geocode_city(city: str):
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city, "format": "json", "limit": 1},
            headers={"User-Agent": "PlanetInMotion/1.0"},
            timeout=6,
        )
        data = resp.json()
        if not data:
            return None
        lat   = float(data[0]["lat"])
        lon   = float(data[0]["lon"])
        label = ", ".join(data[0].get("display_name", city).split(", ")[:3])
        try:
            tz_resp = requests.get(
                "https://timeapi.io/api/timezone/coordinate",
                params={"latitude": lat, "longitude": lon},
                timeout=6,
            )
            tz = tz_resp.json()["currentUtcOffset"]["seconds"] / 3600
        except Exception:
            tz = round(lon / 15 * 2) / 2
        return {"lat": lat, "lon": lon, "tz": tz, "label": label}
    except Exception:
        return None


@st.cache_data(show_spinner="Computing planetary motion…")
def cached_timeseries(start, end, tz, lat, lon, planets_tuple, step_days):
    return planetary_timeseries(start, end, tz, lat, lon,
                                planet_names=list(planets_tuple),
                                step_days=step_days)


def transit_snapshot_frame(tchart, planet_names) -> pd.DataFrame:
    rows = []
    for nm in planet_names:
        p   = tchart.planets[nm]
        rad = math.radians(p.longitude)
        rows.append({
            "planet": nm, "longitude": p.longitude,
            "phase_sin": math.sin(rad), "phase_cos": math.cos(rad),
            "rasi": p.rasi, "deg_in_rasi": p.deg_in_rasi,
            "retro": p.retro, "retro_symbol": "℞" if p.retro else "",
            "longitude_label": f"{int(p.deg_in_rasi)}°{int((p.deg_in_rasi % 1)*60):02d}' {p.rasi}",
        })
    return pd.DataFrame(rows)


def find_house_entries(df: pd.DataFrame, asc_rasi_index: int,
                       target_houses: list[int]) -> list[dict]:
    """
    Detect dates when planets enter target houses from a pre-computed timeseries.
    Returns rows sorted by entry date with approximate duration in that house.
    """
    target_set = set(target_houses)
    results = []

    for planet, g in df.groupby("planet"):
        g = g.sort_values("when_local").copy()
        g["house"] = ((g["longitude"] // 30).astype(int) - asc_rasi_index) % 12 + 1

        # Collect all house transitions for this planet
        transitions: list[tuple[int, datetime]] = []
        prev_h = None
        for _, row in g.iterrows():
            h = int(row["house"])
            if h != prev_h:
                transitions.append((h, row["when_local"]))
                prev_h = h

        for j, (h, entry_date) in enumerate(transitions):
            if h not in target_set:
                continue
            exit_date = transitions[j + 1][1] if j + 1 < len(transitions) else None
            duration  = _fmt_duration(entry_date, exit_date) if exit_date else "beyond range"
            results.append({
                "Planet":  planet,
                "Enters":  f"H{h} · {HOUSE_KEYWORDS.get(h, '')}",
                "Date":    entry_date.strftime("%d %b %Y"),
                "Duration in house": duration,
                "_sort":   entry_date,
            })

    results.sort(key=lambda r: r["_sort"])
    for r in results:
        del r["_sort"]
    return results


def _fmt_duration(start: datetime, end: datetime) -> str:
    days = (end - start).days
    if days < 60:
        return f"~{days}d"
    if days < 365:
        return f"~{days // 30}mo"
    return f"~{days / 365:.1f}y"


# ─── Page config & global style ───────────────────────────────────────────────

st.set_page_config(page_title="Planet in Motion", page_icon="🪐", layout="wide")
st.markdown("""
<style>
  .stApp { background:#ffffff; }
  h1,h2,h3 { color:#92400e !important; font-family:Georgia,serif; }
  .small { color:#78350f; font-size:.85em; }
  div[data-testid="stMetricValue"] { color:#92400e; }
</style>
""", unsafe_allow_html=True)

st.title("🪐 Planet in Motion")
st.markdown("<span class='small'>Sidereal · Lahiri (Chitra-Paksha) ayanamsa · "
            "powered by the Swiss Ephemeris</span>", unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Birth Details")
    name = st.text_input("Name", _PERSON.get("name", ""))

    sex_opts = ["Male", "Female", "Other"]
    _def_sex = _PERSON.get("sex", "Male")
    sex      = st.selectbox("Sex", sex_opts,
                            index=sex_opts.index(_def_sex) if _def_sex in sex_opts else 0)

    _def_date = date.fromisoformat(_BIRTH["date"]) if "date" in _BIRTH else date.today()
    bdate     = st.date_input("Date of birth", _def_date,
                              min_value=APP_MIN_DATE, max_value=APP_MAX_DATE)

    _def_time = time.fromisoformat(_BIRTH["time"]) if "time" in _BIRTH else time(12, 0)
    btime     = st.time_input("Time of birth", _def_time)

    st.markdown("**Place of birth**")
    if "lat_input" not in st.session_state:
        st.session_state.lat_input = float(_BIRTH.get("lat", 0.0))
    if "lon_input" not in st.session_state:
        st.session_state.lon_input = float(_BIRTH.get("lon", 0.0))
    if "tz_input" not in st.session_state:
        st.session_state.tz_input  = float(_BIRTH.get("tz",  0.0))

    city_col, btn_col = st.columns([3, 1])
    city_query = city_col.text_input(
        "City", st.session_state.get("city_query", _BIRTH.get("city", "")),
        label_visibility="collapsed",
    )
    if btn_col.button("🔍", help="Find coordinates", use_container_width=True) and city_query:
        with st.spinner("Looking up…"):
            geo = geocode_city(city_query)
        if geo:
            st.session_state.lat_input  = geo["lat"]
            st.session_state.lon_input  = geo["lon"]
            st.session_state.tz_input   = geo["tz"]
            st.session_state.city_query = city_query
            st.session_state.geo_label  = geo["label"]
            st.rerun()
        else:
            st.error("City not found — try a more specific name.")

    if st.session_state.get("geo_label"):
        st.caption(f"📍 {st.session_state.geo_label}")

    with st.expander("Override coordinates"):
        c1, c2 = st.columns(2)
        c1.number_input("Latitude (°N)",  format="%.4f", key="lat_input")
        c2.number_input("Longitude (°E)", format="%.4f", key="lon_input")
        st.number_input("Timezone (hrs East of GMT)", step=0.25, format="%.2f", key="tz_input")
        st.caption("West longitudes/timezones are negative. India = +5.5, New York = −5/−4.")

    lat          = st.session_state.lat_input
    lon          = st.session_state.lon_input
    tz           = st.session_state.tz_input
    transit_date = st.date_input("Transit date (gochara)", date.today(),
                                 min_value=APP_MIN_DATE, max_value=APP_MAX_DATE)
    generate_chart = st.button("Generate Horoscope", type="primary", use_container_width=True)

# ─── Chart computation ────────────────────────────────────────────────────────

if generate_chart or "chart" not in st.session_state:
    dt_local = datetime.combine(bdate, btime)
    st.session_state.chart = build_chart(dt_local, tz, lat, lon)
    st.session_state.meta  = dict(name=name, sex=sex, dt=dt_local, tz=tz,
                                  lat=lat, lon=lon, transit_date=transit_date)

chart = st.session_state.chart
meta  = st.session_state.meta
moon  = chart.planets["Moon"]

# Summary metrics row
hc1, hc2, hc3, hc4 = st.columns(4)
hc1.metric("Lagna (Ascendant)", RASIS[chart.asc_rasi_index])
hc2.metric("Rasi (Moon sign)",  moon.rasi)
hc3.metric("Birth Star",        f"{moon.nakshatra}-{moon.pada}")
hc4.metric("Western Sun sign",  RASIS_EN[chart.planets["Sun"].rasi_index])
st.divider()

tdt    = datetime.combine(meta["transit_date"], time(12, 0))
tchart = build_chart(tdt, meta["tz"], meta["lat"], meta["lon"])

# ─── Tabs ─────────────────────────────────────────────────────────────────────

tab_birth, tab_transit, tab_tm, tab_house, tab_extra = st.tabs([
    "📜 Birth Chart",
    "🌍 Current Transit",
    "🔭 Transit + Motion",
    "🏠 House Guide",
    "📋 Extra Info",
])

# ── Birth Chart ───────────────────────────────────────────────────────────────

with tab_birth:
    left, right = st.columns(2)
    with left:
        st.markdown(render_chart_svg(chart, title="Rasi"), unsafe_allow_html=True)
    with right:
        st.subheader(meta["name"])
        st.write(f"**{meta['sex']}** · born {meta['dt'].strftime('%d %B %Y, %I:%M %p')}")
        location = st.session_state.get("geo_label") or f"{meta['lat']}°N, {meta['lon']}°E"
        st.write(f"📍 {location} · GMT+{meta['tz']}")
        st.write(f"**Ayanamsa:** {chart.ayanamsa:.4f}°  (Lahiri)")
        st.markdown("---")
        notes = [f"- **{nm}** is *{dignity(nm, p.rasi_index)}* in {p.rasi}"
                 for nm, p in chart.planets.items() if dignity(nm, p.rasi_index)]
        notes.append(f"- Moon sits in the **{ordinal(chart.house_of(moon.rasi_index))} house** from Lagna")
        st.markdown("#### Notable placements")
        st.markdown("\n".join(notes) if notes else "_None_")

# ── Current Transit ───────────────────────────────────────────────────────────

with tab_transit:
    overlay = {}
    for nm, p in tchart.planets.items():
        overlay.setdefault(p.rasi_index, []).append((SHORT[nm], p.retro))
    hi = {tchart.planets["Jupiter"].rasi_index, moon.rasi_index}

    left, right = st.columns(2)
    with left:
        st.markdown(render_chart_svg(chart, title="Gochara", highlight=hi, transit=overlay),
                    unsafe_allow_html=True)
        st.caption("Faded = natal · boxed →tags = transiting · gold = transit Jupiter & Moon-sign")
    with right:
        st.subheader(f"Transit on {meta['transit_date'].strftime('%d %b %Y')}")
        jup, sat = tchart.planets["Jupiter"], tchart.planets["Saturn"]
        jh, sh   = chart.house_of(jup.rasi_index), chart.house_of(sat.rasi_index)
        st.markdown(
            f"- **Jupiter** transiting **{jup.rasi}** → your {ordinal(jh)} house"
            + ("  🌟 *over your Moon-sign!*" if jup.rasi_index == moon.rasi_index else "")
        )
        st.markdown(
            f"- **Saturn** transiting **{sat.rasi}** → your {ordinal(sh)} house"
            + ("  ⚠️ *Sade-Sati zone*"
               if abs(sat.rasi_index - moon.rasi_index) in (0, 1, 11) else "")
        )
        st.markdown("---")
        st.markdown("#### All transiting positions")
        st.dataframe(
            [{"Planet": nm, "Sign": p.rasi, "Deg": f"{p.deg_in_rasi:.1f}°",
              "House": ordinal(chart.house_of(p.rasi_index)), "R": "℞" if p.retro else ""}
             for nm, p in tchart.planets.items()],
            hide_index=True, use_container_width=True,
        )

# ── Transit + Motion ──────────────────────────────────────────────────────────

with tab_tm:
    st.subheader(f"Transit + motion · {meta['transit_date'].strftime('%d %b %Y')}")

    c1, c2 = st.columns([2, 1])
    tsel = c1.multiselect("Planets", ALL_PLANETS, default=["Jupiter", "Saturn"], key="tm_planets")
    win  = c2.selectbox("Window (± years)", [0.5, 1, 2, 5, 10, 15, 30], index=2, key="tm_window")
    tstep = max(3, int(win * 365.25 / 250))

    if not tsel:
        st.info("Pick at least one planet.")
    else:
        overlay_sel = {}
        for nm in tsel:
            p = tchart.planets[nm]
            overlay_sel.setdefault(p.rasi_index, []).append((SHORT[nm], p.retro))
        hi = {tchart.planets["Jupiter"].rasi_index, moon.rasi_index}

        left, right = st.columns(2)
        with left:
            st.markdown(render_chart_svg(chart, title="Gochara",
                                         highlight=hi, transit=overlay_sel),
                        unsafe_allow_html=True)
            st.caption("Only selected planets overlaid (boxed →tags).")
        with right:
            snap = transit_snapshot_frame(tchart, tsel)
            show = snap[["planet", "rasi", "deg_in_rasi", "retro_symbol"]].copy()
            show["deg_in_rasi"] = show["deg_in_rasi"].map(lambda d: f"{d:.1f}°")
            show["House"] = [chart.house_of(tchart.planets[n].rasi_index) for n in snap["planet"]]
            show.columns = ["Planet", "Sign", "Degree", "R", "House"]
            st.dataframe(show, hide_index=True, use_container_width=True)

        win_days = int(win * 365.25)
        start    = tdt - timedelta(days=win_days)
        end      = tdt + timedelta(days=win_days)
        df       = rows_to_frame(cached_timeseries(start, end, meta["tz"],
                                                   meta["lat"], meta["lon"], tuple(tsel), tstep))
        snap     = transit_snapshot_frame(tchart, tsel)

        st.plotly_chart(
            build_motion_figure(df, transit_dt=tdt, transit_snapshot=snap,
                                title="Motion around transit date  ·  ★ = current positions"),
            use_container_width=True,
        )
        if len(tsel) >= 2:
            st.plotly_chart(build_interaction_figure(df, transit_dt=tdt),
                            use_container_width=True)
            st.dataframe(closest_passes(df, top_n=3), hide_index=True, use_container_width=True)

# ── House Guide ───────────────────────────────────────────────────────────────

with tab_house:
    st.subheader(f"Your house guide · {RASIS[chart.asc_rasi_index]} Lagna")
    st.caption("All tables and charts are relative to YOUR ascendant.")

    # ── What's active right now ────────────────────────────────────────────────

    st.markdown("#### 🔭 What's being activated right now")
    st.caption(f"Transit date: {meta['transit_date'].strftime('%d %b %Y')} "
               "· planet → sign → YOUR house → life area")
    live_rows = sorted(
        [{"Planet": nm, "Transiting sign": p.rasi,
          "Your house": f"H{chart.house_of(p.rasi_index)} · {HOUSE_KEYWORDS.get(chart.house_of(p.rasi_index), '')}",
          "Life area": HOUSE_SIGNIFICATIONS.get(chart.house_of(p.rasi_index), ""),
          "R": "℞" if p.retro else ""}
         for nm, p in tchart.planets.items()],
        key=lambda r: int(r["Your house"].split("·")[0][1:].strip()),
    )
    st.dataframe(live_rows, hide_index=True, use_container_width=True)

    # ── Dasa–Transit Confluence ────────────────────────────────────────────────

    st.divider()
    st.markdown("#### 🔗 Dasa–Transit Confluence")
    st.caption(
        "The most powerful timing signal is when your dasa lord also transits a house "
        "aligned with your goal. This block connects those two signals."
    )

    periods = vimshottari_periods(moon.longitude, meta["dt"])
    cur_maha, cur_sub, _ = current_dasa(periods, tdt)

    if cur_maha:
        for kind, lord in [("Maha-dasa", cur_maha["lord"]),
                           ("Antardasa", cur_sub["lord"] if cur_sub else None)]:
            if lord is None:
                continue
            nature = functional_nature(lord, chart.asc_rasi_index)
            tp = tchart.planets.get(lord)
            if tp:
                th       = chart.house_of(tp.rasi_index)
                house_kw = HOUSE_KEYWORDS.get(th, "")
                retro    = " ℞" if tp.retro else ""
                st.markdown(
                    f"**{kind}: {lord}** &nbsp;·&nbsp; "
                    f"<span style='background:{nature['color']}22;"
                    f"color:{nature['color']};padding:1px 6px;"
                    f"border-radius:4px;font-weight:600'>{nature['label']}</span>"
                    f" for your Lagna &nbsp;→&nbsp; "
                    f"transiting **H{th} {house_kw}** ({tp.rasi}{retro})",
                    unsafe_allow_html=True,
                )
                st.caption(nature["explanation"])
            else:
                # Rahu/Ketu handled above; nodes always in tchart
                st.markdown(f"**{kind}: {lord}** — not in transit table (node position varies).")
    else:
        st.info("Could not determine current dasa for the selected transit date.")

    # ── Forward Scanner ────────────────────────────────────────────────────────

    st.divider()
    st.markdown("#### 🔮 Forward Scanner — best windows ahead")
    st.caption(
        "Scan forward in time to find when slow planets enter the houses that matter "
        "for a chosen goal. Fast planets (Sun, Moon, Mercury, Venus, Mars) complete "
        "all 12 houses in under a year and are excluded."
    )

    sc1, sc2, sc3 = st.columns([2, 2, 1])
    goal        = sc1.selectbox("Goal", list(GOAL_HOUSES.keys()), key="scanner_goal")
    scan_planets = sc2.multiselect("Planets to watch", SLOW_PLANETS,
                                   default=["Jupiter", "Saturn", "Rahu"], key="scanner_planets")
    scan_years  = sc3.selectbox("Look ahead (years)", [3, 5, 10, 15, 20], index=2, key="scanner_years")

    target_h = GOAL_HOUSES[goal]
    st.caption(f"Houses to watch for **{goal}**: " +
               ", ".join(f"H{h} ({HOUSE_KEYWORDS.get(h,'')})" for h in target_h))

    if scan_planets:
        scan_end   = tdt + timedelta(days=scan_years * 365)
        # 7-day step is accurate enough for slow planets (Jupiter moves ~1°/week)
        df_scan = rows_to_frame(
            cached_timeseries(tdt, scan_end, meta["tz"], meta["lat"], meta["lon"],
                              tuple(scan_planets), 7)
        )
        scan_results = find_house_entries(df_scan, chart.asc_rasi_index, target_h)
        if scan_results:
            st.dataframe(pd.DataFrame(scan_results), hide_index=True, use_container_width=True)
        else:
            st.info(f"None of the selected planets enter those houses in the next {scan_years} years.")
    else:
        st.info("Pick at least one planet to scan.")

    # ── House map & lordships ──────────────────────────────────────────────────

    st.divider()
    cmap, clord = st.columns(2)
    with cmap:
        st.markdown("#### 🏠 Your 12 houses")
        st.dataframe(
            [{"House": f"H{r['house']}", "Sign": r["rasi"],
              "Theme": r["keyword"], "Governs": r["significations"]}
             for r in lagna_house_map(chart.asc_rasi_index)],
            hide_index=True, use_container_width=True, height=460,
        )
    with clord:
        st.markdown("#### 🪐 What each planet means *for you*")
        st.caption("A planet carries the topics of the house(s) it rules wherever it goes.")
        lords = planet_lordships(chart.asc_rasi_index)
        st.dataframe(
            [{"Planet": r["planet"], "Rules your": r["houses_label"],
              "= themes": ", ".join(HOUSE_KEYWORDS.get(h, "") for h in r["houses_ruled"]) or "—",
              "Natural signification": r["karaka"]}
             for r in lords],
            hide_index=True, use_container_width=True, height=460,
        )

    st.divider()
    st.markdown("#### ✨ Notable for your Lagna")
    bullets = []
    lagna_lord = next((r for r in planet_lordships(chart.asc_rasi_index)
                       if 1 in r["houses_ruled"]), None)
    if lagna_lord:
        bullets.append(
            f"- **{lagna_lord['planet']}** is your **Lagna lord** — "
            f"your most personal planet; its condition colours your whole life.")
    for target_house, label in [(10, "career"), (11, "income"), (7, "marriage"), (9, "fortune")]:
        owner = next((r for r in planet_lordships(chart.asc_rasi_index)
                      if target_house in r["houses_ruled"]), None)
        if owner:
            bullets.append(
                f"- Your **{label}** (H{target_house}) is ruled by **{owner['planet']}** "
                f"— watch its dasa periods & transits for {label}-related shifts.")
    st.markdown("\n".join(bullets))
    st.info("💡 When a life event happened, check which house slow planets were transiting "
            "and whether that house's ruling planet was in a Dasa/Bhukti period.")

    # ── House activation chart ─────────────────────────────────────────────────

    st.divider()
    st.markdown("#### 📊 House activation right now")
    st.caption(f"Weighted by planetary significance · {meta['transit_date'].strftime('%d %b %Y')}")
    house_planet_map: dict[int, list[str]] = {}
    for nm, p in tchart.planets.items():
        house_planet_map.setdefault(chart.house_of(p.rasi_index), []).append(nm)
    st.plotly_chart(
        build_house_activation_figure(house_planet_map, HOUSE_KEYWORDS),
        use_container_width=True,
    )

    # ── Planet journeys ────────────────────────────────────────────────────────

    st.divider()
    st.markdown("#### 🪐 Planet journeys through your houses")
    st.caption("Step lines show exactly when each planet moves from one house to the next.")
    jc1, jc2 = st.columns([2, 1])
    journey_sel  = jc1.multiselect("Planets", ALL_PLANETS,
                                   default=["Jupiter", "Saturn", "Rahu", "Ketu"],
                                   key="journey_planets")
    journey_span = jc2.selectbox("Span (years ±)", [3, 5, 10, 20], index=1, key="journey_span")
    if journey_sel:
        center_j = tdt
        start_j  = center_j.replace(year=max(1900, center_j.year - journey_span))
        end_j    = center_j.replace(year=min(2100, center_j.year + journey_span))
        df_j     = rows_to_frame(cached_timeseries(start_j, end_j, meta["tz"],
                                                   meta["lat"], meta["lon"],
                                                   tuple(journey_sel), 7))
        st.plotly_chart(
            build_house_journey_figure(df_j, chart.asc_rasi_index,
                                       transit_dt=center_j, house_keywords=HOUSE_KEYWORDS),
            use_container_width=True,
        )
    else:
        st.info("Pick at least one planet.")

    # ── Phase wave ────────────────────────────────────────────────────────────

    st.divider()
    st.markdown("#### 🌊 Phase wave through your houses")
    st.caption("Sin-wave of a planet's sidereal longitude · coloured bands = house occupied at each point.")
    wc1, wc2    = st.columns([2, 1])
    wave_planet = wc1.selectbox("Planet", ALL_PLANETS,
                                index=ALL_PLANETS.index("Jupiter"), key="wave_planet")
    wave_span   = wc2.selectbox("Span (years ±)", [3, 5, 10, 20], index=1, key="wave_span")
    start_w = tdt.replace(year=max(1900, tdt.year - wave_span))
    end_w   = tdt.replace(year=min(2100, tdt.year + wave_span))
    df_w    = rows_to_frame(cached_timeseries(start_w, end_w, meta["tz"],
                                              meta["lat"], meta["lon"], (wave_planet,), 3))
    st.plotly_chart(
        build_sinwave_house_figure(df_w, wave_planet, chart.asc_rasi_index,
                                   transit_dt=tdt, house_keywords=HOUSE_KEYWORDS),
        use_container_width=True,
    )

# ── Extra Info ────────────────────────────────────────────────────────────────

with tab_extra:

    # ── Dasa Timeline ─────────────────────────────────────────────────────────

    with st.expander("🪔 Dasa Timeline", expanded=True):
        periods   = vimshottari_periods(moon.longitude, meta["dt"])
        cur_maha, cur_sub, subs = current_dasa(periods, tdt)
        st.subheader("Vimshottari Maha-Dasa periods")

        if cur_maha:
            st.success(
                f"**Currently running:** {cur_maha['lord']} Dasa "
                f"({cur_maha['start'].strftime('%b %Y')} – {cur_maha['end'].strftime('%b %Y')})"
                + (f"  ·  sub-period **{cur_sub['lord']}** (until {cur_sub['end'].strftime('%b %Y')})"
                   if cur_sub else "")
            )

        # Build dasa table with Lagna-specific quality for each dasa lord
        period_rows = []
        for p in periods:
            nat = functional_nature(p["lord"], chart.asc_rasi_index)
            period_rows.append({
                "Maha-Dasa": ("▶ " if p is cur_maha else "") + p["lord"],
                "Quality for your Lagna": nat["label"],
                "From":  p["start"].strftime("%d-%m-%Y"),
                "To":    p["end"].strftime("%d-%m-%Y"),
                "Years": f"{p['years']:.1f}",
            })

        df_periods = pd.DataFrame(period_rows)

        def _style_dasa(row):
            lord = row["Maha-Dasa"].replace("▶ ", "").strip()
            bg   = _QUALITY_BG.get(functional_nature(lord, chart.asc_rasi_index)["label"], "#ffffff")
            return [f"background-color:{bg}"] * len(row)

        st.dataframe(
            df_periods.style.apply(_style_dasa, axis=1),
            hide_index=True, use_container_width=True,
        )

        # Quality legend
        st.caption(
            "**Quality key:** "
            "Yogakaraka = most powerful · Lagna Lord = auspicious · Benefic = growth-oriented · "
            "Mixed = dual themes · Neutral = moderate · Malefic = karmic pressure · "
            "Shadowy = Rahu/Ketu (unpredictable)"
        )

        if cur_maha:
            st.markdown(f"#### Sub-periods (Bhukti) within {cur_maha['lord']} Dasa")
            sub_rows = []
            for s in subs:
                nat = functional_nature(s["lord"], chart.asc_rasi_index)
                sub_rows.append({
                    "Sub-period": ("▶ " if (cur_sub and s["lord"] == cur_sub["lord"]
                                            and s["start"] == cur_sub["start"]) else "")
                                  + f"{cur_maha['lord']}–{s['lord']}",
                    "Quality": nat["label"],
                    "From":  s["start"].strftime("%d-%m-%Y"),
                    "To":    s["end"].strftime("%d-%m-%Y"),
                    "Years": f"{s['years']:.2f}",
                })
            df_subs = pd.DataFrame(sub_rows)

            def _style_sub(row):
                lord = row["Sub-period"].replace("▶ ", "").split("–")[-1].strip()
                bg   = _QUALITY_BG.get(functional_nature(lord, chart.asc_rasi_index)["label"], "#ffffff")
                return [f"background-color:{bg}"] * len(row)

            st.dataframe(
                df_subs.style.apply(_style_sub, axis=1),
                hide_index=True, use_container_width=True,
            )

    # ── Planet Positions ───────────────────────────────────────────────────────

    with st.expander("📊 Planet Positions"):
        st.subheader("Nirayana (sidereal) planetary positions")
        lagna_rasi = RASIS[chart.asc_rasi_index]
        rows = [{"Planet": nm, "Rasi": p.rasi,
                 "Longitude in Rasi": f"{int(p.deg_in_rasi)}°{int((p.deg_in_rasi%1)*60):02d}'",
                 "Nakshatra": p.nakshatra, "Pada": p.pada,
                 "House": chart.house_of(p.rasi_index),
                 "Dignity": dignity(nm, p.rasi_index) or "—",
                 "Retro": "℞" if p.retro else ""}
                for nm, p in chart.planets.items()]
        rows.insert(0, {
            "Planet": "Lagna", "Rasi": lagna_rasi,
            "Longitude in Rasi": f"{int(chart.ascendant%30)}°{int(((chart.ascendant%30)%1)*60):02d}'",
            "Nakshatra": "—", "Pada": "—", "House": 1, "Dignity": "—", "Retro": "",
        })
        st.dataframe(rows, hide_index=True, use_container_width=True)
        st.caption("Rahu/Ketu use mean-node positions.")

    # ── Planet Motion ──────────────────────────────────────────────────────────

    with st.expander("📈 Planet Motion"):
        st.subheader("Planetary motion over time")
        st.caption("Sinusoidal phase + raw longitude. Diamonds mark retrograde samples.")
        c1, c2   = st.columns([2, 1])
        sel      = c1.multiselect("Planets", ALL_PLANETS,
                                  default=["Jupiter", "Saturn", "Mars"], key="motion_planets")
        span_yrs = c2.selectbox("Span (years ±)", [3, 5, 10, 20, 30], index=1, key="motion_span")
        step     = max(3, int(span_yrs * 365.25 / 250))
        if not sel:
            st.info("Pick at least one planet.")
        else:
            start = tdt.replace(year=max(1900, tdt.year - span_yrs))
            end   = tdt.replace(year=min(2100, tdt.year + span_yrs))
            df    = rows_to_frame(cached_timeseries(start, end, meta["tz"],
                                                    meta["lat"], meta["lon"], tuple(sel), step))
            st.plotly_chart(build_motion_figure(df, transit_dt=tdt,
                                                title="Phase & longitude motion"),
                            use_container_width=True)
            if len(sel) >= 2:
                st.markdown("#### Planetary interactions")
                st.plotly_chart(build_interaction_figure(df, transit_dt=tdt),
                                use_container_width=True)
                st.markdown("#### Closest passes (per pair)")
                st.dataframe(closest_passes(df, top_n=3), hide_index=True, use_container_width=True)
            else:
                st.caption("Select 2+ planets to see pairwise interactions.")

st.divider()
st.caption("⚠️ For guidance & self-reflection only. Not a substitute for professional advice.")
