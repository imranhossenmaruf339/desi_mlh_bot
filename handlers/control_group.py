"""
Control Group System
──────────────────────────────────────────────────────────
একটি প্রাইভেট Telegram গ্রুপ থেকে সব বট-গ্রুপ পরিচালনা।

Setup:
  ১. একটি প্রাইভেট গ্রুপ তৈরি করুন (Control Center)
  ২. বটকে Admin করুন
  ৩. সেই গ্রুপে /setcontrolgroup পাঠান

Control Group কমান্ড:
  /groups                         — সব পরিচালিত গ্রুপের তালিকা
  /groupstats                     — বট পরিসংখ্যান
  /sendall [msg]                  — সব গ্রুপে broadcast
  /sendto                         — নির্দিষ্ট গ্রুপে মেসেজ
  /taggroup [chat_id] [msg]       — গ্রুপের সবাইকে invisible tag
  /protect [gid] forward|links|spam on|off — Protection সেট
  /protections                    — সব গ্রুপের protection
  /kw add|del|list|clear          — Keyword auto-reply
  /ctrlhelp                       — এই সাহায্য মেনু
"""

import asyncio
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

from config import HTML, ADMIN_ID, groups_col, settings_col, db, app
from helpers import _auto_del, _is_admin_msg, bot_api, log_event, is_any_admin


# ── DB ──────────────────────────────────────────────────────────────────────────
_ctrl_col = db["control_group_settings"]

# ── In-memory sessions ──────────────────────────────────────────────────────────
_ctrl_sessions: dict[int, dict] = {}

ZWNJ = "\u200c"  # Invisible character for tag mentions


# ── Core helpers ────────────────────────────────────────────────────────────────

async def get_control_group() -> int | None:
    doc = await _ctrl_col.find_one({"key": "control_group"})
    return int(doc["chat_id"]) if doc and doc.get("chat_id") else None


async def set_control_group_db(chat_id: int):
    await _ctrl_col.update_one(
        {"key": "control_group"},
        {"$set": {"key": "control_group", "chat_id": chat_id}},
        upsert=True,
    )


async def is_control_group(chat_id: int) -> bool:
    cg = await get_control_group()
    return cg == chat_id


async def _is_ctrl_admin(client: Client, message: Message) -> bool:
    uid = message.from_user.id if message.from_user else 0
    if await is_any_admin(uid):
        return True
    try:
        member = await client.get_chat_member(message.chat.id, uid)
        from pyrogram.enums import ChatMemberStatus
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER
        )
    except Exception:
        return False


# ── /setcontrolgroup ─────────────────────────────────────────────────────────────

@app.on_message(filters.command("setcontrolgroup") & filters.group)
async def set_control_group_cmd(client: Client, message: Message):
    uid = message.from_user.id if message.from_user else 0
    if not await is_any_admin(uid):
        return

    chat_id = message.chat.id
    title   = message.chat.title or str(chat_id)

    await set_control_group_db(chat_id)

    m = await message.reply_text(
        f"✅ <b>Control Group সেট হয়েছে!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 গ্রুপ: <b>{title}</b>\n"
        f"🆔 ID: <code>{chat_id}</code>\n\n"
        f"এখন এই গ্রুপ থেকে সব বট-গ্রুপ পরিচালনা করা যাবে।\n"
        f"কমান্ডের তালিকা দেখতে: /ctrlhelp",
        parse_mode=HTML,
    )
    asyncio.create_task(_auto_del(m, 30))


