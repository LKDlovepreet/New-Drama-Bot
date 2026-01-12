import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from sqlalchemy.orm import Session
from database.models import Channel, BotUser
from utils.states import PostWizard
from config.settings import OWNER_ID, ADMIN_IDS

# 👇 Ye line missing thi, isliye error aa raha tha
router = Router()

# handlers/post_maker.py

# ... (Imports same rahenge) ...

# 1. Start Creating Post
@router.message(Command("createpost"))
async def start_post(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # 👇 DEBUG PRINT (Logs me dikhega)
    print(f"🔍 DEBUG CHECK: User ID: {user_id}")
    print(f"🔍 DEBUG CONFIG: Owner: {OWNER_ID} | Admins: {ADMIN_IDS}")

    # Security Check
    if user_id not in ADMIN_IDS and user_id != OWNER_ID:
        # 👇 Ab Bot Chup nahi rahega, bata dega ki dikkat hai
        await message.answer(f"❌ <b>Access Denied!</b>\nAap Admin nahi hain.\nAapki ID: <code>{user_id}</code>")
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
    await message.answer("📝 <b>Step 2:</b> Ab Post ka <b>Caption (Text)</b> likhein.\n(Agar text nahi chahiye to 'SKIP' likhein)")
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
        lines = message.text.split("\n")
        for line in lines:
            if "-" in line:
                parts = line.split("-", 1)
                if len(parts) == 2:
                    name, url = parts
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

# 5. Timer & Target Selection
@router.message(PostWizard.waiting_for_timer)
async def process_timer(message: types.Message, state: FSMContext):
    try:
        hours = float(message.text)
    except ValueError:
        hours = 0
    
    await state.update_data(timer_hours=hours)
    
    # Target Selection Keyboard
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
        await message.answer("⚠️ Please niche diye gaye buttons se select karein.")
        return

    await state.update_data(target=target)

    # Preview dikhana
    data = await state.get_data()
    await message.answer("👀 <b>Preview:</b> Ye post aisi dikhegi:", reply_markup=ReplyKeyboardRemove())
    
    method = message.answer_photo if data['media_type'] == 'photo' else message.answer_video
    try:
        await method(
            data['media_id'],
            caption=data['caption'],
            reply_markup=data['reply_markup']
        )
    except Exception as e:
        await message.answer(f"❌ Error in preview: {e}")
        return
    
    await message.answer("Kya main ise send kar du? (YES / NO)")
    await state.set_state(PostWizard.confirmation)

# 7. Final Sending Logic
@router.message(PostWizard.confirmation)
async def confirm_send(message: types.Message, state: FSMContext, db: Session):
    if not message.text or message.text.lower() != "yes":
        await message.answer("❌ Cancelled.")
        await state.clear()
        return

    data = await state.get_data()
    target = data['target']
    bot = message.bot
    
    await message.answer("🚀 Broadcasting Started! Background me bhej raha hu...")
    await state.clear()

    # Background Task Run
    asyncio.create_task(run_broadcast(bot, db, data, target, message.chat.id))

# --- BACKGROUND FUNCTIONS ---
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
