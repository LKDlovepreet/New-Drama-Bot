import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from sqlalchemy.orm import Session
# 👇 SessionLocal import karna zaroori hai (Naya connection banane ke liye)
from database.db import SessionLocal
from database.models import Channel, BotUser
from utils.states import PostWizard
from config.settings import OWNER_ID, ADMIN_IDS

router = Router()

# ... (Step 1 se Step 6 tak ka code SAME rahega) ...
# ... (Sirf confirm_send aur run_broadcast change honge) ...

# 1. Start Post
@router.message(Command("createpost"))
async def start_post(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS and user_id != OWNER_ID:
        await message.answer(f"❌ <b>Access Denied!</b>\nAapki ID: <code>{user_id}</code>")
        return
    await message.answer("📸 <b>Step 1:</b> Photo/Video bhejein.")
    await state.set_state(PostWizard.waiting_for_media)

@router.message(PostWizard.waiting_for_media, F.photo | F.video)
async def process_media(message: types.Message, state: FSMContext):
    if message.photo:
        file_id = message.photo[-1].file_id
        type_ = "photo"
    elif message.video:
        file_id = message.video.file_id
        type_ = "video"
    else:
        return
    await state.update_data(media_id=file_id, media_type=type_)
    await message.answer("📝 <b>Step 2:</b> Caption likhein (ya SKIP).")
    await state.set_state(PostWizard.waiting_for_caption)

@router.message(PostWizard.waiting_for_caption)
async def process_caption(message: types.Message, state: FSMContext):
    caption = message.text if message.text and message.text.lower() != "skip" else None
    await state.update_data(caption=caption)
    await message.answer("🔘 <b>Step 3:</b> Buttons bhejein (Name - Link) ya SKIP.")
    await state.set_state(PostWizard.waiting_for_buttons)

@router.message(PostWizard.waiting_for_buttons)
async def process_buttons(message: types.Message, state: FSMContext):
    keyboard = None
    if message.text and message.text.lower() != "skip":
        rows = []
        for line in message.text.split("\n"):
            if "-" in line:
                parts = line.split("-", 1)
                if len(parts) == 2:
                    rows.append([InlineKeyboardButton(text=parts[0].strip(), url=parts[1].strip())])
        if rows:
            keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    await state.update_data(reply_markup=keyboard)
    await message.answer("⏳ <b>Step 4:</b> Timer set karein (Hours) ya 0.")
    await state.set_state(PostWizard.waiting_for_timer)

@router.message(PostWizard.waiting_for_timer)
async def process_timer(message: types.Message, state: FSMContext):
    try:
        hours = float(message.text)
    except:
        hours = 0
    await state.update_data(timer_hours=hours)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📢 Channels Only")], [KeyboardButton(text="👥 Users Only")], [KeyboardButton(text="🚀 Both (All)")]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await message.answer("🎯 <b>Target Select Karein:</b>", reply_markup=keyboard)
    await state.set_state(PostWizard.waiting_for_target)

@router.message(PostWizard.waiting_for_target)
async def process_target(message: types.Message, state: FSMContext):
    target = message.text
    if target not in ["📢 Channels Only", "👥 Users Only", "🚀 Both (All)"]:
        await message.answer("⚠️ Button se select karein.")
        return
    await state.update_data(target=target)
    data = await state.get_data()
    await message.answer("👀 <b>Preview:</b>", reply_markup=ReplyKeyboardRemove())
    method = message.answer_photo if data['media_type'] == 'photo' else message.answer_video
    try:
        await method(data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
    except Exception as e:
        await message.answer(f"Error: {e}")
        return
    await message.answer("Send kar du? (YES/NO)")
    await state.set_state(PostWizard.confirmation)

# 7. Final Sending Logic
@router.message(PostWizard.confirmation)
async def confirm_send(message: types.Message, state: FSMContext):
    # Note: Yahan hum 'db' session nahi le rahe, background task apna session khud banayega
    if not message.text or message.text.lower() != "yes":
        await message.answer("❌ Cancelled.")
        await state.clear()
        return

    data = await state.get_data()
    target = data['target']
    bot = message.bot
    
    await message.answer("🚀 Broadcasting Started! Background me bhej raha hu...")
    await state.clear()

    # 👇 Yahan hum db pass nahi kar rahe hain
    asyncio.create_task(run_broadcast(bot, data, target, message.chat.id))

# --- BACKGROUND FUNCTIONS ---
async def run_broadcast(bot, data, target, admin_chat_id):
    sent_count = 0
    fail_count = 0
    
    # 👇 SOLUTION: Naya DB Session yahan open karein
    with SessionLocal() as db:
        
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
                    if data['timer_hours'] > 0:
                        asyncio.create_task(delete_later(bot, ch.chat_id, msg.message_id, data['timer_hours']))
                except Exception as e:
                    print(f"Channel Error: {e}")

        # 2. SEND TO USERS
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
                    await asyncio.sleep(0.05) # Flood wait prevention
                except Exception:
                    fail_count += 1 
    
    # Report bhejein
    await bot.send_message(
        admin_chat_id, 
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"🎯 Target: {target}\n"
        f"✅ Sent: {sent_count}\n"
        f"❌ Failed: {fail_count}"
    )

async def delete_later(bot, chat_id, message_id, hours):
    await asyncio.sleep(hours * 3600)
    try:
        await bot.delete_message(chat_id, message_id)
    except:
        pass