# ── /ctrlhelp ────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("ctrlhelp") & filters.group)
async def ctrl_help_cmd(client: Client, message: Message):
    if not await is_control_group(message.chat.id):
        return
    if not await _is_ctrl_admin(client, message):
        return

    m = await message.reply_text(
        "🎛️ <b>Control Group — সম্পূর্ণ কমান্ড গাইড</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>গ্রুপ তথ্য:</b>\n"
        "  /groups                       — সব গ্রুপের তালিকা\n"
        "  /groupstats                   — বট পরিসংখ্যান\n\n"
        "📤 <b>মেসেজ পাঠানো:</b>\n"
        "  /sendall [msg]                — সব গ্রুপে broadcast\n"
        "  /sendall (reply করুন)         — reply করা মেসেজ সব গ্রুপে\n"
        "  /sendto                       — নির্দিষ্ট গ্রুপ বেছে নিন\n"
        "  /sendto [chat_id] [msg]       — সরাসরি ID দিয়ে পাঠান\n\n"
        "🏷️ <b>Tag করা:</b>\n"
        "  /taggroup [gid] [msg]         — গ্রুপের সবাইকে invisible tag\n\n"
        "🛡️ <b>Protection System:</b>\n"
        "  /protect [gid] forward on|off — Forward মেসেজ ব্লক\n"
        "  /protect [gid] links on|off   — লিঙ্ক ব্লক\n"
        "  /protect [gid] spam on|off    — Spam ব্লক\n"
        "  /protect [gid] spam_limit 5   — Spam limit (msgs/10s)\n"
        "  /protections                  — সব গ্রুপের সেটিং দেখুন\n\n"
        "🔑 <b>Keyword Auto-Reply:</b>\n"
        "  /kw add [word] [reply]        — keyword যোগ করুন\n"
        "  /kw del [word]                — keyword সরানো\n"
        "  /kw list                      — সব keyword দেখুন\n"
        "  /kw clear                     — সব keyword মুছুন\n\n"
        "💎 <b>Broadcast বাটন যোগ:</b>\n"
        "  /sendall এর পরে ➕ Add Button ট্যাপ করুন\n"
        "  Format: <code>Button Text | https://url.com</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 সব কমান্ড শুধু Control Group-এই কাজ করবে।",
        parse_mode=HTML,
    )
    asyncio.create_task(_auto_del(m, 90))
    try:
        await message.delete()
    except Exception:
        pass


# ── /groups ──────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("groups") & filters.group)
async def ctrl_groups_cmd(client: Client, message: Message):
    if not await is_control_group(message.chat.id):
        return
    if not await _is_ctrl_admin(client, message):
        return

    docs = await groups_col.find({}).sort("title", 1).to_list(length=200)
    if not docs:
        m = await message.reply_text("📭 এখনো কোনো গ্রুপ নেই।", parse_mode=HTML)
        asyncio.create_task(_auto_del(m, 15))
        return

    lines = [f"📋 <b>পরিচালিত গ্রুপসমূহ</b> (মোট {len(docs)}টি)\n━━━━━━━━━━━━━━━━━━━━━━"]
    for i, d in enumerate(docs, 1):
        cid   = d.get("chat_id", "?")
        title = (d.get("title") or str(cid))[:35]
        lines.append(f"{i}. <b>{title}</b>\n   🆔 <code>{cid}</code>")

    m = await message.reply_text("\n".join(lines), parse_mode=HTML)
    asyncio.create_task(_auto_del(m, 120))
    try:
        await message.delete()
    except Exception:
        pass


# ── /groupstats ──────────────────────────────────────────────────────────────────

@app.on_message(filters.command("groupstats") & filters.group)
async def ctrl_groupstats_cmd(client: Client, message: Message):
    if not await is_control_group(message.chat.id):
        return
    if not await _is_ctrl_admin(client, message):
        return

    from config import users_col, videos_col, clones_col

    total_users  = await users_col.count_documents({})
    total_groups = await groups_col.count_documents({})
    total_videos = await videos_col.count_documents({})
    total_clones = await clones_col.count_documents({})

    m = await message.reply_text(
        f"📊 <b>বট পরিসংখ্যান</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 মোট ব্যবহারকারী : <b>{total_users:,}</b>\n"
        f"📍 গ্রুপ সংখ্যা    : <b>{total_groups:,}</b>\n"
        f"🎬 ভিডিও সংখ্যা   : <b>{total_videos:,}</b>\n"
        f"🤖 Clone বট        : <b>{total_clones:,}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 {datetime.utcnow().strftime('%d %b %Y %H:%M UTC')}",
        parse_mode=HTML,
    )
    asyncio.create_task(_auto_del(m, 60))
    try:
        await message.delete()
    except Exception:
        pass


# ── /sendall ─────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("sendall") & filters.group)
async def ctrl_sendall_cmd(client: Client, message: Message):
    if not await is_control_group(message.chat.id):
        return
    if not await _is_ctrl_admin(client, message):
        return

    uid = message.from_user.id

    # Collect content
    target_msg = message.reply_to_message
    text_args  = " ".join(message.command[1:]).strip()

    if not target_msg and not text_args:
        m = await message.reply_text(
            "⚠️ <b>ব্যবহার:</b>\n"
            "<code>/sendall [মেসেজ]</code>\n"
            "অথবা কোনো মেসেজ reply করে <code>/sendall</code>",
            parse_mode=HTML,
        )
        asyncio.create_task(_auto_del(m, 20))
        return

    _ctrl_sessions[uid] = {
        "step":         "send_all_confirm",
        "content_msg":  target_msg,
        "text":         text_args if not target_msg else "",
        "extra_buttons": [],
    }
    await _show_sendall_confirm(client, message, uid)


