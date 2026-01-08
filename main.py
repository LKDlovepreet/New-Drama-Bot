#start button 

import asyncio
import logging
from aiogram import Bot, Dispatcher
from config.settings import BOT_TOKENS
from database.db import init_db, get_db
from handlers import admin, user
from middlewares.auth import AdminCheckMiddleware

logging.basicConfig(level=logging.INFO)

async def main():
    init_db() # Database start
    
    dp = Dispatcher()
    
    # Database Middleware
    @dp.update.outer_middleware
    async def db_session_middleware(handler, event, data):
        session_gen = get_db()
        data["db"] = next(session_gen)
        return await handler(event, data)

    # Admin Middleware register
    admin.router.message.middleware(AdminCheckMiddleware())

    # Routers register
    dp.include_router(user.router)
    dp.include_router(admin.router)

    # Multi-bot start
    if not BOT_TOKENS or BOT_TOKENS[0] == "":
        print("❌ Error: BOT_TOKENS not found in .env")
        return

    bots = [Bot(token=token) for token in BOT_TOKENS]
    print(f"🚀 Starting {len(bots)} bots...")
    await dp.start_polling(*bots)

if __name__ == "__main__":
    asyncio.run(main())
