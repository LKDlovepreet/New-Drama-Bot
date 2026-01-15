import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config.settings import LINK_BOT_TOKEN, GROUP_BOT_TOKEN
from database.db import init_db

# 👇 Import from NEW Folders
from bot1_core import user_service, admin_service
from bot2_core import group_manager

logging.basicConfig(level=logging.INFO)

async def health_check(request): return web.Response(text="Bots Alive!")

async def start_web_server():
    port = int(os.environ.get("PORT", 8000))
    app = web.Application(); app.add_routes([web.get('/', health_check)])
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port); await site.start()
    print(f"🌍 Server on {port}")

async def main():
    init_db()

    # --- SETUP BOT 1 (Link Bot) ---
    if not LINK_BOT_TOKEN: print("❌ Link Bot Token Missing"); return
    bot1 = Bot(token=LINK_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp1 = Dispatcher()
    dp1.include_router(user_service.router)
    dp1.include_router(admin_service.router)

    # --- SETUP BOT 2 (Group Bot) ---
    if not GROUP_BOT_TOKEN: print("❌ Group Bot Token Missing"); return
    bot2 = Bot(token=GROUP_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp2 = Dispatcher()
    dp2.include_router(group_manager.router)

    print("🚀 Starting Dual-Bot System...")
    await start_web_server()
    
    # Run Both in Parallel
    await asyncio.gather(
        dp1.start_polling(bot1),
        dp2.start_polling(bot2)
    )

if __name__ == "__main__":
    asyncio.run(main())