async def _show_sendall_confirm(client: Client, message: Message, uid: int):
    session = _ctrl_sessions.get(uid, {})
    content = session.get("content_msg")
    txt     = session.get("text", "")
    btns    = session.get("extra_buttons", [])
    gcount  = await groups_col.count_documents({})

    preview = ""
    if content:
        preview = f"\n📎 <i>Reply করা মেসেজ ({content.media and 'মিডিয়া' or 'টেক্সট'})</i>"
    elif txt:
        preview = f"\n📝 <i>{txt[:100]}</i>"

    btn_text = ""
    for row in btns:
        for b in row:
            btn_text += f"\n  🔗 {b['text']} → {b['url']}"

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 সব গ্রুপে পাঠান", callback_data=f"csa_yes:{uid}"),
            InlineKeyboardButton("❌ বাতিল",          callback_data=f"csa_no:{uid}"),
        ],
        [
            InlineKeyboardButton("➕ বাটন যোগ করুন", callback_data=f"csa_addbtn:{uid}"),
        ],
    ])

    m = await message.reply_text(
        f"📤 <b>সব গ্রুপে Broadcast</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 গ্রুপ সংখ্যা: <b>{gcount}</b>{preview}"
        f"{btn_text if btn_text else ''}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"নিশ্চিত করুন?",
        parse_mode=HTML,
        reply_markup=kb,
    )
    asyncio.create_task(_auto_del(m, 120))


@app.on_callback_query(filters.regex(r"^csa_(yes|no|addbtn):(\d+)$"))
async def ctrl_sendall_cb(client: Client, cq: CallbackQuery):
    import re as _re
    m2    = _re.match(r"^csa_(yes|no|addbtn):(\d+)$", cq.data)
    action = m2.group(1)
    uid    = int(m2.group(2))

    if cq.from_user.id != uid:
        await cq.answer("❌ শুধু কমান্ড-দাতাই ব্যবহার করতে পারবেন।", show_alert=True)
        return

    session = _ctrl_sessions.get(uid)
    if not session:
        await cq.answer("⏰ Session শেষ হয়ে গেছে।", show_alert=True)
        return

    if action == "no":
        _ctrl_sessions.pop(uid, None)
        await cq.edit_message_text("❌ Broadcast বাতিল করা হয়েছে।")
        return

    if action == "addbtn":
        session["step"] = "sendall_wait_button"
        _ctrl_sessions[uid] = session
        await cq.edit_message_text(
            "🔗 <b>বাটন যোগ করুন</b>\n\n"
            "Format: <code>Button Text | https://example.com</code>",
            parse_mode=HTML,
        )
        return

    # ── action == "yes" — broadcast ─────────────────────────────────────────
    _ctrl_sessions.pop(uid, None)
    await cq.answer("📡 Broadcast শুরু হচ্ছে…")
    await cq.edit_message_text("📡 <b>Broadcast চলছে…</b>", parse_mode=HTML)

    content_msg  = session.get("content_msg")
    text         = session.get("text", "")
    extra_buttons= session.get("extra_buttons", [])

    kb_json = None
    if extra_buttons:
        kb_json = {"inline_keyboard": extra_buttons}

    docs = await groups_col.find({}).to_list(length=1000)
    ok = fail = 0
    for d in docs:
        gid = d.get("chat_id")
        if not gid:
            continue
        try:
            if content_msg:
                await client.copy_message(
                    chat_id=gid,
                    from_chat_id=content_msg.chat.id,
                    message_id=content_msg.id,
                )
            else:
                params = {"chat_id": gid, "text": text, "parse_mode": "HTML"}
                if kb_json:
                    params["reply_markup"] = kb_json
                await bot_api("sendMessage", params)
            ok += 1
        except FloodWait as fw:
            await asyncio.sleep(fw.value + 1)
        except Exception as e:
            print(f"[SENDALL] {gid} failed: {e}")
            fail += 1
        await asyncio.sleep(0.05)

    try:
        await cq.message.edit_text(
            f"✅ <b>Broadcast সম্পন্ন!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ সফল : <b>{ok}</b>\n"
            f"❌ ব্যর্থ: <b>{fail}</b>",
            parse_mode=HTML,
        )
    except Exception:
        pass


