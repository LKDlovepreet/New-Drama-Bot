import os
import asyncio
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from sqlalchemy import select
from database.models import FileRecord, BotUser
from database.db import get_db
from config.settings import (
    MESSAGES, DEMO_VIDEO_URL, VERIFY_HOURS, OWNER_ID, ADMIN_IDS,
    AD_CHANNEL_URL, AD_GROUP_URL, OWNER_USERNAME
)
from utils.shortener import get_short_link

router = Router()

@router.message(CommandStart())
async def handle_start(message: types.Message, command: CommandObject):
    db = get_db()
    try:
        user_id = message.from_user.id
        first_name = message.from_user.first_name
        args = command.args

        # 1. User Database Entry (Create if not exists)
        user = db.query(BotUser).filter(BotUser.user_id == user_id).first()
        if not user:
            user = BotUser(user_id=user_id)
            db.add(user)
            db.commit()

        # ====================================================
        # SCENARIO 1: Simple Start (No Link / Menu Mode)
        # ====================================================
        if not args:
            # Photo Load Check
            photo_path = "statics/pics/img1.jpg"
            if not os.path.exists(photo_path):
                # Fallback agar photo na mile
                await message.answer("⚠️ System Error: Start Image missing.")
                return

            photo = FSInputFile(photo_path)
            
            # --- A. OWNER VIEW ---
            if user_id == OWNER_ID:
                caption = (
                    "<b>Hello Father 🗽</b>\n\n"
                    "⚙️ <b>Owner Controls:</b>\n"
                    "• /createpost - Broadcast Message\n"
                    "• /set_topic - Manage Storage Topics\n"
                    "• /bulk - Create Bulk Links\n"
                    "• /start - Refresh Menu\n\n"
                    "<i>Forward any file to me to save it.</i>"
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="👮 Manage Admins", callback_data="admin_dashboard")],
                    [InlineKeyboardButton(text="📢 Connected Chats", callback_data="list_chats")],
                    [InlineKeyboardButton(text="💎 Premium", callback_data="premium_alert")]
                ])
                await message.answer_photo(photo, caption=caption, reply_markup=keyboard)

            # --- B. ADMIN VIEW ---
            elif user_id in ADMIN_IDS:
                caption = (
                    "<b>Hello bro 🤌🏻</b>\n\n"
                    "🛠 <b>Admin Commands:</b>\n"
                    "• /createpost - Broadcast\n"
                    "• /bulk - Bulk Link Creation\n"
                    "• Forward file -> Get Link"
                )
                await message.answer_photo(photo, caption=caption)

            # --- C. NORMAL USER VIEW ---
            else:
                caption = (
                    f"<b>Hello {first_name}</b>\n\n"
                    "Agar aapko koi file chahiye to kripya us <b>Link</b> ka use karein jo aapko group ya channel se mila hai.\n\n"
                    "<i>Main direct search support nahi karta.</i>"
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📢 Join Our Channel", url=AD_CHANNEL_URL)],
                    [InlineKeyboardButton(text="💬 Our Community", url=AD_GROUP_URL)],
                    [InlineKeyboardButton(text="📢 Advertise Here", url=f"https://t.me/{OWNER_USERNAME}")]
                ])
                await message.answer_photo(photo, caption=caption, reply_markup=keyboard)
            
            return

        # ====================================================
        # SCENARIO 2: Deep Link Processing (File/Verify)
        # ====================================================
        
        # --- A. Handle Verification Link (verify_TOKEN) ---
        if args.startswith("verify_"):
            original_token = args.split("verify_")[1]
            
            # Update User Expiry
            user.verification_expiry = datetime.utcnow() + timedelta(hours=VERIFY_HOURS)
            db.commit()
            
            bot_username = (await message.bot.get_me()).username
            retry_link = f"https://t.me/{bot_username}?start={original_token}"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📥 Download File Now", url=retry_link)]])
            await message.answer(MESSAGES["verified_success"], reply_markup=keyboard)
            return

        # --- B. Handle File Link ---
        token = args
        stmt = select(FileRecord).where(FileRecord.unique_token == token)
        file_record = db.execute(stmt).scalar_one_or_none()

        if not file_record:
            await message.answer(MESSAGES["invalid_link"])
            return

        # --- C. Check Verification Status ---
        is_verified = False
        if user.is_premium: 
            is_verified = True
        elif user.verification_expiry and user.verification_expiry > datetime.utcnow(): 
            is_verified = True

        if not is_verified:
            # Generate Short Link
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

        # --- D. Send Content (Verified User) ---
        await message.answer(MESSAGES["sending_file"])
        
        try:
            # ➤ CASE 1: BATCH / BULK FILE
            if file_record.file_type == "batch":
                # Split format: "type|id:::type|id"
                all_files = file_record.file_id.split(":::")
                total_files = len(all_files)
                
                await message.answer(f"📦 <b>Bulk Pack Found!</b>\nSending {total_files} files...")
                
                for item in all_files:
                    try:
                        ftype, fid = item.split("|")
                        if ftype == "photo":
                            await message.answer_photo(fid)
                        elif ftype == "video":
                            await message.answer_video(fid)
                        elif ftype == "doc":
                            await message.answer_document(fid)
                        
                        # Anti-Flood Delay (Important for bulk)
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        print(f"Bulk send error: {e}")
                        continue
                
                await message.answer("✅ <b>All files sent!</b>")
                return

            # ➤ CASE 2: SINGLE FILE
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

    except Exception as main_e:
        print(f"User Service Error: {main_e}")
    finally:
        db.close()
