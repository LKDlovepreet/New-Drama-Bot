import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from sqlalchemy.orm import Session
from database.models import Channel, BotUser # <-- BotUser import kiya
from utils.states import PostWizard
from config.settings import OWNER_ID, ADMIN_IDS

router = Router()

# ... (Step 1 se Step 4 tak ka code SAME rahega: Media, Caption, Buttons) ...

# ... (Previous Code for Buttons Step) ...

# 5. Timer ke baad -> Target Selection (NEW STEP)
@router.message(PostWizard.waiting_for_timer)
async def process_timer(message: types.Message, state: FSMContext):
    try:
        hours = float(message.text)
    except ValueError:
        hours = 0
    
    await state.update_data(timer_hours=hours)
    
    # Target puchne ke liye Keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📢 Channels Only")],
            [KeyboardButton(text="👥 Users Only")],
            [KeyboardButton(text="🚀 Both (All)")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        "🎯 <b>Target Select Karein:</b>\n"
        "Ye post kisko bhejni hai?", 
        reply_markup=keyboard
    )
    await state.set_state(PostWizard.waiting_for_target)

# 6. Preview Step
@router.message(PostWizard.waiting_for_target)
async def process_target(message: types.Message, state: FSMContext):
    target = message.text
    if target not in ["📢 Channels Only", "👥 Users Only", "🚀 Both (All)"]:
        await message.answer("Please button use karke select karein.")
        return

    await state.update_data(target=target)

    # Preview dikhana
    data = await state.get_data()
    await message.answer("👀 <b>Preview:</b> Ye post aisi dikhegi:", reply_markup=ReplyKeyboardRemove())
    
    method = message.answer_photo if data['media_type'] == 'photo' else message.answer_video
    await method(
        data['media_id'],
        caption=data['caption'],
        reply_markup=data['reply_markup']
    )
    
    await message.answer("Kya main ise send kar du? (YES / NO)")
    await state.set_state(PostWizard.confirmation)

# 7. Final Sending Logic (POWERFUL BROADCAST)
@router.message(PostWizard.confirmation)
async def confirm_send(message: types.Message, state: FSMContext, db: Session):
    if message.text.lower() != "yes":
        await message.answer("❌ Cancelled.")
        await state.clear()
        return

    data = await state.get_data()
    target = data['target']
    bot = message.bot
    
    await message.answer("🚀 Broadcasting Started! Background me bhej raha hu...")
    await state.clear()

    # Background Task start karte hain taaki bot hang na ho
    asyncio.create_task(run_broadcast(bot, db, data, target, message.chat.id))

# --- BACKGROUND BROADCAST FUNCTION ---
async def run_broadcast(bot, db, data, target, admin_chat_id):
    sent_count = 0
    fail_count = 0
    
    # 1. SEND TO CHANNELS
    if target in ["📢 Channels Only", "🚀 Both (All)"]:
        channels = db.query(Channel).all()
        for ch in channels:
            try:
                method = bot.send_photo if data['media_type'] == 'photo' else bot.send_video
                msg = await method(
                    chat_id=ch.chat_id,
                    photo=data['media_id'] if data['media_type'] == 'photo' else None,
                    video=data['media_id'] if data['media_type'] == 'video' else None,
                    caption=data['caption'],
                    reply_markup=data['reply_markup']
                )
                sent_count += 1
                # Timer Logic
                if data['timer_hours'] > 0:
                    asyncio.create_task(delete_later(bot, ch.chat_id, msg.message_id, data['timer_hours']))
            except Exception as e:
                print(f"Channel Error: {e}")

    # 2. SEND TO USERS (BROADCAST)
    if target in ["👥 Users Only", "🚀 Both (All)"]:
        users = db.query(BotUser).all()
        for user in users:
            try:
                method = bot.send_photo if data['media_type'] == 'photo' else bot.send_video
                await method(
                    chat_id=user.user_id,
                    photo=data['media_id'] if data['media_type'] == 'photo' else None,
                    video=data['media_id'] if data['media_type'] == 'video' else None,
                    caption=data['caption'],
                    reply_markup=data['reply_markup']
                )
                sent_count += 1
                await asyncio.sleep(0.05) # Flood wait bachane ke liye (20 msg/sec)
            except Exception:
                fail_count += 1 # User ne block kiya hoga
    
    # Admin ko report bhejo
    await bot.send_message(
        admin_chat_id, 
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"🎯 Target: {target}\n"
        f"✅ Sent: {sent_count}\n"
        f"❌ Failed/Blocked: {fail_count}"
    )

async def delete_later(bot, chat_id, message_id, hours):
    await asyncio.sleep(hours * 3600)
    try:
        await bot.delete_message(chat_id, message_id)
    except:
        pass
