import uuid
import asyncio
import os
from aiogram import Router, F, types
from aiogram.filters import Command, ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import get_db, SessionLocal
from database.models import BotUser, FileRecord, Channel
from config.settings import OWNER_ID, ADMIN_IDS
from utils.states import PostWizard

# Storage Channel ID (Environment Variable se)
STORAGE_CHANNEL_ID = int(os.getenv("STORAGE_CHANNEL_ID", 0))

router = Router()

# --- STATE GROUPS ---
class AdminState(StatesGroup):
    waiting_for_id_add = State()
    waiting_for_id_remove = State()

class BulkState(StatesGroup):
    uploading = State()

class TopicState(StatesGroup):
    waiting_for_name = State()

def generate_token():
    return str(uuid.uuid4())[:8]

# ====================================================
# 1. TOPIC MANAGEMENT (Save Content to Topics)
# ====================================================
@router.message(Command("set_topic"))
async def manage_topics(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS and message.from_user.id != OWNER_ID: return
    
    if STORAGE_CHANNEL_ID == 0:
        await message.answer("⚠️ <b>Error:</b> STORAGE_CHANNEL_ID .env me set nahi hai.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create New Topic", callback_data="create_new_topic")],
        [InlineKeyboardButton(text="❌ Reset / Deselect", callback_data="reset_topic")]
    ])
    await message.answer("📂 <b>Topic Manager</b>\nSelect kar lo ki files kahan save karni hain.", reply_markup=keyboard)

