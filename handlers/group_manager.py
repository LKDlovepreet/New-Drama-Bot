from aiogram import Router, F, types
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION
from thefuzz import process
from database.db import get_db
from database.models import GroupSettings, FileRecord
from config.settings import GROUP_BOT_ID, OWNER_ID, LINK_BOT_USERNAME

router = Router()

# 👇 FILTER: Ye code sirf Group Bot par chalega
router.message.filter(F.bot.id == GROUP_BOT_ID)

STOP_WORDS = [
    "chahiye", "plz", "pls", "please", "admin", "bhai", "sir", "bro", 
    "upload", "kardo", "hai", "kya", "milegi", "link", "do", "send", 
    "movies", "movie", "series", "season", "episode", "download", 
    "hi", "hello", "koi", "hai", "me", "ko", "ki", "ka"
]

def clean_query(text):
    words = text.lower().split()
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    return " ".join(keywords)

# --- 1. WELCOME MESSAGE ---
@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_user_join(event: types.ChatMemberUpdated):
    if event.chat.type not in ["group", "supergroup"]: return
    session = get_db()
    try:
        group = session.query(GroupSettings).filter(GroupSettings.chat_id == event.chat.id).first()
        if not group:
            group = GroupSettings(chat_id=event.chat.id)
            session.add(group)
            session.commit()
        if group.welcome_enabled:
            await event.bot.send_message(event.chat.id, f"👋 Welcome {event.new_chat_member.user.first_name}!")
    finally:
        session.close()

# --- 2. MESSAGE CONTROLLER (Auto-Reply + Auto-Delete) ---
@router.message(F.text & F.chat.type.in_({"group", "supergroup"}))
async def group_message_handler(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    bot = message.bot

    # A. Check if Admin/Owner (Allow everything)
    member = await bot.get_chat_member(chat_id, user_id)
    if member.status in ["administrator", "creator"] or user_id == OWNER_ID:
        return # Admin hai, kuch mat karo (Rehne do message)

    # B. Normal User Handling
    query = clean_query(message.text)
    match_found = False
    
    # Search Logic (Agar query valid hai)
    if len(query) >= 3:
        session = get_db()
        try:
            group = session.query(GroupSettings).filter(GroupSettings.chat_id == chat_id).first()
            if group and group.auto_search:
                # 1. Search
                all_files = session.query(FileRecord).all()
                file_names = {f.file_name: f for f in all_files}
                best_match = process.extractOne(query, file_names.keys())

                # 2. Match Found
                if best_match and best_match[1] > 70:
                    match_found = True
                    matched_file = file_names[best_match[0]]
                    
                    # 👇 LINK BOT 1 KA HOGA
                    deep_link = f"https://t.me/{LINK_BOT_USERNAME}?start={matched_file.unique_token}"
                    
                    response = (
                        f"✅ <b>Found:</b> {matched_file.file_name}\n"
                        f"Matching Score: {best_match[1]}%\n\n"
                        f"👤 {message.from_user.mention_html()}, link niche hai:\n"
                        f"{deep_link}"
                    )
                    await message.reply(response)
        except Exception as e:
            print(f"Group Error: {e}")
        finally:
            session.close()

    # C. DELETE LOGIC (Agar Match Nahi Mila)
    # Agar match mil gaya, to user ka message rehne do (ya delete kar sakte ho, apki marzi)
    # Agar match NAHI mila (Faltu baat), to DELETE.
   # if not match_found:
    #    try:
    #        await message.delete()
    #    except Exception as e:
   #         print(f"Delete Failed: {e} (Bot ko Admin banayein aur 'Delete Messages' right dein)")
