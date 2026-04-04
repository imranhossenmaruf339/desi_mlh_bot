import asyncio
from datetime import datetime, timezone, timedelta

from pyrogram import Client, filters
from pyrogram.types import Message

from config import HTML, ADMIN_ID, nightmode_col, app
from helpers import log_event, _is_admin_msg, bot_api

# Bangladesh Standard Time = UTC+6
BD_TZ = timezone(timedelta(hours=6))

_RESTRICTED_PERMS = {
    "can_send_messages":       False,
    "can_send_audios":         False,
    "can_send_documents":      False,
    "can_send_photos":         False,
    "can_send_videos":         False,
    "can_send_video_notes":    False,
    "can_send_voice_notes":    False,
    "can_send_polls":          False,
    "can_send_other_messages": False,
    "can_add_web_page_previews": False,
    "can_change_info":         False,
    "can_invite_users":        False,
    "can_pin_messages":        False,
}

_OPEN_PERMS = {
    "can_send_messages":       True,
    "can_send_audios":         True,
    "can_send_documents":      True,
    "can_send_photos":         True,
    "can_send_videos":         True,
    "can_send_video_notes":    True,
    "can_send_voice_notes":    True,
    "can_send_polls":          True,
    "can_send_other_messages": True,
    "can_add_web_page_previews": True,
    "can_change_info":         False,
    "can_invite_users":        True,
    "can_pin_messages":        False,
}


def _parse_hhmm(text: str):
    try:
        parts = text.strip().split(":")
        if len(parts) == 2:
            h, m = int(parts[0]), int(parts[1])
            if 0 <= h <= 23 and 0 <= m <= 59:
                return h, m
    except Exception:
        pass
    return None


def _in_night_window(h: int, m: int, sh: int, sm: int, eh: int, em: int) -> bool:
    now_mins   = h  * 60 + m
    start_mins = sh * 60 + sm
    end_mins   = eh * 60 + em
    if start_mins == end_mins:
        return False
    if start_mins > end_mins:
        return now_mins >= start_mins or now_mins < end_mins
    return start_mins <= now_mins < end_mins


def _night_activate_msg(sh: int, sm: int, eh: int, em: int) -> str:
    return (
        "🌙🌙🌙🌙🌙🌙🌙🌙🌙🌙🌙🌙\n"
        "   🔒 নাইট মোড চালু 🔒\n"
        "🌙🌙🌙🌙🌙🌙🌙🌙🌙🌙🌙🌙\n\n"
        "⛔ এখন গ্রুপে মেসেজ বন্ধ আছে।\n"
        "🛏️ সবাই বিশ্রাম নিন!\n\n"
        f"⏰ রাত {sh:02d}:{sm:02d} থেকে সকাল {eh:02d}:{em:02d} পর্যন্ত\n"
        "    (বাংলাদেশ সময় 🇧🇩)\n\n"
        "😴 শুভ রাত্রি! Good Night! 🌃\n\n"
        "🌙🌙🌙🌙🌙🌙🌙🌙🌙🌙🌙🌙\n"
        "🤖 DESI MLH SYSTEM"
    )


def _night_deactivate_msg(sh: int, sm: int, eh: int, em: int) -> str:
    return (
        "☀️☀️☀️☀️☀️☀️☀️☀️☀️☀️☀️☀️\n"
        "   🔓 নাইট মোড বন্ধ 🔓\n"
        "☀️☀️☀️☀️☀️☀️☀️☀️☀️☀️☀️☀️\n\n"
        "✅ গ্রুপ এখন সবার জন্য উন্মুক্ত!\n"
        "💬 এখন মেসেজ করতে পারবেন।\n\n"
        f"⏰ পরবর্তী নাইট মোড: রাত {sh:02d}:{sm:02d}\n"
        "    (বাংলাদেশ সময় 🇧🇩)\n\n"
        "🌅 শুভ সকাল! Good Morning! 🌞\n\n"
        "☀️☀️☀️☀️☀️☀️☀️☀️☀️☀️☀️☀️\n"
        "🤖 DESI MLH SYSTEM"
    )


