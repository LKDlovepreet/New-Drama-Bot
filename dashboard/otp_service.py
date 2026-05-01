import random
import time
import aiohttp
import os
from config.settings import BOT_TOKEN_3, OWNER_ID

# 👇 यह वह वेरिएबल है जो मिसिंग था
OTP_STORE = {}

def generate_otp():
    return str(random.randint(100000, 999999))

async def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN_3}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload) as resp:
                return await resp.json()
        except Exception as e:
            return None

async def send_otp_to_owner():
    otp = generate_otp()
    OTP_STORE['owner'] = {'otp': otp, 'time': time.time()}
    await send_telegram_message(OWNER_ID, f"🔐 <b>Master OTP:</b> <code>{otp}</code>\n\nDo not share this with anyone.")

async def send_otp_to_customer(telegram_id):
    otp = generate_otp()
    OTP_STORE[str(telegram_id)] = {'otp': otp, 'time': time.time()}
    res = await send_telegram_message(telegram_id, f"📲 <b>Verification OTP:</b> <code>{otp}</code>\n\nWelcome to RAMGARHIA Services!")
    
    # अगर Telegram ने मैसेज रिजेक्ट कर दिया (जैसे यूज़र ने /start नहीं किया)
    if res and not res.get("ok"):
        return False, res.get("description")
    return True, "Sent"

def verify_otp(target_id, otp_input):
    target_id = str(target_id)
    if target_id in OTP_STORE:
        stored_data = OTP_STORE[target_id]
        if time.time() - stored_data['time'] > 300: # 5 मिनट में OTP एक्सपायर
            del OTP_STORE[target_id]
            return False, "❌ OTP Expired!"
        if stored_data['otp'] == otp_input:
            del OTP_STORE[target_id]
            return True, "✅ Verified!"
        else:
            return False, "❌ Invalid OTP!"
    return False, "❌ ID not found or OTP expired."
