import os
import time
from datetime import datetime, timedelta
from aiogram import Router, F, types, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions

from config.settings import OWNER_ID, ADMIN_IDS
from database.db import get_db
from database.models import BotUser, AutoReply, GroupSettings

# Reporting Channel Env Se
REPORTING_CHANNEL_ID = int(os.getenv("REPORTING_CHANNEL_ID", 0))

router = Router()

# Anti-Flood ke liye memory cache
flood_cache = {}

# ====================================================
# 📝 REPORTING SYSTEM
# ====================================================
async def log_report(bot: Bot, action: str, details: str):
    if REPORTING_CHANNEL_ID == 0: return
    log_msg = f"🚨 <b>Bot Activity Report</b>\n\n⚡ <b>Action:</b> {action}\n📄 <b>Details:</b> {details}\n🕒 <b>Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    try: 
        await bot.send_message(chat_id=REPORTING_CHANNEL_ID, text=log_msg, parse_mode="HTML")
    except: 
        pass

# ====================================================
# ⚠️ WARNING & BAN SYSTEM (Strike Logic)
# ====================================================
async def apply_warning(user_id: int, user_name: str, chat_id: int, bot: Bot, reason: str):
    db = get_db()
    try:
        user = db.query(BotUser).filter(BotUser.user_id == user_id).first()
        if not user:
            user = BotUser(user_id=user_id)
            db.add(user)
        
        user.warning_count += 1
        db.commit()
        
        warnings = user.warning_count
        
        # 🟢 STRIKE 1 & 2: Normal Warning
        if warnings < 3:
            await bot.send_message(chat_id, f"⚠️ <b>Warning {warnings}/3 for {user_name}</b>\nReason: {reason}")
            await log_report(bot, "Warning Given", f"User: {user_id}\nWarns: {warnings}\nReason: {reason}")
            
        # 🟡 STRIKE 3: Temp Mute (24 Hours)
        elif warnings == 3:
            until = datetime.now() + timedelta(hours=24)
            user.restricted_until = until
            db.commit()
            
            try:
                await bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=False), until_date=until)
                await bot.send_message(chat_id, f"🔇 <b>{user_name} has been Muted for 24 Hours!</b> (3 Warnings reached)")
                await log_report(bot, "Temp Mute (24h)", f"User: {user_id}\nReason: Reached 3 warnings.")
            except Exception as e:
                print(f"Mute Error: {e}")

        # 🔴 STRIKE 4: GLOBAL BAN
        elif warnings >= 4:
            user.is_global_banned = True
            db.commit()
            try:
                await bot.ban_chat_member(chat_id, user_id)
                await bot.send_message(chat_id, f"⛔ <b>{user_name} has been GLOBALLY BANNED.</b> (4 Strikes)")
                await log_report(bot, "GLOBAL BAN", f"User: {user_id} has been permanently banned from all bots.")
            except: 
                pass

    finally: 
        db.close()


# ====================================================
# 🤖 1. START MENU (Role Based)
# ====================================================
@router.message(CommandStart(), F.chat.type == "private")
async def bot2_start_menu(message: types.Message):
    db = get_db()
    user = db.query(BotUser).filter(BotUser.user_id == message.from_user.id).first()
    db.close()
    
    # Global Ban Check
    if user and user.is_global_banned:
        await log_report(message.bot, "Banned User Tried Start", f"User ID: {message.from_user.id}")
        return

    uid = message.from_user.id
    if uid == OWNER_ID:
        text = "<b>ਹਾਂ ਬੋਲੋ ਡੈਡੀ 🫡</b>\n\nGroup Guard is Active."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👮 Manage Admins", callback_data="b2_manage_admins")],
            [InlineKeyboardButton(text="📊 View Reports", url=f"https://t.me/c/{str(REPORTING_CHANNEL_ID).replace('-100', '')}/1")] if REPORTING_CHANNEL_ID else []
        ])
        await message.answer(text, reply_markup=kb)
        await log_report(message.bot, "Owner Start", "Daddy ne Guard Bot start kiya.")
    elif uid in ADMIN_IDS:
        await message.answer("<b>ਓ ਕਿਵੇਂ ਆ ਸਿੰਘ 🤗</b>\n\nGroup Guard Active.")
    else:
        text = "<b>My Father's Contact:</b>\nContact the owner for help."
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👤 Contact Owner", url="https://t.me/your_username_here")]])
        await message.answer(text, reply_markup=kb)


# ====================================================
# 🔄 2. AUTO-REPLY MANAGER
# ====================================================
@router.message(Command("addreply"))
async def add_reply(message: types.Message):
    if message.from_user.id not in ADMIN_IDS and message.from_user.id != OWNER_ID: return
    try:
        text = message.text.split(" ", 1)[1]
        keyword, reply = text.split("|", 1)
        keyword = keyword.strip().lower()
        reply = reply.strip()
        
        db = get_db()
        exist = db.query(AutoReply).filter(AutoReply.keyword == keyword).first()
        if exist: 
            exist.reply_text = reply
        else: 
            db.add(AutoReply(keyword=keyword, reply_text=reply))
        db.commit()
        db.close()
        
        await message.answer(f"✅ <b>Reply Added!</b>\nKeyword: `{keyword}`")
    except:
        await message.answer("❌ Format Error!\nUse: `/addreply keyword | reply text`")

