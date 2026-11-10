"""Each life event set against the chart: dasa, slow-planet transits and named classical
conditions — described, not scored against chance."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import pandas as pd

from ..core.chart import house_between, sidereal_longitudes, sign_of, to_jd
from ..core.constants import SIGNS_ML
from .gochara import ordinal
from .motion import events as transit_events
from .narrative import tone
from .timeline import LifeWeather

SLOW = ("Saturn", "Jupiter", "Rahu", "Ketu")
DASA_NEAR_DAYS = 90          # an event this close to a sub-period start is flagged
CONTACT_WINDOW_DAYS = 30     # slow planet over birth Moon / Lagna within this many days


@dataclass(frozen=True)
class ExplainedEvent:
    when: date
    category: str
    good: bool
    note: str
    reading: float                       # Life Weather 3-month average
    md: str
    ad: str
    ad_start: date
    ad_end: date
    positions: dict[str, tuple[int, int, int]]   # planet → (sign, house from Lagna, from Moon)
    conditions: tuple[str, ...]          # named classical conditions in force

    @property
    def matches(self) -> bool:
        return (self.reading > 0) == self.good

    @property
    def dasa_text(self) -> str:
        days = (self.when - self.ad_start).days
        near = (f", began {days} days before" if 0 <= days <= DASA_NEAR_DAYS else
                f", {abs((self.ad_end - self.when).days)} days before it ends"
                if (self.ad_end - self.when).days <= DASA_NEAR_DAYS else "")
        return f"{self.md}/{self.ad}{near}"

    def where(self, planet: str) -> str:
        sign, h_lagna, h_moon = self.positions[planet]
        return f"{SIGNS_ML[sign]} · H{h_lagna} · ☾{h_moon}"

    @property
    def summary(self) -> str:
        verdict = "matches" if self.matches else "does not match"
        return (f"{self.md}/{self.ad} period; " + "; ".join(self.conditions[:4])
                + f". Life Weather {self.reading:+.2f} ({tone(self.reading)}) — {verdict} "
                f"a {'good' if self.good else 'hard'} event.")


def _conditions(pos: dict[str, tuple[int, int, int]], lw: LifeWeather, d: date) -> list[str]:
    s_l, s_m = pos["Saturn"][1], pos["Saturn"][2]
    j_l, j_m = pos["Jupiter"][1], pos["Jupiter"][2]
    r_l, r_m = pos["Rahu"][1], pos["Rahu"][2]
    out = []
    if s_m in (12, 1, 2):
        phase = {12: "rising phase", 1: "peak phase", 2: "setting phase"}[s_m]
        out.append(f"Sade Sati, {phase} (Saturn {ordinal(s_m)} from Moon)")
    elif s_m == 8:
        out.append("Ashtama Shani (Saturn 8th from Moon)")
    elif s_m == 4:
        out.append("Ardhashtama Shani (Saturn 4th from Moon)")
    elif s_m in (3, 6, 11):
        out.append(f"Saturn in a good house from Moon ({ordinal(s_m)})")
    if s_l == 1:
        out.append("Saturn in your Lagna")
    elif s_l in (4, 7, 10):
        out.append(f"Saturn in a kendra from Lagna ({ordinal(s_l)} house)")
    if j_m == 1:
        out.append("Jupiter over your birth Moon")
    elif j_m in (2, 5, 7, 9, 11):
        out.append(f"Jupiter in a good house from Moon ({ordinal(j_m)})")
    elif j_m in (8, 12):
        out.append(f"Jupiter in a weak house from Moon ({ordinal(j_m)})")
    if j_l == 1:
        out.append("Jupiter in your Lagna")
    if r_l in (1, 7):
        out.append("Rahu/Ketu across your Lagna (1st–7th axis)")
    if r_m in (1, 7):
        out.append("Rahu/Ketu across your Moon (1st–7th from Moon)")

    centre = datetime.combine(d, time(12))
    window = timedelta(days=CONTACT_WINDOW_DAYS)
    for e in transit_events(lw.chart, centre - window, centre + window, lw.birth.tz_hours,
                            ["Saturn", "Jupiter", "Rahu", "Ketu"], lw.node):
        if e.kind == "contact" and "your birth" in e.text:
            out.append(f"{e.text} ({e.when:%d %b %Y})")
    return out


def explain(lw: LifeWeather, events: pd.DataFrame) -> list[ExplainedEvent]:
    chart, df = lw.chart, lw.frame
    lagna, moon = chart.sign("Lagna"), chart.sign("Moon")
    ev = events.dropna(subset=["date", "valence"]).copy()
    ev["date"] = pd.to_datetime(ev["date"]).dt.date
    out = []
    for _, e in ev.sort_values("date").iterrows():
        d = e["date"]
        if d < lw.birth.when_local.date():
            continue
        lon = sidereal_longitudes(to_jd(datetime.combine(d, time(12)), lw.birth.tz_hours), lw.node)
        pos = {p: (sign_of(lon[p]), house_between(sign_of(lon[p]), lagna),
                   house_between(sign_of(lon[p]), moon)) for p in SLOW}
        on = lw.on(d)
        period = next(p for p in lw.periods
                      if p.start <= d < p.end and p.md == on["md"] and p.ad == on["ad"])
        reading = float(df.iloc[(df["date"] - pd.Timestamp(d)).abs().argmin()].smoothed)
        conditions = _conditions(pos, lw, d)
        days = (d - period.start).days
        if 0 <= days <= DASA_NEAR_DAYS:
            conditions.insert(0, f"{on['ad']} sub-period had just begun ({days} days before)")
        out.append(ExplainedEvent(d, str(e.get("category") or "other"), float(e["valence"]) > 0,
                                  "" if pd.isna(e.get("note")) else str(e.get("note")),
                                  reading, on["md"], on["ad"], period.start, period.end, pos,
                                  tuple(conditions)))
    return out


def themes(explained: list[ExplainedEvent]) -> pd.DataFrame:
    """How often each dasa and named condition appears around good vs hard events."""
    good, hard = Counter(), Counter()
    for e in explained:
        tags = {f"{e.md}/{e.ad} period", f"{e.md} Maha-dasa",
                f"Saturn in {ordinal(e.positions['Saturn'][1])} from Lagna"}
        tags |= {c.split(" (")[0] for c in e.conditions}
        (good if e.good else hard).update(tags)
    rows = [{"Condition": t, "Good events": good[t], "Hard events": hard[t]}
            for t in set(good) | set(hard) if good[t] + hard[t] >= 2]
    return (pd.DataFrame(rows, columns=["Condition", "Good events", "Hard events"])
            .assign(total=lambda d: d["Good events"] + d["Hard events"])
            .sort_values(["total", "Hard events"], ascending=False).drop(columns="total"))
