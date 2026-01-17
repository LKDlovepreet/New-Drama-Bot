import uuid
import asyncio
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import get_db, SessionLocal
from database.models import BotUser, Channel
from config.settings import OWNER_ID

router = Router()

class AdminState(StatesGroup):
    waiting_for_id_add = State()
    waiting_for_id_remove = State()

# ====================================================
# 🔄 BACK TO HOME (Main Menu Restore)
# ====================================================
@router.callback_query(F.data == "owner_home")
async def back_to_home(callback: types.CallbackQuery):
    # Wahi Caption jo /start par tha
    caption = (
        "<b>Hello Father 🗽</b>\n\n"
        "⚙️ <b>Owner Controls:</b>\n"
        "/createpost - Broadcast Message\n"
        "/start - Refresh Menu\n"
        "Add me to Channel -> I will auto-detect."
    )
    
    # Wahi Buttons jo /start par the
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👮 Manage Admins", callback_data="admin_dashboard")],
        [InlineKeyboardButton(text="📢 Connected Chats (Add/Remove)", callback_data="list_chats")],
        [InlineKeyboardButton(text="💎 Premium", callback_data="premium_alert")]
    ])
    
    # Photo wahi rahegi, bas caption aur button badlenge
    try:
        await callback.message.edit_caption(caption=caption, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        # Agar photo delete ho gayi ho (purane message me), to naya bhej do
        # (Lekin ab usually edit hi hoga)
        await callback.answer("Menu Refreshed")

# ====================================================
# 1. MANAGE ADMINS (With Edit Caption)
# ====================================================
@router.callback_query(F.data == "admin_dashboard")
async def show_admin_dashboard(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("🚫 Access Denied!", show_alert=True)
        return

    db = get_db()
    try:
        admins = db.query(BotUser).filter(BotUser.is_admin == True).all()
        
        msg = "👮‍♂️ <b>Manage Admins</b>\n\n<b>Current Admins:</b>\n"
        if not admins:
            msg += "<i>No admins added yet.</i>"
        else:
            for admin in admins:
                msg += f"• <code>{admin.user_id}</code>\n"
        
        msg += "\n👇 <b>Select Action:</b>"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Admin", callback_data="add_admin_action"),
             InlineKeyboardButton(text="➖ Remove Admin", callback_data="remove_admin_action")],
            # 👇 Back Button ab 'owner_home' par jayega
            [InlineKeyboardButton(text="🔙 Back", callback_data="owner_home")]
        ])
        
        # ✨ MAGIC: Edit Caption Use Kiya
        await callback.message.edit_caption(caption=msg, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        await callback.answer(f"Error: {e}", show_alert=True)
    finally:
        db.close()

# --- Add Admin Input ---
@router.callback_query(F.data == "add_admin_action")
async def ask_admin_id(callback: types.CallbackQuery, state: FSMContext):
    # Yahan hum edit nahi kar sakte kyunki user ko type karna hai.
    # Isliye naya message bhejenge, user reply karega.
    await callback.message.answer("👤 <b>Send User ID to make Admin:</b>")
    await state.set_state(AdminState.waiting_for_id_add)
    await callback.answer()

@router.message(AdminState.waiting_for_id_add)
async def process_add_admin(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Invalid ID.")
        return

    db = get_db()
    try:
        new_admin_id = int(message.text)
        user = db.query(BotUser).filter(BotUser.user_id == new_admin_id).first()
        if not user:
            user = BotUser(user_id=new_admin_id, is_admin=True); db.add(user)
        else:
            user.is_admin = True
        db.commit()
        await message.answer(f"✅ User {new_admin_id} is now Admin.")
    finally:
        db.close(); await state.clear()

# --- Remove Admin Input ---
@router.callback_query(F.data == "remove_admin_action")
async def ask_remove_id(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🗑 <b>Send User ID to Remove:</b>")
    await state.set_state(AdminState.waiting_for_id_remove)
    await callback.answer()

@router.message(AdminState.waiting_for_id_remove)
async def process_remove_admin(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): await message.answer("❌ Invalid ID."); return
    db = get_db()
    try:
        tid = int(message.text)
        u = db.query(BotUser).filter(BotUser.user_id == tid).first()
        if u and u.is_admin:
            u.is_admin = False; db.commit()
            await message.answer(f"✅ User {tid} removed.")
        else: await message.answer("⚠️ Not an Admin.")
    finally: db.close(); await state.clear()


# ====================================================
# 2. CONNECTED CHATS (With Edit Caption)
# ====================================================

@router.callback_query(F.data == "list_chats")
async def list_connected_chats(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Access Denied", show_alert=True)
        return

    db = get_db()
    try:
        channels = db.query(Channel).all()
        if not channels:
            await callback.answer("Koi Channel Connect nahi hai.", show_alert=True)
            return
            
        msg = "📢 <b>Connected Chats Manager</b>\n\nClick on a chat to Manage:"
        keyboard = []
        
        for ch in channels:
            status = "✅ ON" if ch.broadcast_enabled else "❌ OFF"
            btn_text = f"{ch.channel_name[:15]}.. [{status}]"
            keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"manage_chat_{ch.id}")])
            
        # Back Button -> Home
        keyboard.append([InlineKeyboardButton(text="🔙 Back", callback_data="owner_home")])
        
        # ✨ MAGIC: Edit Caption
        await callback.message.edit_caption(caption=msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
        
    except Exception as e:
        await callback.answer(f"Error: {e}", show_alert=True)
    finally:
        db.close()

# --- Single Chat Manage Menu ---
@router.callback_query(F.data.startswith("manage_chat_"))
async def manage_single_chat(callback: types.CallbackQuery):
    try:
        chat_db_id = int(callback.data.split("_")[2])
    except:
        await callback.answer("Error parsing ID", show_alert=True); return

    db = get_db()
    try:
        ch = db.query(Channel).filter(Channel.id == chat_db_id).first()
        if not ch:
            await callback.answer("Chat Removed", show_alert=True)
            await list_connected_chats(callback)
            return

        status_text = "✅ Enabled" if ch.broadcast_enabled else "❌ Disabled"
        
        msg = (
            f"⚙️ <b>Managing:</b> {ch.channel_name}\n"
            f"🆔 ID: <code>{ch.chat_id}</code>\n"
            f"📡 Broadcast: <b>{status_text}</b>\n\n"
            f"<i>Broadcast ON karne par hi /createpost isme message bhejega.</i>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Toggle Broadcast", callback_data=f"toggle_br_{ch.id}")],
            [InlineKeyboardButton(text="📤 Leave & Exit", callback_data=f"leave_chat_{ch.id}")],
            # Back Button -> Chat List (Not Home)
            [InlineKeyboardButton(text="🔙 Back to List", callback_data="list_chats")]
        ])
        
        # ✨ MAGIC: Edit Caption
        await callback.message.edit_caption(caption=msg, reply_markup=keyboard, parse_mode="HTML")

    finally:
        db.close()

