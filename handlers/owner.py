from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import Session
from database.models import BotUser, FileRecord
from utils.states import PostWizard # 👈 Ye import zaroori hai Post create karne ke liye
from config.settings import OWNER_ID

router = Router()

# State Machine for adding admin
class AdminState(StatesGroup):
    waiting_for_id_add = State()
    waiting_for_id_remove = State()

# --- 1. ADD ADMIN LOGIC ---
@router.callback_query(F.data == "add_admin_action")
async def ask_admin_id(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Sirf Owner ye kar sakta hai!", show_alert=True)
        return
    
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

# --- 2. REMOVE ADMIN LOGIC ---
@router.callback_query(F.data == "remove_admin_action")
async def ask_remove_id(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        return
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

# --- 3. CREATE POST BUTTON (DIRECT START) ---
@router.callback_query(F.data == "broadcast_info")
async def trigger_broadcast(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    # Check karein ki banda Admin/Owner hai ya nahi
    # (Waise to button owner ko hi dikhta hai, par safety ke liye)
    if user_id != OWNER_ID: 
        await callback.answer("Access Denied", show_alert=True)
        return

    # 👇 Direct Post Wizard Start kar rahe hain
    await callback.message.answer("📸 <b>Step 1:</b> Jo Photo/Video post karni hai use bhejein.")
    await state.set_state(PostWizard.waiting_for_media)
    await callback.answer()

# --- 4. STATS BUTTON ---
@router.callback_query(F.data == "stats_info")
async def show_stats(callback: types.CallbackQuery, db: Session):
    user_count = db.query(BotUser).count()
    file_count = db.query(FileRecord).count()
    await callback.answer(f"📊 Live Stats:\n\n👥 Users: {user_count}\n📂 Files: {file_count}", show_alert=True)
