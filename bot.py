import asyncio

from pyrogram import idle as pyrogram_idle

from config import app, VIDEO_CHANNEL
from helpers import get_log_channel
import handlers  # noqa: F401 — registers all handlers via @app decorators
from tasks import schedule_loop, video_del_loop
from handlers.nightmode import nightmode_loop
from handlers.stars_payment import stars_payment_loop
from clone_manager import start_all_clones


async def main():
    print("Bot is starting...")
    await app.start()

    # Cache main bot's own user ID (needed for clone priority guard)
    import config as _cfg
    try:
        _me = await app.get_me()
        _cfg.MAIN_BOT_ID = _me.id
        print(f"[STARTUP] Main bot ID cached: {_cfg.MAIN_BOT_ID}")
    except Exception as e:
        print(f"[STARTUP] WARNING: Could not get main bot ID: {e}")

    # Cache important peer IDs so "Peer id invalid" never happens
    try:
        await app.get_chat(VIDEO_CHANNEL)
        print(f"[STARTUP] Video channel cached OK ({VIDEO_CHANNEL})")
    except Exception as e:
        print(f"[STARTUP] WARNING: Cannot access video channel {VIDEO_CHANNEL}: {e}")

    try:
        log_cid = await get_log_channel()
        if log_cid:
            await app.get_chat(log_cid)
            print(f"[STARTUP] Log channel cached OK ({log_cid})")
    except Exception as e:
        print(f"[STARTUP] WARNING: Cannot cache log channel: {e}")

    loop = asyncio.get_event_loop()
    loop.create_task(schedule_loop(app))
    loop.create_task(nightmode_loop(app))
    loop.create_task(stars_payment_loop())
    loop.create_task(video_del_loop())
    print("[TASKS] Background loops started (schedule + nightmode + stars_payment + video_del).")

    await start_all_clones()
    print("[CLONE] Clone startup complete.")

    await pyrogram_idle()
    await app.stop()


app.run(main())
