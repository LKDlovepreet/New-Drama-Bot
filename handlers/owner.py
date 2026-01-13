from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import Session
from database.models import BotUser
from config.settings import OWNER_ID

router = Router()

# State Machine for adding admin
class AdminState(StatesGroup):
    waiting_for_id_add = State()
    waiting_for_id_remove = State()

# 1. Add Admin Button Click
@router.callback_query(F.data == "add_admin_action")
async def ask_admin_id(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        return
    await callback.message.answer("👤 <b>New Admin ka Telegram ID bhejein:</b>")
    await state.set_state(AdminState.waiting_for_id_add)
    await callback.answer()

# 2. Process Add Admin ID
@router.message(AdminState.waiting_for_id_add)
async def process_add_admin(message: types.Message, state: FSMContext, db: Session):
    try:
        new_admin_id = int(message.text)
        user = db.query(BotUser).filter(BotUser.user_id == new_admin_id).first()
        
        if not user:
            # Agar user DB me nahi hai, create kar do
            user = BotUser(user_id=new_admin_id, is_admin=True)
            db.add(user)
        else:
            user.is_admin = True
        
        db.commit()
        await message.answer(f"✅ <b>Success!</b> User {new_admin_id} ab Admin hai.")
    except ValueError:
        await message.answer("❌ Invalid ID. Sirf number bhejein.")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")
    
    await state.clear()

# 3. Remove Admin Button Click
@router.callback_query(F.data == "remove_admin_action")
async def ask_remove_id(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        return
    await callback.message.answer("🗑 <b>Kis Admin ko hatana hai? Uski ID bhejein:</b>")
    await state.set_state(AdminState.waiting_for_id_remove)
    await callback.answer()

# 4. Process Remove Admin ID
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
            await message.answer("⚠️ Ye user pehle se Admin nahi hai ya Database me nahi hai.")
            
    except ValueError:
        await message.answer("❌ Invalid ID.")
    
    await state.clear()
