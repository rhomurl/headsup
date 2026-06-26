"""Natural-language parsers for dates, times, and durations."""

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from dateutil import parser as du_parser

WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

UNIT_SECONDS = {
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
    "d": 86400, "day": 86400, "days": 86400,
    "w": 604800, "week": 604800, "weeks": 604800,
}


@dataclass
class ParsedWhen:
    when: datetime          # tz-aware in user's local tz
    has_time: bool          # False = caller should ask for a time


def parse_duration(text: str) -> timedelta | None:
    """Parse '10m', '2h', '1 day', '90 seconds' → timedelta. None if invalid."""
    m = re.fullmatch(r"\s*(\d+)\s*([a-zA-Z]+)\s*", text)
    if not m:
        return None
    qty, unit = int(m.group(1)), m.group(2).lower()
    if unit not in UNIT_SECONDS:
        return None
    return timedelta(seconds=qty * UNIT_SECONDS[unit])


def parse_time_only(text: str) -> time | None:
    """Parse '9am', '9:30 PM', '14:00' → time. None if not a bare time."""
    s = text.strip().lower().replace(" ", "")
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(am|pm)?", s)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    suffix = m.group(3)
    if suffix == "am":
        if hour == 12:
            hour = 0
    elif suffix == "pm":
        if hour != 12:
            hour += 12
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return time(hour, minute)


