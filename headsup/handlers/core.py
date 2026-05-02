from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from headsup import messages
from headsup.db import Database


async def help_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(messages.HELP, parse_mode=ParseMode.MARKDOWN)


async def tz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    chat_id = update.effective_chat.id
    if not context.args:
        await update.effective_message.reply_text(
            messages.TZ_OTHER_HELP, parse_mode=ParseMode.MARKDOWN
        )
        return
    tz = context.args[0]
    try:
        ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        await update.effective_message.reply_text(messages.TZ_INVALID, parse_mode=ParseMode.MARKDOWN)
        return
    db.set_timezone(chat_id, tz)
    await update.effective_message.reply_text(
        messages.TZ_SET.format(tz=tz), parse_mode=ParseMode.MARKDOWN
    )


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    user = db.get_user(update.effective_chat.id)
    if user is None:
        await update.effective_message.reply_text("Use /start first.")
        return
    from headsup.handlers.digest import _format_hhmm
    await update.effective_message.reply_text(
        messages.SETTINGS.format(
            tz=user.timezone,
            digest_morning=_format_hhmm(user.digest_morning),
            digest_evening=_format_hhmm(user.digest_evening),
        ),
        parse_mode=ParseMode.MARKDOWN,
    )


async def notify_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text(
            messages.NOTIFY_EMPTY, parse_mode=ParseMode.MARKDOWN
        )
        return
    await update.effective_message.reply_text(
        messages.NOTIFY_SENT.format(text=text), parse_mode=ParseMode.MARKDOWN
    )


async def feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text(
            messages.FEEDBACK_EMPTY, parse_mode=ParseMode.MARKDOWN
        )
        return
    admin_id: int | None = context.bot_data.get("admin_chat_id")
    user = update.effective_user
    if admin_id:
        sender = f"@{user.username}" if user and user.username else f"id={user.id if user else '?'}"
        await context.bot.send_message(admin_id, f"📨 Feedback from {sender}:\n{text}")
    await update.effective_message.reply_text(messages.FEEDBACK_THANKS)
