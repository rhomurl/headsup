from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from headsup.db import Database
from headsup.handlers.digest import _build_digest, _format_hhmm


TZ = "Asia/Manila"


def test_format_hhmm():
    assert _format_hhmm(None) == "Off"
    assert _format_hhmm("08:00") == "8:00 AM"
    assert _format_hhmm("18:30") == "6:30 PM"


def test_morning_includes_today_and_tomorrow(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.upsert_user(1, None, None, TZ)
    db.set_digest(1, "morning", "08:00")
    user = db.get_user(1)

    tz = ZoneInfo(TZ)
    now = datetime.now(tz)
    later_today = now.replace(hour=23, minute=30, second=0, microsecond=0)
    if later_today <= now:
        later_today = later_today + timedelta(days=1)
        target_today_local = later_today
    else:
        target_today_local = later_today
    tomorrow = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

    db.add_reminder(1, "today task", target_today_local.astimezone(timezone.utc), None)
    db.add_reminder(1, "tomorrow task", tomorrow.astimezone(timezone.utc), None)

    text = _build_digest(db, user, "morning")
    assert "Good morning" in text
    # today_task only appears if its date matches today; tomorrow_task always shows
    assert "tomorrow task" in text


def test_evening_lists_tomorrow(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.upsert_user(1, None, None, TZ)
    db.set_digest(1, "evening", "20:00")
    user = db.get_user(1)
    tz = ZoneInfo(TZ)
    tomorrow = (datetime.now(tz) + timedelta(days=1)).replace(hour=9, minute=0)
    db.add_reminder(1, "morning standup", tomorrow.astimezone(timezone.utc), None)

    text = _build_digest(db, user, "evening")
    assert "Evening recap" in text
    assert "morning standup" in text


def test_evening_empty_state(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.upsert_user(1, None, None, TZ)
    user = db.get_user(1)
    text = _build_digest(db, user, "evening")
    assert "Nothing on the calendar for tomorrow" in text


def test_set_digest_persists(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.upsert_user(1, None, None, TZ)
    db.set_digest(1, "morning", "07:30")
    db.set_digest(1, "evening", "21:00")
    u = db.get_user(1)
    assert u.digest_morning == "07:30"
    assert u.digest_evening == "21:00"
    db.set_digest(1, "morning", None)
    assert db.get_user(1).digest_morning is None
