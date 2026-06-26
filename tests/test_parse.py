from datetime import time, timedelta

from headsup.parse import (
    format_recurrence,
    next_recurring,
    parse_duration,
    parse_time_only,
    parse_when,
    to_utc,
)

TZ = "Asia/Manila"


def test_parse_duration_units():
    assert parse_duration("10m") == timedelta(minutes=10)
    assert parse_duration("2 hours") == timedelta(hours=2)
    assert parse_duration("3d") == timedelta(days=3)
    assert parse_duration("90 seconds") == timedelta(seconds=90)
    assert parse_duration("nope") is None


def test_parse_time_only():
    assert parse_time_only("9am") == time(9, 0)
    assert parse_time_only("9:30 PM") == time(21, 30)
    assert parse_time_only("14:00") == time(14, 0)
    assert parse_time_only("12am") == time(0, 0)
    assert parse_time_only("12pm") == time(12, 0)
    assert parse_time_only("not a time") is None


def test_parse_when_relative():
    p = parse_when("in 2 hours", TZ)
    assert p is not None
    assert p.has_time is True
    assert p.when > p.when.__class__.now(p.when.tzinfo)


def test_parse_when_tomorrow_with_time():
    p = parse_when("tomorrow 9am", TZ)
    assert p is not None
    assert p.has_time is True
    assert p.when.hour == 9
    assert p.when.minute == 0


def test_parse_when_weekday_no_time_defaults_9am_flag_false():
    p = parse_when("monday", TZ)
    assert p is not None
    assert p.has_time is False
    assert p.when.weekday() == 0


def test_parse_when_date_only_dateutil():
    p = parse_when("May 5", TZ)
    assert p is not None
    assert p.has_time is False
    assert p.when.month == 5 and p.when.day == 5


def test_parse_when_garbage_returns_none():
    assert parse_when("asdf zxcv", TZ) is None


def test_next_recurring_daily_weekly_biweekly_and_every():
    base = parse_when("tomorrow 9am", TZ).when
    base_utc = to_utc(base)
    assert next_recurring(base_utc, "daily", TZ) - base_utc == timedelta(days=1)
    assert next_recurring(base_utc, "weekly:mon", TZ) - base_utc == timedelta(days=7)
    assert next_recurring(base_utc, "biweekly:mon", TZ) - base_utc == timedelta(days=14)
    assert next_recurring(base_utc, "every:3d", TZ) - base_utc == timedelta(days=3)
    assert next_recurring(base_utc, "every:14d", TZ) - base_utc == timedelta(days=14)
    assert next_recurring(base_utc, "weird", TZ) is None


def test_format_recurrence_for_weekly_biweekly_and_intervals():
    assert format_recurrence("weekly:mon") == "every Monday"
    assert format_recurrence("biweekly:tue") == "every other Tuesday"
    assert format_recurrence("every:14d") == "every 14 days"
