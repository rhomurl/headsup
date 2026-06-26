"""Schedule reminder fires via PTB's JobQueue. One-time and recurring both use
`run_once` — recurring reminders re-schedule themselves after each fire."""

import logging
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes

from headsup import parse
from headsup.db import Database, Reminder

log = logging.getLogger(__name__)


def _job_name(reminder_id: int) -> str:
    return f"reminder:{reminder_id}"


def schedule(app: Application, reminder: Reminder) -> None:
    """Schedule (or re-schedule) a single reminder."""
    cancel(app, reminder.id)
    when = reminder.next_run_at
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    app.job_queue.run_once(
        _fire,
        when=when,
        chat_id=reminder.chat_id,
        name=_job_name(reminder.id),
        data={"reminder_id": reminder.id},
    )


def cancel(app: Application, reminder_id: int) -> None:
    for job in app.job_queue.get_jobs_by_name(_job_name(reminder_id)):
        job.schedule_removal()


def restore_on_startup(app: Application) -> int:
    db: Database = app.bot_data["db"]
    reminders = db.all_active()
    now = datetime.now(timezone.utc)
    for r in reminders:
        if r.next_run_at < now:
            if r.recurrence:
                user = db.get_user(r.chat_id)
                tz_name = user.timezone if user else "UTC"
                next_utc = parse.next_recurring_after(r.next_run_at, r.recurrence, tz_name, now)
                if next_utc:
                    db.update_next_run(r.id, next_utc)
                    r.next_run_at = next_utc
                else:
                    db.update_next_run(r.id, now)
                    r.next_run_at = now
            else:
                # One-time reminders still fire ~immediately so the user isn't silently skipped.
                db.update_next_run(r.id, now)
                r.next_run_at = now
        schedule(app, r)
    log.info("Restored %d active reminders", len(reminders))
    return len(reminders)


def _action_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Mark Done", callback_data=f"act:done:{reminder_id}"),
                InlineKeyboardButton("Snooze 10 min", callback_data=f"act:snooze:{reminder_id}:10"),
            ],
            [
                InlineKeyboardButton("Snooze 1 hour", callback_data=f"act:snooze:{reminder_id}:60"),
                InlineKeyboardButton("Cancel", callback_data=f"act:cancel:{reminder_id}"),
            ],
            [InlineKeyboardButton("Edit", callback_data=f"edit:start:{reminder_id}")],
        ]
    )


async def _fire(context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.application.bot_data["db"]
    reminder_id = context.job.data["reminder_id"]
    reminder = db.get_reminder(reminder_id)
    if reminder is None or reminder.status != "active":
        return

    user = db.get_user(reminder.chat_id)
    tz_name = user.timezone if user else "UTC"

    text = f"🔔 *Reminder:* {reminder.text}"
    if reminder.recurrence:
        text += f"\n_{parse.format_recurrence(reminder.recurrence)}_"

    await context.bot.send_message(
        chat_id=reminder.chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_action_keyboard(reminder.id),
    )

    if reminder.recurrence:
        next_utc = parse.next_recurring(reminder.next_run_at, reminder.recurrence, tz_name)
        if next_utc:
            db.update_next_run(reminder.id, next_utc)
            reminder.next_run_at = next_utc
            schedule(context.application, reminder)
        else:
            db.set_status(reminder.id, "done")
    else:
        db.set_status(reminder.id, "done")
