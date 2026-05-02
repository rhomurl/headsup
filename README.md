# Headsup

A friendly Telegram reminder bot.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# edit .env and paste your BOT_TOKEN from @BotFather

python -m headsup
```

Then open your bot in Telegram and tap **Start**.

## Commands

Run `/help` in the bot, or see the slash menu (the blue `/` button in Telegram).

## Tests

```bash
pytest
```