def parse_when(text: str, tz_name: str) -> ParsedWhen | None:
    """Parse a free-form 'when' string into a tz-aware future datetime.

    Handles: 'in 2h', 'tomorrow [9am]', 'monday [6pm]', 'next friday',
             'May 5', 'May 5 2026', '5/5', '5/5/2026', '9am' (today/tomorrow).
    Returns None if unparseable.
    """
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    s = text.strip().lower()
    if not s:
        return None

    # "in <n> <unit>"
    m = re.fullmatch(r"in\s+(\d+)\s*([a-zA-Z]+)", s)
    if m:
        delta = parse_duration(f"{m.group(1)}{m.group(2)}")
        if delta:
            return ParsedWhen(when=now + delta, has_time=True)

    # "today [HH:MM]" / "tonight"
    if s == "today" or s.startswith("today "):
        rest = s[len("today"):].strip()
        t = parse_time_only(rest) if rest else None
        return _combine(now.date(), t, tz, default_today=True)
    if s == "tonight":
        return _combine(now.date(), time(20, 0), tz, default_today=True)

    # "tomorrow [HH:MM]"
    if s == "tomorrow" or s.startswith("tomorrow "):
        rest = s[len("tomorrow"):].strip()
        t = parse_time_only(rest) if rest else None
        return _combine(now.date() + timedelta(days=1), t, tz)

    # "[next] <weekday> [HH:MM]"
    m = re.fullmatch(r"(?:next\s+)?([a-z]+)(?:\s+(.+))?", s)
    if m and m.group(1) in WEEKDAYS:
        target_wd = WEEKDAYS[m.group(1)]
        days_ahead = (target_wd - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7  # "monday" on Monday means next Monday
        rest = (m.group(2) or "").strip()
        t = parse_time_only(rest) if rest else None
        return _combine(now.date() + timedelta(days=days_ahead), t, tz)

    # Bare time: "9am", "18:30" → today if future, else tomorrow
    t = parse_time_only(s)
    if t is not None:
        candidate = datetime.combine(now.date(), t, tzinfo=tz)
        if candidate <= now:
            candidate += timedelta(days=1)
        return ParsedWhen(when=candidate, has_time=True)

    # Fallback to dateutil — detect "has_time" by parsing twice with different defaults.
    try:
        d1 = du_parser.parse(text, default=datetime(2000, 1, 1, 0, 0))
        d2 = du_parser.parse(text, default=datetime(2000, 1, 1, 12, 30))
    except (ValueError, OverflowError):
        return None
    has_time = (d1.hour, d1.minute) == (d2.hour, d2.minute)
    when = d1.replace(tzinfo=tz)
    # If year wasn't specified and the date is in the past, roll forward a year.
    if when.date() < now.date() and "20" not in text and "19" not in text:
        try:
            when = when.replace(year=now.year)
            if when.date() < now.date():
                when = when.replace(year=now.year + 1)
        except ValueError:
            pass
    return ParsedWhen(when=when, has_time=has_time)


def _combine(d: date, t: time | None, tz: ZoneInfo, default_today: bool = False) -> ParsedWhen:
    if t is None:
        return ParsedWhen(when=datetime.combine(d, time(9, 0), tzinfo=tz), has_time=False)
    when = datetime.combine(d, t, tzinfo=tz)
    if default_today and when <= datetime.now(tz):
        when += timedelta(days=1)
    return ParsedWhen(when=when, has_time=True)


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _advance_month(dt: datetime, day: int) -> datetime:
    """Return dt advanced one calendar month with day clamped to that month's last day."""
    if dt.month == 12:
        year, month = dt.year + 1, 1
    else:
        year, month = dt.year, dt.month + 1
    last = calendar.monthrange(year, month)[1]
    return dt.replace(year=year, month=month, day=min(day, last))


def next_recurring(prev_utc: datetime, recurrence: str, tz_name: str) -> datetime | None:
    """Given the time a recurring reminder just fired, compute the next fire time (UTC)."""
    tz = ZoneInfo(tz_name)
    local = prev_utc.astimezone(tz)
    if recurrence == "daily":
        return to_utc(local + timedelta(days=1))
    if recurrence.startswith("weekly:"):
        return to_utc(local + timedelta(days=7))
    if recurrence.startswith("every:"):
        delta = parse_duration(recurrence[len("every:"):])
        if delta:
            return to_utc(local + delta)
    if recurrence.startswith("monthly:"):
        day = int(recurrence.split(":")[1])
        return to_utc(_advance_month(local, day))
    return None


def next_recurring_after(
    prev_utc: datetime, recurrence: str, tz_name: str, after_utc: datetime
) -> datetime | None:
    """Return the next scheduled occurrence strictly after ``after_utc``.

    Unlike ``next_recurring()``, this preserves the intended recurrence when the
    app was offline past one or more scheduled fires.
    """
    tz = ZoneInfo(tz_name)
    prev_local = prev_utc.astimezone(tz)
    after_local = after_utc.astimezone(tz)

    if recurrence == "daily":
        candidate = after_local.replace(
            hour=prev_local.hour,
            minute=prev_local.minute,
            second=prev_local.second,
            microsecond=prev_local.microsecond,
        )
        if candidate <= after_local:
            candidate += timedelta(days=1)
        return to_utc(candidate)

    if recurrence.startswith("weekly:"):
        wd = WEEKDAYS[recurrence.split(":", 1)[1]]
        candidate = after_local.replace(
            hour=prev_local.hour,
            minute=prev_local.minute,
            second=prev_local.second,
            microsecond=prev_local.microsecond,
        )
        days_ahead = (wd - candidate.weekday()) % 7
        candidate += timedelta(days=days_ahead)
        if candidate <= after_local:
            candidate += timedelta(days=7)
        return to_utc(candidate)

    if recurrence.startswith("monthly:"):
        day = int(recurrence.split(":")[1])
        candidate = after_local.replace(
            day=min(day, calendar.monthrange(after_local.year, after_local.month)[1]),
            hour=prev_local.hour,
            minute=prev_local.minute,
            second=prev_local.second,
            microsecond=prev_local.microsecond,
        )
        if candidate <= after_local:
            candidate = _advance_month(candidate, day)
        return to_utc(candidate)

    if recurrence.startswith("every:"):
        candidate = prev_utc
        while candidate <= after_utc:
            candidate = next_recurring(candidate, recurrence, tz_name)
            if candidate is None:
                return None
        return candidate

    return None


def format_when(dt_utc: datetime, tz_name: str) -> str:
    """Friendly local-time formatting: 'Monday, May 5 at 9:00 AM'."""
    local = dt_utc.astimezone(ZoneInfo(tz_name))
    return local.strftime("%A, %b %-d at %-I:%M %p")


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]}"


def format_recurrence(recurrence: str | None) -> str:
    if recurrence is None:
        return ""
    if recurrence == "daily":
        return "every day"
    if recurrence.startswith("weekly:"):
        wd = recurrence.split(":", 1)[1]
        idx = WEEKDAYS.get(wd.lower())
        return f"every {WEEKDAY_NAMES[idx]}" if idx is not None else "weekly"
    if recurrence.startswith("every:"):
        return f"every {recurrence[len('every:'):]}"
    if recurrence.startswith("monthly:"):
        day = int(recurrence.split(":")[1])
        return f"monthly on the {_ordinal(day)}"
    return recurrence
