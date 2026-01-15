import os
from dotenv import load_dotenv

load_dotenv()

# --- TOKENS ---
# .env me: BOT_TOKENS=123:ABC,456:XYZ
tokens_env = os.getenv("BOT_TOKENS", "").split(",")
BOT_TOKENS = [t for t in tokens_env if t]

OWNER_ID = int(os.getenv("OWNER_ID", 0))
admin_env = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x) for x in admin_env.split(",")] if admin_env else []

# --- 👇 NEW: IDs FROM ENVIRONMENT VARIABLES ---
# Koyeb me 'LINK_BOT_ID' aur 'GROUP_BOT_ID' add karna mat bhoolna
LINK_BOT_ID = int(os.getenv("LINK_BOT_ID", 0)) 
GROUP_BOT_ID = int(os.getenv("GROUP_BOT_ID", 0))

# Link Bot ka Username (Bina @ ke)
LINK_BOT_USERNAME = os.getenv("LINK_BOT_USERNAME", "videosstoragebot") 

# --- APIs ---
GPLINKS_API = os.getenv("GPLINKS_API") 
DEMO_VIDEO_URL = "https://t.me/LKD_Movies/14"
VERIFY_HOURS = 24

MESSAGES = {
    "welcome": "👋 Welcome! File paane ke liye link use karein.",
    "not_authorized": "🚫 Access Denied.",
    "upload_success": "✅ <b>File Saved!</b>\n\n🔗 Link:\n<code>{link}</code>",
    "invalid_link": "❌ Link expired or invalid.",
    "sending_file": "📂 File bhej raha hu...",
    "verify_first": "⚠️ <b>Verification Required!</b>\n\nAapka free access khatam ho gaya hai. File download karne ke liye niche diye gaye link se verify karein.\n\n⏳ <b>Validity:</b> 24 Hours",
    "verified_success": "✅ <b>Verification Successful!</b>\n\nAb aap agle 24 ghante tak unlimited files download kar sakte hain."
}

# --- IGNORE WORDS FOR INDEXING ---
IGNORE_TERMS = [
    "480p", "720p", "1080p", "2160p", "4k", "hd", "fullhd", "camrip", 
    "print", "pre-dvd", "dvdscr", "web-dl", "webrip", "bluray", "dual", 
    "audio", "hindi", "english", "dubbed", "subbed", "link", "download", 
    "join", "channel", "mkv", "mp4", "avi", "x264", "x265", "hevc", "10bit",
    "season", "episode", "s01", "e01"
]
