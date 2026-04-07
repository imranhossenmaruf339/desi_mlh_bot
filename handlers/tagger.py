"""
Invisible Tagall System - Mention all group members without spam
- Zero-Width Non-Joiner (ZWNJ) invisible mentions
- Batch processing to avoid flood limits
- Hidden hyperlink tagging
- Session management for active tagging operations
- Admin-only access with proper permissions
"""

import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, ChatPermissions, ChatMember
from pyrogram.enums import ChatMemberStatus

from config import HTML, ADMIN_ID, app, db
from helpers import log_event, _is_admin_msg, _auto_del, bot_api

# ══════════════════════════════════════════════════════════════════════════════
# ═════════════════════════ DATABASE & STATE MANAGEMENT ━━━━━━━━━━━━━━━━━━━━━━━
# ══════════════════════════════════════════════════════════════════════════════

# In-memory tagging sessions: {chat_id: {"user_id": uid, "message_id": mid, "cancel": False}}
_tagging_sessions: dict[int, dict] = {}

# ZWNJ character for invisible mentions
ZWNJ = "\u200c"  # Zero-Width Non-Joiner


async def get_tagger_db():
    """Get or create tagger collection."""
    return db["tagall_sessions"]


async def get_batch_config():
    """Get tagging batch configuration from DB."""
    config = await db["bot_settings"].find_one({"key": "tagall_config"})
    if not config:
        return {
            "batch_size": 5,
            "batch_delay": 1.5,  # seconds between batches
            "max_retries": 3,
        }
    return config.get("value", {
        "batch_size": 5,
        "batch_delay": 1.5,
        "max_retries": 3,
    })


# ══════════════════════════════════════════════════════════════════════════════
# ═════════════════════════ HELPER FUNCTIONS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ══════════════════════════════════════════════════════════════════════════════

async def get_group_members(client: Client, chat_id: int) -> list[int]:
    """Get list of all group member IDs."""
    members = []
    try:
        async for member in client.get_chat_members(chat_id):
            if not member.user.is_bot and not member.user.is_self:
                members.append(member.user.id)
            # Limit to 500 members to avoid excessive API calls
            if len(members) >= 500:
                break
    except Exception as e:
        print(f"[TAGGER] Error fetching members: {e}")
    return members


def _build_hidden_mention_batch(user_ids: list[int], use_zwnj: bool = True) -> str:
    """
    Build a batch of hidden mentions using either:
    - ZWNJ + mention URLs (more reliable)
    - Or pure ZWNJ characters (more invisible)
    """
    if use_zwnj:
        # Format: ZWNJ + [mention](tg://user?id=UID)
        mentions = "".join([
            f"{ZWNJ}<a href='tg://user?id={uid}'>\u200b</a>"
            for uid in user_ids
        ])
        return mentions
    else:
        # Pure ZWNJ approach - completely invisible
        return ZWNJ * len(user_ids)


def _build_mention_batch_inline(user_ids: list[int]) -> str:
    """Build inline mentions as HTML."""
    mentions = []
    for uid in user_ids:
        mentions.append(f"<a href='tg://user?id={uid}'>{ZWNJ}</a>")
    return "".join(mentions)


async def validate_bot_permissions(client: Client, chat_id: int) -> dict:
    """Check if bot has required permissions to tag members."""
    try:
        bot_member = await client.get_chat_member(chat_id, (await client.get_me()).id)
        perms = getattr(bot_member, "privileges", None)
        
        if not perms:
            return {
                "can_tag": False,
                "reason": "Bot is not an admin in this group",
                "have_admin": False,
            }
        
        can_tag = bool(getattr(perms, "can_manage_chat", False))
        
        return {
            "can_tag": can_tag,
            "reason": "Bot has required permissions" if can_tag else "Bot lacks admin permissions",
            "have_admin": True,
            "can_restrict_members": bool(getattr(perms, "can_restrict_members", False)),
        }
    except Exception as e:
        return {
            "can_tag": False,
            "reason": f"Permission check failed: {e}",
            "have_admin": False,
        }