@router.callback_query(F.data == "create_new_topic")
async def ask_topic_name(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 <b>Topic ka naam likho:</b>\n(Example: Movies, Notes, Series)")
    await state.set_state(TopicState.waiting_for_name)
    await callback.answer()

@router.message(TopicState.waiting_for_name)
async def create_topic_process(message: types.Message, state: FSMContext):
    topic_name = message.text
    try:
        # Create Topic in Storage Group
        topic = await message.bot.create_forum_topic(chat_id=STORAGE_CHANNEL_ID, name=topic_name)
        
        # Save ID to User DB
        db = get_db()
        user = db.query(BotUser).filter(BotUser.user_id == message.from_user.id).first()
        user.active_topic_id = topic.message_thread_id
        db.commit()
        db.close()
        
        await message.answer(f"✅ <b>Topic Created & Selected!</b>\n\n📂 Name: {topic_name}\n🆔 ID: {topic.message_thread_id}\n\nAb jo file bhejoge wo seedha yahan save hogi.")
    except Exception as e:
        await message.answer(f"❌ Error creating topic: {e}\n(Make sure Bot is Admin in Storage Group)")
    finally:
        await state.clear()

@router.callback_query(F.data == "reset_topic")
async def reset_topic(callback: types.CallbackQuery):
    db = get_db()
    user = db.query(BotUser).filter(BotUser.user_id == callback.from_user.id).first()
    user.active_topic_id = 0
    db.commit()
    db.close()
    await callback.message.edit_text("✅ Topic Deselected. Files ab kahin forward nahi hongi.")


# ====================================================
# 2. BULK LINK FEATURE (/bulk)
# ====================================================
@router.message(Command("bulk"))
async def start_bulk_mode(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS and message.from_user.id != OWNER_ID: return
    
    await state.set_data({'files': [], 'names': []})
    await state.set_state(BulkState.uploading)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ DONE - Create Link", callback_data="finish_bulk")]])
    await message.answer("📚 <b>Bulk Mode ON</b>\n\nAb jitni files bhejni hain bhejo (Forward ya Upload).\nJab ho jaye to neeche button dabana.", reply_markup=keyboard)

@router.message(BulkState.uploading, (F.photo | F.video | F.document))
async def handle_bulk_files(message: types.Message, state: FSMContext):
    # Determine ID and Name
    f_id, f_type, f_name = None, "text", "Unknown"
    
    if message.photo:
        f_id = message.photo[-1].file_id; f_type="photo"; f_name="Photo"
    elif message.video:
        f_id = message.video.file_id; f_type="video"; f_name=message.caption or "Video"
    elif message.document:
        f_id = message.document.file_id; f_type="doc"; f_name=message.document.file_name

    data = await state.get_data()
    current_files = data['files']
    current_names = data['names']
    
    # Store format: "type|file_id"
    current_files.append(f"{f_type}|{f_id}")
    current_names.append(f_name)
    
    await state.update_data(files=current_files, names=current_names)

@router.callback_query(BulkState.uploading, F.data == "finish_bulk")
async def finish_bulk_process(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    files = data['files']
    
    if not files:
        await callback.answer("Koi file nahi mili!", show_alert=True)
        return

    # Join all IDs
    joined_ids = ":::".join(files)
    bulk_name = f"Batch of {len(files)} Files"
    
    db = get_db()
    try:
        token = generate_token()
        new_file = FileRecord(
            unique_token=token,
            file_id=joined_ids,
            file_name=bulk_name,
            file_type="batch",   # Special Type
            uploader_id=callback.from_user.id
        )
        db.add(new_file)
        db.commit()
        
        bot_username = (await callback.bot.get_me()).username
        link = f"https://t.me/{bot_username}?start={token}"
        
        msg = f"📦 <b>Bulk Link Created!</b>\n\n📄 Files: {len(files)}\n🔗 Link:\n{link}"
        await callback.message.edit_text(msg, disable_web_page_preview=True)
        
    finally:
        db.close()
        await state.clear()


# ====================================================
# 3. SINGLE MEDIA SAVE & LINK GEN (With Topic)
# ====================================================
@router.message((F.photo | F.video | F.document | (F.text & ~F.text.startswith("/"))) & F.chat.type == "private")
async def save_media_and_get_link(message: types.Message, state: FSMContext):
    # Ignore if in Wizard
    if await state.get_state(): return

    user_id = message.from_user.id
    if user_id != OWNER_ID and user_id not in ADMIN_IDS: return

    file_id, file_type, file_name = None, "text", "Unknown"

    if message.text:
        file_id = message.text; file_name = message.text.split("\n")[0][:50]; file_type = "text"
    elif message.photo:
        file_id = message.photo[-1].file_id; file_type = "photo"; file_name = message.caption or "Photo"
    elif message.video:
        file_id = message.video.file_id; file_type = "video"; file_name = message.caption or "Video"
    elif message.document:
        file_id = message.document.file_id; file_type = "doc"; file_name = message.document.file_name

    session = get_db()
    try:
        # 1. Save to DB
        token = generate_token()
        new_file = FileRecord(unique_token=token, file_id=file_id, file_name=file_name, file_type=file_type, uploader_id=user_id)
        session.add(new_file)
        
        # 2. Check Topic & Forward
        if STORAGE_CHANNEL_ID != 0:
            user_db = session.query(BotUser).filter(BotUser.user_id == user_id).first()
            if user_db and user_db.active_topic_id and user_db.active_topic_id != 0:
                try:
                    await message.forward(chat_id=STORAGE_CHANNEL_ID, message_thread_id=user_db.active_topic_id)
                except Exception as e:
                    print(f"Topic Forward Error: {e}")

        session.commit()
        
        # 3. Generate Full Link
        bot_username = (await message.bot.get_me()).username
        deep_link = f"https://t.me/{bot_username}?start={token}"
        
        await message.reply(f"✅ <b>Saved!</b>\n📂 {file_name}\n🔗 {deep_link}", disable_web_page_preview=True)
    finally:
        session.close()


# ====================================================
# 4. BROADCAST FEATURE (/createpost)
# ====================================================
@router.message(Command("createpost"))
async def start_post(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS and message.from_user.id != OWNER_ID: return
    await message.answer("📸 <b>Step 1:</b> Photo/Video bhejo.")
    await state.set_state(PostWizard.waiting_for_media)

@router.message(PostWizard.waiting_for_media, F.photo | F.video)
async def process_media(message: types.Message, state: FSMContext):
    if message.photo: await state.update_data(media_id=message.photo[-1].file_id, media_type="photo")
    elif message.video: await state.update_data(media_id=message.video.file_id, media_type="video")
    await message.answer("📝 <b>Step 2:</b> Caption (ya SKIP likho).")
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
    await message.answer("⏳ <b>Step 4:</b> Timer (Hours) ya 0.")
    await state.set_state(PostWizard.waiting_for_timer)

@router.message(PostWizard.waiting_for_timer)
async def process_timer(message: types.Message, state: FSMContext):
    try: hours = float(message.text)
    except: hours = 0
    await state.update_data(timer_hours=hours)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📢 Channels Only")], [KeyboardButton(text="👥 Users Only")], [KeyboardButton(text="🚀 Both (All)")]], resize_keyboard=True, one_time_keyboard=True)
    await message.answer("🎯 <b>Target?</b>", reply_markup=kb)
    await state.set_state(PostWizard.waiting_for_target)

@router.message(PostWizard.waiting_for_target)
async def process_target(message: types.Message, state: FSMContext):
    await state.update_data(target=message.text)
    await message.answer("👀 <b>Preview Ready.</b> Send YES to confirm.", reply_markup=ReplyKeyboardRemove())
    await state.set_state(PostWizard.confirmation)

@router.message(PostWizard.confirmation)
async def confirm_send(message: types.Message, state: FSMContext):
    if message.text and message.text.lower() == "yes":
        data = await state.get_data()
        asyncio.create_task(run_broadcast(message.bot, data, data['target'], message.chat.id))
        await message.answer("🚀 Broadcast Started!")
    else:
        await message.answer("❌ Cancelled.")
    await state.clear()

async def run_broadcast(bot, data, target, admin_chat_id):
    sent = 0
    session = SessionLocal()
    try:
        if target in ["📢 Channels Only", "🚀 Both (All)"]:
            channels = session.query(Channel).filter(Channel.broadcast_enabled == True).all()
            for ch in channels:
                try:
                    if data['media_type'] == 'photo': await bot.send_photo(ch.chat_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    else: await bot.send_video(ch.chat_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    sent += 1
                except: pass
        
        if target in ["👥 Users Only", "🚀 Both (All)"]:
            users = session.query(BotUser).all()
            for u in users:
                try:
                    if data['media_type'] == 'photo': await bot.send_photo(u.user_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    else: await bot.send_video(u.user_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    sent += 1
                    await asyncio.sleep(0.05)
                except: pass
    finally: session.close()
    await bot.send_message(admin_chat_id, f"✅ Done! Sent to {sent} chats.")


# ====================================================
# 5. NAVIGATION & MENUS (Edit Caption Based)
# ====================================================
@router.callback_query(F.data == "owner_home")
async def back_to_home(callback: types.CallbackQuery):
    caption = (
        "<b>Hello Father 🗽</b>\n\n"
        "⚙️ <b>Owner Controls:</b>\n"
        "/createpost - Broadcast Message\n"
        "/set_topic - Manage Storage Topics\n"
        "/bulk - Bulk Link Creation\n"
        "/start - Refresh Menu\n"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👮 Manage Admins", callback_data="admin_dashboard")],
        [InlineKeyboardButton(text="📢 Connected Chats", callback_data="list_chats")],
        [InlineKeyboardButton(text="💎 Premium", callback_data="premium_alert")]
    ])
    try: await callback.message.edit_caption(caption=caption, reply_markup=keyboard, parse_mode="HTML")
    except: pass

@router.callback_query(F.data == "premium_alert")
async def premium_feature_off(callback: types.CallbackQuery):
    msg = "💎 <b>Premium Subscription</b>\n\n⚠️ <b>Feature Currently OFF</b>\nAbhi ye feature available nahi hai."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back", callback_data="owner_home")]])
    try: await callback.message.edit_caption(caption=msg, reply_markup=keyboard, parse_mode="HTML")
    except: await callback.answer("Menu Updated")

# --- MANAGE ADMINS ---
@router.callback_query(F.data == "admin_dashboard")
async def show_admin_dashboard(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID: await callback.answer("Denied", show_alert=True); return
    db = get_db()
    try:
        admins = db.query(BotUser).filter(BotUser.is_admin == True).all()
        msg = "👮‍♂️ <b>Manage Admins</b>\n\n<b>Current Admins:</b>\n" + ("".join([f"• <code>{a.user_id}</code>\n" for a in admins]) if admins else "None")
        msg += "\n👇 <b>Select Action:</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add", callback_data="add_admin_action"), InlineKeyboardButton(text="➖ Remove", callback_data="remove_admin_action")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="owner_home")]
        ])
        await callback.message.edit_caption(caption=msg, reply_markup=kb, parse_mode="HTML")
    finally: db.close()

@router.callback_query(F.data == "add_admin_action")
async def ask_admin_id(c: types.CallbackQuery, s: FSMContext):
    await c.message.answer("👤 <b>Send User ID to make Admin:</b>"); await s.set_state(AdminState.waiting_for_id_add); await c.answer()

@router.message(AdminState.waiting_for_id_add)
async def process_add_admin(m: types.Message, s: FSMContext):
    if not m.text.isdigit(): await m.answer("❌ Numbers only."); return
    db = get_db()
    try:
        uid = int(m.text)
        if not db.query(BotUser).filter(BotUser.user_id == uid).first():
            db.add(BotUser(user_id=uid, is_admin=True)); db.commit(); await m.answer(f"✅ User {uid} is now Admin.")
        else: await m.answer("⚠️ Already added.")
    finally: db.close(); await s.clear()

@router.callback_query(F.data == "remove_admin_action")
async def ask_remove_id(c: types.CallbackQuery, s: FSMContext):
    await c.message.answer("🗑 <b>Send User ID to Remove:</b>"); await s.set_state(AdminState.waiting_for_id_remove); await c.answer()

@router.message(AdminState.waiting_for_id_remove)
async def process_remove_admin(m: types.Message, s: FSMContext):
    if not m.text.isdigit(): await m.answer("❌ Invalid ID."); return
    db = get_db()
    try:
        u = db.query(BotUser).filter(BotUser.user_id == int(m.text)).first()
        if u and u.is_admin: u.is_admin = False; db.commit(); await m.answer(f"✅ User removed.")
        else: await m.answer("⚠️ Not an Admin.")
    finally: db.close(); await s.clear()

# --- MANAGE CHATS ---
@router.callback_query(F.data == "list_chats")
async def list_connected_chats(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID: await callback.answer("Denied", show_alert=True); return
    db = get_db()
    try:
        channels = db.query(Channel).all()
        if not channels: await callback.answer("No Chats Found", show_alert=True); return
        msg = "📢 <b>Connected Chats</b>\nClick to Manage:"
        kb = [[InlineKeyboardButton(text=f"{ch.channel_name[:15]}.. [{'✅' if ch.broadcast_enabled else '❌'}]", callback_data=f"manage_chat_{ch.id}")] for ch in channels]
        kb.append([InlineKeyboardButton(text="🔙 Back", callback_data="owner_home")])
        await callback.message.edit_caption(caption=msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    finally: db.close()

@router.callback_query(F.data.startswith("manage_chat_"))
async def manage_single_chat(callback: types.CallbackQuery):
    try: cid = int(callback.data.split("_")[2])
    except: return
    db = get_db()
    try:
        ch = db.query(Channel).filter(Channel.id == cid).first()
        if not ch: await list_connected_chats(callback); return
        msg = f"⚙️ <b>{ch.channel_name}</b>\nID: <code>{ch.chat_id}</code>\nBroadcast: <b>{'✅ Enabled' if ch.broadcast_enabled else '❌ Disabled'}</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Toggle Broadcast", callback_data=f"toggle_br_{ch.id}")],
            [InlineKeyboardButton(text="📤 Leave Chat", callback_data=f"leave_chat_{ch.id}")],
            [InlineKeyboardButton(text="🔙 Back List", callback_data="list_chats")]
        ])
        await callback.message.edit_caption(caption=msg, reply_markup=kb, parse_mode="HTML")
    finally: db.close()

@router.callback_query(F.data.startswith("toggle_br_"))
async def toggle_broadcast(c: types.CallbackQuery):
    try:
        cid = int(c.data.split("_")[2])
        db = get_db()
        ch = db.query(Channel).filter(Channel.id == cid).first()
        if ch: ch.broadcast_enabled = not ch.broadcast_enabled; db.commit(); await manage_single_chat(c)
        db.close()
    except: pass

@router.callback_query(F.data.startswith("leave_chat_"))
async def leave_chat(c: types.CallbackQuery):
    try:
        cid = int(c.data.split("_")[2])
        db = get_db()
        ch = db.query(Channel).filter(Channel.id == cid).first()
        if ch:
            try: await c.bot.leave_chat(ch.chat_id)
            except: pass
            db.delete(ch); db.commit(); await list_connected_chats(c)
        db.close()
    except: pass

# --- AUTO SAVE CHANNEL ---
@router.my_chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_bot_added(event: types.ChatMemberUpdated):
    if event.chat.type in ["channel", "supergroup", "group"]:
        db = get_db()
        if not db.query(Channel).filter(Channel.chat_id == event.chat.id).first():
            db.add(Channel(chat_id=event.chat.id, channel_name=event.chat.title, added_by=event.from_user.id, broadcast_enabled=False))
            db.commit()
        db.close()