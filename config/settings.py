import os
from dotenv import load_dotenv

load_dotenv()

# --- TOKENS ---
LINK_BOT_TOKEN = os.getenv("LINK_BOT_TOKEN") 
GROUP_BOT_TOKEN = os.getenv("GROUP_BOT_TOKEN")
# 👇 NEW: Auth Bot (Jo OTP bhejega)
AUTH_BOT_TOKEN = os.getenv("AUTH_BOT_TOKEN") 

OWNER_ID = int(os.getenv("OWNER_ID", 0))

# --- DATABASE & IDs ---
LINK_BOT_ID = int(os.getenv("LINK_BOT_ID", 0)) 
GROUP_BOT_ID = int(os.getenv("GROUP_BOT_ID", 0))
LINK_BOT_USERNAME = os.getenv("LINK_BOT_USERNAME", "YourFileBot") 

# --- DASHBOARD SECURITY ---
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "Admin@123") # Hard password rakhein
SESSION_TIME = 3600  # 1 Hour (Seconds)

# --- OTHER SETTINGS ---
GPLINKS_API = os.getenv("GPLINKS_API") 
DEMO_VIDEO_URL = "https://t.me/your_channel/123"
VERIFY_HOURS = 24
IGNORE_TERMS = ["480p", "720p", "1080p", "mkv", "mp4", "hindi", "dubbed"]
MESSAGES = { "welcome": "👋 Welcome!" } # (Shortened for brevity)
