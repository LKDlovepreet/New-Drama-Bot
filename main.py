#start button 

import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties # <--- New Import
from aiogram.enums import ParseMode # <--- New Import
from config.settings import BOT_TOKENS
from database.db import init_db, get_db
from handlers import admin, user
from middlewares.auth import AdminCheckMiddleware
from handlers import admin, user, post_maker, channel_setup

logging.basicConfig(level=logging.INFO)

# --- FAKE SERVER LOGIC (Same as before) ---
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
# ------------------------------------------

async def main():
    init_db()
    dp = Dispatcher()
    
    @dp.update.outer_middleware
    async def db_session_middleware(handler, event, data):
        session_gen = get_db()
        data["db"] = next(session_gen)
        return await handler(event, data)

    admin.router.message.middleware(AdminCheckMiddleware())
    dp.include_router(user.router)
    dp.include_router(admin.router)

    if not BOT_TOKENS or BOT_TOKENS[0] == "":
        print("❌ Error: BOT_TOKENS not found")
        return

    # 👇 Yaha humne HTML Mode ON kiya hai
    bots = [
        Bot(
            token=token, 
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        ) for token in BOT_TOKENS
    ]
    
    print(f"🚀 Starting {len(bots)} bots...")

    await start_web_server()
    await dp.start_polling(*bots)

if __name__ == "__main__":
    asyncio.run(main())