# --- Toggle Broadcast ---
@router.callback_query(F.data.startswith("toggle_br_"))
async def toggle_broadcast_status(callback: types.CallbackQuery):
    try:
        chat_db_id = int(callback.data.split("_")[2])
        db = get_db()
        ch = db.query(Channel).filter(Channel.id == chat_db_id).first()
        if ch:
            ch.broadcast_enabled = not ch.broadcast_enabled
            db.commit()
            # Refresh Menu (Edit Caption apne aap manage_single_chat me ho jayega)
            await manage_single_chat(callback) 
        else:
            await callback.answer("Chat not found", show_alert=True)
        db.close()
    except Exception as e:
        print(f"Toggle Error: {e}")

# --- Leave Chat Logic ---
@router.callback_query(F.data.startswith("leave_chat_"))
async def leave_chat_action(callback: types.CallbackQuery):
    chat_db_id = int(callback.data.split("_")[2])
    db = get_db()
    try:
        ch = db.query(Channel).filter(Channel.id == chat_db_id).first()
        if ch:
            try:
                await callback.bot.leave_chat(ch.chat_id)
            except: pass
            db.delete(ch)
            db.commit()
            # Wapis List par jao
            await list_connected_chats(callback)
        else:
            await callback.answer("Already removed.")
    finally:
        db.close()
