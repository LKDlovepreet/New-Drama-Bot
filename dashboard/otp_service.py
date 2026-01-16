import random
import string
import time
import aiohttp
from config.settings import AUTH_BOT_TOKEN, OWNER_ID

# Temporary Memory for OTPs
otp_storage = {}

def generate_otp():
    """6 Digit Random OTP"""
    return ''.join(random.choices(string.digits, k=6))

async def send_otp_to_owner():
    """Owner ko phone par OTP bhejo"""
    otp = generate_otp()
    expiry = time.time() + 60  # 1 Minute Validity
    
    # Store OTP
    otp_storage[OWNER_ID] = {"code": otp, "expiry": expiry}
    
    # Telegram API Call (Using aiohttp for speed)
    url = f"https://api.telegram.org/bot{AUTH_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": OWNER_ID,
        "text": f"🔐 **Dashboard Login Attempt!**\n\n🔢 OTP: `{otp}`\n⏳ Valid for 1 minute.\n\nAgar ye aap nahi hain, to turant Password change karein!",
        "parse_mode": "Markdown"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            return resp.status == 200

def verify_otp(input_otp):
    """OTP Check karo"""
    data = otp_storage.get(OWNER_ID)
    
    if not data:
        return False, "❌ No OTP generated or Expired."
    
    if time.time() > data["expiry"]:
        return False, "⏳ OTP Expired!"
    
    if data["code"] == input_otp:
        del otp_storage[OWNER_ID] # One-time use
        return True, "✅ Success"
    
    return False, "❌ Wrong OTP"
