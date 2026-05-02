from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from headsup import messages
from headsup.db import Database

# Common timezones offered as one-tap buttons during onboarding.
TZ_PRESETS = [
    ("🇵🇭 Manila", "Asia/Manila"),
    ("🇸🇬 Singapore", "Asia/Singapore"),
    ("🇯🇵 Tokyo", "Asia/Tokyo"),
    ("🇬🇧 London", "Europe/London"),
    ("🇩🇪 Berlin", "Europe/Berlin"),
    ("🇺🇸 New York", "America/New_York"),
    ("🇺🇸 Los Angeles", "America/Los_Angeles"),
    ("🇦🇺 Sydney", "Australia/Sydney"),
]


def _welcome_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Let's go →", callback_data="onb:start")],
            [InlineKeyboardButton("Skip setup", callback_data="onb:skip")],
        ]
    )


def _tz_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(TZ_PRESETS), 2):
        pair = TZ_PRESETS[i : i + 2]
        rows.append(
            [InlineKeyboardButton(label, callback_data=f"onb:tz:{tz}") for label, tz in pair]
        )
    rows.append([InlineKeyboardButton("Other…", callback_data="onb:tz:other")])
    return InlineKeyboardMarkup(rows)


def _first_reminder_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Create my first reminder", callback_data="onb:create")],
            [InlineKeyboardButton("I'll do it later", callback_data="onb:done")],
        ]
    )


MENU_NEW = "➕ New reminder"
MENU_LIST = "📋 My reminders"


def menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(MENU_NEW), KeyboardButton(MENU_LIST)]],
        resize_keyboard=True,
        is_persistent=True,
    )


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    default_tz: str = context.bot_data["default_tz"]
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    existing = db.get_user(chat.id)
    db.upsert_user(chat.id, user.username, user.first_name, default_tz)

    if existing and existing.onboarded:
        active = db.list_active(chat.id)
        await update.effective_message.reply_text(
            messages.WELCOME_BACK.format(name=user.first_name or "there", count=len(active)),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=menu_keyboard(),
        )
        return

    await update.effective_message.reply_text(
        messages.WELCOME,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_welcome_keyboard(),
    )


async def onboarding_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all `onb:*` inline button taps from the onboarding flow."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    db: Database = context.bot_data["db"]
    chat_id = query.message.chat_id
    parts = query.data.split(":", 2)
    action = parts[1] if len(parts) > 1 else ""

    if action == "start":
        await query.edit_message_text(messages.ASK_TIMEZONE, reply_markup=_tz_keyboard())
        return

    if action == "skip":
        db.mark_onboarded(chat_id)
        await query.edit_message_text(messages.SKIP_ONBOARDING)
        await context.bot.send_message(
            chat_id, messages.MENU_TITLE, reply_markup=menu_keyboard()
        )
        return

    if action == "tz":
        tz = parts[2] if len(parts) > 2 else ""
        if tz == "other":
            await query.edit_message_text(
                messages.TZ_OTHER_HELP, parse_mode=ParseMode.MARKDOWN
            )
            return
        db.set_timezone(chat_id, tz)
        db.mark_onboarded(chat_id)
        await query.edit_message_text(
            messages.TZ_SET.format(tz=tz), parse_mode=ParseMode.MARKDOWN
        )
        await context.bot.send_message(
            chat_id,
            messages.TRY_FIRST,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_first_reminder_keyboard(),
        )
        # Drop the persistent keyboard now so the user can see it.
        await context.bot.send_message(
            chat_id, messages.MENU_TITLE, reply_markup=menu_keyboard()
        )
        return

    if action == "done":
        db.mark_onboarded(chat_id)
        await query.edit_message_text(messages.ONBOARDING_DONE)
        return

    if action == "create":
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("One-time", callback_data="new:once"),
                    InlineKeyboardButton("Recurring", callback_data="new:recur"),
                ],
                [InlineKeyboardButton("Cancel", callback_data="r:cancel")],
            ]
        )
        await query.edit_message_text(
            messages.NEW_CHOOSE_TYPE, parse_mode=ParseMode.MARKDOWN, reply_markup=kb
        )
        return
