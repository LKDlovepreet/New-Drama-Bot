import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config.settings import LINK_BOT_TOKEN, GROUP_BOT_TOKEN
from database.db import init_db

# 👇 Secure Dashboard Import
from dashboard.server import start_dashboard_server

from bot1_core import user_service, admin_service
from bot2_core import group_manager

logging.basicConfig(level=logging.INFO)

async def main():
    init_db()

    # Bot 1 Setup
    if not LINK_BOT_TOKEN: print("❌ Link Bot Token Missing"); return
    bot1 = Bot(token=LINK_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp1 = Dispatcher()
    dp1.include_router(user_service.router)
    dp1.include_router(admin_service.router)

    # Bot 2 Setup
    if not GROUP_BOT_TOKEN: print("❌ Group Bot Token Missing"); return
    bot2 = Bot(token=GROUP_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp2 = Dispatcher()
    dp2.include_router(group_manager.router)

    print("🚀 Starting Dual-Bot System with 2FA Dashboard...")
    
    # Start Secure Dashboard
    await start_dashboard_server()
    
    # Run Bots
    await asyncio.gather(
        dp1.start_polling(bot1),
        dp2.start_polling(bot2)
    )

if __name__ == "__main__":
    asyncio.run(main())
