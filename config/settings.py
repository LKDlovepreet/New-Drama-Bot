#setting or config

import os
from dotenv import load_dotenv

load_dotenv()

# Tokens aur IDs load karna
BOT_TOKENS = os.getenv("BOT_TOKENS", "").split(",")
OWNER_ID = int(os.getenv("OWNER_ID", 0))
admin_env = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x) for x in admin_env.split(",")] if admin_env else []

# Messages (Yaha edit karein)
MESSAGES = {
    "welcome": "👋 Welcome! Mai ek File Sharing Bot hu.",
    "not_authorized": "🚫 <b>Access Denied.</b> Sirf Admin files upload kar sakte hain.",
    "upload_success": "✅ <b>File Saved!</b>\n\n🔗 Link:\n{link}",
    "invalid_link": "❌ Ye link galat hai ya file delete ho gayi hai.",
    "sending_file": "📂 File bhej raha hu...",
    "start_admin": "👋 Hello Admin! File bhejein link generate karne ke liye."
}
