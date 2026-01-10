#download wala

from aiogram import Router, types
from aiogram.filters import CommandStart, CommandObject
from sqlalchemy import select
from sqlalchemy.orm import Session
from database.models import FileRecord
from config.settings import MESSAGES

router = Router()

@router.message(CommandStart())
async def handle_start(message: types.Message, command: CommandObject, db: Session):
    token = command.args

    if not token:
        await message.answer(MESSAGES["welcome"])
        return

    stmt = select(FileRecord).where(FileRecord.unique_token == token)
    file_record = db.execute(stmt).scalar_one_or_none()

    if not file_record:
        await message.answer(MESSAGES["invalid_link"])
        return

    await message.answer(MESSAGES["sending_file"])
    
    # File bhejna
    method = {
        "doc": message.answer_document,
        "video": message.answer_video,
        "photo": message.answer_photo
    }
    
    await method[file_record.file_type](
        file_record.file_id, 
        caption=file_record.file_name
    )

# 👇 Logic: Check if user exists, if not, add them
    existing_user = db.query(BotUser).filter(BotUser.user_id == user_id).first()
    if not existing_user:
        new_user = BotUser(user_id=user_id)
        db.add(new_user)
        db.commit()
        # Optional: Console me print karein
        print(f"➕ New User Joined: {user_id}")
