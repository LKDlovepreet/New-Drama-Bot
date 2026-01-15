import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from database.db import SessionLocal
from database.models import Channel, BotUser
from utils.states import PostWizard
from config.settings import OWNER_ID, ADMIN_IDS, LINK_BOT_ID

router = Router()
# 👇 FILTER: Only Link Bot
router.message.filter(F.bot.id == LINK_BOT_ID)

# 1. Start Creating Post
@router.message(Command("createpost"))
async def start_post(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS and user_id != OWNER_ID:
        return
    await message.answer("📸 <b>Step 1:</b> Jo Photo/Video post karni hai use bhejein.")
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
        await message.answer("❌ Sirf Photo ya Video bhejein.")
        return
    await state.update_data(media_id=file_id, media_type=type_)
    await message.answer("📝 <b>Step 2:</b> Caption likhein (ya SKIP).")
    await state.set_state(PostWizard.waiting_for_caption)

@router.message(PostWizard.waiting_for_caption)
async def process_caption(message: types.Message, state: FSMContext):
    caption = message.text if message.text and message.text.lower() != "skip" else None
    await state.update_data(caption=caption)
    msg = "🔘 <b>Step 3:</b> Buttons (Name - Link) or SKIP."
    await message.answer(msg)
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
        if rows: keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
    await state.update_data(reply_markup=keyboard)
    await message.answer("⏳ <b>Step 4:</b> Timer (Hours) or 0.")
    await state.set_state(PostWizard.waiting_for_timer)

@router.message(PostWizard.waiting_for_timer)
async def process_timer(message: types.Message, state: FSMContext):
    try: hours = float(message.text)
    except: hours = 0
    await state.update_data(timer_hours=hours)
    keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📢 Channels Only")], [KeyboardButton(text="👥 Users Only")], [KeyboardButton(text="🚀 Both (All)")]], resize_keyboard=True, one_time_keyboard=True)
    await message.answer("🎯 <b>Target?</b>", reply_markup=keyboard)
    await state.set_state(PostWizard.waiting_for_target)

@router.message(PostWizard.waiting_for_target)
async def process_target(message: types.Message, state: FSMContext):
    target = message.text
    if target not in ["📢 Channels Only", "👥 Users Only", "🚀 Both (All)"]: return
    await state.update_data(target=target)
    data = await state.get_data()
    await message.answer("👀 <b>Preview:</b>", reply_markup=ReplyKeyboardRemove())
    try:
        if data['media_type'] == 'photo': await message.answer_photo(data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
        else: await message.answer_video(data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
    except Exception as e: await message.answer(f"Error: {e}")
    await message.answer("Send? (YES / NO)")
    await state.set_state(PostWizard.confirmation)

@router.message(PostWizard.confirmation)
async def confirm_send(message: types.Message, state: FSMContext):
    if not message.text or message.text.lower() != "yes":
        await message.answer("❌ Cancelled.")
        await state.clear()
        return
    data = await state.get_data()
    target = data['target']
    bot = message.bot
    await message.answer("🚀 Broadcasting...")
    await state.clear()
    asyncio.create_task(run_broadcast(bot, data, target, message.chat.id))

async def run_broadcast(bot, data, target, admin_chat_id):
    sent_count, fail_count = 0, 0
    session = SessionLocal()
    try:
        if target in ["📢 Channels Only", "🚀 Both (All)"]:
            channels = session.query(Channel).all()
            for ch in channels:
                try:
                    if data['media_type'] == 'photo': msg = await bot.send_photo(ch.chat_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    else: msg = await bot.send_video(ch.chat_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    sent_count += 1
                    if data['timer_hours'] > 0: asyncio.create_task(delete_later(bot, ch.chat_id, msg.message_id, data['timer_hours']))
                except: pass
        if target in ["👥 Users Only", "🚀 Both (All)"]:
            users = session.query(BotUser).all()
            for user in users:
                try:
                    if data['media_type'] == 'photo': await bot.send_photo(user.user_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    else: await bot.send_video(user.user_id, data['media_id'], caption=data['caption'], reply_markup=data['reply_markup'])
                    sent_count += 1
                    await asyncio.sleep(0.05)
                except: fail_count += 1
    finally: session.close()
    await bot.send_message(admin_chat_id, f"✅ Done!\nSent: {sent_count}\nFailed: {fail_count}")

async def delete_later(bot, chat_id, message_id, hours):
    await asyncio.sleep(hours * 3600)
    try: await bot.delete_message(chat_id, message_id)
    except: pass
