import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from database.db import SessionLocal
from database.models import Channel, BotUser
from utils.states import PostWizard
from config.settings import OWNER_ID, ADMIN_IDS

router = Router()

# ... (Step 1 se Step 6 tak SAME rahega) ...
# ... (Sirf 'createpost' se lekar 'run_broadcast' tak ka code wapis paste kar raha hu taaki confusion na ho) ...

# 1. Start Creating Post
@router.message(Command("createpost"))
async def start_post(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS and user_id != OWNER_ID:
        await message.answer(f"❌ <b>Access Denied!</b>\nAapki ID: <code>{user_id}</code>")
        return
    await message.answer("📸 <b>Step 1:</b> Jo Photo/Video post karni hai use bhejein.")
    await state.set_state(PostWizard.waiting_for_media)

# 2. Receive Media
@router.message(PostWizard.waiting_for_media, F.photo | F.video)
async def process_media(message: types.Message, state: FSMContext):
    if message.photo:
        file_id = message.photo[-1].file_id
        type_ = "photo"
    elif message.video:
        file_id = message.video.file_id
        type_ = "video"
    else:
        await message.answer("❌ Sirf Photo ya Video bhejein.")
        return
    await state.update_data(media_id=file_id, media_type=type_)
    await message.answer("📝 <b>Step 2:</b> Caption likhein (ya SKIP).")
    await state.set_state(PostWizard.waiting_for_caption)

# 3. Receive Caption
@router.message(PostWizard.waiting_for_caption)
async def process_caption(message: types.Message, state: FSMContext):
    caption = message.text if message.text and message.text.lower() != "skip" else None
    await state.update_data(caption=caption)
    
    msg = (
        "🔘 <b>Step 3: Buttons Add karein</b>\n\n"
        "Format: <code>Button Name - Link</code>\n"
        "Example:\n"
        "Join Channel - https://t.me/example\n"
        "Download - https://google.com\n\n"
        "Agar buttons nahi chahiye to 'SKIP' likhein."
    )
    await message.answer(msg)
    await state.set_state(PostWizard.waiting_for_buttons)

# 4. Receive Buttons
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

# 5. Timer & Target
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

# 6. Preview Step
@router.message(PostWizard.waiting_for_target)
async def process_target(message: types.Message, state: FSMContext):
    target = message.text
    if target not in ["📢 Channels Only", "👥 Users Only", "🚀 Both (All)"]:
        await message.answer("⚠️ Button se select karein.")
        return
    await state.update_data(target=target)
    data = await state.get_data()
    
    await message.answer("👀 <b>Preview:</b>", reply_markup=ReplyKeyboardRemove())
    try:
        if data['media_type'] == 'photo':
            await message.answer_photo(data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
        else:
            await message.answer_video(data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
    except Exception as e:
        await message.answer(f"Error: {e}")
        return
    await message.answer("Send kar du? (YES/NO)")
    await state.set_state(PostWizard.confirmation)

# 7. Final Sending Logic
@router.message(PostWizard.confirmation)
async def confirm_send(message: types.Message, state: FSMContext):
    if not message.text or message.text.lower() != "yes":
        await message.answer("❌ Cancelled.")
        await state.clear()
        return

    data = await state.get_data()
    target = data['target']
    bot = message.bot
    
    await message.answer("🚀 Broadcasting Started! Background me bhej raha hu...")
    await state.clear()
    asyncio.create_task(run_broadcast(bot, data, target, message.chat.id))

# --- BACKGROUND FUNCTIONS ---
async def run_broadcast(bot, data, target, admin_chat_id):
    sent_count = 0
    fail_count = 0
    
    session = SessionLocal()
    
    try:
        # 1. SEND TO CHANNELS
        if target in ["📢 Channels Only", "🚀 Both (All)"]:
            channels = session.query(Channel).all()
            print(f"📢 Found {len(channels)} Channels") # DEBUG PRINT
            
            for ch in channels:
                try:
                    msg = None
                    if data['media_type'] == 'photo':
                        msg = await bot.send_photo(
                            chat_id=ch.chat_id,
                            photo=data['media_id'],
                            caption=data['caption'],
                            reply_markup=data['reply_markup']
                        )
                    else:
                        msg = await bot.send_video(
                            chat_id=ch.chat_id,
                            video=data['media_id'],
                            caption=data['caption'],
                            reply_markup=data['reply_markup']
                        )
                    sent_count += 1
                    if data['timer_hours'] > 0 and msg:
                        asyncio.create_task(delete_later(bot, ch.chat_id, msg.message_id, data['timer_hours']))
                except Exception as e:
                    print(f"❌ Channel Error ({ch.channel_name}): {e}")

        # 2. SEND TO USERS
        if target in ["👥 Users Only", "🚀 Both (All)"]:
            users = session.query(BotUser).all()
            print(f"👥 Found {len(users)} Users in DB") # DEBUG PRINT
            
            for user in users:
                try:
                    if data['media_type'] == 'photo':
                        await bot.send_photo(
                            chat_id=user.user_id,
                            photo=data['media_id'],
                            caption=data['caption'],
                            reply_markup=data['reply_markup']
                        )
                    else:
                        await bot.send_video(
                            chat_id=user.user_id,
                            video=data['media_id'],
                            caption=data['caption'],
                            reply_markup=data['reply_markup']
                        )
                    sent_count += 1
                    await asyncio.sleep(0.05) 
                except Exception as e:
                    fail_count += 1
                    # 👇 AB ERROR DIKHEGA LOGS MEIN
                    print(f"❌ User Error ({user.user_id}): {e}")
    
    finally:
        session.close()

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
