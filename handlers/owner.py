from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import Session
from database.models import BotUser, FileRecord
from utils.states import PostWizard
from config.settings import OWNER_ID, LINK_BOT_ID
from database.db import get_db

router = Router()
# 👇 FILTER: Only Content Bot
router.message.filter(F.bot.id == LINK_BOT_ID)
router.callback_query.filter(F.bot.id == LINK_BOT_ID)

class AdminState(StatesGroup):
    waiting_for_id_add = State()
    waiting_for_id_remove = State()

@router.callback_query(F.data == "admin_dashboard")
async def show_admin_dashboard(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID: return
    db = get_db()
    try:
        admins = db.query(BotUser).filter(BotUser.is_admin == True).all()
        msg = "👮‍♂️ <b>Current Admins List:</b>\n\n"
        if not admins: msg += "<i>Koi Admin nahi hai.</i>"
        else:
            for admin in admins:
                msg += f"👤 <a href='tg://user?id={admin.user_id}'>User {admin.user_id}</a>\n"
        msg += "\n👇 <b>Option select karein:</b>"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add", callback_data="add_admin_action"),
             InlineKeyboardButton(text="➖ Remove", callback_data="remove_admin_action")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="owner_home")]
        ])
        await callback.message.edit_text(msg, reply_markup=keyboard, parse_mode="HTML")
    finally:
        db.close()

@router.callback_query(F.data == "owner_home")
async def back_to_home(callback: types.CallbackQuery):
    msg = f"👑 <b>Hello Sir!</b>\nSelect an option:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Manage Admins", callback_data="admin_dashboard")],
        [InlineKeyboardButton(text="💎 Premium Users", callback_data="premium_info")],
        [InlineKeyboardButton(text="📢 Create Post / Broadcast", callback_data="broadcast_info")],
        [InlineKeyboardButton(text="📊 Check Stats", callback_data="stats_info")]
    ])
    await callback.message.edit_text(msg, reply_markup=keyboard)

@router.callback_query(F.data == "premium_info")
async def premium_alert(callback: types.CallbackQuery):
    await callback.answer("🚧 Feature coming soon!", show_alert=True)

@router.callback_query(F.data == "add_admin_action")
async def ask_admin_id(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("👤 <b>New Admin ID bhejein:</b>")
    await state.set_state(AdminState.waiting_for_id_add)
    await callback.answer()

@router.message(AdminState.waiting_for_id_add)
async def process_add_admin(message: types.Message, state: FSMContext):
    db = get_db()
    try:
        new_admin_id = int(message.text)
        user = db.query(BotUser).filter(BotUser.user_id == new_admin_id).first()
        if not user:
            user = BotUser(user_id=new_admin_id, is_admin=True)
            db.add(user)
        else:
            user.is_admin = True
        db.commit()
        await message.answer(f"✅ Success! User {new_admin_id} is now Admin.")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")
    finally:
        db.close()
        await state.clear()

@router.callback_query(F.data == "remove_admin_action")
async def ask_remove_id(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🗑 <b>Admin ID to remove:</b>")
    await state.set_state(AdminState.waiting_for_id_remove)
    await callback.answer()

@router.message(AdminState.waiting_for_id_remove)
async def process_remove_admin(message: types.Message, state: FSMContext):
    db = get_db()
    try:
        target_id = int(message.text)
        user = db.query(BotUser).filter(BotUser.user_id == target_id).first()
        if user and user.is_admin:
            user.is_admin = False
            db.commit()
            await message.answer(f"✅ User {target_id} removed.")
        else:
            await message.answer("⚠️ Not an admin.")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")
    finally:
        db.close()
        await state.clear()

@router.callback_query(F.data == "broadcast_info")
async def trigger_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID: return
    await callback.message.answer("📸 <b>Step 1:</b> Photo/Video bhejein.")
    await state.set_state(PostWizard.waiting_for_media)
    await callback.answer()

@router.callback_query(F.data == "stats_info")
async def show_stats(callback: types.CallbackQuery):
    db = get_db()
    try:
        u = db.query(BotUser).count()
        f = db.query(FileRecord).count()
        await callback.answer(f"📊 Stats:\nUsers: {u}\nFiles: {f}", show_alert=True)
    finally:
        db.close()
