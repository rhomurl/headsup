import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    chat_id          INTEGER PRIMARY KEY,
    username         TEXT,
    first_name       TEXT,
    timezone         TEXT NOT NULL DEFAULT 'Asia/Manila',
    onboarded        INTEGER NOT NULL DEFAULT 0,
    quiet_hours      TEXT,
    digest_morning   TEXT,
    digest_evening   TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reminders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id      INTEGER NOT NULL REFERENCES users(chat_id),
    text         TEXT NOT NULL,
    next_run_at  TEXT NOT NULL,
    recurrence   TEXT,
    status       TEXT NOT NULL DEFAULT 'active',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_reminders_chat_status
    ON reminders(chat_id, status);
CREATE INDEX IF NOT EXISTS idx_reminders_next_run
    ON reminders(next_run_at) WHERE status = 'active';
"""


@dataclass
class User:
    chat_id: int
    username: str | None
    first_name: str | None
    timezone: str
    onboarded: bool
    quiet_hours: str | None
    digest_morning: str | None
    digest_evening: str | None


@dataclass
class Reminder:
    id: int
    chat_id: int
    text: str
    next_run_at: datetime
    recurrence: str | None
    status: str


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(users)").fetchall()}
        for col, ddl in [
            ("digest_morning", "ALTER TABLE users ADD COLUMN digest_morning TEXT"),
            ("digest_evening", "ALTER TABLE users ADD COLUMN digest_evening TEXT"),
        ]:
            if col not in cols:
                self._conn.execute(ddl)

    @contextmanager
    def cursor(self) -> Iterator[sqlite3.Cursor]:
        cur = self._conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

    # --- users ---

    def get_user(self, chat_id: int) -> User | None:
        with self.cursor() as cur:
            row = cur.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
        return _row_to_user(row) if row else None

    def upsert_user(
        self,
        chat_id: int,
        username: str | None,
        first_name: str | None,
        default_tz: str,
    ) -> User:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (chat_id, username, first_name, timezone)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name
                """,
                (chat_id, username, first_name, default_tz),
            )
        user = self.get_user(chat_id)
        assert user is not None
        return user

    def set_timezone(self, chat_id: int, tz: str) -> None:
        with self.cursor() as cur:
            cur.execute("UPDATE users SET timezone = ? WHERE chat_id = ?", (tz, chat_id))

    def mark_onboarded(self, chat_id: int) -> None:
        with self.cursor() as cur:
            cur.execute("UPDATE users SET onboarded = 1 WHERE chat_id = ?", (chat_id,))

    def set_digest(self, chat_id: int, slot: str, hhmm: str | None) -> None:
        assert slot in {"morning", "evening"}
        col = f"digest_{slot}"
        with self.cursor() as cur:
            cur.execute(f"UPDATE users SET {col} = ? WHERE chat_id = ?", (hhmm, chat_id))

    def all_users_with_digest(self) -> list[User]:
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM users WHERE digest_morning IS NOT NULL OR digest_evening IS NOT NULL"
            ).fetchall()
        return [_row_to_user(r) for r in rows]

    # --- reminders ---

    def add_reminder(
        self,
        chat_id: int,
        text: str,
        next_run_at: datetime,
        recurrence: str | None,
    ) -> int:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO reminders (chat_id, text, next_run_at, recurrence)
                VALUES (?, ?, ?, ?)
                """,
                (chat_id, text, _to_iso(next_run_at), recurrence),
            )
            return int(cur.lastrowid or 0)

    def get_reminder(self, reminder_id: int) -> Reminder | None:
        with self.cursor() as cur:
            row = cur.execute(
                "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
            ).fetchone()
        return _row_to_reminder(row) if row else None

    def list_active(self, chat_id: int) -> list[Reminder]:
        with self.cursor() as cur:
            rows = cur.execute(
                """
                SELECT * FROM reminders
                WHERE chat_id = ? AND status = 'active'
                ORDER BY next_run_at ASC
                """,
                (chat_id,),
            ).fetchall()
        return [_row_to_reminder(r) for r in rows]

    def all_active(self) -> list[Reminder]:
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM reminders WHERE status = 'active'"
            ).fetchall()
        return [_row_to_reminder(r) for r in rows]

    def update_next_run(self, reminder_id: int, next_run_at: datetime) -> None:
        with self.cursor() as cur:
            cur.execute(
                "UPDATE reminders SET next_run_at = ? WHERE id = ?",
                (_to_iso(next_run_at), reminder_id),
            )

    def set_status(self, reminder_id: int, status: str) -> None:
        with self.cursor() as cur:
            cur.execute(
                "UPDATE reminders SET status = ? WHERE id = ?", (status, reminder_id)
            )

    def close(self) -> None:
        self._conn.close()


def _to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _from_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _row_to_user(row: sqlite3.Row) -> User:
    return User(
        chat_id=row["chat_id"],
        username=row["username"],
        first_name=row["first_name"],
        timezone=row["timezone"],
        onboarded=bool(row["onboarded"]),
        quiet_hours=row["quiet_hours"],
        digest_morning=row["digest_morning"],
        digest_evening=row["digest_evening"],
    )


def _row_to_reminder(row: sqlite3.Row) -> Reminder:
    return Reminder(
        id=row["id"],
        chat_id=row["chat_id"],
        text=row["text"],
        next_run_at=_from_iso(row["next_run_at"]),
        recurrence=row["recurrence"],
        status=row["status"],
    )
