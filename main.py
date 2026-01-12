import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config.settings import BOT_TOKENS
from database.db import init_db, get_db
# 👇 Saare handlers import hone chahiye
from handlers import admin, user, post_maker, channel_setup 
from middlewares.auth import AdminCheckMiddleware

logging.basicConfig(level=logging.INFO)

# --- FAKE SERVER LOGIC ---
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
    print(f"🌍 Fake Web Server started on port {port}")
# -------------------------

async def main():
    # 1. Database Start
    init_db()
    
    # 2. Dispatcher Setup
    dp = Dispatcher()

    # 3. Database Middleware
    @dp.update.outer_middleware
    async def db_session_middleware(handler, event, data):
        session_gen = get_db()
        data["db"] = next(session_gen)
        return await handler(event, data)

    # 4. Admin Middleware (Sirf Admin Router ke liye)
    admin.router.message.middleware(AdminCheckMiddleware())

    # 5. REGISTER ROUTERS (Ye sequence important hai)
    # 👇 Ye dono missing the, isliye command nahi chal raha tha
    dp.include_router(channel_setup.router) 
    dp.include_router(post_maker.router)
    
    # 👇 Ye pehle se the
    dp.include_router(user.router)
    dp.include_router(admin.router)

    # 6. Check Tokens
    if not BOT_TOKENS or BOT_TOKENS[0] == "":
        print("❌ Error: BOT_TOKENS not found")
        return

    # 7. Bot Instances with HTML Mode
    bots = [
        Bot(
            token=token, 
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        ) for token in BOT_TOKENS
    ]

    print(f"🚀 Starting {len(bots)} bots...")

    # 8. Start Everything
    await start_web_server()
    await dp.start_polling(*bots)

if __name__ == "__main__":
    asyncio.run(main())
