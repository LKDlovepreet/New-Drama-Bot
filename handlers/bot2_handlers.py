import uuid
import re
from aiogram import Router, F, types
from aiogram.filters import CommandStart, ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from thefuzz import process
from sqlalchemy.orm import Session
from database.db import get_db
from database.models import GroupSettings, FileRecord, Channel
from config.settings import (
    GROUP_BOT_ID, OWNER_ID, ADMIN_IDS, 
    LINK_BOT_USERNAME, IGNORE_TERMS
)

router = Router()
# 👇 SIRF BOT 2 PAR CHALEGA
router.message.filter(F.bot.id == GROUP_BOT_ID)
router.callback_query.filter(F.bot.id == GROUP_BOT_ID)

# --- HELPER: Filename Cleaner ---
def clean_file_name(text):
    """File name me se 480p, 720p jaise words hata kar 'Clean Tag' banata hai"""
    if not text: return "Unknown File"
    
    # Remove Special characters but keep spaces
    text = re.sub(r'[^\w\s]', ' ', text)
    
    words = text.lower().split()
    # Sirf meaningful words rakhein
    clean_words = [w for w in words if w not in IGNORE_TERMS and len(w) > 2]
    
    # Capitalize first letters
    return " ".join(clean_words).title()

def generate_token():
    return str(uuid.uuid4())[:8]

# ==========================================
# 1. OWNER CONTROLS (MANAGE CHANNELS)
# ==========================================
@router.message(CommandStart())
async def bot2_start(message: types.Message):
    user_id = message.from_user.id
    
    # Sirf Owner/Admin ke liye Controls
    if user_id == OWNER_ID or user_id in ADMIN_IDS:
        msg = (
            f"🤖 <b>Group Manager Bot</b>\n\n"
            f"Main Groups ko manage karunga aur Indexing karunga.\n"
            f"⚙️ <b>Controls:</b>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📺 Manage Channels", callback_data="list_channels")],
            [InlineKeyboardButton(text="🗑 Delete All Files", callback_data="flush_db_confirm")]
        ])
        await message.answer(msg, reply_markup=keyboard)
    else:
        await message.answer(
            "👋 <b>Hello!</b>\n"
            "Main Group Manager hu. Mujhe kisi Group me add karein, main wahan movies/series dhundne me help karunga."
        )

# --- CHANNEL MANAGEMENT CALLBACKS ---
@router.callback_query(F.data == "list_channels")
async def list_connected_channels(callback: types.CallbackQuery):
    session = get_db()
    try:
        channels = session.query(Channel).all()
        if not channels:
            await callback.answer("Koi Channel Connect nahi hai.", show_alert=True)
            return
            
        msg = "📺 <b>Connected Channels:</b>\n\n"
        keyboard = []
        
        for ch in channels:
            msg += f"• {ch.channel_name} (ID: {ch.chat_id})\n"
            keyboard.append([
                InlineKeyboardButton(text=f"❌ Remove {ch.channel_name}", callback_data=f"rem_ch_{ch.id}")
            ])
            
        keyboard.append([InlineKeyboardButton(text="🔙 Back", callback_data="bot2_home")])
        await callback.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    finally:
        session.close()

@router.callback_query(F.data.startswith("rem_ch_"))
async def remove_channel(callback: types.CallbackQuery):
    ch_id = int(callback.data.split("_")[2])
    session = get_db()
    try:
        session.query(Channel).filter(Channel.id == ch_id).delete()
        session.commit()
        await callback.answer("✅ Channel Removed!")
        await list_connected_channels(callback)
    finally:
        session.close()

@router.callback_query(F.data == "bot2_home")
async def back_to_home(callback: types.CallbackQuery):
    await bot2_start(callback.message)

