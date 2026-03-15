import os
import asyncio
from aiogram import Router, F, types, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config.settings import OWNER_ID, ADMIN_IDS, REPORTING_CHANNEL_ID
from database.db import get_db
from database.models import BotUser

router = Router()

# ====================================================
# 📝 REPORTING SYSTEM (Logs activities to Channel)
# ====================================================
async def log_report(bot: Bot, action: str, details: str):
    """
    Ye function bot ki har activity ko Reporting Channel me bhejega.
    Ise hum aage banne wale Ban/Warn functions me call karenge.
    """
    if REPORTING_CHANNEL_ID == 0:
        return # Agar channel set nahi hai to ignore karo
        
    log_message = (
        f"🚨 <b>Bot Activity Report</b>\n\n"
        f"⚡ <b>Action:</b> {action}\n"
        f"📄 <b>Details:</b> {details}\n"
        f"🕒 <b>Time:</b> {types.Message.date}" # Optional timestamp framing
    )
    try:
        await bot.send_message(chat_id=REPORTING_CHANNEL_ID, text=log_message, parse_mode="HTML")
    except Exception as e:
        print(f"Reporting Failed: {e}")

# ====================================================
# 🤖 BOT 2: START MENU (Role Based)
# ====================================================
@router.message(CommandStart(), F.chat.type == "private")
async def bot2_start_menu(message: types.Message):
    user_id = message.from_user.id
    
    # 1. OWNER VIEW (Daddy)
    if user_id == OWNER_ID:
        text = "<b>ਹਾਂ ਬੋਲੋ ਡੈਡੀ 🫡</b>\n\nMain group guard duty par hu. Kya command hai?"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👮 Manage Admins", callback_data="b2_manage_admins")],
            [InlineKeyboardButton(text="🛡️ Manage Groups/Channels", callback_data="b2_manage_groups")],
            [InlineKeyboardButton(text="📊 View Reports", url=f"https://t.me/c/{str(REPORTING_CHANNEL_ID).replace('-100', '')}/1")] if REPORTING_CHANNEL_ID else []
        ])
        await message.answer(text, reply_markup=keyboard)
        
        # Owner ko start karne par log bhej kar test karte hain
        await log_report(message.bot, "Owner Login", "Daddy ne Bot 2 start kiya.")

    # 2. ADMIN VIEW (Singh)
    elif user_id in ADMIN_IDS:
        text = "<b>ਓ ਕਿਵੇਂ ਆ ਸਿੰਘ 🤗</b>\n\nGroup management panel me aapka swagat hai."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛡️ Manage Groups/Channels", callback_data="b2_manage_groups")]
        ])
        await message.answer(text, reply_markup=keyboard)

    # 3. NORMAL USER VIEW
    else:
        text = "<b>My Father's Contact:</b>\nAgar aapko koi help chahiye to seedha unse baat karein."
        # Yahan apna username daal dein
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Contact Owner", url="https://t.me/your_username_here")] 
        ])
        await message.answer(text, reply_markup=keyboard)

# ====================================================
# 🎛️ BUTTON HANDLERS (Placeholders for next steps)
# ====================================================
@router.callback_query(F.data == "b2_manage_admins")
async def b2_admin_management(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Only Daddy can do this!", show_alert=True)
        return
    await callback.answer("Admin management menu (Coming soon...)")
    # Yahan hum aage admin add/remove ka logic likhenge

@router.callback_query(F.data == "b2_manage_groups")
async def b2_group_management(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS and callback.from_user.id != OWNER_ID:
        await callback.answer("Access Denied!", show_alert=True)
        return
    await callback.answer("Group management menu (Coming soon...)")
    # Yahan hum groups ko list karne aur unki settings manage karne ka code likhenge

