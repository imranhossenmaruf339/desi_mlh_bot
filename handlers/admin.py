import asyncio

from pyrogram import Client, filters
from pyrogram.types import Message

from config import HTML, ADMIN_ID, users_col, settings_col, app, PACKAGES, PACKAGE_ORDER
from helpers import log_event, bot_api, admin_filter


# ─────────────────────────────────────────────────────────────────────────────
#  Package price management — load overrides from MongoDB on startup
# ─────────────────────────────────────────────────────────────────────────────

async def load_package_overrides():
    """Load admin-set package prices from MongoDB and apply to PACKAGES dict."""
    try:
        doc = await settings_col.find_one({"key": "package_overrides"})
        if not doc:
            return
        overrides = doc.get("packages", {})
        for key, vals in overrides.items():
            if key in PACKAGES:
                PACKAGES[key].update(vals)
        print(f"[PACKAGES] Loaded {len(overrides)} price override(s) from DB.")
    except Exception as e:
        print(f"[PACKAGES] WARNING: Could not load overrides: {e}")


async def _resolve_user_private(client: Client, message: Message):
    args = message.command[1:]
    if not args:
        return None, None, None

    raw = args[0].lstrip("@")

    if raw.isdigit():
        doc = await users_col.find_one({"user_id": int(raw)})
    else:
        doc = await users_col.find_one({"username": raw})

    if not doc:
        return None, None, None

    return doc["user_id"], doc.get("first_name") or "", doc.get("username")


@app.on_message(filters.command("blockuser") & admin_filter & filters.private)
async def blockuser_cmd(client: Client, message: Message):
    args = message.command[1:]
    if not args:
        await message.reply_text(
            "Usage:\n"
            "/blockuser @username\n"
            "/blockuser 123456789\n\n"
            "Blocks a user from using the bot."
        )
        return

    target_id, fname, uname = await _resolve_user_private(client, message)
    if not target_id:
        await message.reply_text("❌ User not found in the database.")
        return

    doc = await users_col.find_one({"user_id": target_id})
    if not doc:
        await message.reply_text("❌ User not found.")
        return

    if doc.get("bot_banned"):
        mention = f"@{uname}" if uname else fname or str(target_id)
        await message.reply_text(
            "⚠️ ALREADY BLOCKED\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 User : {mention}\n"
            f"🆔 ID   : {target_id}\n\n"
            "This user is already blocked from the bot.\n"
            "Use /unblockuser to restore access.\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 DESI MLH SYSTEM"
        )
        return

    mention = f"@{uname}" if uname else fname or str(target_id)
    await users_col.update_one(
        {"user_id": target_id},
        {"$set": {"bot_banned": True}},
    )
    await message.reply_text(
        "🚫 USER BLOCKED\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 User : {mention}\n"
        f"🆔 ID   : {target_id}\n\n"
        "✅ This user can no longer use the bot.\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 DESI MLH SYSTEM"
    )
    asyncio.create_task(bot_api("sendMessage", {
        "chat_id": target_id,
        "text": (
            "🚫 YOUR ACCESS HAS BEEN RESTRICTED\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Your access to this bot has been\n"
            "suspended by the admin.\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 DESI MLH SYSTEM"
        ),
    }))
    print(f"[BLOCK] Blocked user={target_id}")
    await log_event(client, f"🚫 <b>User Blocked</b>\n👤 {mention} — 🆔 <code>{target_id}</code>")


@app.on_message(filters.command("unblockuser") & admin_filter & filters.private)
async def unblockuser_cmd(client: Client, message: Message):
    args = message.command[1:]
    if not args:
        await message.reply_text(
            "Usage:\n"
            "/unblockuser @username\n"
            "/unblockuser 123456789"
        )
        return

    raw = args[0].lstrip("@")
    doc = (
        await users_col.find_one({"user_id": int(raw)})
        if raw.isdigit()
        else await users_col.find_one({"username": raw})
    )
    if not doc:
        await message.reply_text("❌ User not found in the database.")
        return

    target_id = doc["user_id"]
    fname     = doc.get("first_name", "") or ""
    uname     = doc.get("username")
    mention   = f"@{uname}" if uname else fname or str(target_id)

    await users_col.update_one(
        {"user_id": target_id},
        {"$set": {"bot_banned": False, "warn_count": 0}},
    )
    await message.reply_text(
        "✅ USER UNBLOCKED\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 User : {mention}\n"
        f"🆔 ID   : {target_id}\n\n"
        "✅ Bot access fully restored.\n"
        "⚠️ Warning count also cleared.\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 DESI MLH SYSTEM"
    )
    asyncio.create_task(bot_api("sendMessage", {
        "chat_id": target_id,
        "text": (
            "✅ YOUR BOT ACCESS HAS BEEN RESTORED\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Your access to this bot has been\n"
            "restored by the admin. Welcome back!\n\n"
            "You can now use /video and /daily again.\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 DESI MLH SYSTEM"
        ),
    }))
    print(f"[BLOCK] Unblocked user={target_id}")
    await log_event(client, f"✅ <b>User Unblocked</b>\n👤 {mention} — 🆔 <code>{target_id}</code>")


