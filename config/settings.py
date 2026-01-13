import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKENS = os.getenv("BOT_TOKENS", "").split(",")
OWNER_ID = int(os.getenv("OWNER_ID", 0))
admin_env = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x) for x in admin_env.split(",")] if admin_env else []

# 👇 FIX: Ab ye Koyeb ke Environment Variables se Key uthayega
GPLINKS_API = os.getenv("GPLINKS_API") 

DEMO_VIDEO_URL = ""
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
