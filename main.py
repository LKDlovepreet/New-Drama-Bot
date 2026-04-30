import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# 👇 Yahan AUTH_BOT_TOKEN ko bhi import karna zaroori hai
from config.settings import LINK_BOT_TOKEN, GROUP_BOT_TOKEN, AUTH_BOT_TOKEN
from database.db import init_db

# Secure Dashboard Import
from dashboard.server import start_dashboard_server

# Bot 1 Handlers (Link/Admin)
from bot1_core import user_service, admin_service

# Bot 2 Handlers (Group Manager)
from bot2_core import group_manager

# 👇 NAYA: Manager Bot Handlers
from manager_bot_core import manager_service

# Logging Setup
logging.basicConfig(level=logging.INFO)

async def main():
    # 1. Database Initialize karein
    print("🗄️ Database connect ho raha hai...")
    init_db()

    # 2. Bot 1 Setup (Link Bot)
    if not LINK_BOT_TOKEN:
        print("❌ Error: LINK_BOT_TOKEN missing hai! .env check karein.")
        return
    
    bot1 = Bot(
        token=LINK_BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp1 = Dispatcher()
    dp1.include_router(user_service.router)
    dp1.include_router(admin_service.router)
    print("✅ Bot 1 (Link Manager) Ready hai.")

    # 3. Bot 2 Setup (Group Bot)
    if not GROUP_BOT_TOKEN:
        print("❌ Error: GROUP_BOT_TOKEN missing hai! .env check karein.")
        return
    
    bot2 = Bot(
        token=GROUP_BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp2 = Dispatcher()
    dp2.include_router(group_manager.router)
    print("✅ Bot 2 (Group Guard) Ready hai.")

    # 👇 4. NAYA: Bot 3 Setup (Manager / OTP Bot)
    if not AUTH_BOT_TOKEN:
        print("❌ Error: AUTH_BOT_TOKEN missing hai! .env check karein.")
        return
    
    bot3 = Bot(
        token=AUTH_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp3 = Dispatcher()
    dp3.include_router(manager_service.router)
    print("✅ Bot 3 (Manager & OTP) Ready hai.")

    # 5. Start Secure Web Dashboard
    print("🌍 Secure Dashboard start ho raha hai...")
    await start_dashboard_server()

    # 6. Start Polling (Teeno Bots ek saath chalenge)
    print("🚀 System Online! Bots Polling shuru kar rahe hain...")
    
    # asyncio.gather ab teeno loops ko parallel chalayega
    await asyncio.gather(
        dp1.start_polling(bot1),
        dp2.start_polling(bot2),
        dp3.start_polling(bot3)  # 👇 Manager bot ki polling
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Bot Stop ho gaya.")
