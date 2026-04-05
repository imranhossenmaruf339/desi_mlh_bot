"""
Activity Tracker System
────────────────────────
LOG GROUP receives:
  • Member join event
  • Member leave event
  (Moderation events — ban/mute/warn/video — already logged elsewhere)

INBOX GROUP receives (automatic, no toggle):
  • All text messages sent by group members
  • All media messages (photo / video / voice / document / sticker / audio)
  • Commands and bot messages are excluded
"""
import asyncio
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message

from config import app, HTML
from helpers import log_event, _auto_del


async def _get_inbox_group(client):
    from handlers.inbox import _get_inbox_group as _ig
    return await _ig(client)


def _now() -> str:
    return datetime.utcnow().strftime("%d %b %Y %H:%M UTC")


def _link(user) -> str:
    name = (user.first_name or "User") if user else "User"
    uid  = user.id if user else "?"
    return f'<a href="tg://user?id={uid}">{name}</a>'


# ── Track: member join → LOG GROUP ───────────────────────────────────────────

@app.on_message(filters.new_chat_members & filters.group, group=25)
async def track_join(client: Client, message: Message):
    for user in (message.new_chat_members or []):
        if user.is_bot:
            continue
        asyncio.create_task(log_event(client,
            f"➕ <b>Member Joined</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {_link(user)} <code>{user.id}</code>\n"
            f"📍 {message.chat.title or message.chat.id}\n"
            f"🕒 {_now()}"
        ))


# ── Track: member left → LOG GROUP ───────────────────────────────────────────

@app.on_message(filters.left_chat_member & filters.group, group=25)
async def track_leave(client: Client, message: Message):
    user = message.left_chat_member
    if not user or user.is_bot:
        return
    asyncio.create_task(log_event(client,
        f"➖ <b>Member Left</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {_link(user)} <code>{user.id}</code>\n"
        f"📍 {message.chat.title or message.chat.id}\n"
        f"🕒 {_now()}"
    ))


# ── Forward ALL group messages → INBOX GROUP ─────────────────────────────────
# Covers: text, photo, video, voice, sticker, audio, document.
# Skips:  service messages, bot messages, commands.

_MEDIA_FILTER = (
    filters.text
    | filters.photo
    | filters.video
    | filters.voice
    | filters.sticker
    | filters.document
    | filters.audio
    | filters.animation
)


@app.on_message(
    filters.group & ~filters.service & _MEDIA_FILTER,
    group=25,
)
async def forward_to_inbox(client: Client, message: Message):
    if not message.from_user:
        return
    # Skip bot messages and commands
    if message.from_user.is_bot:
        return
    if (message.text or "").startswith("/"):
        return

    inbox_id = await _get_inbox_group(client)
    if not inbox_id:
        return

    user    = message.from_user
    uid     = user.id
    name    = user.first_name or "User"
    chat    = message.chat.title or str(message.chat.id)

    header = (
        f"💬 <b>Group Chat</b>\n"
        f"👤 <a href='tg://user?id={uid}'>{name}</a> "
        f"<code>{uid}</code>\n"
        f"📍 {chat}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    try:
        await client.send_message(inbox_id, header, parse_mode=HTML)
        await message.forward(inbox_id)
    except Exception as exc:
        print(f"[ACTIVITY] Inbox forward failed: {exc}")
