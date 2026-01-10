from aiogram import Router, F, types
from sqlalchemy.orm import Session
from database.models import Channel
from config.settings import OWNER_ID, ADMIN_IDS

router = Router()

# Jab Bot ko Channel me add kiya jaye ya Admin banaya jaye
@router.my_chat_member(F.chat.type.in_({"channel", "supergroup"}))
async def on_channel_add(event: types.ChatMemberUpdated, db: Session):
    # Check karein ki bot ab Admin hai ya nahi
    if event.new_chat_member.status in ["administrator", "creator"]:
        chat_id = event.chat.id
        chat_name = event.chat.title
        
        # Check if already exists
        existing = db.query(Channel).filter(Channel.chat_id == chat_id).first()
        if not existing:
            new_channel = Channel(chat_id=chat_id, channel_name=chat_name, added_by=event.from_user.id)
            db.add(new_channel)
            db.commit()
            
            # Owner ko notify karein
            if event.from_user.id in ADMIN_IDS or event.from_user.id == OWNER_ID:
                await event.bot.send_message(
                    event.from_user.id, 
                    f"✅ <b>Channel Connected:</b> {chat_name}\nAb main yaha post kar sakta hu!"
                )
