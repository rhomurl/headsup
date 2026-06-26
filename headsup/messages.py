"""User-facing strings. Keep all wording here so tone stays consistent."""

WELCOME = (
    "👋 *Hi! I'm Headsup.*\n\n"
    "I'm your personal reminder buddy. Tell me what to remind you about, "
    "and I'll ping you right here in Telegram — once, daily, weekly, whenever you need.\n\n"
    "Things I'm great at:\n"
    "• 🔔 One-time reminders (\"remind me to call mom at 6pm\")\n"
    "• 🔁 Recurring reminders (\"every Monday 8am, foot therapy\")\n"
    "• 💤 Snoozing — tap a button if you need 10 more minutes\n"
    "• 📋 Showing your full list anytime\n\n"
    "Ready? Let's set you up in 30 seconds."
)

WELCOME_BACK = (
    "👋 Welcome back, {name}! You have *{count}* active reminder(s).\n"
    "Type /list to see them, or /help if you need a refresher."
)

ASK_TIMEZONE = (
    "🌏 First, what's your timezone? I need this so reminders fire at the right time."
)

TZ_SET = "✅ Timezone set to *{tz}*. Times will now show in your local time."

TZ_OTHER_HELP = (
    "Type `/tz <zone>` with any IANA timezone, e.g. `/tz Europe/Berlin` or `/tz Asia/Tokyo`.\n"
    "Full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
)

TZ_INVALID = (
    "🤔 I don't recognize that timezone. Use an IANA name like `Asia/Manila` or `America/New_York`."
)

SKIP_ONBOARDING = (
    "👍 No problem. You can always type /help to see what I can do, or /examples for ideas."
)

MENU_TITLE = "Here's your menu — tap a button anytime."

NOTIFY_EMPTY = "Add some text after /notify, e.g. `/notify pick up groceries on the way home`."

NOTIFY_SENT = "📝 *Note:* {text}"

SETTINGS = (
    "*Your settings*\n\n"
    "• Timezone: *{tz}*\n"
    "• Morning digest: *{digest_morning}*\n"
    "• Evening digest: *{digest_evening}*\n\n"
    "Change timezone with `/tz <zone>`. Change digest with /digest."
)

FEEDBACK_EMPTY = "Add your message after /feedback, e.g. `/feedback the snooze button is too small`."
FEEDBACK_THANKS = "🙏 Thanks for the feedback! I've passed it along."

# /remind conversational flow
REMIND_ASK_WHEN = (
    "📅 *When* should I remind you?\n\n"
    "Tap a quick option, or type something like:\n"
    "• `tomorrow 9am`\n"
    "• `in 2 hours`\n"
    "• `Friday 6pm`\n"
    "• `May 5` or `5/5/2026`"
)
REMIND_ASK_TIME = "⏰ What *time* on {date_str}? Tap one or type, e.g. `7:30 PM`."
REMIND_ASK_TEXT = "📝 Got it — *{when_str}*.\n\nWhat should I remind you about?"
REMIND_PAST = "🕰️ That time is already in the past. Try a future time."
REMIND_DONE = "✅ Got it! I'll remind you on *{when_str}* to *{text}*."

# /every conversational flow
EVERY_ASK_FREQ = "🔁 *How often* should this repeat?"
EVERY_ASK_WDAY = "📅 Which *day of the week* should this repeat on?"
EVERY_ASK_MDAY = (
    "📅 Which *day of the month* should this repeat on?\n\n"
    "_Days 29–31 (marked \\*) will fall on the last day of the month when the month is shorter._"
)
EVERY_ASK_TIME = "⏰ At what time on {freq_label}? Tap one or type, e.g. `7:30 AM`."
EVERY_ASK_TEXT = "📝 Set: *{freq_str}*.\n\nWhat should I remind you about?"
EVERY_DONE = "🔁 Set! *{freq_str}* I'll remind you to *{text}*.\nFirst one: *{when_str}*."

