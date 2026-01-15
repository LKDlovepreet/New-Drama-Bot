import uuid
from aiogram import Router, F, types
from database.db import get_db
from database.models import FileRecord
from config.settings import ADMIN_IDS, OWNER_ID, LINK_BOT_ID

router = Router()
# 👇 FILTER: Only Link Bot
router.message.filter(F.bot.id == LINK_BOT_ID)

def generate_token():
    return str(uuid.uuid4())[:8]

# --- SAVE TEXT ---
@router.message(F.text & F.chat.type == "private")
async def save_text(message: types.Message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS and user_id != OWNER_ID: return

    content = message.text
    file_name = content.split("\n")[0][:50]
    
    session = get_db()
    try:
        token = generate_token()
        new_file = FileRecord(
            unique_token=token, file_id=content, file_name=file_name,
            file_type="text", uploader_id=user_id
        )
        session.add(new_file)
        session.commit()
        await message.reply(f"✅ <b>Text Post Saved!</b>\n📂 Name: {file_name}\n🔗 Token: <code>{token}</code>")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
    finally:
        session.close()

# --- SAVE MEDIA ---
@router.message((F.photo | F.video | F.document) & F.chat.type == "private")
async def save_media(message: types.Message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS and user_id != OWNER_ID: return

    file_id = None
    file_type = ""
    file_name = message.caption or "Unknown File"

    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.document:
        file_id = message.document.file_id
        file_type = "doc"
        file_name = message.document.file_name

    session = get_db()
    try:
        token = generate_token()
        new_file = FileRecord(
            unique_token=token, file_id=file_id, file_name=file_name,
            file_type=file_type, uploader_id=user_id
        )
        session.add(new_file)
        session.commit()
        await message.reply(f"✅ <b>File Saved!</b>\n🔗 Token: <code>{token}</code>")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
    finally:
        session.close()
