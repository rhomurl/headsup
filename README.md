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

## PM2 (Ubuntu server)

After cloning the repo on your server:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# edit .env and set BOT_TOKEN and any other needed values

pm2 start ecosystem.config.js
pm2 startup
# run the sudo command that pm2 prints for your systemd setup
pm2 save
```

Useful commands:

```bash
pm2 logs headsup
pm2 restart headsup
pm2 stop headsup
pm2 status
```

## Commands

Run `/help` in the bot, or see the slash menu (the blue `/` button in Telegram).

## Tests

```bash
pytest
```