CANCELLED = "Cancelled."

# /list and action flows
LIST_HEADER = "*Your active reminders:*"
LIST_LINE = "• {pos}. *{text}*\n   {when_str}{rec}"
ACTION_DONE = "✅ Marked done."
ACTION_SNOOZED = "💤 Snoozed until *{when_str}*."
ACTION_CANCELLED = "🔕 Cancelled."
ACTION_SKIPPED = "⏭ Skipped. Next up: *{when_str}*."
NOT_FOUND = "🤷 I couldn't find that reminder. It may have already been completed."

SNOOZE_PICK_DURATION = "Snooze *#{id}* for how long?"

# New-reminder type chooser
NEW_CHOOSE_TYPE = (
    "What kind of reminder do you want to create?\n\n"
    "• *One-time* — fires once at a specific date/time\n"
    "• *Recurring* — repeats on a schedule"
)

# Edit menu
EDIT_MENU_HEADER = "*Edit #{id}* — *{text}*\n{when_str}{rec}\n\nWhat would you like to change?"
EDIT_ASK_WHEN = "📅 New *date/time* for #{id}?\n\nTap a quick option or type a new date."
EDIT_ASK_TIME = "⏰ New *time* on {date_str}?"
EDIT_ASK_TEXT = "📝 New *reminder text* for #{id}?"
EDIT_TIME_SAVED = "✅ Updated. Next fire: *{when_str}*."
EDIT_TEXT_SAVED = "✅ Updated to: *{text}*."
EDIT_NO_CHANGE = "No changes made."

# Digest
DIGEST_MENU_HEADER = (
    "*Daily digest*\n\n"
    "I can send you a quick summary in the morning and/or evening. Tap a slot to set the time."
)
DIGEST_PICK_TIME = "*{slot} digest* — pick a time, or turn it off."
DIGEST_CLOSED = "Done. (Tap /digest anytime to change.)"
DIGEST_NEED_START = "Type /start first so I know your timezone."

DIGEST_MORNING_HEADER = "🌅 *Good morning!*"
DIGEST_EVENING_HEADER = "🌙 *Evening recap*"
DIGEST_TODAY_HEADER = "*Today ({count}):*"
DIGEST_TODAY_EMPTY = "Nothing scheduled today. Enjoy the calm 🌿"
DIGEST_TOMORROW_HEADER = "*Tomorrow ({count}):*"
DIGEST_TOMORROW_EMPTY = "Nothing on the calendar for tomorrow."
DIGEST_MORNING_FOOTER = "Have a good day!"
DIGEST_EVENING_FOOTER = "Sleep well 💤"

TRY_FIRST = (
    "✨ *You're all set!*\n\n"
    "Want to create your first reminder now? I'll walk you through it — just tap a button at each step."
)

ONBOARDING_DONE = (
    "👍 No worries — whenever you're ready, just tap *➕ New reminder* below."
)

HELP = (
    "*Headsup commands*\n\n"
    "*Reminders*\n"
    "• `/new` — create a one-time or recurring reminder (guided)\n"
    "• `/list` — show your active reminders, with Edit / Done / Snooze / Cancel\n\n"
    "*Other*\n"
    "• `/digest` — set up morning/evening summaries\n"
    "• `/tz <zone>` — change your timezone\n"
    "• `/settings` — view your preferences\n"
    "• `/notify <text>` — quick note to yourself\n"
    "• `/feedback <text>` — send me feedback\n\n"
    "Or just tap the buttons in the menu below — no typing needed."
)

EMPTY_LIST = (
    "📭 No active reminders yet!\n"
    "Tap *➕ New reminder* below to create one."
)

PARSE_ERROR = (
    "🤔 I couldn't figure out the time.\n"
    "Try something like `tomorrow 9am`, `in 2 hours`, or `monday 6pm`.\n"
    "Type /examples for more."
)

UNKNOWN_COMMAND = (
    "🤷 I don't know that command. Type /help to see what I can do."
)
