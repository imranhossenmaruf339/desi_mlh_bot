# DESI MLH Telegram Bot

  A feature-rich Telegram bot with video delivery, points system, group moderation, and more.

  ## Required Environment Variables

  Set these as secrets/environment variables before running:

  | Variable | Description |
  |----------|-------------|
  | `TELEGRAM_API_ID` | Telegram API ID (from my.telegram.org) |
  | `TELEGRAM_API_HASH` | Telegram API Hash (from my.telegram.org) |
  | `TELEGRAM_BOT_TOKEN` | Bot token (from @BotFather) |
  | `MONGO_URI` | MongoDB connection string |
  | `ADMIN_ID` | Telegram user ID of the admin |

  ## Run

  ```bash
  pip install pyrogram motor aiohttp python-dotenv tgcrypto
  python bot.py
  ```
  