@router.message(Command("delreply"))
async def del_reply(message: types.Message):
    if message.from_user.id not in ADMIN_IDS and message.from_user.id != OWNER_ID: return
    try:
        keyword = message.text.split(" ", 1)[1].strip().lower()
        db = get_db()
        item = db.query(AutoReply).filter(AutoReply.keyword == keyword).first()
        if item:
            db.delete(item)
            db.commit()
            await message.answer(f"🗑️ Reply deleted for `{keyword}`")
        else:
            await message.answer("⚠️ Keyword not found.")
        db.close()
    except: 
        await message.answer("❌ Use: `/delreply keyword`")

@router.message(Command("replies"))
async def list_replies(message: types.Message):
    if message.from_user.id not in ADMIN_IDS and message.from_user.id != OWNER_ID: return
    db = get_db()
    replies = db.query(AutoReply).all()
    db.close()
    
    if not replies:
        await message.answer("📭 Auto-replies list is empty.")
        return
        
    text = "📋 <b>Saved Auto-Replies:</b>\n\n"
    for r in replies:
        text += f"• <b>{r.keyword}</b> ➡️ {r.reply_text[:20]}...\n"
    await message.answer(text)


# ====================================================
# 🛡️ 3. WELCOME & RULES SYSTEM
# ====================================================
@router.message(F.new_chat_members)
async def welcome_new_member(message: types.Message):
    # 1. Delete Default "XYZ Joined" message
    try: 
        await message.delete()
    except: 
        pass

    # 2. Global Ban Check for new user
    db = get_db()
    for new_user in message.new_chat_members:
        user_db = db.query(BotUser).filter(BotUser.user_id == new_user.id).first()
        if user_db and user_db.is_global_banned:
            try:
                await message.bot.ban_chat_member(message.chat.id, new_user.id)
                await log_report(message.bot, "Global Ban Prevented Entry", f"Banned User {new_user.id} tried to join {message.chat.title}.")
            except: 
                pass
            continue
        
        # 3. Send Welcome Message
        first_name = new_user.first_name
        text = f"👋 <b>Welcome {first_name}!</b>\n\nWe are glad to have you here. Please read our rules before sending messages."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📜 Rules", callback_data="show_rules"),
             InlineKeyboardButton(text="✨ Features", callback_data="show_features")]
        ])
        
        sent_msg = await message.answer(text, reply_markup=kb)
        asyncio.create_task(delete_later(message.bot, message.chat.id, sent_msg.message_id, 60))
        
    db.close()

async def delete_later(bot, chat_id, msg_id, seconds):
    await asyncio.sleep(seconds)
    try: 
        await bot.delete_message(chat_id, msg_id)
    except: 
        pass

@router.callback_query(F.data == "show_rules")
async def show_rules_cb(callback: types.CallbackQuery):
    db = get_db()
    settings = db.query(GroupSettings).filter(GroupSettings.chat_id == callback.message.chat.id).first()
    rules = settings.rules_text if settings else "1. Be respectful.\n2. No Links.\n3. No Spam."
    db.close()
    
    text = f"📜 <b>Group Rules:</b>\n\n{rules}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back to Welcome", callback_data="back_welcome")]])
    await callback.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "back_welcome")
async def back_welcome_cb(callback: types.CallbackQuery):
    text = "👋 <b>Welcome!</b>\n\nWe are glad to have you here. Please read our rules before sending messages."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Rules", callback_data="show_rules"), InlineKeyboardButton(text="✨ Features", callback_data="show_features")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)


# ====================================================
# 🚨 4. GROUP MESSAGE HANDLER (Anti-Spam, Links, Auto-Reply)
# ====================================================
@router.message(F.chat.type.in_({"group", "supergroup"}))
async def group_guard_logic(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # --- A. Check Global Ban ---
    db = get_db()
    user = db.query(BotUser).filter(BotUser.user_id == user_id).first()
    if user and user.is_global_banned:
        try: 
            await message.delete()
        except: 
            pass
        db.close()
        return

    # --- B. Bypass Owners & Admins ---
    if user_id == OWNER_ID or user_id in ADMIN_IDS:
        if message.text:
            reply_obj = db.query(AutoReply).filter(AutoReply.keyword == message.text.lower().strip()).first()
            if reply_obj: 
                await message.reply(reply_obj.reply_text)
        db.close()
        return

    # --- C. ANTI-FLOOD (3 sec me 5 msg = 1 hour mute) ---
    now = time.time()
    if user_id not in flood_cache: flood_cache[user_id] = []
    flood_cache[user_id].append(now)
    flood_cache[user_id] = [t for t in flood_cache[user_id] if now - t < 3]
    
    if len(flood_cache[user_id]) >= 5:
        try: 
            await message.delete() 
        except: 
            pass
        until = datetime.now() + timedelta(hours=1)
        try:
            await message.bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=False), until_date=until)
            await message.answer(f"⏳ <b>Anti-Flood System Triggered!</b>\n{message.from_user.first_name} muted for 1 Hour for spamming.")
            await log_report(message.bot, "Anti-Flood Mute (1h)", f"User {user_id} spammed in {message.chat.title}.")
        except Exception as e: 
            print(f"Flood Mute Error: {e}")
        db.close()
        return

    # --- D. ANTI-LINK (Delete and Warn) ---
    has_link = False
    if message.entities:
        for ent in message.entities:
            if ent.type in ["url", "text_link"]: 
                has_link = True
    
    if has_link:
        try: 
            await message.delete() 
        except: 
            pass
        await apply_warning(user_id, message.from_user.first_name, chat_id, message.bot, "Sending unauthorized links.")
        db.close()
        return

    # --- E. AUTO-REPLY ---
    if message.text:
        reply_obj = db.query(AutoReply).filter(AutoReply.keyword == message.text.lower().strip()).first()
        if reply_obj:
            await message.reply(reply_obj.reply_text)

    db.close()
