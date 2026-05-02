import aiohttp
import hashlib
from aiohttp import web
from aiohttp_session import get_session
from database.db import SessionLocal
from database.models import WebsiteUser
from dashboard.utils import render_template

async def user_dashboard(request):
    session = await get_session(request)
    db = SessionLocal()
    user = db.query(WebsiteUser).filter(WebsiteUser.telegram_id == session.get('target_user_id')).first()
    pic = user.profile_pic_url if user else ""
    db.close()
    return web.Response(text=render_template("user/templates", "customer_dashboard.html", profile_pic=pic), content_type='text/html')

async def user_api_handler(request, page, target_id):
    db = SessionLocal()
    if page == 'store':
        html = "<h1>Bot Store</h1><p>Buy premium bots here.</p>"
    elif page == 'profile':
        user = db.query(WebsiteUser).filter(WebsiteUser.telegram_id == target_id).first()
        html = f"<h1>Profile</h1><p>Name: {user.full_name}</p>"
    db.close()
    return web.Response(text=html, content_type='text/html')

async def update_profile_handler(request, target_id):
    # Profile update logic with Cloudinary
    return web.json_response({"success": True})
