# Headsup — Simple Telegram Notifier Bot (MVP)

## Context

We're starting a fresh project (`/Users/rhomuel/Dev/projects/headsup` is empty) to build **Headsup**, a personal Telegram bot for reminders and quick notifications. The goal of this first cut is intentionally small: a working bot the user (and later Ross) can talk to in Telegram, set reminders, and get pinged on time.

Inbound webhook for external tools is explicitly **out of scope for now** but the architecture should leave room for it later. Updates come in via **long polling** (no public URL needed — runs from a laptop, VPS, or a cheap Render/Fly worker).

**Stack decisions (locked in by user):**
- Language: **Python 3.11+**
- Telegram library: **python-telegram-bot v21+** (async, batteries-included, JobQueue for scheduling)
- DB: **SQLite** via `sqlite3` stdlib (single file, zero ops)
- Scheduler: PTB's built-in **JobQueue** (APScheduler under the hood) — handles one-time and recurring jobs with persistence on restart
- Transport: **long polling** (`Application.run_polling()`)

---

## Slash Commands (every feature gets its own)

| Command | Purpose |
|---|---|
| `/start` | Register the user (chat_id, timezone), show welcome + command list |
| `/help` | List all commands with short descriptions |
| `/remind <when> <text>` | Create a one-time reminder. e.g. `/remind tomorrow 9am pay rent` |
| `/every <interval> <text>` | Recurring reminder. e.g. `/every monday 8am foot therapy`, `/every 3d water plants` |
| `/list` | Show pending reminders with IDs |
| `/done <id>` | Mark a reminder done (or use inline button) |
| `/snooze <id> <duration>` | Snooze. e.g. `/snooze 5 1h`. Defaults to 10m if no duration |
| `/cancel <id>` | Delete a reminder |
| `/tz <zone>` | Set timezone (e.g. `/tz Asia/Manila`). Default `Asia/Manila` |
| `/notify <text>` | Send yourself a quick note/notification (useful for testing + scratchpad) |
| `/ping` | Health check — bot replies "pong" |

Inline buttons on each reminder message: **✅ Done · 💤 Snooze 10m · 🔕 Cancel**.

---

## Project Layout

```
headsup/
├── .env.example            # BOT_TOKEN, DEFAULT_TZ, DB_PATH
├── .gitignore
├── README.md
├── pyproject.toml          # deps: python-telegram-bot[job-queue], python-dateutil, pytz
├── headsup/
│   ├── __init__.py
│   ├── __main__.py         # entrypoint: load env, build Application, register handlers, run_polling
│   ├── config.py           # env loading
│   ├── db.py               # sqlite connection, schema init, CRUD helpers
│   ├── parse.py            # natural-language time parsing ("tomorrow 9am", "in 2h", "every monday")
│   ├── scheduler.py        # JobQueue helpers: schedule_one_time, schedule_recurring, restore_on_startup
│   └── handlers/
│       ├── __init__.py
│       ├── core.py         # /start /help /ping /tz /notify
│       ├── reminders.py    # /remind /every /list /done /snooze /cancel
│       └── callbacks.py    # inline button callback_query handlers
└── tests/
    ├── test_parse.py
    └── test_db.py
```

---

## Database Schema (SQLite)

```sql
CREATE TABLE users (
  chat_id      INTEGER PRIMARY KEY,
  username     TEXT,
  timezone     TEXT NOT NULL DEFAULT 'Asia/Manila',
  created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE reminders (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id      INTEGER NOT NULL REFERENCES users(chat_id),
  text         TEXT NOT NULL,
  next_run_at  TEXT NOT NULL,            -- ISO8601 UTC
  recurrence   TEXT,                     -- NULL = one-time; else cron-ish ("daily", "weekly:mon", "every:3d")
  status       TEXT NOT NULL DEFAULT 'active',  -- active | done | cancelled
  created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_reminders_chat_status ON reminders(chat_id, status);
CREATE INDEX idx_reminders_next_run ON reminders(next_run_at) WHERE status = 'active';
```

On startup, `scheduler.restore_on_startup()` queries all `active` reminders and re-registers them with JobQueue.

---

## Key Files to Create

- **[headsup/__main__.py](headsup/__main__.py)** — `Application.builder().token(...).build()`, register handlers, call `restore_on_startup`, then `run_polling()`
- **[headsup/parse.py](headsup/parse.py)** — small wrapper around `dateutil.parser` + a few regex patterns for `in 2h`, `tomorrow 9am`, `every monday 8am`, `every 3d`. Return `(next_run_dt_utc, recurrence_str_or_none)`
- **[headsup/scheduler.py](headsup/scheduler.py)** — `schedule_reminder(app, reminder)` calls `app.job_queue.run_once(...)` or `run_repeating(...)`. Job callback fires the message with inline buttons and, for recurring reminders, computes the next `next_run_at` and updates the row
- **[headsup/handlers/reminders.py](headsup/handlers/reminders.py)** — command handlers that parse args, insert row, schedule job, ack to user
- **[headsup/handlers/callbacks.py](headsup/handlers/callbacks.py)** — handles `done:<id>`, `snooze:<id>:<minutes>`, `cancel:<id>` callback data

---

## Reuse / Libraries (no need to write from scratch)

- **python-telegram-bot's JobQueue** for scheduling — don't reinvent with `asyncio.sleep` loops
- **dateutil.parser** for free-form date strings
- **pytz** (or stdlib `zoneinfo` on 3.11+) for timezone handling
- PTB's built-in `CommandHandler`, `CallbackQueryHandler`, `Application.persistence` (optional later)

---

## Verification

1. `cp .env.example .env`, paste `BOT_TOKEN` from @BotFather
2. `pip install -e .` then `python -m headsup`
3. In Telegram, message the bot:
   - `/start` → registers, replies welcome
   - `/remind in 1m test` → wait 60s, message arrives with Done/Snooze buttons
   - `/every 2m heartbeat` → fires twice to confirm recurrence
   - `/list` → shows both reminders with IDs
   - Tap **Done** → reminder marked done, `/list` no longer shows it
   - `/snooze <id> 30s` → message reappears 30s later
   - `/notify hello` → bot echoes back "hello" (sanity check)
4. Restart the process — pending reminders should still fire (restore_on_startup works)
5. `pytest tests/` — covers `parse.py` (date strings) and `db.py` (CRUD)

---

## Out of Scope (future iterations)

- Inbound `POST /notify` webhook for n8n/GitHub/etc. (architecture leaves room — add a FastAPI app sharing the same DB and `bot.send_message`)
- Categories, priority, escalation, daily digest, shared workspaces, templates, approval buttons, CRM, calendar
- Web dashboard