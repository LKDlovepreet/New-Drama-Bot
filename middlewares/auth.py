#admin di aakh

from aiogram import BaseMiddleware
from aiogram.types import Message
from config.settings import OWNER_ID, ADMIN_IDS, MESSAGES

class AdminCheckMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        user_id = event.from_user.id
        
        # /start sabke liye allowed hai
        if event.text and event.text.startswith("/start"):
            return await handler(event, data)
            
        # Uploading sirf Admin/Owner ke liye
        if user_id == OWNER_ID or user_id in ADMIN_IDS:
            return await handler(event, data)
        
        await event.answer(MESSAGES["not_authorized"])
        return
