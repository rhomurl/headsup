from datetime import datetime, time
from zoneinfo import ZoneInfo

from headsup.handlers.reminders import _first_fire, _freq_kb, _weekday_kb


def _labels(markup):
    return [[button.text for button in row] for row in markup.inline_keyboard]


def test_freq_keyboard_exposes_weekly_biweekly_and_14_day_options():
    labels = _labels(_freq_kb())
    assert ["Every week", "Every other week"] in labels
    assert ["Every 3 days", "Every 14 days"] in labels


def test_first_fire_biweekly_uses_next_matching_weekday():
    tz = ZoneInfo("Asia/Manila")
    now = datetime(2026, 6, 26, 22, 37, tzinfo=tz)

    assert _first_fire("biweekly:mon", time(7, 0), now, tz) == datetime(
        2026, 6, 29, 7, 0, tzinfo=tz
    )


def test_first_fire_every_14_days_uses_next_local_slot():
    tz = ZoneInfo("Asia/Manila")
    now = datetime(2026, 6, 26, 22, 37, tzinfo=tz)

    assert _first_fire("every:14d", time(7, 0), now, tz) == datetime(
        2026, 6, 27, 7, 0, tzinfo=tz
    )


def test_weekday_keyboard_lists_all_days():
    labels = _labels(_weekday_kb("weekly"))
    assert labels[0] == ["Mon", "Tue", "Wed", "Thu"]
    assert labels[1] == ["Fri", "Sat", "Sun"]


def test_weekday_keyboard_uses_biweekly_callbacks():
    callbacks = [
        button.callback_data
        for row in _weekday_kb("biweekly").inline_keyboard[:2]
        for button in row
    ]
    assert "e:wd:biweekly:mon" in callbacks
    assert "e:wd:biweekly:sun" in callbacks
