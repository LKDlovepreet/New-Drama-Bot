import asyncio
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION

from database.db import get_db, SessionLocal
from database.models import BotUser, Channel
from config.settings import OWNER_ID

router = Router()

class AdminState(StatesGroup):
    waiting_for_id_add = State()
    waiting_for_id_remove = State()

# --- 1. MANAGE ADMINS BUTTON LOGIC ---
@router.callback_query(F.data == "admin_dashboard")
async def show_admin_dashboard(callback: types.CallbackQuery):
    # Security Check
    if callback.from_user.id != OWNER_ID:
        await callback.answer("🚫 Access Denied! Only Owner can use this.", show_alert=True)
        return

    db = get_db()
    try:
        admins = db.query(BotUser).filter(BotUser.is_admin == True).all()
        
        msg = "👮‍♂️ <b>Manage Admins</b>\n\nCurrent Admins:\n"
        if not admins:
            msg += "<i>No admins added yet.</i>"
        else:
            for admin in admins:
                # Telegram Link format
                msg += f"• <a href='tg://user?id={admin.user_id}'>{admin.user_id}</a>\n"
        
        msg += "\n👇 <b>Select Action:</b>"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Admin", callback_data="add_admin_action"),
             InlineKeyboardButton(text="➖ Remove Admin", callback_data="remove_admin_action")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="delete_msg")]
        ])
        
        # Message Edit karein
        await callback.message.edit_text(msg, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        await callback.answer(f"Error: {str(e)}", show_alert=True)
    finally:
        db.close()

# --- Delete Message Helper ---
@router.callback_query(F.data == "delete_msg")
async def delete_msg(callback: types.CallbackQuery):
    await callback.message.delete()

# --- Add Admin Logic ---
@router.callback_query(F.data == "add_admin_action")
async def ask_admin_id(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("👤 <b>Send the Telegram User ID to make Admin:</b>")
    await state.set_state(AdminState.waiting_for_id_add)
    await callback.answer()

@router.message(AdminState.waiting_for_id_add)
async def process_add_admin(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Invalid ID. Please send numbers only.")
        return

    db = get_db()
    try:
        new_admin_id = int(message.text)
        user = db.query(BotUser).filter(BotUser.user_id == new_admin_id).first()
        
        if not user:
            # Create new user if not exists
            user = BotUser(user_id=new_admin_id, is_admin=True)
            db.add(user)
        else:
            user.is_admin = True
        
        db.commit()
        await message.answer(f"✅ <b>Success!</b> User <code>{new_admin_id}</code> is now an Admin.")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")
    finally:
        db.close()
        await state.clear()

# --- Remove Admin Logic ---
@router.callback_query(F.data == "remove_admin_action")
async def ask_remove_id(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🗑 <b>Send the Telegram User ID to Remove:</b>")
    await state.set_state(AdminState.waiting_for_id_remove)
    await callback.answer()

@router.message(AdminState.waiting_for_id_remove)
async def process_remove_admin(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Invalid ID.")
        return

    db = get_db()
    try:
        target_id = int(message.text)
        user = db.query(BotUser).filter(BotUser.user_id == target_id).first()
        
        if user and user.is_admin:
            user.is_admin = False
            db.commit()
            await message.answer(f"✅ User <code>{target_id}</code> removed from Admins.")
        else:
            await message.answer("⚠️ This user is not an Admin.")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")
    finally:
        db.close()
        await state.clear()


# ====================================================
# 2. CONNECTED CHATS (Channels/Groups Manager)
# ====================================================

@router.callback_query(F.data == "list_channels_bot1")
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
            
        msg = "📢 <b>Connected Chats Manager</b>\n\nClick on a chat to Manage settings (Broadcast/Leave)."
        keyboard = []
        
        for ch in channels:
            status = "✅ ON" if ch.broadcast_enabled else "❌ OFF"
            # Button Text: "Channel Name [ON]"
            btn_text = f"{ch.channel_name[:20]} [{status}]"
            # Callback: manage_chat_1, manage_chat_2 etc.
            keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"manage_chat_{ch.id}")])
            
        keyboard.append([InlineKeyboardButton(text="🔙 Close", callback_data="delete_msg")])
        
        await callback.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
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
        await callback.answer("Invalid Data", show_alert=True); return

    db = get_db()
    try:
        ch = db.query(Channel).filter(Channel.id == chat_db_id).first()
        if not ch:
            await callback.answer("Chat Removed from DB", show_alert=True)
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
            [InlineKeyboardButton(text="🔙 Back to List", callback_data="list_channels_bot1")]
        ])
        
        await callback.message.edit_text(msg, reply_markup=keyboard, parse_mode="HTML")
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
            # Flip status (True -> False, False -> True)
            ch.broadcast_enabled = not ch.broadcast_enabled
            db.commit()
            await callback.answer(f"Broadcast set to {ch.broadcast_enabled}")
            # Refresh the menu to show new status
            await manage_single_chat(callback) 
        else:
            await callback.answer("Chat not found", show_alert=True)
    finally:
        db.close()

# --- Leave Chat Logic ---
@router.callback_query(F.data.startswith("leave_chat_"))
async def leave_chat_action(callback: types.CallbackQuery):
    chat_db_id = int(callback.data.split("_")[2])
    db = get_db()
    try:
        ch = db.query(Channel).filter(Channel.id == chat_db_id).first()
        if ch:
            # 1. Telegram se Leave karein
            try:
                await callback.bot.leave_chat(ch.chat_id)
                await callback.answer("Left channel successfully.")
            except Exception as e:
                await callback.answer(f"Error leaving TG: {e}", show_alert=True)

            # 2. Database se Remove karein
            db.delete(ch)
            db.commit()
            
            # Wapis list par
            await list_connected_chats(callback)
        else:
            await callback.answer("Already removed.")
    finally:
        db.close()


# ====================================================
# 3. AUTO-DETECT CHANNELS (Jab Bot Add Ho)
# ====================================================
@router.my_chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_bot_added(event: types.ChatMemberUpdated):
    # Sirf Channels/Groups ke liye
    if event.chat.type not in ["channel", "supergroup", "group"]:
        return

    db = get_db()
    try:
        exists = db.query(Channel).filter(Channel.chat_id == event.chat.id).first()
        if not exists:
            # DB me add karo par Broadcast OFF rakho (Safety ke liye)
            new_ch = Channel(
                chat_id=event.chat.id,
                channel_name=event.chat.title,
                added_by=event.from_user.id,
                broadcast_enabled=False 
            )
            db.add(new_ch)
            db.commit()
            
            # Owner ko notification
            if OWNER_ID:
                try:
                    await event.bot.send_message(
                        OWNER_ID,
                        f"🔔 <b>New Channel Detected!</b>\n"
                        f"Name: {event.chat.title}\n"
                        f"Status: Broadcast OFF (Enable from /start -> Connected Chats)"
                    )
                except: pass
    except Exception as e:
        print(f"Join Error: {e}")
    finally:
        db.close()
