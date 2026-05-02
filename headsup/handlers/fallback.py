from telegram import Update
from telegram.ext import ContextTypes

from headsup import messages
from headsup.handlers import onboarding, reminders


async def unknown_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(messages.UNKNOWN_COMMAND)


async def menu_button_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route taps on the persistent reply-keyboard buttons to the right command."""
    text = (update.effective_message.text or "").strip()
    if text == onboarding.MENU_LIST:
        await reminders.list_cmd(update, context)
    elif text == onboarding.MENU_NEW:
        await reminders.new_chooser(update, context)