# ── /sendto ──────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("sendto") & filters.group)
async def ctrl_sendto_cmd(client: Client, message: Message):
    if not await is_control_group(message.chat.id):
        return
    if not await _is_ctrl_admin(client, message):
        return

    uid  = message.from_user.id
    args = message.command[1:]

    # Direct: /sendto -1001234 [message]
    if args and args[0].lstrip("-").isdigit():
        gid    = int(args[0])
        text   = " ".join(args[1:]).strip()
        replied = message.reply_to_message

        try:
            chat  = await client.get_chat(gid)
            title = chat.title or str(gid)
        except Exception:
            title = str(gid)

        try:
            if replied:
                await client.copy_message(gid, replied.chat.id, replied.id)
            elif text:
                await bot_api("sendMessage", {
                    "chat_id": gid, "text": text, "parse_mode": "HTML"
                })
            else:
                m = await message.reply_text(
                    "⚠️ মেসেজ বা reply করা মেসেজ দিন।", parse_mode=HTML
                )
                asyncio.create_task(_auto_del(m, 15))
                return

            m = await message.reply_text(
                f"✅ পাঠানো হয়েছে → <b>{title}</b>", parse_mode=HTML
            )
        except Exception as e:
            m = await message.reply_text(f"❌ ব্যর্থ: <code>{e}</code>", parse_mode=HTML)
        asyncio.create_task(_auto_del(m, 15))
        return

    # Interactive: show group picker
    docs = await groups_col.find({}).sort("title", 1).to_list(length=100)
    if not docs:
        m = await message.reply_text("📭 কোনো গ্রুপ নেই।", parse_mode=HTML)
        asyncio.create_task(_auto_del(m, 15))
        return

    rows = []
    for d in docs:
        cid   = d.get("chat_id", "?")
        title = (d.get("title") or str(cid))[:20]
        rows.append([InlineKeyboardButton(title, callback_data=f"cst_pick:{uid}:{cid}")])

    rows.append([InlineKeyboardButton("❌ বাতিল", callback_data=f"cst_cancel:{uid}")])

    _ctrl_sessions[uid] = {"step": "sendto_pick"}
    m = await message.reply_text(
        "📍 <b>কোন গ্রুপে পাঠাবেন?</b>",
        parse_mode=HTML,
        reply_markup=InlineKeyboardMarkup(rows),
    )
    asyncio.create_task(_auto_del(m, 60))


@app.on_callback_query(filters.regex(r"^cst_(pick|cancel)"))
async def ctrl_sendto_pick_cb(client: Client, cq: CallbackQuery):
    parts = cq.data.split(":", 2)
    action = parts[0].replace("cst_", "")
    uid    = int(parts[1])

    if cq.from_user.id != uid:
        await cq.answer("❌ শুধু কমান্ড-দাতাই ব্যবহার করতে পারবেন।", show_alert=True)
        return

    if action == "cancel":
        _ctrl_sessions.pop(uid, None)
        await cq.edit_message_text("❌ বাতিল।")
        return

    gid = int(parts[2])
    try:
        chat  = await client.get_chat(gid)
        title = chat.title or str(gid)
    except Exception:
        title = str(gid)

    _ctrl_sessions[uid] = {"step": "sendto_wait_content", "gid": gid, "title": title}
    await cq.edit_message_text(
        f"📝 এখন <b>{title}</b> গ্রুপে পাঠানোর মেসেজ লিখুন বা forward করুন।\n"
        f"/cancel লিখুন বাতিল করতে।",
        parse_mode=HTML,
    )


