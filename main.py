import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config.settings import BOT_TOKENS
from database.db import init_db
from handlers import admin, user, post_maker, channel_setup, owner, bot2_handlers, save_media
from middlewares.auth import AdminCheckMiddleware

logging.basicConfig(level=logging.INFO)

async def health_check(request):
    return web.Response(text="Bot is Alive!")

async def start_web_server():
    port = int(os.environ.get("PORT", 8000))
    app = web.Application()
    app.add_routes([web.get('/', health_check)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌍 Server running on port {port}")

async def main():
    init_db()
    dp = Dispatcher()
    admin.router.message.middleware(AdminCheckMiddleware())

    # 👇 REGISTER ROUTERS
    dp.include_router(channel_setup.router)
    dp.include_router(owner.router)
    dp.include_router(save_media.router)
    dp.include_router(post_maker.router)
    
    # Bot 2 Logic
    dp.include_router(bot2_handlers.router)
    
    # Bot 1 Logic
    dp.include_router(user.router)
    dp.include_router(admin.router)

    if not BOT_TOKENS:
        print("❌ Error: BOT_TOKENS missing")
        return

    bots = [
        Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML)) 
        for token in BOT_TOKENS
    ]

    print(f"🚀 Starting {len(bots)} bots...")
    await start_web_server()
    await dp.start_polling(*bots)

if __name__ == "__main__":
    asyncio.run(main())
