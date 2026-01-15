from datetime import datetime, timedelta
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.orm import Session
from database.models import FileRecord, BotUser
from database.db import get_db
from config.settings import MESSAGES, DEMO_VIDEO_URL, VERIFY_HOURS, OWNER_ID, LINK_BOT_ID
from utils.shortener import get_short_link

router = Router()
# 👇 FILTER: Ye code sirf Content Bot par chalega
router.message.filter(F.bot.id == LINK_BOT_ID)

@router.message(CommandStart())
async def handle_start(message: types.Message, command: CommandObject):
    db = get_db()
    try:
        user_id = message.from_user.id
        first_name = message.from_user.first_name
        args = command.args

        # 1. User Find/Create
        user = db.query(BotUser).filter(BotUser.user_id == user_id).first()
        if not user:
            user = BotUser(user_id=user_id)
            db.add(user)
            db.commit()

        # 2. IF NO LINK (Simple /start)
        if not args:
            if user_id == OWNER_ID:
                msg = (
                    f"👑 <b>Hello Sir!</b>\n"
                    f"Welcome back to your Bot Control Center.\n\n"
                    f"⚙️ <b>Select an option:</b>"
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="👤 Manage Admins", callback_data="admin_dashboard")],
                    [InlineKeyboardButton(text="💎 Premium Users", callback_data="premium_info")],
                    [InlineKeyboardButton(text="📢 Create Post / Broadcast", callback_data="broadcast_info")],
                    [InlineKeyboardButton(text="📊 Check Stats", callback_data="stats_info")]
                ])
                await message.answer(msg, reply_markup=keyboard)
            elif user.is_admin:
                await message.answer("👮‍♂️ <b>Hello Admin!</b>\nFile bhejein -> Link lein.")
            else:
                await message.answer(f"👋 <b>Hello {first_name} ji!</b>\nLink bhejein to file dunga.")
            return

        # --- IF LINK EXISTS ---
        if args.startswith("verify_"):
            original_token = args.split("verify_")[1]
            user.verification_expiry = datetime.utcnow() + timedelta(hours=VERIFY_HOURS)
            db.commit()
            bot_username = (await message.bot.get_me()).username
            retry_link = f"https://t.me/{bot_username}?start={original_token}"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📥 Download File Now", url=retry_link)]])
            await message.answer(MESSAGES["verified_success"], reply_markup=keyboard)
            return

        token = args
        stmt = select(FileRecord).where(FileRecord.unique_token == token)
        file_record = db.execute(stmt).scalar_one_or_none()

        if not file_record:
            await message.answer(MESSAGES["invalid_link"])
            return

        is_verified = False
        if user.is_premium: is_verified = True
        elif user.verification_expiry and user.verification_expiry > datetime.utcnow(): is_verified = True

        if not is_verified:
            bot_username = (await message.bot.get_me()).username
            verify_deep_link = f"https://t.me/{bot_username}?start=verify_{token}"
            wait_msg = await message.answer("🔄 Generating Verification Link...")
            short_url = await get_short_link(verify_deep_link)
            await wait_msg.delete()
            
            if not short_url:
                await message.answer("⚠️ Link Generation Failed. Try again later.")
                return

            buttons = []
            buttons.append([InlineKeyboardButton(text="🔓 Verify Access (Click Here)", url=short_url)])
            if DEMO_VIDEO_URL and DEMO_VIDEO_URL.startswith("http"):
                buttons.append([InlineKeyboardButton(text="📺 How to Verify (Video)", url=DEMO_VIDEO_URL)])
            
            await message.answer(MESSAGES["verify_first"], reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
            return

        await message.answer(MESSAGES["sending_file"])
        try:
            if file_record.file_type == "text":
                await message.answer(file_record.file_id, disable_web_page_preview=False)
            elif file_record.file_type == "photo":
                await message.answer_photo(file_record.file_id, caption=file_record.file_name)
            elif file_record.file_type == "video":
                await message.answer_video(file_record.file_id, caption=file_record.file_name)
            elif file_record.file_type == "doc":
                await message.answer_document(file_record.file_id, caption=file_record.file_name)
        except Exception as e:
            await message.answer(f"❌ Error sending file: {e}")

    finally:
        db.close()
