import logging

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from headsup import scheduler
from headsup.config import load_config
from headsup.db import Database
from headsup.handlers import core, digest, fallback, onboarding, reminders

BOT_COMMANDS = [
    BotCommand("start", "Get started / welcome"),
    BotCommand("new", "Create a one-time or recurring reminder"),
    BotCommand("list", "Show your active reminders"),
    BotCommand("digest", "Set up morning/evening summaries"),
    BotCommand("tz", "Set your timezone"),
    BotCommand("notify", "Quick note to yourself"),
    BotCommand("settings", "View your preferences"),
    BotCommand("help", "Show command guide"),
    BotCommand("feedback", "Send feedback or a bug report"),
]

MENU_BUTTON_LABELS = {
    onboarding.MENU_LIST,
    onboarding.MENU_NEW,
}


async def _post_init(app: Application) -> None:
    await app.bot.set_my_commands(BOT_COMMANDS)
    scheduler.restore_on_startup(app)
    digest.restore_on_startup(app)


def main() -> None:
    cfg = load_config()
    logging.basicConfig(
        level=cfg.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db = Database(cfg.db_path)

    app = (
        Application.builder()
        .token(cfg.bot_token)
        .post_init(_post_init)
        .build()
    )
    app.bot_data["db"] = db
    app.bot_data["default_tz"] = cfg.default_tz
    app.bot_data["admin_chat_id"] = cfg.admin_chat_id

    # Onboarding
    app.add_handler(CommandHandler("start", onboarding.start_cmd))
    app.add_handler(CallbackQueryHandler(onboarding.onboarding_callback, pattern=r"^onb:"))

    # Reminder conversations (entered via /remind, /every, or the type-chooser buttons).
    app.add_handler(reminders.remind_conversation())
    app.add_handler(reminders.every_conversation())
    app.add_handler(reminders.edit_conversation())

    # The "All set" button on a post-create confirmation just clears the keyboard.
    app.add_handler(CallbackQueryHandler(reminders.edit_close, pattern=r"^edit:close$"))

    # New-reminder picker (also reachable from the menu button)
    app.add_handler(CommandHandler("new", reminders.new_chooser))

    # List + per-reminder action callbacks (Manage menu, Done, Snooze, Cancel)
    app.add_handler(CommandHandler("list", reminders.list_cmd))
    app.add_handler(CallbackQueryHandler(reminders.action_callback, pattern=r"^act:"))

    # Core
    app.add_handler(CommandHandler("help", core.help_cmd))
    app.add_handler(CommandHandler("tz", core.tz_cmd))
    app.add_handler(CommandHandler("settings", core.settings_cmd))
    app.add_handler(CommandHandler("notify", core.notify_cmd))
    app.add_handler(CommandHandler("feedback", core.feedback_cmd))

    # Digest
    app.add_handler(CommandHandler("digest", digest.digest_cmd))
    app.add_handler(CallbackQueryHandler(digest.digest_callback, pattern=r"^dig:"))

    # Persistent reply-keyboard taps come in as plain text.
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Text(MENU_BUTTON_LABELS),
            fallback.menu_button_router,
        )
    )

    # Fallback for unknown slash commands.
    app.add_handler(MessageHandler(filters.COMMAND, fallback.unknown_cmd))

    logging.getLogger(__name__).info("Headsup starting (long polling)…")
    app.run_polling()


if __name__ == "__main__":
    main()
