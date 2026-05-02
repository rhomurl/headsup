"""Daily digest: morning and evening summaries of upcoming reminders.

User configures times via the interactive `/digest` flow. Jobs are scheduled
per-user via PTB's JobQueue.run_daily and re-armed on startup.
"""

import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes

from headsup import messages, parse
from headsup.db import Database, User

log = logging.getLogger(__name__)

MORNING_PRESETS = [("6 AM", "06:00"), ("7 AM", "07:00"), ("8 AM", "08:00"), ("9 AM", "09:00")]
EVENING_PRESETS = [("6 PM", "18:00"), ("8 PM", "20:00"), ("9 PM", "21:00"), ("10 PM", "22:00")]


def _job_name(slot: str, chat_id: int) -> str:
    return f"digest:{slot}:{chat_id}"


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _format_hhmm(s: str | None) -> str:
    if not s:
        return "Off"
    h, m = s.split(":")
    return time(int(h), int(m)).strftime("%-I:%M %p")


# ---------------- scheduling ----------------

def schedule_user(app: Application, user: User) -> None:
    """(Re-)schedule both digest jobs for a single user."""
    cancel_user(app, user.chat_id)
    tz = ZoneInfo(user.timezone)
    if user.digest_morning:
        t = _parse_hhmm(user.digest_morning).replace(tzinfo=tz)
        app.job_queue.run_daily(
            _fire_digest,
            time=t,
            chat_id=user.chat_id,
            name=_job_name("morning", user.chat_id),
            data={"slot": "morning"},
        )
    if user.digest_evening:
        t = _parse_hhmm(user.digest_evening).replace(tzinfo=tz)
        app.job_queue.run_daily(
            _fire_digest,
            time=t,
            chat_id=user.chat_id,
            name=_job_name("evening", user.chat_id),
            data={"slot": "evening"},
        )


def cancel_user(app: Application, chat_id: int) -> None:
    for slot in ("morning", "evening"):
        for job in app.job_queue.get_jobs_by_name(_job_name(slot, chat_id)):
            job.schedule_removal()


def restore_on_startup(app: Application) -> int:
    db: Database = app.bot_data["db"]
    users = db.all_users_with_digest()
    for u in users:
        schedule_user(app, u)
    log.info("Restored digest jobs for %d users", len(users))
    return len(users)


# ---------------- fire ----------------

async def _fire_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.application.bot_data["db"]
    chat_id = context.job.chat_id
    slot = context.job.data["slot"]
    user = db.get_user(chat_id)
    if user is None:
        return
    text = _build_digest(db, user, slot)
    if text:
        await context.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN)


def _build_digest(db: Database, user: User, slot: str) -> str:
    tz = ZoneInfo(user.timezone)
    now = datetime.now(tz)
    today = now.date()
    tomorrow = today + timedelta(days=1)
    items = db.list_active(user.chat_id)

    def on(d, items_):
        return [r for r in items_ if r.next_run_at.astimezone(tz).date() == d]

    if slot == "morning":
        today_items = [r for r in on(today, items) if r.next_run_at >= now]
        tomorrow_items = on(tomorrow, items)
        body = [messages.DIGEST_MORNING_HEADER]
        if today_items:
            body.append(messages.DIGEST_TODAY_HEADER.format(count=len(today_items)))
            body.extend(_format_lines(today_items, tz))
        else:
            body.append(messages.DIGEST_TODAY_EMPTY)
        if tomorrow_items:
            body.append("")
            body.append(messages.DIGEST_TOMORROW_HEADER.format(count=len(tomorrow_items)))
            body.extend(_format_lines(tomorrow_items[:3], tz))
        body.append("")
        body.append(messages.DIGEST_MORNING_FOOTER)
        return "\n".join(body)

    # evening
    tomorrow_items = on(tomorrow, items)
    body = [messages.DIGEST_EVENING_HEADER]
    if tomorrow_items:
        body.append(messages.DIGEST_TOMORROW_HEADER.format(count=len(tomorrow_items)))
        body.extend(_format_lines(tomorrow_items, tz))
    else:
        body.append(messages.DIGEST_TOMORROW_EMPTY)
    body.append("")
    body.append(messages.DIGEST_EVENING_FOOTER)
    return "\n".join(body)


def _format_lines(items, tz: ZoneInfo) -> list[str]:
    lines = []
    for r in sorted(items, key=lambda x: x.next_run_at):
        local = r.next_run_at.astimezone(tz)
        lines.append(f"• {local.strftime('%-I:%M %p')} — {r.text}")
    return lines


# ---------------- interactive /digest ----------------

def _menu_kb(user: User) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                f"Morning: {_format_hhmm(user.digest_morning)}",
                callback_data="dig:pick:morning",
            )],
            [InlineKeyboardButton(
                f"Evening: {_format_hhmm(user.digest_evening)}",
                callback_data="dig:pick:evening",
            )],
            [InlineKeyboardButton("Close", callback_data="dig:close")],
        ]
    )


def _pick_kb(slot: str) -> InlineKeyboardMarkup:
    presets = MORNING_PRESETS if slot == "morning" else EVENING_PRESETS
    rows = [
        [InlineKeyboardButton(label, callback_data=f"dig:set:{slot}:{value}")
         for label, value in presets[i : i + 2]]
        for i in range(0, len(presets), 2)
    ]
    rows.append([InlineKeyboardButton("Turn off", callback_data=f"dig:set:{slot}:off")])
    rows.append([InlineKeyboardButton("← Back", callback_data="dig:menu")])
    return InlineKeyboardMarkup(rows)


async def digest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    user = db.get_user(update.effective_chat.id)
    if user is None:
        await update.effective_message.reply_text(messages.DIGEST_NEED_START)
        return
    await update.effective_message.reply_text(
        messages.DIGEST_MENU_HEADER, parse_mode=ParseMode.MARKDOWN, reply_markup=_menu_kb(user)
    )


async def digest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.data:
        return
    await q.answer()
    db: Database = context.bot_data["db"]
    chat_id = q.message.chat_id
    parts = q.data.split(":")
    action = parts[1]

    if action == "close":
        await q.edit_message_text(messages.DIGEST_CLOSED)
        return

    if action == "menu":
        user = db.get_user(chat_id)
        await q.edit_message_text(
            messages.DIGEST_MENU_HEADER,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_menu_kb(user),
        )
        return

    if action == "pick":
        slot = parts[2]
        await q.edit_message_text(
            messages.DIGEST_PICK_TIME.format(slot=slot.capitalize()),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_pick_kb(slot),
        )
        return

    if action == "set":
        slot = parts[2]
        value = parts[3] if parts[3] != "off" else None
        if value is not None:
            # Stored as HH:MM, presets pass "06:00" — for "06" "00" splits we need to rejoin
            if len(parts) > 4:
                value = f"{parts[3]}:{parts[4]}"
        db.set_digest(chat_id, slot, value)
        user = db.get_user(chat_id)
        schedule_user(context.application, user)
        await q.edit_message_text(
            messages.DIGEST_MENU_HEADER,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_menu_kb(user),
        )
        return
