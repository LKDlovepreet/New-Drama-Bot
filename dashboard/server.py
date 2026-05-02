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

async def landing_page(request):
    return web.Response(text=render_template("templates", "landing.html"), content_type='text/html')

async def login_page(request):
    return web.Response(text=render_template("templates", "login.html", error=""), content_type='text/html')

async def signup_page(request):
    return web.Response(text=render_template("templates", "signup.html", error=""), content_type='text/html')

async def verify_page(request):
    return web.Response(text=render_template("templates", "verify.html", error=""), content_type='text/html')

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
            session['pre_auth'] = True
            session['user_role'] = 'owner'
            return web.HTTPFound('/verify')
        
        user = db.query(WebsiteUser).filter(WebsiteUser.telegram_id.cast(String) == login_id).filter(WebsiteUser.web_password == hashed_pw).first()
        
        if user:
            success, msg = await send_otp_to_customer(user.telegram_id)
            if not success:
                return web.Response(text=render_template("templates", "login.html", error=f"❌ {msg}"), content_type='text/html')
            
            session = await get_session(request)
            session['pre_auth'] = True
            session['user_role'] = user.role
            session['target_user_id'] = user.telegram_id
            return web.HTTPFound('/verify')
            
        return web.Response(text=render_template("templates", "login.html", error="❌ Invalid Credentials!"), content_type='text/html')
    finally:
        db.close()

async def signup_post(request):
    try:
        data = await request.post()
        full_name = data.get('full_name')
        dob = data.get('dob')
        telegram_id = data.get('telegram_id')
        passkey = data.get('passkey')
        
        db = SessionLocal()
        if db.query(WebsiteUser).filter(WebsiteUser.telegram_id == int(telegram_id)).first():
            db.close()
            return web.json_response({"success": False, "message": "ID already registered."})

        profile_pic_url = "https://i.pinimg.com/736x/8f/33/2d/8f332dd34b6e5114705bd364741db457.jpg"
        profile_pic_file = data.get('profile_pic')
        
        if profile_pic_file and hasattr(profile_pic_file, 'filename') and profile_pic_file.filename:
            try:
                url = "https://api.cloudinary.com/v1_1/dordvtopl/image/upload"
                form_data = aiohttp.FormData()
                form_data.add_field('file', profile_pic_file.file.read(), filename=profile_pic_file.filename, content_type=profile_pic_file.content_type)
                form_data.add_field('upload_preset', 'Profile_pictures')
                
                async with aiohttp.ClientSession() as http_session:
                    async with http_session.post(url, data=form_data) as resp:
                        res = await resp.json()
                        if 'secure_url' in res:
                            profile_pic_url = res['secure_url']
            except Exception:
                pass

        new_user = WebsiteUser(
            telegram_id=int(telegram_id),
            web_password=hashlib.sha256(passkey.encode()).hexdigest(),
            role='customer',
            full_name=full_name,
            dob=dob,
            profile_pic_url=profile_pic_url
        )
        db.add(new_user)
        db.commit()
        db.close()
        
        session = await get_session(request)
        session['pre_auth'] = True
        session['user_role'] = 'customer'
        session['target_user_id'] = int(telegram_id)
        return web.json_response({"success": True, "redirect": "/verify"})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})

async def verify_post(request):
    session = await get_session(request)
    data = await request.post()
    role = session.get('user_role')
    target_id = session.get('target_user_id') if role != 'owner' else 'owner'
    
    success, msg = verify_otp(target_id, data.get('otp'))
    
    if success:
        session['authenticated'] = True
        session['login_time'] = time.time()
        del session['pre_auth']
        return web.HTTPFound('/dashboard')
        
    return web.Response(text=render_template("templates", "verify.html", error=msg), content_type='text/html')

async def logout(request):
    session = await get_session(request)
    session.invalidate()
    return web.HTTPFound('/')

# 🎯 SMART ROUTERS (Traffic Controller)
async def smart_dashboard(request):
    session = await get_session(request)
    if not session.get('authenticated'):
        return web.HTTPFound('/login')
        
    role = session.get('user_role', 'customer')
    if role == 'owner':
        return await owner_dashboard(request)
    elif role == 'admin':
        return await admin_dashboard(request)
    else:
        return await user_dashboard(request)

async def smart_api(request):
    session = await get_session(request)
    if not session.get('authenticated'):
        return web.Response(text="Unauthorized", status=401)
        
    role = session.get('user_role')
    page = request.match_info['page']
    
    if role == 'admin':
        return await admin_api_handler(request, page)
    elif role == 'customer':
        return await user_api_handler(request, page, session.get('target_user_id'))
        
    return web.Response(text="Forbidden", status=403)

async def smart_action(request):
    session = await get_session(request)
    if not session.get('authenticated') or session.get('user_role') != 'admin':
        return web.json_response({"success": False, "message": "Unauthorized"})
        
    data = await request.json()
    return await admin_action_handler(request, data)

async def smart_profile_update(request):
    session = await get_session(request)
    if not session.get('authenticated') or session.get('user_role') != 'customer':
        return web.json_response({"success": False, "message": "Unauthorized"})
        
    return await update_profile_handler(request, session.get('target_user_id'))

async def start_dashboard_server():
    app = web.Application()
    secret_key = base64.urlsafe_b64encode(hashlib.sha256(DASHBOARD_PASSWORD.encode()).digest())
    setup(app, EncryptedCookieStorage(base64.urlsafe_b64decode(secret_key), max_age=SESSION_TIME))

    # All Static Folders Mounted Securely
    app.router.add_static('/static/owner/', path='dashboard/owner/static', name='owner_static')
    app.router.add_static('/static/admin/', path='dashboard/admin/static', name='admin_static')
    app.router.add_static('/static/user/', path='dashboard/user/static', name='user_static')
    app.router.add_static('/static/', path='dashboard/static', name='main_static')

    app.router.add_get('/', landing_page)
    app.router.add_get('/login', login_page)
    app.router.add_post('/login', login_post)
    app.router.add_get('/verify', verify_page)
    app.router.add_post('/verify', verify_post)
    app.router.add_post('/logout', logout)
    app.router.add_get('/signup', signup_page)
    app.router.add_post('/signup', signup_post)

    # Core Smart Routes
    app.router.add_get('/dashboard', smart_dashboard)
    app.router.add_get('/api/{page}', smart_api)
    app.router.add_post('/api/action', smart_action)
    app.router.add_post('/api/update_profile', smart_profile_update)

    port = int(os.environ.get("PORT", 8000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌍 MODULAR Dashboard running on port {port}")
