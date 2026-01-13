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
    
    # 1. User ko DB me Find/Create karein
    user = db.query(BotUser).filter(BotUser.user_id == user_id).first()
    if not user:
        user = BotUser(user_id=user_id)
        db.add(user)
        db.commit()

    # 2. Agar koi Argument nahi hai (Sirf /start)
    if not args:
        await message.answer(MESSAGES["welcome"])
        return

    # --- CASE A: USER VERIFY KARKE WAPIS AAYA HAI ---
    if args.startswith("verify_"):
        # Logic: Link hoga t.me/bot?start=verify_ORIGINALTOKEN
        original_token = args.split("verify_")[1]
        
        # User ka time update karein
        user.verification_expiry = datetime.utcnow() + timedelta(hours=VERIFY_HOURS)
        db.commit()
        
        # Success Message aur "Try Again" button (Jo purani file par le jayega)
        bot_username = (await message.bot.get_me()).username
        retry_link = f"https://t.me/{bot_username}?start={original_token}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Download File Now", url=retry_link)]
        ])
        
        await message.answer(MESSAGES["verified_success"], reply_markup=keyboard)
        return

    # --- CASE B: USER FILE MAANG RAHA HAI ---
    
    # Pehle file check karein ki exist karti hai ya nahi
    token = args
    stmt = select(FileRecord).where(FileRecord.unique_token == token)
    file_record = db.execute(stmt).scalar_one_or_none()

    if not file_record:
        await message.answer(MESSAGES["invalid_link"])
        return

    # 3. VERIFICATION CHECK
    is_verified = False
    
    # Premium user hamesha verified hai
    if user.is_premium:
        is_verified = True
    # Normal user ka time check karein
    elif user.verification_expiry and user.verification_expiry > datetime.utcnow():
        is_verified = True

    # 4. AGAR VERIFIED NAHI HAI -> AD DIKHAO
    if not is_verified:
        bot_username = (await message.bot.get_me()).username
        # Hum user ko bhejenge: t.me/Bot?start=verify_FILETOKEN
        # Taaki verify hone ke baad humein pata chale use konsi file chahiye thi
        verify_deep_link = f"https://t.me/{bot_username}?start=verify_{token}"
        
        # Is link ko AdrinoLinks se short karein
        wait_msg = await message.answer("🔄 Generating Verification Link...")
        short_url = await get_short_link(verify_deep_link)
        await wait_msg.delete()
        
        if not short_url:
            await message.answer("❌ Error generating link. Please try again later.")
            return

        # Buttons create karein
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔓 Verify Access (Click Here)", url=short_url)],
            [InlineKeyboardButton(text="📺 How to Verify (Video)", url=DEMO_VIDEO_URL)]
        ])
        
        await message.answer(MESSAGES["verify_first"], reply_markup=keyboard)
        return

    # 5. AGAR VERIFIED HAI -> FILE BHEJO
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
