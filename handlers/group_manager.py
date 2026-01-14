from aiogram import Router, F, types
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION
from sqlalchemy.orm import Session
from sqlalchemy import or_
from database.db import SessionLocal
from database.models import GroupSettings, FileRecord
from config.settings import MESSAGES

router = Router()

# 👇 STOP WORDS: In shabdon ko search me ignore kiya jayega
STOP_WORDS = [
    "chahiye", "plz", "pls", "please", "admin", "bhai", "sir", "bro", 
    "upload", "kardo", "hai", "kya", "milegi", "link", "do", "send", 
    "movies", "movie", "series", "season", "episode", "download", 
    "hi", "hello", "koi", "hai", "me", "ko", "ki", "ka"
]

def clean_query(text):
    """Message me se faltu words hatata hai"""
    words = text.lower().split()
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    return " ".join(keywords)

# --- 1. WELCOME MESSAGE HANDLER ---
@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_user_join(event: types.ChatMemberUpdated):
    # Sirf Group me kaam kare
    if event.chat.type not in ["group", "supergroup"]:
        return

    session = SessionLocal()
    try:
        # Check settings
        group = session.query(GroupSettings).filter(GroupSettings.chat_id == event.chat.id).first()
        
        # Agar group DB me nahi hai, to add karlo (Default ON)
        if not group:
            group = GroupSettings(chat_id=event.chat.id)
            session.add(group)
            session.commit()

        if group.welcome_enabled:
            name = event.new_chat_member.user.first_name
            await event.bot.send_message(
                event.chat.id,
                f"👋 <b>Welcome {name}!</b>\n\nIs group me aap movie/series ka naam likhein, agar channel par hogi to Bot turant link de dega."
            )
    except Exception as e:
        print(f"Welcome Error: {e}")
    finally:
        session.close()

# --- 2. AUTO-SEARCH & REPLY HANDLER ---
@router.message(F.text & F.chat.type.in_({"group", "supergroup"}))
async def group_message_handler(message: types.Message):
    # 1. Message clean karo
    query = clean_query(message.text)
    
    # Agar query bahut choti hai (eg: "Hi"), to ignore karo
    if len(query) < 3:
        return

    session = SessionLocal()
    try:
        # Check if auto_search is enabled
        group = session.query(GroupSettings).filter(GroupSettings.chat_id == message.chat.id).first()
        if group and not group.auto_search:
            return

        # 2. Database me dhundo (Case Insensitive Search)
        # %query% ka matlab: aage-peeche kuch bhi ho, bas ye shabd match hona chahiye
        file_match = session.query(FileRecord).filter(
            FileRecord.file_name.ilike(f"%{query}%")
        ).first()

        # 3. Agar File Mil Gayi
        if file_match:
            bot_username = (await message.bot.get_me()).username
            # Ye wahi link hai jo Ad Verification flow trigger karega
            deep_link = f"https://t.me/{bot_username}?start={file_match.unique_token}"
            
            response = (
                f"✅ <b>File Found:</b> {file_match.file_name}\n\n"
                f"👤 {message.from_user.mention_html()}, ye rahi aapki requested file.\n"
                f"👇 <b>Niche click karke download karein:</b>\n"
                f"{deep_link}"
            )
            
            # User ke message ko reply karo
            await message.reply(response)
            
        else:
            # Agar file nahi mili -> Chup raho (Ignore)
            # Aap chaho to console me print kar sakte ho
            print(f"🔍 Ignored Query: {query} (No match found)")

    except Exception as e:
        print(f"Search Error: {e}")
    finally:
        session.close()