async def _set_permissions(chat_id: int, perms: dict) -> tuple[bool, str]:
    r = await bot_api("setChatPermissions", {
        "chat_id":    chat_id,
        "permissions": perms,
        "use_independent_chat_permissions": True,
    })
    if r.get("ok"):
        return True, ""
    desc = r.get("description", "unknown error")
    if "CHAT_NOT_MODIFIED" in desc:
        return True, ""
    return False, desc


@app.on_message(filters.command("nightmode") & (filters.group | filters.supergroup))
async def nightmode_cmd(client: Client, message: Message):
    if not await _is_admin_msg(client, message):
        await message.reply_text(
            "❌ শুধুমাত্র গ্রুপ অ্যাডমিন এই কমান্ড ব্যবহার করতে পারবেন।",
            parse_mode=HTML,
        )
        return

    args = message.command[1:]
    if not args:
        now_bd = datetime.now(BD_TZ)
        doc    = await nightmode_col.find_one({"chat_id": message.chat.id})
        status_line = ""
        if doc and doc.get("enabled"):
            sh, sm = doc.get("start_h", 0), doc.get("start_m", 0)
            eh, em = doc.get("end_h", 0),   doc.get("end_m", 0)
            is_restricted = doc.get("is_restricted", False)
            current = "🔒 এখন বন্ধ (Night Mode চালু)" if is_restricted else "🔓 এখন খোলা"
            status_line = (
                f"\n\n📌 <b>বর্তমান অবস্থা:</b> {current}\n"
                f"🌙 বন্ধ হয়: রাত <code>{sh:02d}:{sm:02d}</code> (বাংলাদেশ সময়)\n"
                f"☀️ খোলে  : সকাল <code>{eh:02d}:{em:02d}</code> (বাংলাদেশ সময়)"
            )
        else:
            status_line = "\n\n📌 <b>বর্তমান অবস্থা:</b> ❌ নাইট মোড বন্ধ"
        await message.reply_text(
            "🌙 <b>Night Mode — ব্যবহারের নিয়ম</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "▶️ চালু করতে:\n"
            "<code>/nightmode on 23:00 06:00</code>\n"
            "  (রাত ১১টায় বন্ধ → ভোর ৬টায় খুলবে)\n\n"
            "⏹ বন্ধ করতে:\n"
            "<code>/nightmode off</code>\n\n"
            "📊 অবস্থা দেখতে:\n"
            "<code>/nightmode status</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 এখন বাংলাদেশ সময়: <b>{now_bd.strftime('%I:%M %p')}</b>"
            f"{status_line}",
            parse_mode=HTML,
        )
        return

    sub = args[0].lower()

    # ── OFF ──────────────────────────────────────────────────────────────────
    if sub == "off":
        ok, err = await _set_permissions(message.chat.id, _OPEN_PERMS)
        await nightmode_col.update_one(
            {"chat_id": message.chat.id},
            {"$set": {"enabled": False, "is_restricted": False}},
            upsert=True,
        )
        if not ok:
            await message.reply_text(
                f"⚠️ নাইট মোড DB তে বন্ধ করা হয়েছে, কিন্তু permissions পরিবর্তন হয়নি।\n"
                f"❌ কারণ: <code>{err}</code>\n\n"
                "💡 নিশ্চিত করুন বট গ্রুপে অ্যাডমিন এবং তার Members Restrict করার অনুমতি আছে।",
                parse_mode=HTML,
            )
            return
        await message.reply_text(
            "☀️☀️☀️☀️☀️☀️☀️☀️☀️☀️☀️☀️\n"
            "   ✅ নাইট মোড বন্ধ করা হয়েছে\n"
            "☀️☀️☀️☀️☀️☀️☀️☀️☀️☀️☀️☀️\n\n"
            "💬 গ্রুপ এখন সবার জন্য উন্মুক্ত।\n"
            "🤖 DESI MLH SYSTEM",
        )
        asyncio.create_task(log_event(client,
            f"🌙 <b>Night Mode Disabled</b>\n"
            f"📍 Chat: {message.chat.title or message.chat.id}\n"
            f"👤 By: {message.from_user.first_name} (<code>{message.from_user.id}</code>)"
        ))
        return

    # ── STATUS ────────────────────────────────────────────────────────────────
    if sub == "status":
        doc    = await nightmode_col.find_one({"chat_id": message.chat.id})
        now_bd = datetime.now(BD_TZ)
        if not doc or not doc.get("enabled"):
            await message.reply_text(
                "📊 <b>Night Mode Status</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "❌ এই গ্রুপে নাইট মোড বন্ধ আছে।\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🕐 এখন: <b>{now_bd.strftime('%I:%M %p')}</b> (বাংলাদেশ সময় 🇧🇩)",
                parse_mode=HTML,
            )
        else:
            sh, sm = doc.get("start_h", 0), doc.get("start_m", 0)
            eh, em = doc.get("end_h", 0),   doc.get("end_m", 0)
            is_restricted = doc.get("is_restricted", False)
            h, m   = now_bd.hour, now_bd.minute
            in_night = _in_night_window(h, m, sh, sm, eh, em)
            state  = "🔒 বন্ধ (Night Mode চালু)" if is_restricted else "🔓 খোলা (সাধারণ সময়)"
            await message.reply_text(
                "📊 <b>Night Mode Status</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ নাইট মোড: <b>চালু</b>\n"
                f"🌙 বন্ধ হয়  : রাত <b>{sh:02d}:{sm:02d}</b> (বাংলাদেশ সময় 🇧🇩)\n"
                f"☀️ খোলে    : সকাল <b>{eh:02d}:{em:02d}</b> (বাংলাদেশ সময় 🇧🇩)\n\n"
                f"📌 বর্তমান অবস্থা: {state}\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🕐 এখন: <b>{now_bd.strftime('%I:%M %p')}</b> (বাংলাদেশ সময় 🇧🇩)",
                parse_mode=HTML,
            )
        return

    # ── ON ────────────────────────────────────────────────────────────────────
    if sub == "on":
        if len(args) < 3:
            await message.reply_text(
                "❌ সময় দিন!\n\n"
                "✅ সঠিক নিয়ম:\n"
                "<code>/nightmode on 23:00 06:00</code>\n"
                "(রাত ১১:০০ থেকে ভোর ০৬:০০ পর্যন্ত বন্ধ থাকবে)\n\n"
                "⚠️ সময় অবশ্যই বাংলাদেশ সময়ে দিতে হবে 🇧🇩",
                parse_mode=HTML,
            )
            return

        start_t = _parse_hhmm(args[1])
        end_t   = _parse_hhmm(args[2])

        if not start_t:
            await message.reply_text(
                f"❌ শুরুর সময় <code>{args[1]}</code> ভুল!\n"
                "✅ সঠিক format: <code>HH:MM</code>  যেমন: <code>23:00</code>",
                parse_mode=HTML,
            )
            return
        if not end_t:
            await message.reply_text(
                f"❌ শেষ সময় <code>{args[2]}</code> ভুল!\n"
                "✅ সঠিক format: <code>HH:MM</code>  যেমন: <code>06:00</code>",
                parse_mode=HTML,
            )
            return

        sh, sm = start_t
        eh, em = end_t

        if (sh * 60 + sm) == (eh * 60 + em):
            await message.reply_text(
                "❌ শুরু ও শেষের সময় একই হতে পারবে না!",
                parse_mode=HTML,
            )
            return

        await nightmode_col.update_one(
            {"chat_id": message.chat.id},
            {"$set": {
                "enabled":       True,
                "chat_id":       message.chat.id,
                "start_h":       sh, "start_m": sm,
                "end_h":         eh, "end_m":   em,
                "is_restricted": False,
            }},
            upsert=True,
        )

        now_bd = datetime.now(BD_TZ)
        h, m   = now_bd.hour, now_bd.minute
        in_night_now = _in_night_window(h, m, sh, sm, eh, em)

        # যদি এখনই রাতের সময় হয়, তাহলে এখনই lock করে দাও
        if in_night_now:
            ok, err = await _set_permissions(message.chat.id, _RESTRICTED_PERMS)
            if ok:
                await nightmode_col.update_one(
                    {"chat_id": message.chat.id}, {"$set": {"is_restricted": True}}
                )

        await message.reply_text(
            "🌙🌙🌙🌙🌙🌙🌙🌙🌙🌙🌙🌙\n"
            "  ✅ নাইট মোড সেট করা হয়েছে!\n"
            "🌙🌙🌙🌙🌙🌙🌙🌙🌙🌙🌙🌙\n\n"
            f"🔒 বন্ধ হবে  : রাত <b>{sh:02d}:{sm:02d}</b>\n"
            f"🔓 খুলবে    : সকাল <b>{eh:02d}:{em:02d}</b>\n"
            f"🇧🇩 সময়জোন  : বাংলাদেশ সময় (UTC+6)\n\n"
            + ("⚡ <b>এখনই রাতের সময়, গ্রুপ লক করা হয়েছে!</b>\n\n" if in_night_now else "")
            + "🤖 DESI MLH SYSTEM",
            parse_mode=HTML,
        )
        asyncio.create_task(log_event(client,
            f"🌙 <b>Night Mode Set</b>\n"
            f"📍 Chat: {message.chat.title or message.chat.id}\n"
            f"👤 By: {message.from_user.first_name} (<code>{message.from_user.id}</code>)\n"
            f"⏰ {sh:02d}:{sm:02d} → {eh:02d}:{em:02d} (BD Time)"
        ))
        return

    await message.reply_text(
        "❌ অজানা কমান্ড।\n\n"
        "সঠিক ব্যবহার:\n"
        "<code>/nightmode on 23:00 06:00</code>\n"
        "<code>/nightmode off</code>\n"
        "<code>/nightmode status</code>",
        parse_mode=HTML,
    )


