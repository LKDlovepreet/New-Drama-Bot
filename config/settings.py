import os
from dotenv import load_dotenv

load_dotenv()

#TOKENS (Comma separated in .env)
# .env me: BOT_TOKENS=123:ABC,456:XYZ
tokens_env = os.getenv("BOT_TOKENS", "").split(",")

# Agar tokens set nahi hain to crash na ho
BOT_TOKENS = [t for t in tokens_env if t]

OWNER_ID = int(os.getenv("OWNER_ID", 0))
admin_env = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x) for x in admin_env.split(",")] if admin_env else []

# --- 👇 NEW SETTINGS (IDs manually daalein) ---
# Yahan apne Bots ki Numeric ID replace karein
LINK_BOT_ID = 7949301887   # <--- CONTENT BOT KI ID YAHA DALEIN
GROUP_BOT_ID = 7635882029  # <--- GROUP MANAGER BOT KI ID YAHA DALEIN

# Link Bot ka Username (Taaki Group bot sahi link bana sake)
# Bina @ ke likhein (Example: "MyFileBot")
LINK_BOT_USERNAME = "videosstoragebot" 

# APIs
GPLINKS_API = os.getenv("GPLINKS_API") 
DEMO_VIDEO_URL = "https://t.me/LKD_Movies/14"
VERIFY_HOURS = 1

MESSAGES = {
    "welcome": "👋 Welcome! File paane ke liye link use karein.",
    "not_authorized": "🚫 Access Denied.",
    "upload_success": "✅ <b>File Saved!</b>\n\n🔗 Link:\n<code>{link}</code>",
    "invalid_link": "❌ Link expired or invalid.",
    "sending_file": "📂 File bhej raha hu...",
    "verify_first": "⚠️ <b>Verification Required!</b>\n\nAapka free access khatam ho gaya hai. File download karne ke liye niche diye gaye link se verify karein.\n\n⏳ <b>Validity:</b> 24 Hours",
    "verified_success": "✅ <b>Verification Successful!</b>\n\nAb aap agle 24 ghante tak unlimited files download kar sakte hain."
}