# ==========================================
# 2. SMART INDEXING (ON FORWARD)
# ==========================================
@router.message((F.photo | F.video | F.document | F.text) & F.chat.type == "private")
async def smart_indexer(message: types.Message):
    user_id = message.from_user.id
    if user_id != OWNER_ID and user_id not in ADMIN_IDS: return 

    # Content identify karein
    file_id = None
    file_type = "text"
    raw_caption = message.caption or message.text or ""
    
    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.document:
        file_id = message.document.file_id
        file_type = "doc"
        raw_caption = message.document.file_name or raw_caption
    elif message.text:
        file_id = message.text
        file_type = "text"

    # 👇 SMART TAG LOGIC (Clean Name)
    clean_name = clean_file_name(raw_caption)
    
    session = get_db()
    try:
        # Duplicate Check
        exists = session.query(FileRecord).filter(FileRecord.file_name == clean_name).first()
        if exists:
            await message.reply(f"⚠️ <b>Already Indexed:</b>\n{clean_name}")
            return

        token = generate_token()
        new_file = FileRecord(
            unique_token=token,
            file_id=file_id,
            file_name=clean_name, # Clean naam save hoga
            file_type=file_type,
            uploader_id=user_id
        )
        session.add(new_file)
        session.commit()
        
        await message.reply(
            f"✅ <b>Indexed Successfully!</b>\n\n"
            f"🏷 <b>Smart Tag:</b> {clean_name}\n"
            f"🔗 Token: <code>{token}</code>"
        )
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
    finally:
        session.close()

# ==========================================
# 3. GROUP MANAGEMENT (WELCOME + REPLY + IGNORE)
# ==========================================

# A. WELCOME NEW USERS
@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_join(event: types.ChatMemberUpdated):
    if event.chat.type not in ["group", "supergroup"]: return
    
    user_name = event.new_chat_member.user.first_name
    msg = (
        f"👋 <b>Welcome {user_name}!</b>\n\n"
        f"🎥 <b>Features:</b>\n"
        f"1. Movie/Series ka naam likhein.\n"
        f"2. Agar mere paas hogi to main link dunga.\n"
        f"3. Admin help ke liye 'Admin' likhein."
    )
    await event.bot.send_message(event.chat.id, msg)

# B. GROUP MESSAGE HANDLER
@router.message(F.text & F.chat.type.in_({"group", "supergroup"}))
async def group_chat_logic(message: types.Message):
    text = message.text.lower()
    
    # 1. ADMIN CALL
    if any(x in text for x in ["admin", "owner", "help", "problem", "issue"]):
        # Admins ko tag karo
        admin_mentions = [f"<a href='tg://user?id={uid}'>Admin</a>" for uid in ADMIN_IDS]
        if not admin_mentions: admin_mentions = ["Admin"]
        
        await message.reply(
            f"🚨 <b>Admin Call!</b>\n"
            f"{', '.join(admin_mentions)}, please check this.",
            parse_mode="HTML"
        )
        return

    # 2. CASUAL TALK FILTER (Ignore these)
    CASUAL_WORDS = ["hi", "hello", "kaise", "ho", "gm", "gn", "ok", "thanks", "bhai", "bro", "yrr", "acha", "sahi", "hn", "ha"]
    
    # Check if exact word match or very short message
    if text in CASUAL_WORDS or len(text) < 3:
        return # Chup raho (Ignore)

    # 3. SMART SEARCH (Agar user kuch maang raha hai)
    session = get_db()
    try:
        # Clean query
        search_query = clean_file_name(text)
        
        all_files = session.query(FileRecord).all()
        file_names = {f.file_name: f for f in all_files}
        
        # Fuzzy Matching
        best_match = process.extractOne(search_query, file_names.keys())
        
        if best_match and best_match[1] > 60: # 60% match bhi chalega
            matched_file = file_names[best_match[0]]
            
            # Link Bot 1 ka denge
            link = f"https://t.me/{LINK_BOT_USERNAME}?start={matched_file.unique_token}"
            
            await message.reply(
                f"🎬 <b>File Found!</b>\n"
                f"📂 {matched_file.file_name}\n"
                f"👇 <b>Download Link:</b>\n{link}"
            )
        else:
            # Match nahi mila.
            # Agar casual talk bhi nahi hai aur content bhi nahi hai, to ye spam ho sakta hai.
            # Lekin aapne kaha "Ignore" karo agar casual hai. 
            pass 

    except Exception as e:
        print(f"Group Search Error: {e}")
    finally:
        session.close()
