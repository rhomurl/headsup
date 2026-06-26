from datetime import datetime, timezone

from headsup.db import Database
from headsup import scheduler


class _FakeJobQueue:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run_once(self, callback, when, chat_id, name, data):
        self.calls.append(
            {
                "callback": callback,
                "when": when,
                "chat_id": chat_id,
                "name": name,
                "data": data,
            }
        )

    def get_jobs_by_name(self, _name):
        return []


class _FakeApp:
    def __init__(self, db: Database) -> None:
        self.bot_data = {"db": db}
        self.job_queue = _FakeJobQueue()


class _FixedDateTime(datetime):
    current = datetime(2026, 6, 26, 13, 52, 12, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls.current
        return cls.current.astimezone(tz)


def test_restore_on_startup_preserves_daily_wall_clock_for_overdue_recurring(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "test.db"))
    db.upsert_user(1, "alice", "Alice", "Asia/Manila")
    reminder_id = db.add_reminder(
        1,
        "daily devotion",
        datetime(2026, 6, 26, 1, 0, tzinfo=timezone.utc),
        "daily",
    )
    app = _FakeApp(db)

    monkeypatch.setattr(scheduler, "datetime", _FixedDateTime)

    scheduler.restore_on_startup(app)

    reminder = db.get_reminder(reminder_id)
    assert reminder is not None
    assert reminder.next_run_at == datetime(2026, 6, 27, 1, 0, tzinfo=timezone.utc)
    assert app.job_queue.calls[0]["when"] == datetime(2026, 6, 27, 1, 0, tzinfo=timezone.utc)


def test_restore_on_startup_preserves_weekly_day_for_overdue_recurring(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "test.db"))
    db.upsert_user(1, "alice", "Alice", "Asia/Manila")
    reminder_id = db.add_reminder(
        1,
        "church",
        datetime(2026, 6, 21, 10, 30, tzinfo=timezone.utc),
        "weekly:sun",
    )
    app = _FakeApp(db)

    monkeypatch.setattr(scheduler, "datetime", _FixedDateTime)

    scheduler.restore_on_startup(app)

    reminder = db.get_reminder(reminder_id)
    assert reminder is not None
    assert reminder.next_run_at == datetime(2026, 6, 28, 10, 30, tzinfo=timezone.utc)
    assert app.job_queue.calls[0]["when"] == datetime(2026, 6, 28, 10, 30, tzinfo=timezone.utc)
