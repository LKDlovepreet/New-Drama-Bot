import os
from dotenv import load_dotenv

load_dotenv()

# --- TOKENS ---
LINK_BOT_TOKEN = os.getenv("LINK_BOT_TOKEN") 
GROUP_BOT_TOKEN = os.getenv("GROUP_BOT_TOKEN")
AUTH_BOT_TOKEN = os.getenv("AUTH_BOT_TOKEN") 

# --- OWNER & ADMINS (Ye Missing Tha) ---
OWNER_ID = int(os.getenv("OWNER_ID", 0))
admin_env = os.getenv("ADMIN_IDS", "")
# 👇 Ye line wapis aa gayi hai
ADMIN_IDS = [int(x) for x in admin_env.split(",")] if admin_env else []

# --- DATABASE & IDs ---
LINK_BOT_ID = int(os.getenv("LINK_BOT_ID", 0)) 
GROUP_BOT_ID = int(os.getenv("GROUP_BOT_ID", 0))
LINK_BOT_USERNAME = os.getenv("LINK_BOT_USERNAME", "YourFileBot") 

# --- DASHBOARD SECURITY ---
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "Admin@123") 
SESSION_TIME = 3600 

# --- ADVERTISEMENT LINKS ---
AD_CHANNEL_URL = os.getenv("AD_CHANNEL_URL", "https://t.me/YourChannel")
AD_GROUP_URL = os.getenv("AD_GROUP_URL", "https://t.me/YourGroup")
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "YourUsername") # Bina @ ke

# --- OTHER SETTINGS ---
GPLINKS_API = os.getenv("GPLINKS_API") 
DEMO_VIDEO_URL = "https://t.me/your_channel/123"
VERIFY_HOURS = 24

IGNORE_TERMS = [
    "480p", "720p", "1080p", "2160p", "4k", "hd", "fullhd", "camrip", 
    "print", "pre-dvd", "dvdscr", "web-dl", "webrip", "bluray", "dual", 
    "audio", "hindi", "english", "dubbed", "subbed", "link", "download", 
    "join", "channel", "mkv", "mp4", "avi", "x264", "x265", "hevc", "10bit",
    "season", "episode", "s01", "e01"
]

MESSAGES = {
    "welcome": "👋 Welcome! File paane ke liye link use karein.",
    "not_authorized": "🚫 Access Denied.",
    "upload_success": "✅ <b>File Saved!</b>\n\n🔗 Link:\n<code>{link}</code>",
    "invalid_link": "❌ Link expired or invalid.",
    "sending_file": "📂 File bhej raha hu...",
    "verify_first": "⚠️ <b>Verification Required!</b>\n\nAapka free access khatam ho gaya hai. File download karne ke liye niche diye gaye link se verify karein.\n\n⏳ <b>Validity:</b> 24 Hours",
    "verified_success": "✅ <b>Verification Successful!</b>\n\nAb aap agle 24 ghante tak unlimited files download kar sakte hain."
}
