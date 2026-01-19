import uuid
import asyncio
import os
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import get_db, SessionLocal
# 👇 StorageTopic added here
from database.models import BotUser, FileRecord, Channel, StorageTopic
from config.settings import OWNER_ID, ADMIN_IDS

# 👇 PostWizard yahan se import hoga (Duplicate hataya)
from utils.states import PostWizard

# Env se Storage Channel ID
STORAGE_CHANNEL_ID = int(os.getenv("STORAGE_CHANNEL_ID", 0))

router = Router()

# --- LOCAL STATES (Sirf is file ke liye) ---
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
# 🚨 1. CANCEL COMMAND (Global Stop)
# ====================================================
@router.message(Command("cancel"))
async def cancel_process(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("🛑 <b>Main free hu.</b> Koi process chal nahi raha.")
        return

    await state.clear()
    await message.answer("✅ <b>Process Cancelled!</b>\nMain ab normal mode me hu.", reply_markup=ReplyKeyboardRemove())

# ====================================================
# 2. TOPIC MANAGEMENT (Smart List & Select)
# ====================================================
@router.message(Command("set_topic"))
async def manage_topics(message: types.Message):
    if message.from_user.id not in ADMIN_IDS and message.from_user.id != OWNER_ID: return

    if STORAGE_CHANNEL_ID == 0:
        await message.answer("⚠️ <b>Error:</b> STORAGE_CHANNEL_ID .env me set nahi hai.")
        return

    db = get_db()
    try:
        # Purane Topics Fetch karo
        saved_topics = db.query(StorageTopic).all()

        # User ka current active topic
        user = db.query(BotUser).filter(BotUser.user_id == message.from_user.id).first()
        current_active = user.active_topic_id if user else 0

        msg = f"📂 <b>Topic Manager</b>\nActive Topic ID: <code>{current_active}</code>\n\nSelect a topic or Create New:"

        keyboard = []
        # List Existing Topics
        for topic in saved_topics:
            status = "✅" if topic.topic_id == current_active else "▪️"
            btn_text = f"{status} {topic.topic_name}"
            # Button click par select karega
            keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"select_topic_{topic.topic_id}")])

        # New Create Button
        keyboard.append([InlineKeyboardButton(text="➕ Create New Topic", callback_data="create_new_topic")])
        keyboard.append([InlineKeyboardButton(text="❌ Deselect / Reset", callback_data="reset_topic")])

        await message.answer(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    finally:
        db.close()

# --- Select Existing Topic ---
@router.callback_query(F.data.startswith("select_topic_"))
async def select_existing_topic(c: types.CallbackQuery):
    try:
        topic_id = int(c.data.split("_")[2])
    except: return

    db = get_db()
    try:
        user = db.query(BotUser).filter(BotUser.user_id == c.from_user.id).first()
        if user:
            user.active_topic_id = topic_id
            db.commit()

            # Topic ka naam dhundo display ke liye
            t_name = "Selected"
            topic_record = db.query(StorageTopic).filter(StorageTopic.topic_id == topic_id).first()
            if topic_record: t_name = topic_record.topic_name

            await c.message.edit_text(f"✅ <b>Topic Active:</b> {t_name}\nID: {topic_id}\n\nAb files yahan save hongi.")
        else:
            await c.answer("User not found", show_alert=True)
    finally:
        db.close()

# --- Create New Topic ---
@router.callback_query(F.data == "create_new_topic")
async def ask_topic_name(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("📝 <b>New Topic ka naam likho:</b>")
    await state.set_state(TopicState.waiting_for_name)
    await c.answer()

@router.message(TopicState.waiting_for_name)
async def create_topic_process(message: types.Message, state: FSMContext):
    topic_name = message.text
    db = get_db()
    try:
        # 1. Telegram par Topic Banao
        topic = await message.bot.create_forum_topic(chat_id=STORAGE_CHANNEL_ID, name=topic_name)

        # 2. StorageTopic Table me Save karo (Taaki list me aaye)
        new_storage_topic = StorageTopic(topic_name=topic_name, topic_id=topic.message_thread_id)
        db.add(new_storage_topic)

        # 3. User ka Active Topic set karo
        user = db.query(BotUser).filter(BotUser.user_id == message.from_user.id).first()
        if user:
            user.active_topic_id = topic.message_thread_id

        db.commit()

        await message.answer(f"✅ <b>Topic Created & Selected!</b>\n\n📂 Name: {topic_name}\n🆔 ID: {topic.message_thread_id}\n\nList me add ho gaya hai.")
    except Exception as e:
        await message.answer(f"❌ Error creating topic: {e}\n(Make sure Bot is Admin in Storage Group)")
    finally:
        db.close()
        await state.clear()

@router.callback_query(F.data == "reset_topic")
async def reset_topic(c: types.CallbackQuery):
    db = get_db()
    user = db.query(BotUser).filter(BotUser.user_id == c.from_user.id).first()
    if user:
        user.active_topic_id = 0
        db.commit()
    db.close()
    await c.message.edit_text("✅ Topic Deselected. Files Group me forward nahi hongi.")

# ====================================================
# 3. BULK LINK FEATURE (/bulk)
# ====================================================
@router.message(Command("bulk"))
async def start_bulk_mode(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS and message.from_user.id != OWNER_ID: return

    await state.set_data({'files': [], 'names': []})
    await state.set_state(BulkState.uploading)

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ DONE - Make Link", callback_data="finish_bulk")]])
    await message.answer("📚 <b>Bulk Mode ON</b>\nFiles bhejo. Cancel karne ke liye /cancel dabayein.", reply_markup=kb)

@router.message(BulkState.uploading, (F.photo | F.video | F.document))
async def handle_bulk_files(message: types.Message, state: FSMContext):
    f_id, f_type, f_name = None, "doc", "Unknown"

    if message.photo:
        f_id = message.photo[-1].file_id; f_type="photo"; f_name="Photo"
    elif message.video:
        f_id = message.video.file_id; f_type="video"; f_name=message.caption or "Video"
    elif message.document:
        f_id = message.document.file_id; f_type="doc"; f_name=message.document.file_name

    data = await state.get_data()
    data['files'].append(f"{f_type}|{f_id}")
    data['names'].append(f_name)
    await state.update_data(files=data['files'], names=data['names'])

@router.callback_query(BulkState.uploading, F.data == "finish_bulk")
async def finish_bulk_process(c: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    files = data['files']
    if not files: await c.answer("No files!", show_alert=True); return

    db = get_db()
    try:
        token = generate_token()
        new_file = FileRecord(
            unique_token=token,
            file_id=":::".join(files),
            file_name=f"Batch ({len(files)} files)",
            file_type="batch",
            uploader_id=c.from_user.id
        )
        db.add(new_file)
        db.commit()

        bot_username = (await c.bot.get_me()).username
        link = f"https://t.me/{bot_username}?start={token}"
        await c.message.edit_text(f"📦 <b>Bulk Link Created!</b>\n\n📄 Files: {len(files)}\n🔗 {link}")
    finally:
        db.close()
        await state.clear()

# ====================================================
# 4. SINGLE FILE SAVE & LINK
# ====================================================
@router.message((F.photo | F.video | F.document | (F.text & ~F.text.startswith("/"))) & F.chat.type == "private")
async def save_media_and_get_link(message: types.Message, state: FSMContext):
    # 🛑 AGAR STATE ACTIVE HAI TO IGNORE KARO
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
        # 1. DB Save
        token = generate_token()
        new_file = FileRecord(unique_token=token, file_id=file_id, file_name=file_name, file_type=file_type, uploader_id=user_id)
        session.add(new_file)

        # 2. Topic Forward Logic
        forwarded_msg = ""
        if STORAGE_CHANNEL_ID != 0:
            user_db = session.query(BotUser).filter(BotUser.user_id == user_id).first()
            if user_db and user_db.active_topic_id and user_db.active_topic_id != 0:
                try:
                    await message.forward(chat_id=STORAGE_CHANNEL_ID, message_thread_id=user_db.active_topic_id)
                    forwarded_msg = "\n✅ <b>Saved to Topic!</b>"
                except Exception as e:
                    print(f"Forward Error: {e}")

        session.commit()

        bot_username = (await message.bot.get_me()).username
        link = f"https://t.me/{bot_username}?start={token}"

        await message.reply(
            f"✅ <b>Content Saved!</b>\n"
            f"📂 {file_name}\n"
            f"🔗 {link}"
            f"{forwarded_msg}",
            disable_web_page_preview=True
        )
    except Exception as e:
        await message.reply(f"❌ Error: {e}")
    finally:
        session.close()

# ====================================================
# 5. BROADCAST & ADMIN DASHBOARD
# ====================================================
@router.message(Command("createpost"))
async def start_post(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS and message.from_user.id != OWNER_ID: return
    await state.clear()
    await message.answer("📸 <b>Step 1:</b> Send Media or /cancel.")
    await state.set_state(PostWizard.waiting_for_media)

@router.message(PostWizard.waiting_for_media)
async def process_media(message: types.Message, state: FSMContext):
    media_id = None
    media_type = "text"

    if message.photo:
        media_id = message.photo[-1].file_id; media_type = "photo"
    elif message.video:
        media_id = message.video.file_id; media_type = "video"
    elif message.document:
        media_id = message.document.file_id; media_type = "doc"
    else:
        await message.answer("❌ Invalid Media! Photo, Video ya File bhejein."); return

    await state.update_data(media_id=media_id, media_type=media_type)
    await message.answer("📝 <b>Step 2:</b> Caption (or SKIP).")
    await state.set_state(PostWizard.waiting_for_caption)

@router.message(PostWizard.waiting_for_caption)
async def process_caption(message: types.Message, state: FSMContext):
    caption = message.text if message.text and message.text.lower() != "skip" else None
    if message.caption: caption = message.caption
    await state.update_data(caption=caption)
    await message.answer("🔘 <b>Step 3:</b> Buttons (Name - Link) or SKIP.")
    await state.set_state(PostWizard.waiting_for_buttons)

@router.message(PostWizard.waiting_for_buttons)
async def process_buttons(message: types.Message, state: FSMContext):
    kb = None
    if message.text and message.text.lower() != "skip":
        rows = []
        for line in message.text.split("\n"):
            if "-" in line:
                try:
                    p = line.split("-", 1)
                    rows.append([InlineKeyboardButton(text=p[0].strip(), url=p[1].strip())])
                except: continue
        if rows: kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await state.update_data(reply_markup=kb)
    await message.answer("⏳ <b>Step 4:</b> Timer (Hours) or 0.")
    await state.set_state(PostWizard.waiting_for_timer)

@router.message(PostWizard.waiting_for_timer)
async def process_timer(message: types.Message, state: FSMContext):
    try: h = float(message.text)
    except: h = 0
    await state.update_data(timer_hours=h)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📢 Channels Only")], [KeyboardButton(text="👥 Users Only")], [KeyboardButton(text="🚀 Both (All)")]], resize_keyboard=True, one_time_keyboard=True)
    await message.answer("🎯 <b>Target?</b>", reply_markup=kb)
    await state.set_state(PostWizard.waiting_for_target)

@router.message(PostWizard.waiting_for_target)
async def process_target(message: types.Message, state: FSMContext):
    if message.text not in ["📢 Channels Only", "👥 Users Only", "🚀 Both (All)"]:
        await message.answer("❌ Use Buttons"); return
    await state.update_data(target=message.text)
    await message.answer("👀 <b>Send YES to confirm.</b>", reply_markup=ReplyKeyboardRemove())
    await state.set_state(PostWizard.confirmation)

@router.message(PostWizard.confirmation)
async def confirm_send(message: types.Message, state: FSMContext):
    if message.text and message.text.lower() == "yes":
        data = await state.get_data()
        asyncio.create_task(run_broadcast(message.bot, data, data['target'], message.chat.id))
        await message.answer("🚀 Started!")
    else:
        await message.answer("❌ Cancelled.")
    await state.clear()

async def run_broadcast(bot, data, target, admin_chat_id):
    sent = 0
    session = SessionLocal()
    try:
        # Channels
        if target in ["📢 Channels Only", "🚀 Both (All)"]:
            channels = session.query(Channel).filter(Channel.broadcast_enabled == True).all()
            for ch in channels:
                try:
                    if data['media_type'] == 'photo': await bot.send_photo(ch.chat_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    elif data['media_type'] == 'video': await bot.send_video(ch.chat_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    elif data['media_type'] == 'doc': await bot.send_document(ch.chat_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    sent += 1
                except: pass
                await asyncio.sleep(0.05)

        # Users
        if target in ["👥 Users Only", "🚀 Both (All)"]:
            users = session.query(BotUser).all()
            for u in users:
                try:
                    if data['media_type'] == 'photo': await bot.send_photo(u.user_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    elif data['media_type'] == 'video': await bot.send_video(u.user_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    elif data['media_type'] == 'doc': await bot.send_document(u.user_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    sent += 1
                except: pass
                await asyncio.sleep(0.05)
    finally: session.close()
    await bot.send_message(admin_chat_id, f"✅ Done! Sent: {sent}")

# --- Admin Dashboard Handlers ---
@router.callback_query(F.data == "owner_home")
async def back_to_home(c: types.CallbackQuery):
    cap = "<b>Hello Father 🗽</b>\n\n⚙️ <b>Owner Controls:</b>\n/createpost - Broadcast\n/set_topic - Topics\n/start - Menu"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👮 Manage Admins", callback_data="admin_dashboard")], [InlineKeyboardButton(text="📢 Connected Chats", callback_data="list_chats")], [InlineKeyboardButton(text="💎 Premium", callback_data="premium_alert")]])
    await c.message.edit_caption(caption=cap, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "premium_alert")
async def premium_off(c: types.CallbackQuery):
    msg = "💎 <b>Premium</b>\n⚠️ <b>Feature OFF</b>"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back", callback_data="owner_home")]])
    await c.message.edit_caption(caption=msg, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "admin_dashboard")
async def admin_dash(c: types.CallbackQuery):
    if c.from_user.id != OWNER_ID: await c.answer("Denied", show_alert=True); return
    db = get_db()
    try:
        admins = db.query(BotUser).filter(BotUser.is_admin == True).all()
        msg = "👮‍♂️ <b>Admins:</b>\n" + ("".join([f"• <code>{a.user_id}</code>\n" for a in admins]) if admins else "None")
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Add", callback_data="add_admin_action"), InlineKeyboardButton(text="➖ Remove", callback_data="remove_admin_action")], [InlineKeyboardButton(text="🔙 Back", callback_data="owner_home")]])
        await c.message.edit_caption(caption=msg, reply_markup=kb, parse_mode="HTML")
    finally: db.close()

@router.callback_query(F.data == "add_admin_action")
async def ask_admin_id(c: types.CallbackQuery, s: FSMContext):
    await c.message.answer("👤 <b>Send User ID:</b>"); await s.set_state(AdminState.waiting_for_id_add); await c.answer()

@router.message(AdminState.waiting_for_id_add)
async def process_add_admin(m: types.Message, s: FSMContext):
    if not m.text.isdigit(): await m.answer("❌ Numbers only."); return
    db = get_db()
    try:
        uid = int(m.text)
        if not db.query(BotUser).filter(BotUser.user_id == uid).first():
            db.add(BotUser(user_id=uid, is_admin=True)); db.commit(); await m.answer(f"✅ User {uid} Added.")
        else: await m.answer("⚠️ Already added.")
    finally: db.close(); await s.clear()

@router.callback_query(F.data == "remove_admin_action")
async def ask_remove_id(c: types.CallbackQuery, s: FSMContext):
    await c.message.answer("🗑 <b>Send User ID:</b>"); await s.set_state(AdminState.waiting_for_id_remove); await c.answer()

@router.message(AdminState.waiting_for_id_remove)
async def process_remove_admin(m: types.Message, s: FSMContext):
    if not m.text.isdigit(): await m.answer("❌ Invalid ID."); return
    db = get_db()
    try:
        u = db.query(BotUser).filter(BotUser.user_id == int(m.text)).first()
        if u and u.is_admin: u.is_admin = False; db.commit(); await m.answer(f"✅ Removed.")
        else: await m.answer("⚠️ Not an Admin.")
    finally: db.close(); await s.clear()

@router.callback_query(F.data == "list_chats")
async def list_chats(c: types.CallbackQuery):
    if c.from_user.id != OWNER_ID: return
    db = get_db()
    try:
        chans = db.query(Channel).all()
        if not chans: await c.answer("No Chats", show_alert=True); return
        kb = [[InlineKeyboardButton(text=f"{ch.channel_name[:15]}.. [{'✅' if ch.broadcast_enabled else '❌'}]", callback_data=f"manage_chat_{ch.id}")] for ch in chans]
        kb.append([InlineKeyboardButton(text="🔙 Back", callback_data="owner_home")])
        await c.message.edit_caption(caption="📢 <b>Connected Chats</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    finally: db.close()

@router.callback_query(F.data.startswith("manage_chat_"))
async def manage_single_chat(callback: types.CallbackQuery):
    try: cid = int(callback.data.split("_")[2])
    except: return
    db = get_db()
    try:
        ch = db.query(Channel).filter(Channel.id == cid).first()
        if not ch: await list_chats(callback); return
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
            db.delete(ch); db.commit(); await list_chats(c)
        db.close()
    except: pass