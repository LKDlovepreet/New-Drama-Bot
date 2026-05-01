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

# --- TEMPLATE RENDERER ---
def render_template(filename, **kwargs):
    filepath = os.path.join("dashboard", "templates", filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    for key, value in kwargs.items():
        content = content.replace(f"{{{key}}}", str(value))
        
    return content

# --- HANDLERS ---
async def login_page(request):
    session = await get_session(request)
    if session.get('authenticated'):
        return web.HTTPFound('/')
        
    html = render_template("login.html", error="")
    return web.Response(text=html, content_type='text/html')

async def login_post(request):
    data = await request.post()
    password = data.get('passkey') 
    
    if password == DASHBOARD_PASSWORD:
        await send_otp_to_owner()
        session = await get_session(request)
        session['pre_auth'] = True
        return web.HTTPFound('/verify')
    else:
        html = render_template("login.html", error="❌ Wrong Password!")
        return web.Response(text=html, content_type='text/html')

async def verify_page(request):
    session = await get_session(request)
    if session.get('authenticated'):
        return web.HTTPFound('/')
    if not session.get('pre_auth'): 
        return web.HTTPFound('/login')
        
    html = render_template("verify.html", error="")
    return web.Response(text=html, content_type='text/html')

async def verify_post(request):
    session = await get_session(request)
    if not session.get('pre_auth'): 
        return web.HTTPFound('/login')
    
    data = await request.post()
    success, msg = verify_otp(data.get('otp'))
    
    if success:
        session['authenticated'] = True
        session['login_time'] = time.time()
        del session['pre_auth']
        return web.HTTPFound('/')
    else:
        html = render_template("verify.html", error=msg)
        return web.Response(text=html, content_type='text/html')

async def logout(request):
    session = await get_session(request)
    session.invalidate()
    return web.HTTPFound('/login')

async def dashboard(request):
    session = await get_session(request)
    if not session.get('authenticated') or (time.time() - session.get('login_time', 0) > SESSION_TIME):
        session.invalidate()
        return web.HTTPFound('/login')
    
    html = render_template("dashboard.html", error="")
    resp = web.Response(text=html, content_type='text/html')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp

# --- API HANDLERS ---
async def api_handler(request):
    session = await get_session(request)
    if not session.get('authenticated'):
        return web.Response(text="Unauthorized", status=401)
    
    page = request.match_info['page']
    db = SessionLocal()
    html = ""
    try:
        if page == 'status':
            u = db.query(BotUser).count()
            f = db.query(FileRecord).count()
            c = db.query(Channel).count()
            
            html = f"""
            <div class="welcome-msg">
                <h1>Welcome back, Boss! 👋</h1>
                <p>System is running smoothly. Here is your live overview.</p>
            </div>
            
            <div class="bot-cards-grid">
                <a href="#bot1_details" class="bot-card">
                    <div class="card-header">
                        <h3>Link Manager Bot</h3>
                        <span class="live-dot"></span>
                    </div>
                    <div class="card-body">
                        <p>Handling Deep Linking, File Storage & User Broadcasting automatically.</p>
                        <div class="bot-stats">📁 Indexed Files: {f}</div>
                    </div>
                </a>

                <a href="#bot2_details" class="bot-card">
                    <div class="card-header">
                        <h3>Group Guard Bot</h3>
                        <span class="live-dot"></span>
                    </div>
                    <div class="card-body">
                        <p>Managing Security, Auto-replies, Anti-Spam & Warning Systems.</p>
                        <div class="bot-stats">👥 Active Users: {u}</div>
                    </div>
                </a>
                
                <a href="#security_details" class="bot-card">
                    <div class="card-header">
                        <h3>System API Security</h3>
                        <span class="live-dot" style="background: var(--bg-sidebar); animation: none; box-shadow: none;"></span>
                    </div>
                    <div class="card-body">
                        <p>Core Database, Security Logs & 2FA Authentication Engine.</p>
                        <div class="bot-stats">🛡️ 2FA Protected</div>
                    </div>
                </a>
            </div>
            """
        elif page == 'users':
            users = db.query(BotUser).order_by(BotUser.id.desc()).limit(20).all()
            rows = "".join([f"<tr><td><code>{user.user_id}</code></td><td>{user.joined_date.strftime('%Y-%m-%d %H:%M')}</td></tr>" for user in users])
            html = f"<h1>Latest Users</h1><table><tr><th>User ID</th><th>Joined Date</th></tr>{rows}</table>"
        elif page == 'files':
            files = db.query(FileRecord).order_by(FileRecord.id.desc()).limit(20).all()
            rows = "".join([f"<tr><td>{file.file_name}</td><td><span style='background:rgba(255,255,255,0.1); padding:4px 8px; border-radius:4px; font-size:12px;'>{file.file_type}</span></td></tr>" for file in files])
            html = f"<h1>Recent Files</h1><table><tr><th>File Name</th><th>Type</th></tr>{rows}</table>"
        elif page == 'admins':
            admins = db.query(BotUser).filter(BotUser.is_admin == True).all()
            rows = "".join([f"<tr><td><code>{admin.user_id}</code></td><td><span style='color:var(--success)'>Super Admin</span></td></tr>" for admin in admins])
            html = f"<h1>Admin Directory</h1><table><tr><th>Admin ID</th><th>Role Level</th></tr>{rows}</table>"
    finally:
        db.close()
        
    return web.Response(text=html, content_type='text/html')

# --- SERVER STARTUP ---
async def start_dashboard_server():
    app = web.Application()
    
    secret_hash = hashlib.sha256(DASHBOARD_PASSWORD.encode()).digest()
    secret_key = base64.urlsafe_b64encode(secret_hash)
    
    setup(app, EncryptedCookieStorage(base64.urlsafe_b64decode(secret_key), max_age=SESSION_TIME))

    app.router.add_static('/static/', path='dashboard/static', name='static')

    app.router.add_get('/login', login_page)
    app.router.add_post('/login', login_post)
    app.router.add_get('/verify', verify_page)
    app.router.add_post('/verify', verify_post)
    app.router.add_post('/logout', logout)
    app.router.add_get('/', dashboard)
    app.router.add_get('/api/{page}', api_handler)

    port = int(os.environ.get("PORT", 8000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌍 SECURE Dashboard running on port {port}")
