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
from sqlalchemy import String
from database.models import BotUser, FileRecord, Channel
from dashboard.otp_service import send_otp_to_owner, send_otp_to_customer, verify_otp
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
    login_id = data.get('login_id')
    password = data.get('passkey')
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    
    db = SessionLocal()
    try:
        # Check if it's the Master Owner (Environment Variable wala)
        if login_id == "owner" and password == DASHBOARD_PASSWORD:
            await send_otp_to_owner()
            session = await get_session(request)
            session['pre_auth'] = True
            session['user_role'] = 'owner'
            return web.HTTPFound('/verify')

        # Check for Customer/Admin in Database
        user = db.query(BotUser).filter(
            (BotUser.web_username == login_id) | (BotUser.user_id.cast(String) == login_id)
        ).filter(BotUser.web_password == hashed_pw).first()

        if user:
            # TODO: Send OTP to user's Telegram via Bot 3
            session = await get_session(request)
            session['pre_auth'] = True
            session['user_role'] = user.role
            session['target_user_id'] = user.user_id
            return web.HTTPFound('/verify')
        else:
            return web.Response(text=render_template("login.html", error="❌ Invalid Credentials!"), content_type='text/html')
    finally:
        db.close()

async def verify_post(request):
    session = await get_session(request)
    if not session.get('pre_auth'): return web.HTTPFound('/login')
    
    data = await request.post()
    otp = data.get('otp')
    
    # Simple OTP check for now (verify_otp logic)
    success, msg = verify_otp(otp)
    
    if success:
        session['authenticated'] = True
        session['login_time'] = time.time()
        role = session.get('user_role')
        del session['pre_auth']
        
        # Role ke hisaab se alag page par bhejna
        if role == 'owner':
            return web.HTTPFound('/dashboard')
        else:
            return web.HTTPFound('/customer-panel') # Naya Customer Panel
    else:
        return web.Response(text=render_template("verify.html", error=msg), content_type='text/html')

async def signup_page(request):
    html = render_template("signup.html", error="")
    return web.Response(text=html, content_type='text/html')

async def signup_post(request):
    # Enctype multipart/form-data hone ke kaaran post() se data lenge
    data = await request.post()
    
    full_name, dob, telegram_id = data.get('full_name'), data.get('dob'), data.get('telegram_id')
    passkey, email, mobile = data.get('passkey'), data.get('email'), data.get('mobile_number')
    
    profile_pic_url = "https://i.pinimg.com/736x/8f/33/2d/8f332dd34b6e5114705bd364741db457.jpg" # Default Oggy
    
    # --- Backend Cloudinary Upload System ---
    profile_pic_file = data.get('profile_pic')
    if profile_pic_file and profile_pic_file.filename:
        try:
            # File ko read karna aur Cloudinary par bhejna
            url = "https://api.cloudinary.com/v1_1/dordvtopl/image/upload"
            form_data = aiohttp.FormData()
            form_data.add_field('file', profile_pic_file.file.read(), filename=profile_pic_file.filename, content_type=profile_pic_file.content_type)
            form_data.add_field('upload_preset', 'Profile_pictures')
            
            async with aiohttp.ClientSession() as http_session:
                async with http_session.post(url, data=form_data) as resp:
                    res_json = await resp.json()
                    if 'secure_url' in res_json:
                        profile_pic_url = res_json['secure_url']
        except Exception as e:
            print("Cloudinary Upload Error:", str(e))
    # ----------------------------------------

    db = SessionLocal()
    try:
        hashed_password = hashlib.sha256(passkey.encode()).hexdigest()
        new_user = BotUser(
            user_id=int(telegram_id),
            web_username=telegram_id, web_password=hashed_password, role='customer',
            full_name=full_name, dob=dob, email=email, mobile_number=mobile, profile_pic_url=profile_pic_url
        )
        db.add(new_user)
        db.commit()
        
        # User details save ho gayi, ab seedha Verify Page par bhejo OTP lene ke liye
        session = await get_session(request)
        session['pre_auth'] = True
        session['user_role'] = 'customer'
        session['target_user_id'] = int(telegram_id)
        
        return web.HTTPFound('/verify')
        
    except ValueError:
        return web.Response(text=render_template("signup.html", error="❌ Telegram ID must be Numbers only!"), content_type='text/html')
    except Exception as e:
        db.rollback()
        return web.Response(text=render_template("signup.html", error="❌ ID already exists! Please Login."), content_type='text/html')
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
