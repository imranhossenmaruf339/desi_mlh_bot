import asyncio
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.types import Message, ChatPermissions

from config import HTML, ADMIN_ID, users_col, app
from helpers import (
    log_event, _parse_duration, _resolve_target,
    _is_admin_msg, _auto_del, _FULL_PERMS, MAX_WARNS,
)


@app.on_message(filters.command("mute") & filters.group)
async def mute_cmd(client: Client, message: Message):
    if not await _is_admin_msg(client, message):
        return

    args = message.command[1:]
    try:
        user_id, fname, remaining = await _resolve_target(client, message, list(args))
    except ValueError as e:
        m = await message.reply_text(str(e), parse_mode=HTML)
        asyncio.create_task(_auto_del(m, 20))
        return

    if remaining:
        secs, label = _parse_duration(remaining[0])
    else:
        secs, label = None, "permanent"

    until_date = (datetime.utcnow() + timedelta(seconds=secs)) if secs else None
    try:
        await client.restrict_chat_member(
            message.chat.id, user_id,
            ChatPermissions(can_send_messages=False),
            until_date=until_date,
        )
    except Exception as e:
        m = await message.reply_text(f"❌ Could not mute: {e}")
        asyncio.create_task(_auto_del(m, 15))
        return

    m = await message.reply_text(
        f"🔇 <b>User Muted</b>\n"
        f"👤 {fname} — <code>{user_id}</code>\n"
        f"⏱ Duration: {label}",
        parse_mode=HTML,
    )
    asyncio.create_task(_auto_del(m, 30))
    asyncio.create_task(log_event(client,
        f"🔇 <b>Muted</b>  👤 {fname} <code>{user_id}</code>  ⏱ {label}"
        f"  📍 {message.chat.title or message.chat.id}"
    ))


@app.on_message(filters.command("unmute") & filters.group)
async def unmute_cmd(client: Client, message: Message):
    if not await _is_admin_msg(client, message):
        return

    args = message.command[1:]
    try:
        user_id, fname, _ = await _resolve_target(client, message, list(args))
    except ValueError as e:
        m = await message.reply_text(str(e), parse_mode=HTML)
        asyncio.create_task(_auto_del(m, 20))
        return

    try:
        await client.restrict_chat_member(message.chat.id, user_id, _FULL_PERMS)
    except Exception as e:
        m = await message.reply_text(f"❌ Could not unmute: {e}")
        asyncio.create_task(_auto_del(m, 15))
        return

    m = await message.reply_text(
        f"🔊 <b>User Unmuted</b>\n"
        f"👤 {fname} — <code>{user_id}</code>",
        parse_mode=HTML,
    )
    asyncio.create_task(_auto_del(m, 30))
    asyncio.create_task(log_event(client,
        f"🔊 <b>Unmuted</b>  👤 {fname} <code>{user_id}</code>"
        f"  📍 {message.chat.title or message.chat.id}"
    ))


@app.on_message(filters.command("ban") & filters.group)
async def ban_cmd(client: Client, message: Message):
    if not await _is_admin_msg(client, message):
        return

    args = message.command[1:]
    reason_start = 1
    try:
        user_id, fname, rest = await _resolve_target(client, message, list(args))
    except ValueError as e:
        m = await message.reply_text(str(e), parse_mode=HTML)
        asyncio.create_task(_auto_del(m, 20))
        return

    reason = " ".join(rest) if rest else "No reason given"
    try:
        await client.ban_chat_member(message.chat.id, user_id)
    except Exception as e:
        m = await message.reply_text(f"❌ Could not ban: {e}")
        asyncio.create_task(_auto_del(m, 15))
        return

    m = await message.reply_text(
        f"🚫 <b>User Banned</b>\n"
        f"👤 {fname} — <code>{user_id}</code>\n"
        f"📋 Reason: {reason}",
        parse_mode=HTML,
    )
    asyncio.create_task(_auto_del(m, 30))
    asyncio.create_task(log_event(client,
        f"🚫 <b>Banned</b>  👤 {fname} <code>{user_id}</code>"
        f"  📋 {reason}  📍 {message.chat.title or message.chat.id}"
    ))


