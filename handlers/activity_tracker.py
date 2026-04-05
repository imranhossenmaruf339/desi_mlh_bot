"""
Chat Monitor Group System
──────────────────────────
• All group messages (text + media) → Monitor Group
• Admin replies in Monitor Group  → bot DMs the original user
• Works for BOTH main bot and clone bot groups
• Log Group  = bot operational logs only (no group chat)
• Inbox Group = private DMs only (unchanged)

Setup:
  1. Create a dedicated Telegram group (e.g. "Chat Monitor")
  2. Add the bot as admin
  3. Send /setmonitorgroup in that group
"""
import asyncio
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message

from config import app, HTML, settings_col, clones_col
from helpers import _is_admin_msg, _auto_del, get_cfg, _clone_config_ctx


# ── MongoDB: monitor message mappings ─────────────────────────────────────────
_monitor_col = None


def _mon_col():
    global _monitor_col
    if _monitor_col is None:
        from config import db
        _monitor_col = db["chat_monitor_msgs"]
    return _monitor_col


# ── Clone-aware monitor group helpers ─────────────────────────────────────────

async def _get_monitor_group(client=None) -> int | None:
    """Clone-aware: clone config → settings_col fallback."""
    # 1. client attribute (clone bot via injector)
    if client is not None:
        cfg = getattr(client, "_clone_config", None)
        if cfg and cfg.get("monitor_group"):
            return int(cfg["monitor_group"])
    # 2. ContextVar (injector sets this per message)
    clone_mg = get_cfg("monitor_group")
    if clone_mg:
        return int(clone_mg)
    # 3. Main bot's global setting
    doc = await settings_col.find_one({"key": "chat_monitor_group"})
    if doc and doc.get("chat_id"):
        return int(doc["chat_id"])
    return None


async def _set_monitor_group(chat_id: int):
    """Save monitor group (clone-aware)."""
    cfg = _clone_config_ctx.get()
    if cfg:
        from clone_manager import reload_clone_config
        tok = cfg.get("token")
        await clones_col.update_one(
            {"token": tok},
            {"$set": {"monitor_group": chat_id}},
            upsert=True,
        )
        await reload_clone_config(tok)
        return
    await settings_col.update_one(
        {"key": "chat_monitor_group"},
        {"$set": {"chat_id": chat_id}},
        upsert=True,
    )


def _now() -> str:
    return datetime.utcnow().strftime("%d %b %Y %H:%M UTC")


def _link(user) -> str:
    name = (user.first_name or "User") if user else "User"
    uid  = user.id if user else "?"
    return f'<a href="tg://user?id={uid}">{name}</a>'


# ── /setmonitorgroup — run inside the dedicated monitor group ─────────────────

@app.on_message(filters.command("setmonitorgroup") & filters.group)
async def set_monitor_group_cmd(client: Client, message: Message):
    if not await _is_admin_msg(client, message):
        return
    chat_id = message.chat.id
    await _set_monitor_group(chat_id)
    m = await message.reply_text(
        f"✅ <b>Monitor Group Set!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 Group: <code>{chat_id}</code>\n"
        f"All group messages will now be forwarded here.\n"
        f"Reply to any message to DM the original user.",
        parse_mode=HTML,
    )
    asyncio.create_task(_auto_del(m, 30))
    try:
        await message.delete()
    except Exception:
        pass


# ── Forward ALL group messages → Monitor Group ────────────────────────────────
# Covers: text, photo, video, voice, sticker, document, audio, animation.
# Excluded: service messages, bot messages, /commands, monitor group itself.

_CONTENT_FILTER = (
    filters.text
    | filters.photo
    | filters.video
    | filters.voice
    | filters.sticker
    | filters.document
    | filters.audio
    | filters.animation
    | filters.video_note
)


@app.on_message(
    filters.group & ~filters.service & _CONTENT_FILTER,
    group=8,
)
async def forward_to_monitor(client: Client, message: Message):
    # Must be a real user
    if not message.from_user:
        return
    if message.from_user.is_bot:
        return
    # Skip commands
    if (message.text or message.caption or "").lstrip().startswith("/"):
        return

    monitor_id = await _get_monitor_group(client)
    if not monitor_id:
        return

    # Don't forward messages FROM the monitor group itself (avoid noise)
    if message.chat.id == monitor_id:
        return

    user  = message.from_user
    uid   = user.id
    uname = f"@{user.username}" if user.username else "—"
    name  = user.first_name or "User"
    chat  = message.chat.title or str(message.chat.id)

    header = (
        f"💬 <b>Group Message</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {_link(user)}  <code>{uid}</code>\n"
        f"🔖 {uname}\n"
        f"📍 {chat}\n"
        f"🕒 {_now()}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>↩️ Reply here to DM this user</i>"
    )

    try:
        header_msg = await client.send_message(monitor_id, header, parse_mode=HTML)

        # copy_message preserves content without forwarding restrictions
        copied = await client.copy_message(
            chat_id=monitor_id,
            from_chat_id=message.chat.id,
            message_id=message.id,
        )

        # Store mapping: monitor_msg_id → user_id
        await _mon_col().insert_one({
            "header_msg_id":  header_msg.id,
            "copied_msg_id":  copied.id if copied else None,
            "user_id":        uid,
            "user_name":      name,
            "group_title":    chat,
            "group_id":       message.chat.id,
            "monitor_id":     monitor_id,
            "created_at":     datetime.utcnow(),
        })
        print(f"[MONITOR] Forwarded msg from {uid} in '{chat}' → monitor {monitor_id}")

    except Exception as exc:
        print(f"[MONITOR] Forward failed from {message.chat.id}: {exc}")


# ── Admin replies in Monitor Group → DM to original user ─────────────────────

@app.on_message(filters.reply & filters.group, group=9)
async def monitor_reply_handler(client: Client, message: Message):
    if not message.from_user:
        return

    monitor_id = await _get_monitor_group(client)
    if not monitor_id or message.chat.id != monitor_id:
        return

    # Only admins can send replies
    if not await _is_admin_msg(client, message):
        return

    replied_id = message.reply_to_message.id if message.reply_to_message else None
    if not replied_id:
        return

    # Find original user from DB (check both header and copied message IDs)
    doc = await _mon_col().find_one({
        "$or": [
            {"header_msg_id": replied_id},
            {"copied_msg_id": replied_id},
        ],
        "monitor_id": monitor_id,
    })
    if not doc:
        return  # Not a tracked group message — ignore silently

    user_id     = doc["user_id"]
    group_title = doc.get("group_title", "a group")

    intro = (
        f"📩 <b>Reply from Admin</b>\n"
        f"<i>(regarding your message in {group_title})</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        await client.send_message(user_id, intro, parse_mode=HTML)
        await client.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat.id,
            message_id=message.id,
        )
        confirm = await message.reply_text(
            f"✅ Sent to user <code>{user_id}</code>",
            parse_mode=HTML,
        )
        asyncio.create_task(_auto_del(confirm, 8))
    except Exception as exc:
        err = await message.reply_text(
            f"❌ Could not DM <code>{user_id}</code>: <code>{exc}</code>",
            parse_mode=HTML,
        )
        asyncio.create_task(_auto_del(err, 20))
        print(f"[MONITOR] Reply DM failed to {user_id}: {exc}")
