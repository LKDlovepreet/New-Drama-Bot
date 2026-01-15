import uuid
import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import get_db, SessionLocal
from database.models import BotUser, FileRecord, Channel
from config.settings import OWNER_ID, ADMIN_IDS
from utils.states import PostWizard

router = Router()

class AdminState(StatesGroup):
    waiting_for_id_add = State()
    waiting_for_id_remove = State()

def generate_token(): return str(uuid.uuid4())[:8]

# --- 1. SAVE MEDIA (Only Admin/Owner) ---
@router.message((F.photo | F.video | F.document | F.text) & F.chat.type == "private")
async def save_media(message: types.Message, state: FSMContext):
    # Ignore if in Wizard
    if await state.get_state(): return 
    
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS and user_id != OWNER_ID: return

    file_id, file_type, file_name = None, "text", "Unknown"

    if message.text:
        file_id = message.text
        file_name = message.text.split("\n")[0][:50]
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
        file_name = message.caption or "Photo"
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
        file_name = message.caption or "Video"
    elif message.document:
        file_id = message.document.file_id
        file_type = "doc"
        file_name = message.document.file_name

    session = get_db()
    try:
        token = generate_token()
        new_file = FileRecord(
            unique_token=token, file_id=file_id, file_name=file_name,
            file_type=file_type, uploader_id=user_id
        )
        session.add(new_file)
        session.commit()
        await message.reply(f"✅ <b>Saved!</b>\n🔗 Token: <code>{token}</code>")
    finally:
        session.close()

# --- 2. BROADCAST WIZARD ---
@router.callback_query(F.data == "broadcast_info")
async def trigger_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID: return
    await callback.message.answer("📸 <b>Step 1:</b> Photo/Video bhejein.")
    await state.set_state(PostWizard.waiting_for_media)
    await callback.answer()

@router.message(PostWizard.waiting_for_media, F.photo | F.video)
async def process_media(message: types.Message, state: FSMContext):
    if message.photo:
        await state.update_data(media_id=message.photo[-1].file_id, media_type="photo")
    elif message.video:
        await state.update_data(media_id=message.video.file_id, media_type="video")
    await message.answer("📝 <b>Step 2:</b> Caption (ya SKIP).")
    await state.set_state(PostWizard.waiting_for_caption)

@router.message(PostWizard.waiting_for_caption)
async def process_caption(message: types.Message, state: FSMContext):
    caption = message.text if message.text and message.text.lower() != "skip" else None
    await state.update_data(caption=caption)
    await message.answer("🔘 <b>Step 3:</b> Buttons (Name - Link) or SKIP.")
    await state.set_state(PostWizard.waiting_for_buttons)

@router.message(PostWizard.waiting_for_buttons)
async def process_buttons(message: types.Message, state: FSMContext):
    keyboard = None
    if message.text and message.text.lower() != "skip":
        rows = []
        for line in message.text.split("\n"):
            if "-" in line:
                parts = line.split("-", 1)
                if len(parts) == 2: rows.append([InlineKeyboardButton(text=parts[0].strip(), url=parts[1].strip())])
        if rows: keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    await state.update_data(reply_markup=keyboard)
    await message.answer("⏳ <b>Step 4:</b> Timer (Hours) or 0.")
    await state.set_state(PostWizard.waiting_for_timer)

@router.message(PostWizard.waiting_for_timer)
async def process_timer(message: types.Message, state: FSMContext):
    try: hours = float(message.text)
    except: hours = 0
    await state.update_data(timer_hours=hours)
    keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📢 Channels Only")], [KeyboardButton(text="👥 Users Only")], [KeyboardButton(text="🚀 Both (All)")]], resize_keyboard=True, one_time_keyboard=True)
    await message.answer("🎯 <b>Target?</b>", reply_markup=keyboard)
    await state.set_state(PostWizard.waiting_for_target)

@router.message(PostWizard.waiting_for_target)
async def process_target(message: types.Message, state: FSMContext):
    await state.update_data(target=message.text)
    data = await state.get_data()
    await message.answer("👀 Preview Sent. Send YES to confirm.", reply_markup=ReplyKeyboardRemove())
    await state.set_state(PostWizard.confirmation)

@router.message(PostWizard.confirmation)
async def confirm_send(message: types.Message, state: FSMContext):
    if message.text.lower() != "yes":
        await message.answer("❌ Cancelled."); await state.clear(); return
    data = await state.get_data()
    asyncio.create_task(run_broadcast(message.bot, data, data['target'], message.chat.id))
    await message.answer("🚀 Started!"); await state.clear()

async def run_broadcast(bot, data, target, admin_chat_id):
    sent_count = 0
    session = SessionLocal()
    try:
        if target in ["📢 Channels Only", "🚀 Both (All)"]:
            channels = session.query(Channel).all()
            for ch in channels:
                try:
                    m = await (bot.send_photo if data['media_type']=='photo' else bot.send_video)(ch.chat_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    sent_count += 1
                    if data['timer_hours'] > 0: asyncio.create_task(delete_later(bot, ch.chat_id, m.message_id, data['timer_hours']))
                except: pass
        if target in ["👥 Users Only", "🚀 Both (All)"]:
            users = session.query(BotUser).all()
            for user in users:
                try:
                    await (bot.send_photo if data['media_type']=='photo' else bot.send_video)(user.user_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    sent_count += 1
                    await asyncio.sleep(0.05)
                except: pass
    finally: session.close()
    await bot.send_message(admin_chat_id, f"✅ Done! Sent: {sent_count}")

async def delete_later(bot, chat_id, message_id, hours):
    await asyncio.sleep(hours * 3600)
    try: await bot.delete_message(chat_id, message_id)
    except: pass

# --- 3. OWNER DASHBOARD CALLBACKS ---
@router.callback_query(F.data == "admin_dashboard")
async def show_admin_dashboard(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID: return
    db = get_db()
    try:
        admins = db.query(BotUser).filter(BotUser.is_admin == True).all()
        msg = "👮‍♂️ <b>Admins:</b>\n" + "\n".join([f"• {a.user_id}" for a in admins])
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Add", callback_data="add_admin_action"), InlineKeyboardButton(text="➖ Remove", callback_data="remove_admin_action")]])
        await callback.message.edit_text(msg, reply_markup=keyboard)
    finally: db.close()

@router.callback_query(F.data == "add_admin_action")
async def ask_admin_id(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("👤 <b>New Admin ID?</b>")
    await state.set_state(AdminState.waiting_for_id_add)
    await callback.answer()

@router.message(AdminState.waiting_for_id_add)
async def process_add_admin(message: types.Message, state: FSMContext):
    db = get_db()
    try:
        uid = int(message.text)
        u = db.query(BotUser).filter(BotUser.user_id == uid).first()
        if not u: db.add(BotUser(user_id=uid, is_admin=True))
        else: u.is_admin = True
        db.commit(); await message.answer("✅ Added!")
    except: await message.answer("❌ Error")
    finally: db.close(); await state.clear()
