from datetime import datetime, timedelta
from aiogram import Router, types
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.orm import Session
from database.models import FileRecord, BotUser
from database.db import SessionLocal
from config.settings import MESSAGES, DEMO_VIDEO_URL, VERIFY_HOURS
from utils.shortener import get_short_link

router = Router()

@router.message(CommandStart())
async def handle_start(message: types.Message, command: CommandObject, db: Session):
    user_id = message.from_user.id
    args = command.args
    
    # 1. User Find/Create
    user = db.query(BotUser).filter(BotUser.user_id == user_id).first()
    if not user:
        try:
            user = BotUser(user_id=user_id)
            db.add(user)
            db.commit()
            print(f"🆕 New User: {user_id}")
        except:
            db.rollback()

    if not args:
        await message.answer(MESSAGES["welcome"])
        return

    # --- CASE A: USER VERIFY KARKE AAYA HAI ---
    if args.startswith("verify_"):
        original_token = args.split("verify_")[1]
        
        user.verification_expiry = datetime.utcnow() + timedelta(hours=VERIFY_HOURS)
        db.commit()
        
        bot_username = (await message.bot.get_me()).username
        retry_link = f"https://t.me/{bot_username}?start={original_token}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Download File Now", url=retry_link)]
        ])
        
        await message.answer(MESSAGES["verified_success"], reply_markup=keyboard)
        return

    # --- CASE B: FILE REQUEST ---
    token = args
    stmt = select(FileRecord).where(FileRecord.unique_token == token)
    file_record = db.execute(stmt).scalar_one_or_none()

    if not file_record:
        await message.answer(MESSAGES["invalid_link"])
        return

    # Verification Check
    is_verified = False
    if user.is_premium:
        is_verified = True
    elif user.verification_expiry and user.verification_expiry > datetime.utcnow():
        is_verified = True

    # 4. SHOW AD (Verification Needed)
    if not is_verified:
        bot_username = (await message.bot.get_me()).username
        verify_deep_link = f"https://t.me/{bot_username}?start=verify_{token}"
        
        wait_msg = await message.answer("🔄 Generating Verification Link...")
        
        # 👇 Short Link Generate Check
        short_url = await get_short_link(verify_deep_link)
        
        await wait_msg.delete()
        
        # 👇 AGAR LINK FAIL HUA TO USER KO BATAO (Crash mat karo)
        if not short_url:
            await message.answer("⚠️ <b>Link Generation Failed.</b>\nShayad API Key galat hai ya Shortener down hai.\nAdmin se contact karein.")
            return

        # Buttons Preparation
        buttons = []
        # Verify Button (Valid URL hona zaroori hai)
        buttons.append([InlineKeyboardButton(text="🔓 Verify Access (Click Here)", url=short_url)])
        
        # Demo Video Button (Check karein ki URL valid hai)
        if DEMO_VIDEO_URL and DEMO_VIDEO_URL.startswith("http"):
            buttons.append([InlineKeyboardButton(text="📺 How to Verify (Video)", url=DEMO_VIDEO_URL)])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await message.answer(MESSAGES["verify_first"], reply_markup=keyboard)
        return

    # 5. SEND FILE (Verified)
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
