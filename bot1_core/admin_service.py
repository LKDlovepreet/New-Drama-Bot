import uuid
import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command, ChatMemberUpdatedFilter, JOIN_TRANSITION, LEAVE_TRANSITION
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

# ====================================================
# 1. MANAGE ADMINS (Fixed)
# ====================================================
@router.callback_query(F.data == "admin_dashboard")
async def show_admin_dashboard(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Access Denied", show_alert=True)
        return

    db = get_db()
    try:
        admins = db.query(BotUser).filter(BotUser.is_admin == True).all()
        msg = "👮‍♂️ <b>Current Admins:</b>\n\n"
        if not admins:
            msg += "<i>No admins found.</i>"
        else:
            for admin in admins:
                msg += f"• <code>{admin.user_id}</code>\n"
        
        msg += "\n👇 <b>Options:</b>"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Admin", callback_data="add_admin_action"),
             InlineKeyboardButton(text="➖ Remove Admin", callback_data="remove_admin_action")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="delete_msg")]
        ])
        await callback.message.edit_text(msg, reply_markup=keyboard, parse_mode="HTML")
    finally:
        db.close()

@router.callback_query(F.data == "delete_msg")
async def delete_msg(callback: types.CallbackQuery):
    await callback.message.delete()

# --- Add/Remove Handlers ---
@router.callback_query(F.data == "add_admin_action")
async def ask_admin_id(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("👤 <b>Send User ID to make Admin:</b>")
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
        db.commit()
        await message.answer(f"✅ User {uid} is now Admin.")
    except: await message.answer("❌ Invalid ID.")
    finally: db.close(); await state.clear()

@router.callback_query(F.data == "remove_admin_action")
async def ask_remove_id(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🗑 <b>Send User ID to remove:</b>")
    await state.set_state(AdminState.waiting_for_id_remove)
    await callback.answer()

@router.message(AdminState.waiting_for_id_remove)
async def process_remove_admin(message: types.Message, state: FSMContext):
    db = get_db()
    try:
        uid = int(message.text)
        u = db.query(BotUser).filter(BotUser.user_id == uid).first()
        if u: 
            u.is_admin = False; db.commit()
            await message.answer(f"✅ User {uid} removed from Admin.")
        else: await message.answer("⚠️ User not found.")
    except: await message.answer("❌ Invalid ID.")
    finally: db.close(); await state.clear()

# ====================================================
# 2. CONNECTED CHATS MANAGER (New Feature)
# ====================================================
@router.callback_query(F.data == "list_chats")
async def list_connected_chats(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID: return
    
    db = get_db()
    try:
        channels = db.query(Channel).all()
        if not channels:
            await callback.answer("Koi Channel/Group connected nahi hai.", show_alert=True)
            return

        msg = "📢 <b>Connected Chats Manager</b>\n\nClick on a chat to Toggle Broadcast or Leave."
        keyboard = []
        for ch in channels:
            status = "✅ ON" if ch.broadcast_enabled else "❌ OFF"
            btn_text = f"{ch.channel_name} [{status}]"
            # Chat specific menu kholne ke liye callback
            keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"manage_chat_{ch.id}")])
        
        keyboard.append([InlineKeyboardButton(text="🔙 Back", callback_data="delete_msg")])
        await callback.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    finally:
        db.close()

# --- Single Chat Manage Menu ---
@router.callback_query(F.data.startswith("manage_chat_"))
async def manage_single_chat(callback: types.CallbackQuery):
    chat_db_id = int(callback.data.split("_")[2])
    db = get_db()
    try:
        ch = db.query(Channel).filter(Channel.id == chat_db_id).first()
        if not ch:
            await callback.answer("Chat not found in DB.", show_alert=True)
            await list_connected_chats(callback) # Refresh list
            return

        status_text = "✅ Enabled" if ch.broadcast_enabled else "❌ Disabled"
        msg = (
            f"⚙️ <b>Managing:</b> {ch.channel_name}\n"
            f"🆔 ID: <code>{ch.chat_id}</code>\n"
            f"📡 Broadcast: <b>{status_text}</b>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Toggle Broadcast", callback_data=f"toggle_br_{ch.id}")],
            [InlineKeyboardButton(text="📤 Leave & Remove", callback_data=f"leave_chat_{ch.id}")],
            [InlineKeyboardButton(text="🔙 Back to List", callback_data="list_chats")]
        ])
        await callback.message.edit_text(msg, reply_markup=keyboard)
    finally:
        db.close()