@app.on_message(filters.command("unban") & filters.group)
async def unban_cmd(client: Client, message: Message):
    if not await _is_admin_msg(client, message):
        return

    args = message.command[1:]
    try:
        user_id, fname, _ = await _resolve_target(client, message, list(args))
    except ValueError as e:
        m = await message.reply_text(str(e), parse_mode=HTML)
        asyncio.create_task(_auto_del(m, 20))
        return

    try:
        await client.unban_chat_member(message.chat.id, user_id)
    except Exception as e:
        m = await message.reply_text(f"❌ Could not unban: {e}")
        asyncio.create_task(_auto_del(m, 15))
        return

    m = await message.reply_text(
        f"✅ <b>User Unbanned</b>\n"
        f"👤 {fname} — <code>{user_id}</code>",
        parse_mode=HTML,
    )
    asyncio.create_task(_auto_del(m, 30))
    asyncio.create_task(log_event(client,
        f"✅ <b>Unbanned</b>  👤 {fname} <code>{user_id}</code>"
        f"  📍 {message.chat.title or message.chat.id}"
    ))


@app.on_message(filters.command("warn") & filters.group)
async def warn_cmd(client: Client, message: Message):
    if not await _is_admin_msg(client, message):
        return

    args = message.command[1:]
    try:
        user_id, fname, rest = await _resolve_target(client, message, list(args))
    except ValueError as e:
        m = await message.reply_text(str(e), parse_mode=HTML)
        asyncio.create_task(_auto_del(m, 20))
        return

    reason = " ".join(rest) if rest else "No reason given"
    doc    = await users_col.find_one({"user_id": user_id})
    warns  = (doc or {}).get("warn_count", 0) + 1

    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"warn_count": warns}},
        upsert=True,
    )

    if warns >= MAX_WARNS:
        try:
            await client.ban_chat_member(message.chat.id, user_id)
            auto_ban_note = f"\n\n⛔ Auto-banned after {MAX_WARNS} warnings!"
        except Exception:
            auto_ban_note = "\n\n⚠️ Could not auto-ban — please ban manually."
        await users_col.update_one(
            {"user_id": user_id},
            {"$set": {"warn_count": 0}},
        )
    else:
        auto_ban_note = ""

    m = await message.reply_text(
        f"⚠️ <b>Warning {warns}/{MAX_WARNS}</b>\n"
        f"👤 {fname} — <code>{user_id}</code>\n"
        f"📋 Reason: {reason}"
        f"{auto_ban_note}",
        parse_mode=HTML,
    )
    asyncio.create_task(_auto_del(m, 60))
    asyncio.create_task(log_event(client,
        f"⚠️ <b>Warned</b>  👤 {fname} <code>{user_id}</code>"
        f"  {warns}/{MAX_WARNS}  📋 {reason}"
        f"  📍 {message.chat.title or message.chat.id}"
        f"{auto_ban_note}"
    ))


@app.on_message(filters.command("clearwarn") & filters.group)
async def clearwarn_cmd(client: Client, message: Message):
    if not await _is_admin_msg(client, message):
        return

    args = message.command[1:]
    try:
        user_id, fname, _ = await _resolve_target(client, message, list(args))
    except ValueError as e:
        m = await message.reply_text(str(e), parse_mode=HTML)
        asyncio.create_task(_auto_del(m, 20))
        return

    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"warn_count": 0}},
        upsert=True,
    )
    m = await message.reply_text(
        f"🗑️ <b>Warnings Cleared</b>\n"
        f"👤 {fname} — <code>{user_id}</code>",
        parse_mode=HTML,
    )
    asyncio.create_task(_auto_del(m, 30))
    asyncio.create_task(log_event(client,
        f"🗑️ <b>Warnings Cleared</b>  👤 {fname} <code>{user_id}</code>"
        f"  📍 {message.chat.title or message.chat.id}"
    ))
