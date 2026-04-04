import asyncio

from pyrogram import Client, filters, StopPropagation
from pyrogram.types import Message

from config import API_ID, API_HASH, BOT_TOKEN, app, clones_col
from helpers import _bot_token_ctx, _clone_config_ctx

_active_clones:  dict[str, Client] = {}
_clone_configs:  dict[str, dict]   = {}   # token → full DB doc (in-memory cache)

# ── Main bot presence cache for group priority ─────────────────────────────
# chat_id → True (main bot present) | False (not present)
# Cached per session; invalidated when main bot joins/leaves a group.
_main_bot_presence: dict[int, bool] = {}


def invalidate_presence_cache(chat_id: int | None = None):
    """Clear the presence cache for a specific group (or all groups)."""
    if chat_id is None:
        _main_bot_presence.clear()
    else:
        _main_bot_presence.pop(chat_id, None)


async def _is_main_bot_in_chat(clone_client: Client, chat_id: int) -> bool:
    """True if the main bot is an active member of chat_id.
    Result is cached; use invalidate_presence_cache() to refresh.
    """
    if chat_id in _main_bot_presence:
        return _main_bot_presence[chat_id]

    import config as _cfg
    main_id = getattr(_cfg, "MAIN_BOT_ID", 0)
    if not main_id:
        return False           # ID not cached yet — don't block

    try:
        from pyrogram import enums as _enums
        member = await clone_client.get_chat_member(chat_id, main_id)
        present = member.status not in (
            _enums.ChatMemberStatus.LEFT,
            _enums.ChatMemberStatus.BANNED,
        )
    except Exception:
        present = False        # Can't check → assume not present (safe fallback)

    _main_bot_presence[chat_id] = present
    return present


def refresh_clone_config(token: str, doc: dict):
    """Update in-memory cache with new DB doc."""
    _clone_configs[token] = doc


async def reload_clone_config(token: str):
    """Re-read config from DB, update in-memory cache AND client attribute."""
    doc = await clones_col.find_one({"token": token})
    if doc:
        _clone_configs[token] = doc
        # Also update the client object attribute so handlers see fresh config
        clone = _active_clones.get(token)
        if clone:
            clone._clone_config = doc
    return _clone_configs.get(token)


def _make_token_injector(token: str):
    """Returns a handler function that sets both ContextVars for this clone."""
    async def _inject(client: Client, message: Message):
        _bot_token_ctx.set(token)
        _clone_config_ctx.set(_clone_configs.get(token))
    return _inject


async def _main_bot_priority_guard(client: Client, message: Message):
    """If the main bot is present in this group, the clone bot stays silent.
    Registered at group=-98 (runs right after the injector at group=-99).
    Only applies to group/supergroup chats — private chats are unaffected.
    """
    chat = message.chat
    if chat is None:
        return
    chat_type = getattr(chat, "type", None)
    if chat_type is None:
        return
    type_value = chat_type.value if hasattr(chat_type, "value") else str(chat_type)
    if type_value not in ("group", "supergroup"):
        return
    if await _is_main_bot_in_chat(client, chat.id):
        raise StopPropagation


async def _build_clone_client(token: str, session_name: str, doc: dict = None) -> Client:
    clone = Client(
        session_name,
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=token,
    )
    # ── Store config & token directly on the client object (most reliable) ─
    clone._clone_token  = token
    clone._bot_token    = token
    clone._clone_config = doc or _clone_configs.get(token)

    from pyrogram.handlers import MessageHandler

    # ── group=-99: Inject token + config ContextVars ───────────────────────
    injector = _make_token_injector(token)
    clone.add_handler(MessageHandler(injector), group=-99)

    # ── group=-98: Main bot priority guard ────────────────────────────────
    # If main bot is in a group, clone bot does nothing there.
    clone.add_handler(MessageHandler(_main_bot_priority_guard), group=-98)

    # ── Copy all handlers from main app ───────────────────────────────────
    for group_id in sorted(app.dispatcher.groups.keys()):
        for handler in app.dispatcher.groups[group_id]:
            clone.add_handler(handler, group=group_id)

    return clone


async def start_clone(token: str, name: str, doc: dict = None) -> bool:
    if token in _active_clones:
        return False
    try:
        # Cache config before starting
        if doc:
            _clone_configs[token] = doc
        else:
            await reload_clone_config(token)

        session_name = f"clone_{abs(hash(token)) % 10**8}"
        clone = await _build_clone_client(token, session_name, doc=_clone_configs.get(token))
        await clone.start()
        _active_clones[token] = clone
        print(f"[CLONE] ✅ Started: {name}")
        return True
    except Exception as e:
        print(f"[CLONE] ❌ Failed to start {name}: {e}")
        return False


async def stop_clone(token: str) -> bool:
    clone = _active_clones.pop(token, None)
    _clone_configs.pop(token, None)
    if clone:
        try:
            await clone.stop()
        except Exception:
            pass
        print(f"[CLONE] 🛑 Stopped: {token[:15]}...")
        return True
    return False


# ── Cache invalidation when main bot joins/leaves a group ─────────────────
# This handler runs on the main bot (app), not clone clients.

@app.on_chat_member_updated()
async def _main_bot_group_membership_changed(client: Client, update):
    """When the main bot's own membership in a group changes, clear the
    presence cache for that group so clone bots re-check on next message.
    """
    import config as _cfg
    main_id = getattr(_cfg, "MAIN_BOT_ID", 0)
    if not main_id:
        return
    new = update.new_chat_member
    if new and new.user and new.user.id == main_id:
        chat_id = update.chat.id if update.chat else None
        if chat_id:
            invalidate_presence_cache(chat_id)
            from pyrogram import enums as _enums
            status = new.status
            state  = "joined" if status not in (
                _enums.ChatMemberStatus.LEFT, _enums.ChatMemberStatus.BANNED
            ) else "left/banned"
            print(f"[CLONE_GUARD] Main bot {state} group {chat_id} — cache cleared")


async def start_all_clones():
    """Called at startup — loads all active clones from MongoDB."""
    docs = await clones_col.find({"active": True}).to_list(length=100)
    if not docs:
        print("[CLONE] No active clones.")
        return
    print(f"[CLONE] Starting {len(docs)} clone(s)...")
    for doc in docs:
        token = doc["token"]
        name  = doc.get("name", token[:15])
        await start_clone(token, name, doc=doc)


def get_active_clones() -> dict:
    return {token: client for token, client in _active_clones.items()}