async def nightmode_loop(client: Client):
    print("[NIGHTMODE] Loop started.")
    while True:
        try:
            now_bd = datetime.now(BD_TZ)
            h, m   = now_bd.hour, now_bd.minute
            docs   = await nightmode_col.find({"enabled": True}).to_list(length=None)

            for doc in docs:
                chat_id = doc["chat_id"]
                sh, sm  = doc.get("start_h", 23), doc.get("start_m", 0)
                eh, em  = doc.get("end_h",   6),  doc.get("end_m",  0)

                is_night_time        = _in_night_window(h, m, sh, sm, eh, em)
                currently_restricted = doc.get("is_restricted", False)

                if is_night_time and not currently_restricted:
                    ok, err = await _set_permissions(chat_id, _RESTRICTED_PERMS)
                    if ok:
                        await nightmode_col.update_one(
                            {"chat_id": chat_id}, {"$set": {"is_restricted": True}}
                        )
                        await bot_api("sendMessage", {
                            "chat_id":    chat_id,
                            "parse_mode": "HTML",
                            "text":       _night_activate_msg(sh, sm, eh, em),
                        })
                        print(f"[NIGHTMODE] 🔒 Locked chat={chat_id} at {h:02d}:{m:02d} BD")
                    else:
                        print(f"[NIGHTMODE] ❌ Lock failed chat={chat_id}: {err}")

                elif not is_night_time and currently_restricted:
                    ok, err = await _set_permissions(chat_id, _OPEN_PERMS)
                    if ok:
                        await nightmode_col.update_one(
                            {"chat_id": chat_id}, {"$set": {"is_restricted": False}}
                        )
                        await bot_api("sendMessage", {
                            "chat_id":    chat_id,
                            "parse_mode": "HTML",
                            "text":       _night_deactivate_msg(sh, sm, eh, em),
                        })
                        print(f"[NIGHTMODE] 🔓 Opened chat={chat_id} at {h:02d}:{m:02d} BD")
                    else:
                        print(f"[NIGHTMODE] ❌ Open failed chat={chat_id}: {err}")

        except Exception as e:
            print(f"[NIGHTMODE] Loop error: {e}")

        await asyncio.sleep(60)
