import os
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dashboard.otp_service import generate_otp, OTP_STORE
from database.db import SessionLocal
from database.models import BotUser
import time

from config.settings import OWNER_ID
from database.db import get_db
from database.models import BotUser, FileRecord

router = Router()

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    args = message.get_args() # 'start=' ke aage ka text nikalta hai
    
    # Agar user website se OTP lene aaya hai
    if args == 'getotp':
        user_id = message.from_user.id
        db = SessionLocal()
        user = db.query(BotUser).filter(BotUser.user_id == user_id).first()
        db.close()
        
        if user:
            otp = generate_otp()
            OTP_STORE[str(user_id)] = {'otp': otp, 'time': time.time()}
            await message.reply(f"📲 <b>Your Login OTP:</b> <code>{otp}</code>\n\nValid for 5 minutes. Enter this on the website to verify your account.", parse_mode="HTML")
        else:
            await message.reply("❌ Your account was not found. Please fill the Sign Up form on the website first.")
        return
        
    # Yahan aapke purane /start command ka code aayega...
    await message.reply("Welcome to RAMGARHIA Services Bot!")
# ====================================================
# 1. OTP SYSTEM (Purana kaam jo ye bot karta tha)
# ====================================================
# (Yahan aapka purana OTP verification wala logic aayega)
# Example placeholder:
@router.message(Command("getotp"))
async def send_otp_logic(message: types.Message):
    await message.answer("🔐 Aapka OTP: 123456 (Dashboard login ke liye)")

# ====================================================
# 2. MANAGER SYSTEM (Naya Dashboard Features)
# ====================================================
@router.message(CommandStart(), F.chat.type == "private")
async def manager_start(message: types.Message):
    # Manager Bot sirf aapko (Owner) ko control dega
    if message.from_user.id != OWNER_ID:
        await message.answer("⚠️ Yeh ek private Manager Bot hai. Access Denied.")
        return

    text = (
        "👑 **Master Dashboard Bot**\n\n"
        "Welcome Back, Boss! 🫡\nYahan se aap apne poore system ka live data dekh sakte hain."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Quick Stats", callback_data="mgr_quick_stats")],
        [InlineKeyboardButton(text="💻 Open Web Dashboard", url="https://aapka-web-url.com")], # Baad me set karenge
        [InlineKeyboardButton(text="🔑 Generate Login OTP", callback_data="mgr_gen_otp")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "mgr_quick_stats")
async def show_quick_stats(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID: return
    
    db = get_db()
    try:
        # Live data fetch kar rahe hain
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
    # Wapas start menu dikhane ke liye
    await manager_start(callback.message)
    await callback.message.delete()
