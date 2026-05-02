import os
import time
from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config.settings import OWNER_ID
from dashboard.otp_service import generate_otp, OTP_STORE
from database.db import SessionLocal, get_db
# Yahan dono tables import ki gayi hain
from database.models import BotUser, FileRecord, WebsiteUser

router = Router()

@router.message(CommandStart(), F.chat.type == "private")
async def manager_start_cmd(message: types.Message, command: CommandObject):
    args = command.args 
    
    if args == 'getotp':
        user_id = message.from_user.id
        db = SessionLocal()
        
        # Ab ye specifically WebsiteUser table me check karega
        user = db.query(WebsiteUser).filter(WebsiteUser.telegram_id == user_id).first()
        
        if user:
            db.close()
            otp = generate_otp()
            OTP_STORE[str(user_id)] = {'otp': otp, 'time': time.time()}
            await message.reply(f"📲 <b>Your Login OTP:</b> <code>{otp}</code>\n\nWelcome {user.full_name}!\n\nValid for 5 minutes. Enter this on the website to verify your account.", parse_mode="HTML")
        else:
            db.close()
            await message.reply("❌ Your account was not found in the Customers Database. Please Sign Up on the website first.")
        return
        
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
            f"👥 **Total Bot Users:** {total_users}\n"
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
