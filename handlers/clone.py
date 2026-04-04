import asyncio
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message

from config import HTML, ADMIN_ID, clones_col, app
from helpers import _auto_del, log_event


# ─── /addclone ────────────────────────────────────────────────────────────────

@app.on_message(filters.command("addclone") & filters.user(ADMIN_ID) & filters.private)
async def addclone_cmd(client: Client, message: Message):
    args = message.command[1:]
    if not args:
        await message.reply_text(
            "📌 <b>Usage:</b>\n"
            "<code>/addclone {bot_token} [name]</code>\n\n"
            "Example:\n"
            "<code>/addclone 7123456789:AAH... MyCloneBot</code>\n\n"
            "ℹ️ Get your token from @BotFather with /newbot",
            parse_mode=HTML,
        )
        return

    token = args[0]
    name  = " ".join(args[1:]) if len(args) > 1 else f"Clone {token[:10]}..."

    if ":" not in token or len(token) < 20:
        await message.reply_text("❌ Invalid bot token format.", parse_mode=HTML)
        return

    existing = await clones_col.find_one({"token": token})
    if existing and existing.get("active"):
        await message.reply_text(
            f"ℹ️ Clone <b>{existing.get('name','?')}</b> is already active.",
            parse_mode=HTML,
        )
        return

    wait = await message.reply_text("⏳ Starting clone bot...", parse_mode=HTML)

    from clone_manager import start_clone
    ok = await start_clone(token, name)

    if ok:
        await clones_col.update_one(
            {"token": token},
            {"$set": {
                "token":      token,
                "name":       name,
                "active":     True,
                "added_at":   datetime.utcnow(),
                "added_by":   ADMIN_ID,
            }},
            upsert=True,
        )
        await wait.edit_text(
            f"✅ <b>Clone Bot Started!</b>\n\n"
            f"🤖 Name  : <b>{name}</b>\n"
            f"🔑 Token : <code>{token[:20]}...</code>\n\n"
            f"The clone bot is now running with all the same features.\n"
            f"Users can interact with it just like the main bot.",
            parse_mode=HTML,
        )
        await log_event(client,
            f"🤖 <b>Clone Bot Added</b>\n"
            f"📌 Name: {name}\n"
            f"🔑 Token: <code>{token[:20]}...</code>"
        )
    else:
        await wait.edit_text(
            "❌ <b>Failed to start clone.</b>\n\n"
            "Possible reasons:\n"
            "• Invalid or expired token\n"
            "• Bot already running elsewhere\n"
            "• Token doesn't have correct API access",
            parse_mode=HTML,
        )


# ─── /removeclone ─────────────────────────────────────────────────────────────

@app.on_message(filters.command("removeclone") & filters.user(ADMIN_ID) & filters.private)
async def removeclone_cmd(client: Client, message: Message):
    docs = await clones_col.find({"active": True}).to_list(length=100)
    if not docs:
        await message.reply_text("📭 No active clones.", parse_mode=HTML)
        return

    args = message.command[1:]
    if not args:
        lines = ["📋 <b>Active Clones:</b>\n"]
        for i, doc in enumerate(docs, 1):
            lines.append(f"{i}. <b>{doc.get('name','?')}</b>")
            lines.append(f"   Token: <code>{doc['token'][:20]}...</code>")
        lines.append("\nUsage: <code>/removeclone {token}</code>")
        await message.reply_text("\n".join(lines), parse_mode=HTML)
        return

    token = args[0]
    doc   = await clones_col.find_one({"token": token, "active": True})
    if not doc:
        await message.reply_text("❌ Clone not found.", parse_mode=HTML)
        return

    from clone_manager import stop_clone
    await stop_clone(token)
    await clones_col.update_one({"token": token}, {"$set": {"active": False}})

    await message.reply_text(
        f"✅ <b>Clone Removed</b>\n🤖 {doc.get('name','?')}",
        parse_mode=HTML,
    )
    await log_event(client,
        f"🗑 <b>Clone Bot Removed</b>\n📌 {doc.get('name','?')}"
    )


# ─── /clones ──────────────────────────────────────────────────────────────────

@app.on_message(filters.command("clones") & filters.user(ADMIN_ID) & filters.private)
async def clones_list_cmd(client: Client, message: Message):
    from clone_manager import get_active_clones
    docs = await clones_col.find({"active": True}).to_list(length=100)
    running = get_active_clones()

    if not docs:
        await message.reply_text(
            "📭 <b>No clones configured.</b>\n\n"
            "Use <code>/addclone {token} {name}</code> to add a clone bot.",
            parse_mode=HTML,
        )
        return

    lines = [
        "🤖 <b>CLONE BOTS — DESI MLH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]

    for i, doc in enumerate(docs, 1):
        token    = doc["token"]
        name     = doc.get("name", "?")
        added_at = doc.get("added_at")
        added_str = added_at.strftime("%d %b %Y") if added_at else "—"
        status   = "🟢 Running" if token in running else "🔴 Stopped"
        lines.append(
            f"{i}. {status}  <b>{name}</b>\n"
            f"   🔑 <code>{token[:20]}...</code>\n"
            f"   📅 Added: {added_str}"
        )

    lines.append(
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Total: {len(docs)} clone(s)  |  🟢 {len(running)} running\n"
        "🤖 DESI MLH SYSTEM"
    )
    await message.reply_text("\n\n".join(lines), parse_mode=HTML)
