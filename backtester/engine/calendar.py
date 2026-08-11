"""
calendar.py -- session boundaries for the US equity regular session.

WHY THIS MODULE EXISTS, AND THE ONE BUG IT PREVENTS

It is tempting to hard-code the regular session as 13:30-20:00 UTC. That
mapping is correct only while New York is on daylight time. Under
standard time (roughly November to March) the same session runs
14:30-21:00 UTC. A hard-coded UTC window therefore silently includes the
first hour of pre-market for four to five months of every year, and an
"09:35 entry" resolves to 08:35 local -- an hour before the open, on
thin pre-market prints.

So the rule for the whole framework is:

    STORE AND COMPUTE IN UTC. DEFINE SESSIONS IN America/New_York.

Every session boundary is derived by converting to the exchange's local
timezone and comparing local clock times. `zoneinfo` handles the DST
transitions, including the ones that land mid-sample.

EARLY CLOSES are not inferred from a hard-coded holiday list, because a
stale list fails silently and asymmetrically. The session end is taken
from the data itself (the last bar actually printed in the session),
with the scheduled 16:00 close used only as an upper bound. A half day
therefore needs no special casing: it simply has fewer bars.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd

EXCHANGE_TZ = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# Scheduled regular session in EXCHANGE LOCAL time. Never in UTC.
SESSION_OPEN = dt.time(9, 30)
SESSION_CLOSE = dt.time(16, 0)


def to_exchange_tz(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Convert a tz-aware UTC index to exchange local time."""
    if idx.tz is None:
        raise ValueError("index must be tz-aware; naive timestamps are ambiguous")
    return idx.tz_convert(EXCHANGE_TZ)


def session_date(idx: pd.DatetimeIndex) -> pd.Series:
    """The exchange-local calendar date each bar belongs to.

    This is the correct grouping key for "a trading session". Grouping on
    the UTC date would split a session in half for any bar after 19:00
    local during standard time... and more importantly would mis-assign
    pre-market bars. Local date is unambiguous for a session that never
    crosses local midnight.
    """
    local = to_exchange_tz(idx)
    return pd.Series(local.date, index=idx, name="session_date")


def is_regular_session(idx: pd.DatetimeIndex) -> pd.Series:
    """True for bars inside the scheduled regular session, DST-correct.

    The window is half-open on the right: a bar timestamped 16:00 local
    is the closing print of the 15:59-16:00 interval under a
    left-labelled convention and is excluded, matching the 09:30 bar
    being the first included one. If your vendor labels bars on the
    right edge, flip this -- but flip it deliberately, and say so.
    """
    local_t = to_exchange_tz(idx).time
    keep = [(SESSION_OPEN <= t) and (t < SESSION_CLOSE) for t in local_t]
    return pd.Series(keep, index=idx, name="regular_session")


def minutes_from_open(idx: pd.DatetimeIndex) -> pd.Series:
    """Minutes elapsed since the 09:30 local open, per bar.

    Computed against each bar's OWN session open in local time, so it is
    unaffected by DST and by early closes. The 09:30 bar is 0, the 09:35
    bar is 5.
    """
    local = to_exchange_tz(idx)
    mins = local.hour * 60 + local.minute
    open_min = SESSION_OPEN.hour * 60 + SESSION_OPEN.minute
    return pd.Series(mins - open_min, index=idx, name="minutes_from_open")


def local_time_to_utc(session: dt.date, local: dt.time) -> pd.Timestamp:
    """Resolve an exchange-local wall-clock time on a session to UTC.

    Used to turn a config value like entry_time: "09:35" into the actual
    UTC instant for a given trading day. Doing this per session is what
    makes the framework DST-safe: the same local time maps to different
    UTC instants across the year.
    """
    naive = dt.datetime.combine(session, local)
    return pd.Timestamp(naive.replace(tzinfo=EXCHANGE_TZ)).tz_convert(UTC)


def parse_local_time(text: str) -> dt.time:
    """Parse "09:35" / "09:35:00" as an exchange-local wall-clock time."""
    parts = text.strip().split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"expected HH:MM or HH:MM:SS, got {text!r}")
    try:
        nums = [int(p) for p in parts]
    except ValueError as exc:
        raise ValueError(f"non-numeric time component in {text!r}") from exc
    return dt.time(*nums)
