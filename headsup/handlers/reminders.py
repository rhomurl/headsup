"""Conversational handlers for /remind, /every, /list, /done, /snooze, /cancel,
plus the New-reminder type chooser, the Edit flow, and the per-reminder Manage menu."""

import calendar
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from headsup import messages, parse, scheduler
from headsup.db import Database, Reminder

# /remind states
R_WHEN, R_TIME, R_TEXT = range(3)
# /every states
E_FREQ, E_TIME, E_TEXT = range(3, 6)
# Edit states
ED_MENU, ED_WHEN, ED_TIME, ED_TEXT = range(6, 10)
# Monthly day-of-month picker state
E_MDAY = 10

TIME_PRESETS = [
    ("7 AM", time(7, 0)),
    ("8 AM", time(8, 0)),
    ("9 AM", time(9, 0)),
    ("12 PM", time(12, 0)),
    ("3 PM", time(15, 0)),
    ("6 PM", time(18, 0)),
    ("8 PM", time(20, 0)),
    ("9 PM", time(21, 0)),
]


# ---------------- helpers ----------------

def _user_tz(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> str:
    db: Database = context.bot_data["db"]
    user = db.get_user(chat_id)
    return user.timezone if user else context.bot_data.get("default_tz", "UTC")


def _ensure_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Make sure the chat's user row exists before any reminder is inserted.
    Reminders have a FK to users; without this, a fresh chat that jumps straight
    to /remind or ➕ New reminder hits an IntegrityError."""
    db: Database = context.bot_data["db"]
    chat = update.effective_chat
    user = update.effective_user
    if chat is None:
        return
    if db.get_user(chat.id) is None:
        db.upsert_user(
            chat.id,
            user.username if user else None,
            user.first_name if user else None,
            context.bot_data.get("default_tz", "Asia/Manila"),
        )


async def _send_or_edit(
    update: Update, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> None:
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup
        )
    else:
        await update.effective_message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup
        )


# ---------------- keyboards ----------------

def _cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="r:cancel")]])


def _when_quick_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("In 1 hour", callback_data="r:quick:in 1h"),
                InlineKeyboardButton("Tonight 8 PM", callback_data="r:quick:tonight"),
            ],
            [
                InlineKeyboardButton("Tomorrow 9 AM", callback_data="r:quick:tomorrow 9am"),
                InlineKeyboardButton("Tomorrow 6 PM", callback_data="r:quick:tomorrow 6pm"),
            ],
            [InlineKeyboardButton("Cancel", callback_data="r:cancel")],
        ]
    )


def _time_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(TIME_PRESETS), 4):
        rows.append(
            [InlineKeyboardButton(label, callback_data=f"r:t:{t.hour}:{t.minute}")
             for label, t in TIME_PRESETS[i : i + 4]]
        )
    rows.append([InlineKeyboardButton("Cancel", callback_data="r:cancel")])
    return InlineKeyboardMarkup(rows)


def _freq_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Every day", callback_data="e:f:daily")],
            [
                InlineKeyboardButton("Every week", callback_data="e:f:weekly"),
                InlineKeyboardButton("Every other week", callback_data="e:f:biweekly"),
            ],
            [
                InlineKeyboardButton("Every 3 days", callback_data="e:f:every:3d"),
                InlineKeyboardButton("Every 14 days", callback_data="e:f:every:14d"),
            ],
            [InlineKeyboardButton("Monthly", callback_data="e:f:monthly")],
            [InlineKeyboardButton("Cancel", callback_data="r:cancel")],
        ]
    )


def _month_day_kb() -> InlineKeyboardMarkup:
    rows = []
    for start in range(1, 29, 7):
        rows.append([
            InlineKeyboardButton(str(d), callback_data=f"e:md:{d}")
            for d in range(start, start + 7)
        ])
    rows.append([
        InlineKeyboardButton(f"{d}*", callback_data=f"e:md:{d}")
        for d in (29, 30, 31)
    ])
    rows.append([InlineKeyboardButton("Cancel", callback_data="r:cancel")])
    return InlineKeyboardMarkup(rows)


def _post_create_kb(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Edit", callback_data=f"edit:start:{reminder_id}"),
                InlineKeyboardButton("All set", callback_data="edit:close"),
            ]
        ]
    )


def _fired_kb(reminder_id: int) -> InlineKeyboardMarkup:
    """Keyboard attached to a reminder when it fires."""
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


# ---------------- New-reminder type chooser ----------------

async def new_chooser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _ensure_user(update, context)
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("One-time", callback_data="new:once"),
                InlineKeyboardButton("Recurring", callback_data="new:recur"),
            ],
            [InlineKeyboardButton("Cancel", callback_data="r:cancel")],
        ]
    )
    await update.effective_message.reply_text(
        messages.NEW_CHOOSE_TYPE, parse_mode=ParseMode.MARKDOWN, reply_markup=kb
    )


# ---------------- /remind ----------------

async def remind_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
    _ensure_user(update, context)
    context.user_data.pop("remind", None)
    context.user_data["remind"] = {}
    await _send_or_edit(update, messages.REMIND_ASK_WHEN, _when_quick_kb())
    return R_WHEN


async def remind_when_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _handle_when(update, context, update.effective_message.text or "")


async def remind_when_quick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    text = q.data.split(":", 2)[2]
    return await _handle_when(update, context, text, edit=True)


async def _handle_when(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, edit: bool = False
) -> int:
    chat_id = update.effective_chat.id
    tz_name = _user_tz(context, chat_id)
    parsed = parse.parse_when(text, tz_name)
    if parsed is None:
        await update.effective_message.reply_text(messages.PARSE_ERROR, reply_markup=_cancel_kb())
        return R_WHEN

    now = datetime.now(ZoneInfo(tz_name))
    if parsed.has_time and parsed.when <= now:
        await update.effective_message.reply_text(messages.REMIND_PAST, reply_markup=_cancel_kb())
        return R_WHEN

    context.user_data["remind"]["date"] = parsed.when.date().isoformat()

    if not parsed.has_time:
        date_str = parsed.when.strftime("%A, %b %-d")
        prompt = messages.REMIND_ASK_TIME.format(date_str=date_str)
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(
                prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=_time_kb()
            )
        else:
            await update.effective_message.reply_text(
                prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=_time_kb()
            )
        return R_TIME

    return await _ask_text(update, context, parsed.when, edit=edit)


async def remind_time_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    return await _apply_time(update, context, time(int(parts[2]), int(parts[3])), edit=True)


async def remind_time_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    t = parse.parse_time_only(update.effective_message.text or "")
    if t is None:
        await update.effective_message.reply_text(messages.PARSE_ERROR, reply_markup=_cancel_kb())
        return R_TIME
    return await _apply_time(update, context, t, edit=False)


async def _apply_time(
    update: Update, context: ContextTypes.DEFAULT_TYPE, t: time, edit: bool
) -> int:
    chat_id = update.effective_chat.id
    tz_name = _user_tz(context, chat_id)
    tz = ZoneInfo(tz_name)
    d = datetime.fromisoformat(context.user_data["remind"]["date"]).date()
    when = datetime.combine(d, t, tzinfo=tz)
    now = datetime.now(tz)
    if when <= now:
        msg = messages.REMIND_PAST
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(msg, reply_markup=_time_kb())
        else:
            await update.effective_message.reply_text(msg, reply_markup=_time_kb())
        return R_TIME
    return await _ask_text(update, context, when, edit=edit)


async def _ask_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, when: datetime, edit: bool
) -> int:
    chat_id = update.effective_chat.id
    tz_name = _user_tz(context, chat_id)
    when_utc = parse.to_utc(when)
    context.user_data["remind"]["when_utc"] = when_utc.isoformat()
    when_str = parse.format_when(when_utc, tz_name)
    prompt = messages.REMIND_ASK_TEXT.format(when_str=when_str)
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=_cancel_kb()
        )
    else:
        await update.effective_message.reply_text(
            prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=_cancel_kb()
        )
    return R_TEXT


async def remind_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.effective_message.text or "").strip()
    if not text:
        return R_TEXT
    chat_id = update.effective_chat.id
    tz_name = _user_tz(context, chat_id)
    when_utc = datetime.fromisoformat(context.user_data["remind"]["when_utc"])
    db: Database = context.bot_data["db"]
    rid = db.add_reminder(chat_id, text, when_utc, recurrence=None)
    reminder = db.get_reminder(rid)
    scheduler.schedule(context.application, reminder)
    when_str = parse.format_when(when_utc, tz_name)
    await update.effective_message.reply_text(
        messages.REMIND_DONE.format(when_str=when_str, text=text),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_post_create_kb(rid),
    )
    context.user_data.pop("remind", None)
    return ConversationHandler.END


# ---------------- /every ----------------

async def every_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
    _ensure_user(update, context)
    context.user_data.pop("every", None)
    context.user_data["every"] = {}
    await _send_or_edit(update, messages.EVERY_ASK_FREQ, _freq_kb())
    return E_FREQ


async def every_freq_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":", 2)[2]
    if parts == "daily":
        recurrence = "daily"
        freq_label = "every day"
    elif parts.startswith("weekly:"):
        wd = parts.split(":", 1)[1]
        recurrence = f"weekly:{wd}"
        freq_label = f"every {parse.WEEKDAY_NAMES[parse.WEEKDAYS[wd]]}"
    elif parts.startswith("every:"):
        recurrence = parts
        freq_label = f"every {parts[len('every:'):]}"
    elif parts == "monthly":
        await q.edit_message_text(
            messages.EVERY_ASK_MDAY,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_month_day_kb(),
        )
        return E_MDAY
    else:
        return E_FREQ
    context.user_data["every"]["recurrence"] = recurrence
    context.user_data["every"]["freq_label"] = freq_label
    await q.edit_message_text(
        messages.EVERY_ASK_TIME.format(freq_label=freq_label),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_time_kb(),
    )
    return E_TIME


async def every_mday_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    day = int(q.data.split(":")[2])
    recurrence = f"monthly:{day}"
    freq_label = f"monthly on the {parse._ordinal(day)}"
    context.user_data["every"]["recurrence"] = recurrence
    context.user_data["every"]["freq_label"] = freq_label
    await q.edit_message_text(
        messages.EVERY_ASK_TIME.format(freq_label=freq_label),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_time_kb(),
    )
    return E_TIME


async def every_time_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    return await _every_apply_time(update, context, time(int(parts[2]), int(parts[3])), edit=True)


async def every_time_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    t = parse.parse_time_only(update.effective_message.text or "")
    if t is None:
        await update.effective_message.reply_text(messages.PARSE_ERROR, reply_markup=_cancel_kb())
        return E_TIME
    return await _every_apply_time(update, context, t, edit=False)


async def _every_apply_time(
    update: Update, context: ContextTypes.DEFAULT_TYPE, t: time, edit: bool
) -> int:
    chat_id = update.effective_chat.id
    tz_name = _user_tz(context, chat_id)
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    recurrence = context.user_data["every"]["recurrence"]

    first = _first_fire(recurrence, t, now, tz)
    context.user_data["every"]["first_utc"] = parse.to_utc(first).isoformat()
    freq_label = context.user_data["every"]["freq_label"]
    freq_str = f"{freq_label} at {t.strftime('%-I:%M %p')}"
    context.user_data["every"]["freq_str"] = freq_str

    prompt = messages.EVERY_ASK_TEXT.format(freq_str=freq_str)
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=_cancel_kb()
        )
    else:
        await update.effective_message.reply_text(
            prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=_cancel_kb()
        )
    return E_TEXT


def _first_fire(recurrence: str, t: time, now: datetime, tz: ZoneInfo) -> datetime:
    today_at = datetime.combine(now.date(), t, tzinfo=tz)
    if recurrence == "daily" or recurrence.startswith("every:"):
        return today_at if today_at > now else today_at + timedelta(days=1)
    if recurrence.startswith("weekly:") or recurrence.startswith("biweekly:"):
        wd = parse.WEEKDAYS[recurrence.split(":", 1)[1]]
        days_ahead = (wd - now.weekday()) % 7
        candidate = today_at + timedelta(days=days_ahead)
        if candidate <= now:
            candidate += timedelta(days=7)
        return candidate
    if recurrence.startswith("monthly:"):
        target_day = int(recurrence.split(":")[1])
        year, month = now.year, now.month
        last = calendar.monthrange(year, month)[1]
        candidate = today_at.replace(day=min(target_day, last))
        if candidate <= now:
            if month == 12:
                year, month = year + 1, 1
            else:
                month += 1
            last = calendar.monthrange(year, month)[1]
            candidate = candidate.replace(year=year, month=month, day=min(target_day, last))
        return candidate
    return today_at


async def every_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.effective_message.text or "").strip()
    if not text:
        return E_TEXT
    chat_id = update.effective_chat.id
    tz_name = _user_tz(context, chat_id)
    state = context.user_data["every"]
    first_utc = datetime.fromisoformat(state["first_utc"])
    db: Database = context.bot_data["db"]
    rid = db.add_reminder(chat_id, text, first_utc, recurrence=state["recurrence"])
    reminder = db.get_reminder(rid)
    scheduler.schedule(context.application, reminder)
    when_str = parse.format_when(first_utc, tz_name)
    await update.effective_message.reply_text(
        messages.EVERY_DONE.format(freq_str=state["freq_str"], text=text, when_str=when_str),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_post_create_kb(rid),
    )
    context.user_data.pop("every", None)
    return ConversationHandler.END


# ---------------- shared cancel ----------------

async def conv_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("remind", None)
    context.user_data.pop("every", None)
    context.user_data.pop("edit", None)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(messages.CANCELLED)
    else:
        await update.effective_message.reply_text(messages.CANCELLED)
    return ConversationHandler.END


# ---------------- /list, /done, /snooze, /cancel ----------------

def _format_reminder_line(r: Reminder, tz_name: str, pos: int) -> str:
    return messages.LIST_LINE.format(
        pos=pos,
        text=r.text,
        when_str=parse.format_when(r.next_run_at, tz_name),
        rec=f" · {parse.format_recurrence(r.recurrence)}" if r.recurrence else "",
    )


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    chat_id = update.effective_chat.id
    items = db.list_active(chat_id)
    if not items:
        await update.effective_message.reply_text(messages.EMPTY_LIST)
        return
    tz_name = _user_tz(context, chat_id)
    body = messages.LIST_HEADER + "\n\n" + "\n\n".join(
        _format_reminder_line(r, tz_name, pos) for pos, r in enumerate(items, 1)
    )
    buttons = [
        InlineKeyboardButton(f"Manage {pos}", callback_data=f"act:manage:{r.id}")
        for pos, r in enumerate(items, 1)
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    await update.effective_message.reply_text(
        body, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(rows)
    )


# ---------------- inline action callbacks ----------------

SNOOZE_PRESETS = [
    ("10 min", 10), ("30 min", 30), ("1 hour", 60),
    ("3 hours", 180), ("Tomorrow 9 AM", -1),
]


def _snooze_kb(reminder_id: int) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(SNOOZE_PRESETS), 3):
        rows.append(
            [
                InlineKeyboardButton(label, callback_data=f"act:snooze:{reminder_id}:{mins}")
                for label, mins in SNOOZE_PRESETS[i : i + 3]
            ]
        )
    return InlineKeyboardMarkup(rows)


def _manage_kb(reminder: Reminder) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("Mark Done", callback_data=f"act:done:{reminder.id}"),
            InlineKeyboardButton("Snooze", callback_data=f"act:snoozepick:{reminder.id}"),
        ],
        [
            InlineKeyboardButton("Edit", callback_data=f"edit:start:{reminder.id}"),
            InlineKeyboardButton("Cancel reminder", callback_data=f"act:cancel:{reminder.id}"),
        ],
    ]
    if reminder.recurrence:
        rows.append([InlineKeyboardButton("Skip this one", callback_data=f"act:skip:{reminder.id}")])
    return InlineKeyboardMarkup(rows)


async def action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.data:
        return
    await q.answer()
    db: Database = context.bot_data["db"]
    parts = q.data.split(":")
    action = parts[1]
    reminder_id = int(parts[2])
    reminder = db.get_reminder(reminder_id)
    if reminder is None or reminder.status != "active":
        await q.edit_message_text(messages.NOT_FOUND)
        return

    if action == "manage":
        chat_id = q.message.chat_id
        tz_name = _user_tz(context, chat_id)
        body = (
            f"*{reminder.text}*\n"
            f"{parse.format_when(reminder.next_run_at, tz_name)}"
            f"{' · ' + parse.format_recurrence(reminder.recurrence) if reminder.recurrence else ''}"
        )
        await q.edit_message_text(
            body, parse_mode=ParseMode.MARKDOWN, reply_markup=_manage_kb(reminder)
        )
        return

    if action == "done":
        db.set_status(reminder_id, "done")
        scheduler.cancel(context.application, reminder_id)
        await q.edit_message_text(messages.ACTION_DONE)
        return

    if action == "cancel":
        db.set_status(reminder_id, "cancelled")
        scheduler.cancel(context.application, reminder_id)
        await q.edit_message_text(messages.ACTION_CANCELLED)
        return

    if action == "skip":
        chat_id = q.message.chat_id
        tz_name = _user_tz(context, chat_id)
        next_utc = parse.next_recurring(reminder.next_run_at, reminder.recurrence, tz_name)
        if next_utc:
            db.update_next_run(reminder_id, next_utc)
            reminder.next_run_at = next_utc
            scheduler.schedule(context.application, reminder)
            await q.edit_message_text(
                messages.ACTION_SKIPPED.format(when_str=parse.format_when(next_utc, tz_name)),
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            db.set_status(reminder_id, "done")
            scheduler.cancel(context.application, reminder_id)
            await q.edit_message_text(messages.ACTION_DONE)
        return

    if action == "snoozepick":
        await q.edit_message_text(
            messages.SNOOZE_PICK_DURATION.format(id=reminder_id),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_snooze_kb(reminder_id),
        )
        return

    if action == "snooze":
        mins = int(parts[3])
        chat_id = q.message.chat_id
        tz_name = _user_tz(context, chat_id)
        if mins == -1:
            tz = ZoneInfo(tz_name)
            tomorrow_9 = datetime.combine(
                datetime.now(tz).date() + timedelta(days=1), time(9, 0), tzinfo=tz
            )
            new_when = parse.to_utc(tomorrow_9)
        else:
            new_when = datetime.now(timezone.utc) + timedelta(minutes=mins)
        db.update_next_run(reminder_id, new_when)
        reminder.next_run_at = new_when
        scheduler.schedule(context.application, reminder)
        await q.edit_message_text(
            messages.ACTION_SNOOZED.format(when_str=parse.format_when(new_when, tz_name)),
            parse_mode=ParseMode.MARKDOWN,
        )
        return


# ---------------- Edit conversation ----------------

def _edit_menu_kb(reminder: Reminder) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("Change time", callback_data="edit:do:time")],
        [InlineKeyboardButton("Change text", callback_data="edit:do:text")],
        [InlineKeyboardButton("Cancel reminder", callback_data="edit:do:cancel")],
        [InlineKeyboardButton("Close", callback_data="edit:do:close")],
    ]
    return InlineKeyboardMarkup(rows)


async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    rid = int(parts[2])
    db: Database = context.bot_data["db"]
    reminder = db.get_reminder(rid)
    if reminder is None or reminder.status != "active":
        await q.edit_message_text(messages.NOT_FOUND)
        return ConversationHandler.END
    chat_id = q.message.chat_id
    tz_name = _user_tz(context, chat_id)
    context.user_data["edit"] = {"id": rid}
    body = messages.EDIT_MENU_HEADER.format(
        id=reminder.id,
        text=reminder.text,
        when_str=parse.format_when(reminder.next_run_at, tz_name),
        rec=f" · {parse.format_recurrence(reminder.recurrence)}" if reminder.recurrence else "",
    )
    await q.edit_message_text(
        body, parse_mode=ParseMode.MARKDOWN, reply_markup=_edit_menu_kb(reminder)
    )
    return ED_MENU


async def edit_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    if q.data == "edit:close":
        # From the post-create "All set" button — just clear the keyboard.
        await q.edit_message_reply_markup(reply_markup=None)
        return ConversationHandler.END
    # From the edit menu's "Close" button.
    await q.edit_message_text(messages.EDIT_NO_CHANGE)
    context.user_data.pop("edit", None)
    return ConversationHandler.END


async def edit_menu_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    action = q.data.split(":")[2]
    rid = context.user_data["edit"]["id"]
    db: Database = context.bot_data["db"]

    if action == "close":
        await q.edit_message_text(messages.EDIT_NO_CHANGE)
        context.user_data.pop("edit", None)
        return ConversationHandler.END

    if action == "cancel":
        db.set_status(rid, "cancelled")
        scheduler.cancel(context.application, rid)
        await q.edit_message_text(messages.ACTION_CANCELLED)
        context.user_data.pop("edit", None)
        return ConversationHandler.END

    if action == "time":
        await q.edit_message_text(
            messages.EDIT_ASK_WHEN.format(id=rid),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_when_quick_kb(),
        )
        return ED_WHEN

    if action == "text":
        await q.edit_message_text(
            messages.EDIT_ASK_TEXT.format(id=rid),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_cancel_kb(),
        )
        return ED_TEXT

    return ED_MENU


async def edit_when_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _edit_handle_when(update, context, update.effective_message.text or "")


async def edit_when_quick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    text = q.data.split(":", 2)[2]
    return await _edit_handle_when(update, context, text, edit=True)


async def _edit_handle_when(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, edit: bool = False
) -> int:
    chat_id = update.effective_chat.id
    tz_name = _user_tz(context, chat_id)
    parsed = parse.parse_when(text, tz_name)
    if parsed is None:
        await update.effective_message.reply_text(messages.PARSE_ERROR, reply_markup=_cancel_kb())
        return ED_WHEN
    now = datetime.now(ZoneInfo(tz_name))
    if parsed.has_time and parsed.when <= now:
        await update.effective_message.reply_text(messages.REMIND_PAST, reply_markup=_cancel_kb())
        return ED_WHEN

    context.user_data["edit"]["date"] = parsed.when.date().isoformat()

    if not parsed.has_time:
        date_str = parsed.when.strftime("%A, %b %-d")
        prompt = messages.EDIT_ASK_TIME.format(date_str=date_str)
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(
                prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=_time_kb()
            )
        else:
            await update.effective_message.reply_text(
                prompt, parse_mode=ParseMode.MARKDOWN, reply_markup=_time_kb()
            )
        return ED_TIME
    return await _edit_save_time(update, context, parsed.when, edit=edit)


async def edit_time_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    return await _edit_apply_time(update, context, time(int(parts[2]), int(parts[3])), edit=True)


async def edit_time_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    t = parse.parse_time_only(update.effective_message.text or "")
    if t is None:
        await update.effective_message.reply_text(messages.PARSE_ERROR, reply_markup=_cancel_kb())
        return ED_TIME
    return await _edit_apply_time(update, context, t, edit=False)


async def _edit_apply_time(
    update: Update, context: ContextTypes.DEFAULT_TYPE, t: time, edit: bool
) -> int:
    chat_id = update.effective_chat.id
    tz_name = _user_tz(context, chat_id)
    tz = ZoneInfo(tz_name)
    d = datetime.fromisoformat(context.user_data["edit"]["date"]).date()
    when = datetime.combine(d, t, tzinfo=tz)
    if when <= datetime.now(tz):
        msg = messages.REMIND_PAST
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(msg, reply_markup=_time_kb())
        else:
            await update.effective_message.reply_text(msg, reply_markup=_time_kb())
        return ED_TIME
    return await _edit_save_time(update, context, when, edit=edit)


async def _edit_save_time(
    update: Update, context: ContextTypes.DEFAULT_TYPE, when: datetime, edit: bool
) -> int:
    chat_id = update.effective_chat.id
    tz_name = _user_tz(context, chat_id)
    rid = context.user_data["edit"]["id"]
    db: Database = context.bot_data["db"]
    when_utc = parse.to_utc(when)
    db.update_next_run(rid, when_utc)
    reminder = db.get_reminder(rid)
    if reminder:
        scheduler.schedule(context.application, reminder)
    msg = messages.EDIT_TIME_SAVED.format(when_str=parse.format_when(when_utc, tz_name))
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.effective_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    context.user_data.pop("edit", None)
    return ConversationHandler.END


async def edit_text_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_text = (update.effective_message.text or "").strip()
    if not new_text:
        return ED_TEXT
    rid = context.user_data["edit"]["id"]
    db: Database = context.bot_data["db"]
    with db.cursor() as cur:
        cur.execute("UPDATE reminders SET text = ? WHERE id = ?", (new_text, rid))
    await update.effective_message.reply_text(
        messages.EDIT_TEXT_SAVED.format(text=new_text), parse_mode=ParseMode.MARKDOWN
    )
    context.user_data.pop("edit", None)
    return ConversationHandler.END


# ---------------- handler builders ----------------

def remind_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("remind", remind_start),
            CallbackQueryHandler(remind_start, pattern=r"^new:once$"),
        ],
        states={
            R_WHEN: [
                CallbackQueryHandler(remind_when_quick, pattern=r"^r:quick:"),
                CallbackQueryHandler(conv_cancel, pattern=r"^r:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, remind_when_text),
            ],
            R_TIME: [
                CallbackQueryHandler(remind_time_pick, pattern=r"^r:t:"),
                CallbackQueryHandler(conv_cancel, pattern=r"^r:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, remind_time_text),
            ],
            R_TEXT: [
                CallbackQueryHandler(conv_cancel, pattern=r"^r:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, remind_text),
            ],
        },
        fallbacks=[CommandHandler("cancel", conv_cancel)],
        per_message=False,
    )


def every_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("every", every_start),
            CallbackQueryHandler(every_start, pattern=r"^new:recur$"),
        ],
        states={
            E_FREQ: [
                CallbackQueryHandler(every_freq_pick, pattern=r"^e:f:"),
                CallbackQueryHandler(conv_cancel, pattern=r"^r:cancel$"),
            ],
            E_MDAY: [
                CallbackQueryHandler(every_mday_pick, pattern=r"^e:md:"),
                CallbackQueryHandler(conv_cancel, pattern=r"^r:cancel$"),
            ],
            E_TIME: [
                CallbackQueryHandler(every_time_pick, pattern=r"^r:t:"),
                CallbackQueryHandler(conv_cancel, pattern=r"^r:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, every_time_text),
            ],
            E_TEXT: [
                CallbackQueryHandler(conv_cancel, pattern=r"^r:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, every_text),
            ],
        },
        fallbacks=[CommandHandler("cancel", conv_cancel)],
        per_message=False,
    )


def edit_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_start, pattern=r"^edit:start:")],
        states={
            ED_MENU: [CallbackQueryHandler(edit_menu_pick, pattern=r"^edit:do:")],
            ED_WHEN: [
                CallbackQueryHandler(edit_when_quick, pattern=r"^r:quick:"),
                CallbackQueryHandler(conv_cancel, pattern=r"^r:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_when_text),
            ],
            ED_TIME: [
                CallbackQueryHandler(edit_time_pick, pattern=r"^r:t:"),
                CallbackQueryHandler(conv_cancel, pattern=r"^r:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_time_text),
            ],
            ED_TEXT: [
                CallbackQueryHandler(conv_cancel, pattern=r"^r:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_text_save),
            ],
        },
        fallbacks=[CommandHandler("cancel", conv_cancel)],
        per_message=False,
    )
