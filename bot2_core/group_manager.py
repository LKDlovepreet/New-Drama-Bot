import uuid, re
from aiogram import Router, F, types
from aiogram.filters import CommandStart, ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from thefuzz import process
from database.db import get_db
from database.models import GroupSettings, FileRecord, Channel
from config.settings import OWNER_ID, ADMIN_IDS, LINK_BOT_USERNAME, IGNORE_TERMS

router = Router()

def clean_file_name(text):
    if not text: return "Unknown"
    text = re.sub(r'[^\w\s]', ' ', text)
    words = text.lower().split()
    clean_words = [w for w in words if w not in IGNORE_TERMS and len(w) > 2]
    return " ".join(clean_words).title()

def generate_token(): return str(uuid.uuid4())[:8]

# --- START (Channel Controls) ---
@router.message(CommandStart())
async def bot2_start(message: types.Message):
    if message.from_user.id == OWNER_ID or message.from_user.id in ADMIN_IDS:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📺 Manage Channels", callback_data="list_channels")]])
        await message.answer("🤖 <b>Group Manager</b>\nControls:", reply_markup=keyboard)
    else:
        await message.answer("👋 Hello! Add me to groups to manage files.")

@router.callback_query(F.data == "list_channels")
async def list_channels(callback: types.CallbackQuery):
    session = get_db()
    try:
        channels = session.query(Channel).all()
        keyboard = [[InlineKeyboardButton(text=f"❌ Remove {c.channel_name}", callback_data=f"rem_ch_{c.id}")] for c in channels]
        await callback.message.edit_text("📺 <b>Channels:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    finally: session.close()

@router.callback_query(F.data.startswith("rem_ch_"))
async def remove_channel(callback: types.CallbackQuery):
    cid = int(callback.data.split("_")[2])
    session = get_db()
    session.query(Channel).filter(Channel.id == cid).delete()
    session.commit()
    session.close()
    await callback.answer("Removed!")

# --- INDEXING (Forward to Index) ---
@router.message((F.photo | F.video | F.document | F.text) & F.chat.type == "private")
async def smart_indexer(message: types.Message):
    if message.from_user.id != OWNER_ID and message.from_user.id not in ADMIN_IDS: return

    file_id = message.text or (message.photo[-1].file_id if message.photo else message.video.file_id if message.video else message.document.file_id)
    file_type = "text" if message.text else ("photo" if message.photo else ("video" if message.video else "doc"))
    raw_name = message.caption or message.text or (message.document.file_name if message.document else "")
    
    clean_name = clean_file_name(raw_name)
    session = get_db()
    try:
        if session.query(FileRecord).filter(FileRecord.file_name == clean_name).first():
            await message.reply(f"⚠️ Exists: {clean_name}"); return
        token = generate_token()
        session.add(FileRecord(unique_token=token, file_id=file_id, file_name=clean_name, file_type=file_type, uploader_id=message.from_user.id))
        session.commit()
        await message.reply(f"✅ Indexed: {clean_name}\nCode: {token}")
    except Exception as e: await message.reply(f"Error: {e}")
    finally: session.close()

# --- GROUP LOGIC ---
@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_join(event: types.ChatMemberUpdated):
    if event.chat.type in ["group", "supergroup"]:
        await event.bot.send_message(event.chat.id, f"👋 Welcome {event.new_chat_member.user.first_name}!")

@router.message(F.text & F.chat.type.in_({"group", "supergroup"}))
async def group_chat(message: types.Message):
    text = message.text.lower()
    
    # Admin Call
    if "admin" in text or "help" in text:
        await message.reply("🚨 Admin Called!")
        return

    # Casual Filter
    if text in ["hi", "hello", "gm", "gn", "ok"] or len(text) < 3: return

    # Search
    session = get_db()
    try:
        all_files = session.query(FileRecord).all()
        names = {f.file_name: f for f in all_files}
        match = process.extractOne(clean_file_name(text), names.keys())
        
        if match and match[1] > 60:
            file = names[match[0]]
            link = f"https://t.me/{LINK_BOT_USERNAME}?start={file.unique_token}"
            await message.reply(f"🎬 <b>Found:</b> {file.file_name}\n👇 Link:\n{link}")
        else:
            # Delete if no match (Strict Mode)
            try: await message.delete()
            except: pass
    finally: session.close()