# ── /taggroup ────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("taggroup") & filters.group)
async def ctrl_taggroup_cmd(client: Client, message: Message):
    if not await is_control_group(message.chat.id):
        return
    if not await _is_ctrl_admin(client, message):
        return

    args = message.command[1:]
    if len(args) < 2:
        m = await message.reply_text(
            "⚠️ <b>ব্যবহার:</b>\n"
            "<code>/taggroup [group_id] [মেসেজ]</code>",
            parse_mode=HTML,
        )
        asyncio.create_task(_auto_del(m, 20))
        return

    raw_gid = args[0]
    if not raw_gid.lstrip("-").isdigit():
        m = await message.reply_text("❌ সঠিক group ID দিন।", parse_mode=HTML)
        asyncio.create_task(_auto_del(m, 15))
        return

    gid     = int(raw_gid)
    msg_txt = " ".join(args[1:]).strip()

    try:
        chat = await client.get_chat(gid)
    except Exception as e:
        m = await message.reply_text(f"❌ গ্রুপ খুঁজে পাওয়া যায়নি: <code>{e}</code>", parse_mode=HTML)
        asyncio.create_task(_auto_del(m, 15))
        return

    members_tagged = 0
    chunk_size     = 5
    tags_chunk     = []
    chunks_sent    = 0

    async for member in client.get_chat_members(gid):
        u = member.user
        if u.is_bot or u.is_deleted:
            continue
        tag = f'<a href="tg://user?id={u.id}">{ZWNJ}</a>'
        tags_chunk.append(tag)
        members_tagged += 1

        if len(tags_chunk) >= chunk_size:
            prefix  = msg_txt if chunks_sent == 0 else ""
            payload = (prefix + " " + "".join(tags_chunk)).strip()
            try:
                await bot_api("sendMessage", {
                    "chat_id": gid, "text": payload, "parse_mode": "HTML"
                })
                chunks_sent += 1
            except FloodWait as fw:
                await asyncio.sleep(fw.value + 1)
            except Exception:
                pass
            tags_chunk = []
            await asyncio.sleep(1)

    if tags_chunk:
        prefix  = msg_txt if chunks_sent == 0 else ""
        payload = (prefix + " " + "".join(tags_chunk)).strip()
        try:
            await bot_api("sendMessage", {
                "chat_id": gid, "text": payload, "parse_mode": "HTML"
            })
        except Exception:
            pass

    m = await message.reply_text(
        f"✅ <b>Tag সম্পন্ন!</b>\n"
        f"👥 Tagged: <b>{members_tagged}</b> জন\n"
        f"📍 Group: <b>{chat.title}</b>",
        parse_mode=HTML,
    )
    asyncio.create_task(_auto_del(m, 30))
    try:
        await message.delete()
    except Exception:
        pass


# ── Session handler for sendto and sendall button ─────────────────────────────

@app.on_message(filters.group, group=10)
async def _ctrl_session_handler(client: Client, message: Message):
    if not message.from_user:
        return
    if not await is_control_group(message.chat.id):
        return

    uid = message.from_user.id
    if uid not in _ctrl_sessions:
        return

    session = _ctrl_sessions[uid]
    text    = (message.text or "").strip()

    if text == "/cancel":
        _ctrl_sessions.pop(uid, None)
        m = await message.reply_text("❌ বাতিল।", parse_mode=HTML)
        asyncio.create_task(_auto_del(m, 10))
        return

    step = session.get("step")

    if step == "sendall_wait_content":
        session["msg_type"]    = "content"
        session["content_msg"] = message
        session["step"]        = "send_all_confirm"
        _ctrl_sessions[uid]    = session
        await _show_sendall_confirm(client, message, uid)

    elif step == "sendto_wait_content":
        gid   = session.get("gid")
        title = session.get("title", str(gid))
        _ctrl_sessions.pop(uid, None)
        try:
            await client.copy_message(gid, message.chat.id, message.id)
            m = await message.reply_text(
                f"✅ পাঠানো হয়েছে — <b>{title}</b>", parse_mode=HTML
            )
        except Exception as e:
            m = await message.reply_text(
                f"❌ ব্যর্থ: <code>{e}</code>", parse_mode=HTML
            )
        asyncio.create_task(_auto_del(m, 15))

    elif step == "sendall_wait_button":
        if "|" in text:
            parts    = text.split("|", 1)
            btn_text = parts[0].strip()
            btn_url  = parts[1].strip()
            session.setdefault("extra_buttons", []).append(
                [{"text": btn_text, "url": btn_url}]
            )
            session["step"] = "send_all_confirm"
            _ctrl_sessions[uid] = session
            m = await message.reply_text(
                f"✅ বাটন যোগ হয়েছে: <b>{btn_text}</b>",
                parse_mode=HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🚀 পাঠান",     callback_data=f"csa_yes:{uid}"),
                    InlineKeyboardButton("❌ বাতিল",     callback_data=f"csa_no:{uid}"),
                    InlineKeyboardButton("➕ আরো বাটন", callback_data=f"csa_addbtn:{uid}"),
                ]]),
            )
        else:
            m = await message.reply_text(
                "⚠️ Format: <code>Button Text | https://example.com</code>",
                parse_mode=HTML,
            )
        asyncio.create_task(_auto_del(m, 25))