# ─────────────────────────────────────────────────────────────────────────────
#  /packages — view all current package prices
# ─────────────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("packages") & admin_filter & filters.private)
async def packages_cmd(_, message: Message):
    lines = [
        "<b>💎 Current Package Prices</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>To change: /setprice &lt;key&gt; &lt;price_usd&gt; &lt;stars&gt; [days] [limit]</i>\n\n"
    ]
    for key in PACKAGE_ORDER:
        pkg  = PACKAGES[key]
        lim  = "∞" if pkg["video_limit"] >= 999 else str(pkg["video_limit"])
        lines.append(
            f"<b>{pkg['label']}</b>  <code>{key}</code>\n"
            f"  💵 Price : <b>{pkg['price']}</b>\n"
            f"  ⭐ Stars : <b>{pkg['stars']}</b>\n"
            f"  📅 Days  : <b>{pkg['days']}</b>\n"
            f"  🎬 Limit : <b>{lim}/day</b>\n"
        )
    lines.append(
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Example:</b>\n"
        "<code>/setprice basic 5 250 7 30</code>\n"
        "→ key=basic, $5 USDT, 250 Stars, 7 days, 30 vids/day\n\n"
        "<code>/setprice vip 25 1250</code>\n"
        "→ only price/stars updated, days & limit unchanged"
    )
    await message.reply_text("\n".join(lines), parse_mode=HTML)


# ─────────────────────────────────────────────────────────────────────────────
#  /setprice <key> <price_usd> <stars> [days] [limit]
# ─────────────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("setprice") & admin_filter & filters.private)
async def setprice_cmd(_, message: Message):
    args = message.command[1:]
    usage = (
        "⚠️ <b>Usage:</b>\n"
        "<code>/setprice &lt;key&gt; &lt;price_usd&gt; &lt;stars&gt; [days] [limit]</code>\n\n"
        "<b>Keys:</b> starter basic standard pro vip elite\n\n"
        "<b>Examples:</b>\n"
        "<code>/setprice basic 5 250 7 30</code>\n"
        "<code>/setprice vip 25 1250</code>  ← days & limit unchanged"
    )
    if len(args) < 3:
        await message.reply_text(usage, parse_mode=HTML)
        return

    pkg_key = args[0].lower()
    if pkg_key not in PACKAGES:
        await message.reply_text(
            f"❌ Unknown package key: <code>{pkg_key}</code>\n"
            f"Valid: starter, basic, standard, pro, vip, elite",
            parse_mode=HTML,
        )
        return

    try:
        price_usd = float(args[1])
        stars     = int(args[2])
        days      = int(args[3]) if len(args) > 3 else None
        limit     = int(args[4]) if len(args) > 4 else None
    except ValueError:
        await message.reply_text("❌ Invalid numbers. " + usage, parse_mode=HTML)
        return

    if price_usd <= 0 or stars <= 0:
        await message.reply_text("❌ Price and stars must be > 0.", parse_mode=HTML)
        return

    # Build price label (e.g. "$5 USDT" or "৳500")
    price_label = f"${price_usd:.0f} USDT" if price_usd == int(price_usd) else f"${price_usd} USDT"

    # Apply to in-memory dict
    PACKAGES[pkg_key]["price"]     = price_label
    PACKAGES[pkg_key]["price_usd"] = price_usd
    PACKAGES[pkg_key]["stars"]     = stars
    if days is not None:
        PACKAGES[pkg_key]["days"] = days
    if limit is not None:
        PACKAGES[pkg_key]["video_limit"] = limit
        lim_str = "∞" if limit >= 999 else f"{limit}/day"
    else:
        lim_str = "∞" if PACKAGES[pkg_key]["video_limit"] >= 999 else f"{PACKAGES[pkg_key]['video_limit']}/day"

    # Persist to MongoDB
    override_vals = {
        "price":     PACKAGES[pkg_key]["price"],
        "price_usd": price_usd,
        "stars":     stars,
    }
    if days is not None:
        override_vals["days"] = days
    if limit is not None:
        override_vals["video_limit"] = limit

    await settings_col.update_one(
        {"key": "package_overrides"},
        {"$set": {f"packages.{pkg_key}": override_vals}},
        upsert=True,
    )

    pkg = PACKAGES[pkg_key]
    await message.reply_text(
        f"✅ <b>Package Updated!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Package : <b>{pkg['label']}</b>\n"
        f"💵 Price   : <b>{price_label}</b>\n"
        f"⭐ Stars   : <b>{stars}</b>\n"
        f"📅 Days    : <b>{pkg['days']}</b>\n"
        f"🎬 Limit   : <b>{lim_str}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Changes are live immediately.\n"
        f"Use /packages to view all.",
        parse_mode=HTML,
    )