# ══════════════════════════════════════════════════════════════════════════════
# ═════════════════════════ MAIN TAGGING LOGIC ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.command("tagall") & filters.group)
async def tagall_cmd(client: Client, message: Message):
    """Main /tagall command - tag all group members."""
    if not await _is_admin_msg(client, message):
        m = await message.reply_text(
            "❌ <b>Admin Only</b>\n\n"
            "This command can only be used by group admins.",
            parse_mode=HTML,
        )
        asyncio.create_task(_auto_del(m, 30))
        return

    chat_id = message.chat.id

    # Check if already tagging in this group
    if chat_id in _tagging_sessions and not _tagging_sessions[chat_id].get("cancel"):
        m = await message.reply_text(
            "⚠️ <b>Tagging Already in Progress</b>\n\n"
            "Use /stoptag to cancel the current operation.",
            parse_mode=HTML,
        )
        asyncio.create_task(_auto_del(m, 30))
        return

    # Get custom message if provided
    args = message.command[1:]
    custom_msg = " ".join(args) if args else None

    # Check bot permissions
    perm_check = await validate_bot_permissions(client, chat_id)
    if not perm_check["have_admin"]:
        m = await message.reply_text(
            f"❌ <b>Bot Permission Error</b>\n\n"
            f"{perm_check['reason']}\n\n"
            f"Please make the bot an admin in this group.",
            parse_mode=HTML,
        )
        asyncio.create_task(_auto_del(m, 30))
        return

    # Fetch group members
    status_msg = await message.reply_text(
        "🔄 <b>Fetching group members...</b>",
        parse_mode=HTML,
    )

    members = await get_group_members(client, chat_id)

    if not members:
        await status_msg.edit_text(
            "❌ <b>No members found</b>\n\n"
            "Could not retrieve group member list.",
            parse_mode=HTML,
        )
        asyncio.create_task(_auto_del(status_msg, 30))
        return

    # Create tagging session
    admin_id = message.from_user.id
    admin_name = message.from_user.first_name or "Admin"
    session_id = f"{chat_id}_{admin_id}_{int(datetime.now().timestamp())}"

    _tagging_sessions[chat_id] = {
        "user_id": admin_id,
        "message_id": message.id,
        "cancel": False,
        "session_id": session_id,
        "members_count": len(members),
        "admin_name": admin_name,
        "custom_msg": custom_msg,
        "started_at": datetime.utcnow(),
    }

    # Store in DB
    await (await get_tagger_db()).insert_one({
        "session_id": session_id,
        "chat_id": chat_id,
        "admin_id": admin_id,
        "admin_name": admin_name,
        "members_count": len(members),
        "custom_msg": custom_msg,
        "created_at": datetime.utcnow(),
        "status": "active",
    })

    # Start tagging process
    await status_msg.edit_text(
        f"👥 <b>Starting tagging process</b>\n\n"
        f"Members to tag: <b>{len(members)}</b>\n"
        f"Status: <code>Initializing...</code>",
        parse_mode=HTML,
    )

    asyncio.create_task(
        _execute_tagall(client, chat_id, members, custom_msg, status_msg)
    )


async def _execute_tagall(
    client: Client,
    chat_id: int,
    members: list[int],
    custom_msg: str | None,
    status_msg: Message,
):
    """Execute the tagging process in batches."""
    config = await get_batch_config()
    batch_size = config.get("batch_size", 5)
    batch_delay = config.get("batch_delay", 1.5)
    max_retries = config.get("max_retries", 3)

    session = _tagging_sessions.get(chat_id, {})
    admin_name = session.get("admin_name", "Admin")
    session_id = session.get("session_id", "")

    total_batches = (len(members) + batch_size - 1) // batch_size
    tagged_count = 0
    failed_count = 0

    try:
        # Send batches
        for batch_idx, i in enumerate(range(0, len(members), batch_size)):
            # Check if cancellation requested
            if chat_id not in _tagging_sessions or _tagging_sessions[chat_id].get("cancel"):
                await status_msg.edit_text(
                    f"⏸️ <b>Tagging Cancelled</b>\n\n"
                    f"Tagged: <b>{tagged_count}/{len(members)}</b>",
                    parse_mode=HTML,
                )
                break

            batch_members = members[i : i + batch_size]

            # Build message with custom text
            text_parts = []

            if custom_msg:
                text_parts.append(f"<b>Message from {admin_name}:</b>\n{custom_msg}\n\n")

            # Add invisible mentions
            mention_batch = _build_hidden_mention_batch(batch_members, use_zwnj=True)
            text_parts.append(mention_batch)

            text = "".join(text_parts)

            # Send with retries
            retry_count = 0
            success = False

            while retry_count < max_retries and not success:
                try:
                    await client.send_message(
                        chat_id,
                        text,
                        parse_mode=HTML,
                    )
                    tagged_count += len(batch_members)
                    success = True
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        await asyncio.sleep(batch_delay * 2)
                    else:
                        failed_count += len(batch_members)
                        print(f"[TAGGER] Batch {batch_idx} failed: {e}")

            # Update status
            progress = f"{batch_idx + 1}/{total_batches}"
            await status_msg.edit_text(
                f"🏷️ <b>Tagging in Progress</b>\n\n"
                f"Progress: <code>{progress}</code>\n"
                f"Tagged: <b>{tagged_count}/{len(members)}</b>\n"
                f"Failed: <b>{failed_count}</b>\n"
                f"Status: <code>Processing batch {batch_idx + 1}...</code>",
                parse_mode=HTML,
            )

            # Delay between batches to avoid flood
            if i + batch_size < len(members):
                await asyncio.sleep(batch_delay)

        # Final status
        success_rate = (tagged_count / len(members) * 100) if members else 0
        await status_msg.edit_text(
            f"✅ <b>Tagging Complete</b>\n\n"
            f"Total Members: <b>{len(members)}</b>\n"
            f"Tagged: <b>{tagged_count}</b>\n"
            f"Failed: <b>{failed_count}</b>\n"
            f"Success Rate: <b>{success_rate:.1f}%</b>\n\n"
            f"📊 Took {total_batches} batch(es)",
            parse_mode=HTML,
        )

        # Log event
        await log_event(client,
            f"🏷️ <b>Group Tagall Completed</b>\n"
            f"👥 Members: {len(members)}\n"
            f"✅ Tagged: {tagged_count}\n"
            f"❌ Failed: {failed_count}\n"
            f"👤 Admin: {admin_name}\n"
            f"📍 Group: {(await client.get_chat(chat_id)).title or chat_id}"
        )

        # Update DB
        await (await get_tagger_db()).update_one(
            {"session_id": session_id},
            {"$set": {
                "status": "completed",
                "completed_at": datetime.utcnow(),
                "tagged_count": tagged_count,
                "failed_count": failed_count,
            }}
        )

    except Exception as e:
        print(f"[TAGGER] Error during tagall execution: {e}")
        await status_msg.edit_text(
            f"❌ <b>Error During Tagging</b>\n\n"
            f"Error: <code>{str(e)[:100]}</code>\n\n"
            f"Tagged before error: <b>{tagged_count}</b>",
            parse_mode=HTML,
        )

    finally:
        # Cleanup session
        if chat_id in _tagging_sessions:
            del _tagging_sessions[chat_id]


