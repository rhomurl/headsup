from datetime import datetime, timezone

from headsup.db import Database


def test_user_upsert_and_onboarding(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    assert db.get_user(1) is None

    user = db.upsert_user(1, "alice", "Alice", "Asia/Manila")
    assert user.chat_id == 1
    assert user.timezone == "Asia/Manila"
    assert user.onboarded is False

    db.mark_onboarded(1)
    assert db.get_user(1).onboarded is True

    db.set_timezone(1, "America/New_York")
    assert db.get_user(1).timezone == "America/New_York"


def test_reminder_lifecycle(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.upsert_user(1, None, None, "UTC")
    when = datetime(2030, 1, 1, 9, 0, tzinfo=timezone.utc)
    rid = db.add_reminder(1, "pay rent", when, None)
    assert rid > 0

    reminder = db.get_reminder(rid)
    assert reminder.text == "pay rent"
    assert reminder.status == "active"

    assert len(db.list_active(1)) == 1
    db.set_status(rid, "done")
    assert db.list_active(1) == []
