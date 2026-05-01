import os
import time
import base64
import hashlib
from aiohttp import web
import aiohttp_session
from aiohttp_session import setup, get_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage

from config.settings import DASHBOARD_PASSWORD, SESSION_TIME
from database.db import SessionLocal
from database.models import BotUser, FileRecord, Channel
from .otp_service import send_otp_to_owner, verify_otp

def render_template(filename, **kwargs):
    filepath = os.path.join("dashboard", "templates", filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    for key, value in kwargs.items():
        content = content.replace(f"{{{key}}}", str(value))
    return content

async def landing_page(request):
    html = render_template("landing.html")
    return web.Response(text=html, content_type='text/html')

async def login_page(request):
    session = await get_session(request)
    if session.get('authenticated'): return web.HTTPFound('/dashboard')
    html = render_template("login.html", error="")
    return web.Response(text=html, content_type='text/html')

async def login_post(request):
    data = await request.post()
    if data.get('passkey') == DASHBOARD_PASSWORD:
        await send_otp_to_owner()
        session = await get_session(request)
        session['pre_auth'] = True
        return web.HTTPFound('/verify')
    else:
        return web.Response(text=render_template("login.html", error="❌ Wrong Password!"), content_type='text/html')

async def signup_page(request):
    html = render_template("signup.html", error="")
    return web.Response(text=html, content_type='text/html')

async def signup_post(request):
    data = await request.post()
    
    full_name = data.get('full_name')
    dob = data.get('dob')
    telegram_id = data.get('telegram_id') # Ye Username ya ID dono ho sakta hai
    passkey = data.get('passkey')
    email = data.get('email')
    mobile = data.get('mobile_number')
    profile_pic = data.get('profile_pic_url')
    
    db = SessionLocal()
    try:
        # Password ko super secure banakar hash karna
        hashed_password = hashlib.sha256(passkey.encode()).hexdigest()
        
        # User create karna
        new_user = BotUser(
            web_username=telegram_id, # Telegram ID ko hi login username bana diya
            web_password=hashed_password,
            role='customer', # By default har naya user customer hoga
            full_name=full_name,
            dob=dob,
            email=email,
            mobile_number=mobile,
            profile_pic_url=profile_pic
        )
        db.add(new_user)
        db.commit()
        
        # Signup ke baad OTP verification ke liye bhejna
        session = await get_session(request)
        session['pre_auth'] = True
        session['temp_telegram_id'] = telegram_id
        
        # TODO: Yahan par bot us user ko OTP bhejega (Bot Integration next step me karenge)
        
        return web.HTTPFound('/verify')
        
    except Exception as e:
        db.rollback()
        html = render_template("signup.html", error="❌ Username/ID already exists or Database Error!")
        return web.Response(text=html, content_type='text/html')
    finally:
        db.close()

async def verify_page(request):
    session = await get_session(request)
    if session.get('authenticated'): return web.HTTPFound('/dashboard')
    if not session.get('pre_auth'): return web.HTTPFound('/login')
    return web.Response(text=render_template("verify.html", error=""), content_type='text/html')

async def verify_post(request):
    session = await get_session(request)
    if not session.get('pre_auth'): return web.HTTPFound('/login')
    data = await request.post()
    success, msg = verify_otp(data.get('otp'))
    if success:
        session['authenticated'] = True
        session['login_time'] = time.time()
        del session['pre_auth']
        return web.HTTPFound('/dashboard')
    else:
        return web.Response(text=render_template("verify.html", error=msg), content_type='text/html')

async def logout(request):
    session = await get_session(request)
    session.invalidate()
    return web.HTTPFound('/')

async def dashboard_page(request):
    session = await get_session(request)
    if not session.get('authenticated') or (time.time() - session.get('login_time', 0) > SESSION_TIME):
        session.invalidate()
        return web.HTTPFound('/login')
    resp = web.Response(text=render_template("dashboard.html", error=""), content_type='text/html')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp

async def action_handler(request):
    session = await get_session(request)
    if not session.get('authenticated'): return web.json_response({"success": False, "message": "Unauthorized"})
    
    data = await request.json()
    action, target_id = data.get('action'), data.get('id')
    db = SessionLocal()
    try:
        if action == 'make_admin':
            user = db.query(BotUser).filter(BotUser.user_id == target_id).first()
            if user: user.is_admin, user.role = True, 'admin'
        elif action == 'remove_admin':
            user = db.query(BotUser).filter(BotUser.user_id == target_id).first()
            if user: user.is_admin, user.role = False, 'user'
        elif action == 'ban_user':
            user = db.query(BotUser).filter(BotUser.user_id == target_id).first()
            if user: user.is_global_banned = True
        elif action == 'delete_file':
            file = db.query(FileRecord).filter(FileRecord.id == target_id).first()
            if file: db.delete(file)
        db.commit()
        return web.json_response({"success": True})
    except Exception as e: return web.json_response({"success": False, "message": str(e)})
    finally: db.close()

async def api_handler(request):
    session = await get_session(request)
    if not session.get('authenticated'): return web.Response(text="Unauthorized", status=401)
    
    page = request.match_info['page']
    db = SessionLocal()
    html = ""
    try:
        if page == 'status':
            u, f, c = db.query(BotUser).count(), db.query(FileRecord).count(), db.query(Channel).count()
            html = f"""<div class="welcome-msg"><h1>Welcome back, Boss! 👋</h1><p>System is running smoothly.</p></div>
            <div class="bot-cards-grid">
                <a href="#bot1" class="bot-card"><div class="card-header"><h3>Link Manager Bot</h3><span class="live-dot"></span></div><div class="card-body"><p>Handling Deep Linking & File Storage.</p><div class="bot-stats">📁 Indexed Files: {f}</div></div></a>
                <a href="#bot2" class="bot-card"><div class="card-header"><h3>Group Guard Bot</h3><span class="live-dot"></span></div><div class="card-body"><p>Managing Security & Auto-replies.</p><div class="bot-stats">👥 Active Users: {u}</div></div></a>
            </div>"""
        elif page == 'users':
            users = db.query(BotUser).order_by(BotUser.id.desc()).limit(20).all()
            rows = "".join([f"<tr><td><code>{u.user_id}</code></td><td>{u.joined_date.strftime('%Y-%m-%d')}</td><td><button class='action-btn' style='background:var(--success);' onclick='performAction(\"make_admin\", {u.user_id})'>Make Admin</button><button class='action-btn' style='background:var(--danger);' onclick='performAction(\"ban_user\", {u.user_id})'>Ban</button></td></tr>" for u in users])
            html = f"<h1>Manage Users</h1><table><tr><th>User ID</th><th>Joined Date</th><th>Actions</th></tr>{rows}</table>"
        elif page == 'files':
            files = db.query(FileRecord).order_by(FileRecord.id.desc()).limit(20).all()
            rows = "".join([f"<tr><td>{f.file_name}</td><td>{f.file_type}</td><td><button class='action-btn' style='background:var(--danger);' onclick='performAction(\"delete_file\", {f.id})'>Delete</button></td></tr>" for f in files])
            html = f"<h1>Manage Files</h1><table><tr><th>File Name</th><th>Type</th><th>Actions</th></tr>{rows}</table>"
        elif page == 'admins':
            admins = db.query(BotUser).filter(BotUser.is_admin == True).all()
            rows = "".join([f"<tr><td><code>{a.user_id}</code></td><td>Admin</td><td><button class='action-btn' style='background:var(--accent);' onclick='performAction(\"remove_admin\", {a.user_id})'>Remove</button></td></tr>" for a in admins])
            html = f"<h1>Admin Directory</h1><table><tr><th>Admin ID</th><th>Role Level</th><th>Actions</th></tr>{rows}</table>"
    finally: db.close()
    return web.Response(text=html, content_type='text/html')

async def start_dashboard_server():
    app = web.Application()
    secret_key = base64.urlsafe_b64encode(hashlib.sha256(DASHBOARD_PASSWORD.encode()).digest())
    setup(app, EncryptedCookieStorage(base64.urlsafe_b64decode(secret_key), max_age=SESSION_TIME))

    app.router.add_static('/static/', path='dashboard/static', name='static')
    app.router.add_get('/', landing_page)
    app.router.add_get('/login', login_page)
    app.router.add_post('/login', login_post)
    app.router.add_get('/verify', verify_page)
    app.router.add_post('/verify', verify_post)
    app.router.add_post('/logout', logout)
    app.router.add_get('/dashboard', dashboard_page)
    app.router.add_post('/api/action', action_handler)
    app.router.add_get('/api/{page}', api_handler)
    app.router.add_get('/signup', signup_page)
    app.router.add_post('/signup', signup_post)

    port = int(os.environ.get("PORT", 8000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌍 SECURE Dashboard running on port {port}")