# ══════════════════════════════════════════════════════════════════════════════
# ═════════════════════════ CANCEL/STOP COMMANDS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.command(["stoptag", "cancel"]) & filters.group)
async def stop_tag_cmd(client: Client, message: Message):
    """Stop ongoing tagging operation."""
    if not await _is_admin_msg(client, message):
        m = await message.reply_text(
            "❌ <b>Admin Only</b>",
            parse_mode=HTML,
        )
        asyncio.create_task(_auto_del(m, 30))
        return

    chat_id = message.chat.id

    if chat_id not in _tagging_sessions or _tagging_sessions[chat_id].get("cancel"):
        m = await message.reply_text(
            "ℹ️ <b>No tagging in progress</b>\n\n"
            "There's no active tagging operation to stop.",
            parse_mode=HTML,
        )
        asyncio.create_task(_auto_del(m, 30))
        return

    # Mark session for cancellation
    _tagging_sessions[chat_id]["cancel"] = True

    m = await message.reply_text(
        "⏹️ <b>Tagging Stopped</b>\n\n"
        "The tagging operation will stop after the current batch completes.",
        parse_mode=HTML,
    )
    asyncio.create_task(_auto_del(m, 30))

    await log_event(client,
        f"⏹️ <b>Tagall Cancelled</b>\n"
        f"Admin: {message.from_user.first_name}\n"
        f"📍 Group: {message.chat.title or chat_id}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# ═════════════════════════ STATUS & ADMIN COMMANDS ━━━━━━━━━━━━━━━━━━━━━━━━━━
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.command("taggingstatus") & filters.group)
async def tagging_status_cmd(client: Client, message: Message):
    """Show current tagging status."""
    if not await _is_admin_msg(client, message):
        return

    chat_id = message.chat.id
    session = _tagging_sessions.get(chat_id)

    if not session:
        m = await message.reply_text(
            "ℹ️ <b>No tagging in progress</b>",
            parse_mode=HTML,
        )
        asyncio.create_task(_auto_del(m, 30))
        return

    status = "🔄 In Progress" if not session.get("cancel") else "⏸️ Stopping"
    text = (
        f"<b>📊 Tagging Status</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Status:</b> {status}\n"
        f"<b>Admin:</b> {session.get('admin_name', 'Unknown')}\n"
        f"<b>Members:</b> {session.get('members_count', 0)}\n"
        f"<b>Session ID:</b> <code>{session.get('session_id', 'N/A')}</code>\n\n"
        f"Use /stoptag to stop the operation."
    )

    m = await message.reply_text(text, parse_mode=HTML)
    asyncio.create_task(_auto_del(m, 60))


