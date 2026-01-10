import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session
from database.models import Channel
from utils.states import PostWizard
from config.settings import OWNER_ID, ADMIN_IDS

router = Router()

# 1. Start Creating Post
@router.message(Command("createpost"))
async def start_post(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS and message.from_user.id != OWNER_ID:
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
    
    await state.update_data(media_id=file_id, media_type=type_)
    await message.answer("📝 <b>Step 2:</b> Ab Post ka <b>Caption (Text)</b> likhein.\n(Agar text nahi chahiye to 'SKIP' likhein)")
    await state.set_state(PostWizard.waiting_for_caption)

# 3. Receive Caption
@router.message(PostWizard.waiting_for_caption)
async def process_caption(message: types.Message, state: FSMContext):
    caption = message.text if message.text.lower() != "skip" else None
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
    if message.text.lower() != "skip":
        rows = []
        lines = message.text.split("\n")
        for line in lines:
            if "-" in line:
                name, url = line.split("-", 1)
                rows.append([InlineKeyboardButton(text=name.strip(), url=url.strip())])
        if rows:
            keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    
    await state.update_data(reply_markup=keyboard)
    
    await message.answer(
        "⏳ <b>Step 4: Auto-Delete Timer</b>\n"
        "Kitne ghante baad delete karna hai? (Example: 24)\n"
        "Agar delete nahi karna to '0' likhein."
    )
    await state.set_state(PostWizard.waiting_for_timer)

# 5. Timer & Preview
@router.message(PostWizard.waiting_for_timer)
async def process_timer(message: types.Message, state: FSMContext):
    try:
        hours = float(message.text)
    except ValueError:
        hours = 0
        
    data = await state.get_data()
    await state.update_data(timer_hours=hours)
    
    # Show Preview
    await message.answer("👀 <b>Preview:</b> Ye post channels me aisi dikhegi:")
    
    method = message.answer_photo if data['media_type'] == 'photo' else message.answer_video
    await method(
        data['media_id'],
        caption=data['caption'],
        reply_markup=data['reply_markup']
    )
    
    await message.answer("Kya main ise sabhi connected channels par bhej du? (YES / NO)")
    await state.set_state(PostWizard.confirmation)

# 6. Final Send
@router.message(PostWizard.confirmation)
async def confirm_send(message: types.Message, state: FSMContext, db: Session):
    if message.text.lower() != "yes":
        await message.answer("❌ Cancelled.")
        await state.clear()
        return

    data = await state.get_data()
    channels = db.query(Channel).all()
    
    if not channels:
        await message.answer("⚠️ Koi Channel connected nahi hai. Bot ko channel me Admin banayein.")
        return

    sent_count = 0
    await message.answer(f"🚀 {len(channels)} Channels par bhej raha hu...")

    for ch in channels:
        try:
            bot = message.bot
            method = bot.send_photo if data['media_type'] == 'photo' else bot.send_video
            
            sent_msg = await method(
                chat_id=ch.chat_id,
                photo=data['media_id'] if data['media_type'] == 'photo' else None,
                video=data['media_id'] if data['media_type'] == 'video' else None,
                caption=data['caption'],
                reply_markup=data['reply_markup']
            )
            sent_count += 1
            
            # Auto Delete Logic (Background Task)
            if data['timer_hours'] > 0:
                asyncio.create_task(delete_later(bot, ch.chat_id, sent_msg.message_id, data['timer_hours']))
                
        except Exception as e:
            print(f"Failed to send to {ch.chat_id}: {e}")

    await message.answer(f"✅ Successfully sent to {sent_count} channels!")
    await state.clear()

async def delete_later(bot, chat_id, message_id, hours):
    await asyncio.sleep(hours * 3600) # Convert hours to seconds
    try:
        await bot.delete_message(chat_id, message_id)
    except:
        pass
