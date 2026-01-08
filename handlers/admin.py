#upload wala

from aiogram import Router, F, types
from sqlalchemy.orm import Session
from database.models import FileRecord
from utils.key_generator import generate_token
from config.settings import MESSAGES

router = Router()

@router.message(F.document | F.video | F.photo)
async def handle_file_upload(message: types.Message, db: Session):
    # File details nikalna
    if message.document:
        file_obj = message.document
        ftype = "doc"
        fname = file_obj.file_name
    elif message.video:
        file_obj = message.video
        ftype = "video"
        fname = f"video_{file_obj.file_unique_id}.mp4"
    elif message.photo:
        file_obj = message.photo[-1]
        ftype = "photo"
        fname = "photo.jpg"
    else:
        return

    # Database me save karna
    token = generate_token()
    new_file = FileRecord(
        unique_token=token,
        file_id=file_obj.file_id,
        file_name=fname,
        file_type=ftype,
        uploader_id=message.from_user.id
    )
    db.add(new_file)
    db.commit()

    # Link generate karna
    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={token}"
    
    await message.answer(MESSAGES["upload_success"].format(link=link))
