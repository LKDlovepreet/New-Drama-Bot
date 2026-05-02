import os
import time
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config.settings import OWNER_ID
from dashboard.otp_service import generate_otp, OTP_STORE
from database.db import SessionLocal, get_db
from database.models import BotUser, FileRecord

router = Router()

@router.message(CommandStart(), F.chat.type == "private")
async def manager_start_cmd(message: types.Message, command: CommandObject):
    args = command.args 
    
    # 🟢 1. Web Signup / Login ke baad User OTP lene aayega
    if args == 'getotp':
        user_id = message.from_user.id
        db = SessionLocal()
        user = db.query(BotUser).filter(BotUser.user_id == user_id).first()
        
        if user:
            # User ki Telegram se taaza jankari (Username / DP id) save karna
            user.web_username = message.from_user.username or str(user_id)
            
            photos = await message.bot.get_user_profile_photos(user_id)
            if photos.total_count > 0:
                tg_dp_file_id = photos.photos[0][-1].file_id
                # Aap DB mein telegram_dp column banakar ise bhi save kar sakte hain
                
            db.commit()
            db.close()
            
            otp = generate_otp()
            OTP_STORE[str(user_id)] = {'otp': otp, 'time': time.time()}
            
            # OTP bhejna
            await message.reply(f"📲 <b>Your Login OTP:</b> <code>{otp}</code>\n\nWelcome {message.from_user.first_name}! Your details have been synced.\n\nValid for 5 minutes. Enter this on the website to verify your account.", parse_mode="HTML")
        else:
            db.close()
            await message.reply("❌ Your account was not found in the system. Please fill the Sign Up form on the website first.")
        return
        
    # 👑 2. Manager Bot sirf Owner Dashboard ke liye kaam karega
    if message.from_user.id != OWNER_ID:
        await message.answer("⚠️ You are not authorized. This is a private system bot.")
        return

    text = (
        "👑 **Master Dashboard Bot**\n\n"
        "Welcome Back, Boss! 🫡\nHere is your live control panel."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Quick Stats", callback_data="mgr_quick_stats")],
        [InlineKeyboardButton(text="💻 Open Web Dashboard", url="https://your-app-url.com")], 
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "mgr_quick_stats")
async def show_quick_stats(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID: return
    
    db = get_db()
    try:
        total_users = db.query(BotUser).count()
        total_files = db.query(FileRecord).count()
        banned_users = db.query(BotUser).filter(BotUser.is_global_banned == True).count()
        
        stats_text = (
            "📊 **System Live Stats:**\n\n"
            f"👥 **Total Users:** {total_users}\n"
            f"📁 **Total Files Saved:** {total_files}\n"
            f"⛔ **Global Banned Users:** {banned_users}\n"
        )
        await callback.message.edit_text(stats_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back", callback_data="mgr_back")]]))
    finally:
        db.close()

@router.callback_query(F.data == "mgr_back")
async def mgr_back_home(callback: types.CallbackQuery):
    dummy_cmd = type('CommandObject', (), {'args': None})()
    await manager_start_cmd(callback.message, dummy_cmd)
    await callback.message.delete()
