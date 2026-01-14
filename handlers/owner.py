from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import Session
from database.models import BotUser, FileRecord
from utils.states import PostWizard
from config.settings import OWNER_ID

router = Router()

class AdminState(StatesGroup):
    waiting_for_id_add = State()
    waiting_for_id_remove = State()

# --- 1. ADMIN DASHBOARD (LIST SHOW KARNA) ---
@router.callback_query(F.data == "admin_dashboard")
async def show_admin_dashboard(callback: types.CallbackQuery, db: Session):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Access Denied", show_alert=True)
        return

    # Database se saare admins nikalein
    admins = db.query(BotUser).filter(BotUser.is_admin == True).all()
    
    msg = "👮‍♂️ <b>Current Admins List:</b>\n\n"
    
    if not admins:
        msg += "<i>Koi Admin nahi hai.</i>"
    else:
        for admin in admins:
            # HTML Link format: <a href="tg://user?id=123">Name</a>
            msg += f"👤 <a href='tg://user?id={admin.user_id}'>User {admin.user_id}</a>\n"
            
    msg += "\n👇 <b>Niche se option select karein:</b>"

    # Buttons: Add | Remove | Back
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Add", callback_data="add_admin_action"),
            InlineKeyboardButton(text="➖ Remove", callback_data="remove_admin_action")
        ],
        [InlineKeyboardButton(text="🔙 Back", callback_data="owner_home")]
    ])
    
    # Message Edit karein (Naya message bhejne ki jagah purana update hoga)
    await callback.message.edit_text(msg, reply_markup=keyboard, parse_mode="HTML")

# --- 2. BACK TO HOME LOGIC ---
@router.callback_query(F.data == "owner_home")
async def back_to_home(callback: types.CallbackQuery):
    msg = (
        f"👑 <b>Hello Sir!</b>\n"
        f"Welcome back to your Bot Control Center.\n\n"
        f"⚙️ <b>Select an option:</b>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Manage Admins", callback_data="admin_dashboard")],
        [InlineKeyboardButton(text="💎 Premium Users", callback_data="premium_info")],
        [InlineKeyboardButton(text="📢 Create Post / Broadcast", callback_data="broadcast_info")],
        [InlineKeyboardButton(text="📊 Check Stats", callback_data="stats_info")]
    ])
    await callback.message.edit_text(msg, reply_markup=keyboard)

# --- 3. PREMIUM INFO BUTTON ---
@router.callback_query(F.data == "premium_info")
async def premium_alert(callback: types.CallbackQuery):
    await callback.answer("🚧 Ye feature future me aayega!\nAbhi working progress me hai.", show_alert=True)

# --- 4. ADD ADMIN LOGIC ---
@router.callback_query(F.data == "add_admin_action")
async def ask_admin_id(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("👤 <b>New Admin ka Telegram ID bhejein:</b>")
    await state.set_state(AdminState.waiting_for_id_add)
    await callback.answer()

@router.message(AdminState.waiting_for_id_add)
async def process_add_admin(message: types.Message, state: FSMContext, db: Session):
    try:
        new_admin_id = int(message.text)
        user = db.query(BotUser).filter(BotUser.user_id == new_admin_id).first()
        
        if not user:
            user = BotUser(user_id=new_admin_id, is_admin=True)
            db.add(user)
        else:
            user.is_admin = True
        
        db.commit()
        await message.answer(f"✅ <b>Success!</b> User <code>{new_admin_id}</code> ab Admin hai.")
    except ValueError:
        await message.answer("❌ Invalid ID. Sirf number bhejein.")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")
    
    await state.clear()

# --- 5. REMOVE ADMIN LOGIC ---
@router.callback_query(F.data == "remove_admin_action")
async def ask_remove_id(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🗑 <b>Kis Admin ko hatana hai? Uski ID bhejein:</b>")
    await state.set_state(AdminState.waiting_for_id_remove)
    await callback.answer()

@router.message(AdminState.waiting_for_id_remove)
async def process_remove_admin(message: types.Message, state: FSMContext, db: Session):
    try:
        target_id = int(message.text)
        user = db.query(BotUser).filter(BotUser.user_id == target_id).first()
        
        if user and user.is_admin:
            user.is_admin = False
            db.commit()
            await message.answer(f"✅ User {target_id} ab Admin nahi hai.")
        else:
            await message.answer("⚠️ Ye user pehle se Admin nahi hai.")
    except ValueError:
        await message.answer("❌ Invalid ID.")
    
    await state.clear()

# --- 6. OTHER CONTROLS ---
@router.callback_query(F.data == "broadcast_info")
async def trigger_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID: 
        await callback.answer("Access Denied", show_alert=True)
        return
    await callback.message.answer("📸 <b>Step 1:</b> Jo Photo/Video post karni hai use bhejein.")
    await state.set_state(PostWizard.waiting_for_media)
    await callback.answer()

@router.callback_query(F.data == "stats_info")
async def show_stats(callback: types.CallbackQuery, db: Session):
    user_count = db.query(BotUser).count()
    file_count = db.query(FileRecord).count()
    await callback.answer(f"📊 Live Stats:\n\n👥 Users: {user_count}\n📂 Files: {file_count}", show_alert=True)
