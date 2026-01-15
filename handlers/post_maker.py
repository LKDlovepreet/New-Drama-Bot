import asyncio
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from database.db import SessionLocal
from database.models import Channel, BotUser
from utils.states import PostWizard
from config.settings import OWNER_ID, ADMIN_IDS, LINK_BOT_ID

router = Router()
# 👇 FILTER: Only Content Bot
router.message.filter(F.bot.id == LINK_BOT_ID)

# ... (Is file ka baaki content same rahega jo pehle diya tha, bas import me LINK_BOT_ID check kar lein) ...
# Agar aapko poora content chahiye to bata dena, waise logic same hai.
