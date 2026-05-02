import os
import time
import base64
import hashlib
import aiohttp
from aiohttp import web
from aiohttp_session import setup, get_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage

from config.settings import DASHBOARD_PASSWORD, SESSION_TIME
from database.db import SessionLocal
from sqlalchemy import String
from database.models import WebsiteUser

from dashboard.otp_service import send_otp_to_owner, send_otp_to_customer, verify_otp
from dashboard.utils import render_template

# 👉 Import Modular Views
from dashboard.owner.owner_views import owner_dashboard
from dashboard.admin.admin_views import admin_dashboard, admin_action_handler, admin_api_handler
from dashboard.user.user_views import user_dashboard, user_api_handler, update_profile_handler

# --- Basic Page Handlers ---
async def landing_page(request):
    return web.Response(text=render_template("templates", "landing.html"), content_type='text/html')

async def login_page(request):
    session = await get_session(request)
    if session.get('authenticated'): return web.HTTPFound('/dashboard')
    return web.Response(text=render_template("templates", "login.html", error=""), content_type='text/html')

async def signup_page(request):
    return web.Response(text=render_template("templates", "signup.html", error=""), content_type='text/html')

async def verify_page(request):
    session = await get_session(request)
    if session.get('authenticated'): return web.HTTPFound('/dashboard')
    if not session.get('pre_auth'): return web.HTTPFound('/login')
    return web.Response(text=render_template("templates", "verify.html", error=""), content_type='text/html')

# --- Logic Handlers ---
async def login_post(request):
    data = await request.post()
    login_id = data.get('login_id')
    password = data.get('passkey')
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    db = SessionLocal()
    try:
        if login_id == "owner" and password == DASHBOARD_PASSWORD:
            await send_otp_to_owner()
            session = await get_session(request)
            session['pre_auth'], session['user_role'] = True, 'owner'
            return web.HTTPFound('/verify')
        
        user = db.query(WebsiteUser).filter(WebsiteUser.telegram_id.cast(String) == login_id).filter(WebsiteUser.web_password == hashed_pw).first()
        if user:
            success, msg = await send_otp_to_customer(user.telegram_id)
            if not success:
                return web.Response(text=render_template("templates", "login.html", error=f"❌ {msg}"), content_type='text/html')
            session = await get_session(request)
            session['pre_auth'], session['user_role'], session['target_user_id'] = True, user.role, user.telegram_id
            return web.HTTPFound('/verify')
        return web.Response(text=render_template("templates", "login.html", error="❌ Invalid Credentials!"), content_type='text/html')
    finally:
        db.close()

async def signup_post(request):
    try:
        data = await request.post()
        full_name, dob, telegram_id, passkey = data.get('full_name'), data.get('dob'), data.get('telegram_id'), data.get('passkey')
        db = SessionLocal()
        if db.query(WebsiteUser).filter(WebsiteUser.telegram_id == int(telegram_id)).first():
            db.close()
            return web.json_response({"success": False, "message": "ID already registered."})

        profile_pic_url = "https://i.pinimg.com/736x/8f/33/2d/8f332dd34b6e5114705bd364741db457.jpg"
        profile_pic_file = data.get('profile_pic')
        if profile_pic_file and hasattr(profile_pic_file, 'filename'):
            try:
                url = f"https://api.cloudinary.com/v1_1/dordvtopl/image/upload"
                form_data = aiohttp.FormData()
                form_data.add_field('file', profile_pic_file.file.read(), filename=profile_pic_file.filename)
                form_data.add_field('upload_preset', 'Profile_pictures')
                async with aiohttp.ClientSession() as http_session:
                    async with http_session.post(url, data=form_data) as resp:
                        res = await resp.json()
                        if 'secure_url' in res: profile_pic_url = res['secure_url']
            except Exception: pass

        db.add(WebsiteUser(telegram_id=int(telegram_id), web_password=hashlib.sha256(passkey.encode()).hexdigest(), role='customer', full_name=full_name, dob=dob, profile_pic_url=profile_pic_url))
        db.commit()
        db.close()
        session = await get_session(request)
        session['pre_auth'], session['user_role'], session['target_user_id'] = True, 'customer', int(telegram_id)
        return web.json_response({"success": True, "redirect": "/verify"})
    except Exception as e: return web.json_response({"success": False, "message": str(e)})

async def verify_post(request):
    session = await get_session(request)
    data = await request.post()
    role = session.get('user_role')
    target_id = session.get('target_user_id') if role != 'owner' else 'owner'
    success, msg = verify_otp(target_id, data.get('otp'))
    if success:
        session['authenticated'], session['login_time'] = True, time.time()
        del session['pre_auth']
        return web.HTTPFound('/dashboard')
    return web.Response(text=render_template("templates", "verify.html", error=msg), content_type='text/html')

async def logout(request):
    session = await get_session(request)
    session.invalidate()
    return web.HTTPFound('/')

# --- Smart Routers ---
async def smart_dashboard(request):
    session = await get_session(request)
    if not session.get('authenticated'): return web.HTTPFound('/login')
    role = session.get('user_role', 'customer')
    if role == 'owner': return await owner_dashboard(request)
    elif role == 'admin': return await admin_dashboard(request)
    else: return await user_dashboard(request)

async def smart_api(request):
    session = await get_session(request)
    if not session.get('authenticated'): return web.Response(text="Unauthorized", status=401)
    role, page = session.get('user_role'), request.match_info['page']
    if role == 'admin': return await admin_api_handler(request, page)
    elif role == 'customer': return await user_api_handler(request, page, session.get('target_user_id'))
    return web.Response(status=403)

async def start_dashboard_server():
    app = web.Application()
    secret_key = base64.urlsafe_b64encode(hashlib.sha256(DASHBOARD_PASSWORD.encode()).digest())
    setup(app, EncryptedCookieStorage(base64.urlsafe_b64decode(secret_key), max_age=SESSION_TIME))

    # Folders ensure karna
    for f in ['dashboard/owner/static', 'dashboard/admin/static', 'dashboard/user/static', 'dashboard/static']:
        os.makedirs(f, exist_ok=True)

    app.router.add_static('/static/admin/', path='dashboard/admin/static', name='admin_static')
    app.router.add_static('/static/user/', path='dashboard/user/static', name='user_static')
    app.router.add_static('/static/', path='dashboard/static', name='main_static')

    app.router.add_get('/', landing_page)
    app.router.add_get('/login', login_page)
    app.router.add_post('/login', login_post)
    app.router.add_get('/signup', signup_page)
    app.router.add_post('/signup', signup_post)
    app.router.add_get('/verify', verify_page)
    app.router.add_post('/verify', verify_post)
    app.router.add_post('/logout', logout)
    app.router.add_get('/dashboard', smart_dashboard)
    app.router.add_get('/api/{page}', smart_api)
    app.router.add_post('/api/action', admin_action_handler)
    app.router.add_post('/api/update_profile', update_profile_handler)

    port = int(os.environ.get("PORT", 8000))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', port).start()
    print(f"🌍 MODULAR Server running on port {port}")