@app.on_message(filters.command("tagconfig") & filters.user(ADMIN_ID) & filters.private)
async def tagconfig_cmd(_, message: Message):
    """Configure tagging behavior (super admin only)."""
    args = message.command[1:]

    if not args or args[0].lower() not in ("batchsize", "delay", "retries"):
        text = (
            "<b>Tagging Configuration</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Usage:\n"
            "<code>/tagconfig batchsize 5</code> — Members per batch\n"
            "<code>/tagconfig delay 1.5</code> — Seconds between batches\n"
            "<code>/tagconfig retries 3</code> — Max retries per batch\n\n"
            "Current config:\n"
        )

        config = await get_batch_config()
        for key, val in config.items():
            text += f"  • {key}: <b>{val}</b>\n"

        await message.reply_text(text, parse_mode=HTML)
        return

    try:
        setting = args[0].lower()
        value = float(args[1]) if setting == "delay" else int(args[1])

        config_key = "tagall_config"
        await db["bot_settings"].update_one(
            {"key": config_key},
            {"$set": {
                f"value.{setting}": value,
                "updated_at": datetime.utcnow(),
            }},
            upsert=True,
        )

        await message.reply_text(
            f"✅ <b>Config Updated</b>\n\n"
            f"Setting: <b>{setting}</b>\n"
            f"Value: <b>{value}</b>",
            parse_mode=HTML,
        )

        await log_event(None,
            f"⚙️ <b>Tagall Config Changed</b>\n"
            f"Setting: {setting} = {value}"
        )

    except (ValueError, IndexError):
        await message.reply_text("❌ Invalid arguments.", parse_mode=HTML)


@app.on_message(filters.command("taghistory") & filters.user(ADMIN_ID) & filters.private)
async def taghistory_cmd(_, message: Message):
    """View tagging history (super admin only)."""
    args = message.command[1:]

    if args and args[0].lstrip("-").isdigit():
        chat_id = int(args[0])
        limit = 10
    else:
        limit = int(args[0]) if args and args[0].isdigit() else 20

    sessions = await (await get_tagger_db()).find(
        {"status": "completed"}
    ).sort("created_at", -1).to_list(length=limit)

    if not sessions:
        await message.reply_text("📭 No tagging history found.", parse_mode=HTML)
        return

    text = f"<b>📝 Tagging History (Last {len(sessions)})</b>\n" "━━━━━━━━━━━━━━━━━\n\n"

    for i, session in enumerate(sessions, 1):
        success_rate = (
            (session.get("tagged_count", 0) / session.get("members_count", 1) * 100)
            if session.get("members_count")
            else 0
        )
        text += (
            f"<b>{i}.</b> Group: <code>{session.get('chat_id')}</code>\n"
            f"   👤 {session.get('admin_name')}\n"
            f"   👥 {session.get('members_count')} → "
            f"✅ {session.get('tagged_count')} "
            f"({success_rate:.0f}%)\n"
            f"   📅 {session.get('created_at').strftime('%d %b %Y %H:%M')}\n\n"
        )

    await message.reply_text(text, parse_mode=HTML)


# ══════════════════════════════════════════════════════════════════════════════
# ═════════════════════════ HELP COMMAND ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ══════════════════════════════════════════════════════════════════════════════

@app.on_message(filters.command("taghelp") & filters.group)
async def taghelp_cmd(client: Client, message: Message):
    """Show tagging help."""
    if not await _is_admin_msg(client, message):
        return

    text = (
        "<b>🏷️ Invisible Tagall - Help</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>Commands:</b>\n\n"
        "<b>1. /tagall [message]</b>\n"
        "   Tag all group members invisibly\n"
        "   Optional: Add custom message\n"
        "   Example: /tagall Check pinned message!\n\n"
        "<b>2. /stoptag</b>\n"
        "   Stop ongoing tagging operation\n\n"
        "<b>3. /taggingstatus</b>\n"
        "   View current tagging progress\n\n"
        "<b>⚠️ Requirements:</b>\n"
        "   • You must be a group admin\n"
        "   • Bot must be a group admin\n"
        "   • Members must not be bots\n\n"
        "<b>💡 Features:</b>\n"
        "   ✅ Invisible Zero-Width mentions\n"
        "   ✅ Batch processing (avoids flood)\n"
        "   ✅ Custom message support\n"
        "   ✅ Session management\n"
        "   ✅ Error handling & retries\n"
    )

    m = await message.reply_text(text, parse_mode=HTML)
    asyncio.create_task(_auto_del(m, 120))
