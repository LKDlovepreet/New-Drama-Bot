import asyncio
import logging
import os
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config.settings import BOT_TOKENS
from database.db import init_db, get_db

from handlers import (
    admin,
    user,
    post_maker,
    channel_setup,
    owner,
    group_manager
)

from middlewares.auth import AdminCheckMiddleware

logging.basicConfig(level=logging.INFO)

# ------------------ FAKE WEB SERVER ------------------
async def health_check(request):
    return web.Response(text="Bot is Alive!")

async def start_web_server():
    port = int(os.environ.get("PORT", 8000))
    app = web.Application()
    app.add_routes([web.get("/", health_check)])

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"🌍 Fake Web Server started on port {port}")
# ----------------------------------------------------


async def main():
    # ✅ Initialize database
    init_db()

    dp = Dispatcher()

    # ✅ Database session middleware
    @dp.update.outer_middleware
    async def db_session_middleware(handler, event, data):
        data["db"] = get_db()
        return await handler(event, data)

    # ✅ Admin check middleware (sirf admin router ke liye)
    admin.router.message.middleware(AdminCheckMiddleware())

    # ✅ Router order (IMPORTANT)
    dp.include_router(channel_setup.router)
    dp.include_router(owner.router)
    dp.include_router(post_maker.router)
    dp.include_router(group_manager.router)
    dp.include_router(user.router)
    dp.include_router(admin.router)

    # ✅ Token check
    if not BOT_TOKENS or BOT_TOKENS[0] == "":
        logging.error("❌ BOT_TOKENS not found in environment")
        return

    # ✅ Multiple bots support
    bots = [
        Bot(
            token=token.strip(),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        for token in BOT_TOKENS
    ]

    print(f"🚀 Starting {len(bots)} bots...")

    # ✅ Start fake web server (Railway / Koyeb keep-alive)
    await start_web_server()

    # ✅ Start polling all bots
    await dp.start_polling(*bots)


if __name__ == "__main__":
    asyncio.run(main())