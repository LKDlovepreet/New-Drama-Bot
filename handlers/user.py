from aiogram import Router, types
from aiogram.filters import CommandStart, CommandObject
from sqlalchemy import select
from sqlalchemy.orm import Session
from database.models import FileRecord, BotUser # 👈 BotUser import hona zaroori hai
from config.settings import MESSAGES

router = Router()

@router.message(CommandStart())
async def handle_start(message: types.Message, command: CommandObject, db: Session):
    user_id = message.from_user.id
    
    # ✅ FIX: User Save Logic (Sabse Pehle)
    # Check karein user pehle se hai ya nahi
    existing_user = db.query(BotUser).filter(BotUser.user_id == user_id).first()
    
    if not existing_user:
        try:
            new_user = BotUser(user_id=user_id)
            db.add(new_user)
            db.commit()
            print(f"🆕 NEW USER SAVED: {user_id}") # 👈 Ye Logs me dikhna chahiye
        except Exception as e:
            print(f"❌ Error saving user: {e}")
            db.rollback()
    else:
        # Agar user purana hai to bhi print karein (Debugging ke liye)
        print(f"ℹ️ User already exists: {user_id}")

    # --- Niche ka code same rahega (File Fetching Wala) ---
    
    token = command.args
    # Agar sirf /start kiya hai (bina link ke)
    if not token:
        await message.answer(MESSAGES["welcome"])
        return

    # Agar Link ke saath aaya hai
    stmt = select(FileRecord).where(FileRecord.unique_token == token)
    file_record = db.execute(stmt).scalar_one_or_none()

    if not file_record:
        await message.answer(MESSAGES["invalid_link"])
        return

    await message.answer(MESSAGES["sending_file"])
    
    method = {
        "doc": message.answer_document,
        "video": message.answer_video,
        "photo": message.answer_photo
    }
    
    try:
        await method[file_record.file_type](
            file_record.file_id, 
            caption=file_record.file_name
        )
    except Exception as e:
        await message.answer(f"❌ Error sending file: {e}")