# --- Toggle Broadcast ---
@router.callback_query(F.data.startswith("toggle_br_"))
async def toggle_broadcast_status(callback: types.CallbackQuery):
    chat_db_id = int(callback.data.split("_")[2])
    db = get_db()
    try:
        ch = db.query(Channel).filter(Channel.id == chat_db_id).first()
        if ch:
            ch.broadcast_enabled = not ch.broadcast_enabled
            db.commit()
            await callback.answer(f"Broadcast set to {ch.broadcast_enabled}")
            await manage_single_chat(callback) # Refresh menu
        else:
            await callback.answer("Error.", show_alert=True)
    finally:
        db.close()

# --- Leave Chat ---
@router.callback_query(F.data.startswith("leave_chat_"))
async def leave_chat_action(callback: types.CallbackQuery):
    chat_db_id = int(callback.data.split("_")[2])
    db = get_db()
    try:
        ch = db.query(Channel).filter(Channel.id == chat_db_id).first()
        if ch:
            # 1. Telegram se Exit
            try:
                await callback.bot.leave_chat(ch.chat_id)
                await callback.answer("Left channel successfully.")
            except Exception as e:
                await callback.answer(f"Left DB but Error leaving TG: {e}", show_alert=True)

            # 2. Database se Remove
            db.delete(ch)
            db.commit()
            
            # Wapis list par jao
            await list_connected_chats(callback)
        else:
            await callback.answer("Already removed.")
    finally:
        db.close()

# ====================================================
# 3. AUTO-SAVE CHANNELS (MyChatMember Handler)
# ====================================================
@router.my_chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_bot_added_to_channel(event: types.ChatMemberUpdated):
    # Sirf Channels aur Groups me save karein
    if event.chat.type not in ["channel", "supergroup", "group"]:
        return

    db = get_db()
    try:
        # Check if already exists
        exists = db.query(Channel).filter(Channel.chat_id == event.chat.id).first()
        if not exists:
            # Add to DB but Broadcast OFF (Default)
            new_ch = Channel(
                chat_id=event.chat.id,
                channel_name=event.chat.title,
                added_by=event.from_user.id,
                broadcast_enabled=False # Aapne kaha "Direct list me na jode", isliye OFF rakha hai
            )
            db.add(new_ch)
            db.commit()
            
            # Owner ko notify karein (Optional)
            if OWNER_ID:
                await event.bot.send_message(
                    OWNER_ID,
                    f"🔔 <b>New Chat Detected!</b>\n"
                    f"Name: {event.chat.title}\n"
                    f"Type: {event.chat.type}\n"
                    f"⚠️ Broadcast is currently <b>OFF</b>.\n"
                    f"Go to /start -> Connected Chats to enable."
                )
    except Exception as e:
        print(f"DB Error on join: {e}")
    finally:
        db.close()

# ====================================================
# 4. MEDIA SAVING & BROADCAST (Existing Logic)
# ====================================================
# ... (Save media logic same rahega) ...

# Broadcast Logic Update (Sirf Enabled Channels me bheje)
async def run_broadcast(bot, data, target, admin_chat_id):
    sent_count, fail_count = 0, 0
    session = SessionLocal()
    try:
        if target in ["📢 Channels Only", "🚀 Both (All)"]:
            # 👇 FILTER ADDED: Only broadcast_enabled=True
            channels = session.query(Channel).filter(Channel.broadcast_enabled == True).all()
            for ch in channels:
                try:
                    if data['media_type'] == 'photo': 
                        msg = await bot.send_photo(ch.chat_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    else: 
                        msg = await bot.send_video(ch.chat_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    sent_count += 1
                    if data['timer_hours'] > 0: 
                        asyncio.create_task(delete_later(bot, ch.chat_id, msg.message_id, data['timer_hours']))
                except Exception as e:
                    print(f"Fail {ch.channel_name}: {e}")
                    pass
        
        # Users loop same rahega...
        if target in ["👥 Users Only", "🚀 Both (All)"]:
            users = session.query(BotUser).all()
            for user in users:
                try:
                    if data['media_type'] == 'photo': await bot.send_photo(user.user_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    else: await bot.send_video(user.user_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    sent_count += 1
                    await asyncio.sleep(0.05)
                except: fail_count += 1
    finally: session.close()
    await bot.send_message(admin_chat_id, f"✅ Broadcast Done!\nSent: {sent_count}\nFailed: {fail_count}")

async def delete_later(bot, chat_id, message_id, hours):
    await asyncio.sleep(hours * 3600)
    try: await bot.delete_message(chat_id, message_id)
    except: pass

@router.callback_query(F.data == "premium_alert")
async def premium_feature_off(callback: types.CallbackQuery):
    await callback.answer("⚠️ Ye feature abhi OFF hai!", show_alert=True)
    
# Broadcast Wizard Handlers (Copy paste from previous code or let me know if you need them fully written out here)
# (Assuming previous broadcast wizard code is here...)
# ... [Paste Broadcast Wizard Code Here] ...
