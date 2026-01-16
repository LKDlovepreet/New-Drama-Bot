import os
import time
from aiohttp import web
import aiohttp_session
from aiohttp_session import setup, get_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography import fernet
import base64

from config.settings import DASHBOARD_PASSWORD, SESSION_TIME
from database.db import SessionLocal
from database.models import BotUser, FileRecord, Channel, GroupSettings
from .otp_service import send_otp_to_owner, verify_otp

# --- HTML TEMPLATES (Internal) ---
LOGIN_HTML = """
<!DOCTYPE html>
<html><head><title>Login</title>
<style>body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;background:#1e1e1e;color:white}
.box{background:#2d2d2d;padding:30px;border-radius:10px;text-align:center;box-shadow:0 0 20px rgba(0,0,0,0.5)}
input{padding:10px;margin:10px 0;width:80%;border-radius:5px;border:none}
button{padding:10px 20px;background:#0088cc;color:white;border:none;border-radius:5px;cursor:pointer}
</style></head><body>
<div class="box">
    <h2>🔒 Admin Access</h2>
    <form action="/login" method="post">
        <input type="password" name="password" placeholder="Enter Password" required><br>
        <button type="submit">Next ➡️</button>
    </form>
    <p style="color:red">{error}</p>
</div></body></html>
"""

VERIFY_HTML = """
<!DOCTYPE html>
<html><head><title>2FA Verification</title>
<style>body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;background:#1e1e1e;color:white}
.box{background:#2d2d2d;padding:30px;border-radius:10px;text-align:center}
input{padding:10px;margin:10px 0;width:80%;font-size:20px;letter-spacing:5px;text-align:center}
button{background:#28a745;color:white;border:none;padding:10px 20px;border-radius:5px;cursor:pointer}
</style></head><body>
<div class="box">
    <h2>📲 Two-Step Verification</h2>
    <p>OTP sent to your Telegram.</p>
    <form action="/verify" method="post">
        <input type="text" name="otp" placeholder="123456" required maxlength="6"><br>
        <button type="submit">Verify & Login 🔓</button>
    </form>
    <p style="color:red">{error}</p>
</div></body></html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html><head><title>Bot Dashboard</title>
<style>
body { margin:0; font-family: 'Segoe UI', sans-serif; display: flex; height: 100vh; background: #f4f6f9; }
.sidebar { width: 250px; background: #343a40; color: white; display: flex; flex-direction: column; }
.sidebar h2 { text-align: center; padding: 20px 0; background: #212529; margin:0; }
.sidebar button { background: none; border: none; color: #ddd; padding: 15px; text-align: left; cursor: pointer; font-size: 16px; border-bottom: 1px solid #4b545c; }
.sidebar button:hover { background: #495057; color: white; }
.sidebar button.active { background: #007bff; color: white; }
.content { flex: 1; padding: 20px; overflow-y: auto; }
.card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
.logout { margin-top: auto; background: #dc3545 !important; }
</style>
<script>
async function loadData(page) {
    document.getElementById('main-view').innerHTML = '<p>Loading...</p>';
    // Update active button
    document.querySelectorAll('.sidebar button').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-'+page).classList.add('active');

    const res = await fetch('/api/' + page);
    const html = await res.text();
    document.getElementById('main-view').innerHTML = html;
}
</script>
</head>
<body onload="loadData('status')">
    <div class="sidebar">
        <h2>🤖 Control Panel</h2>
        <button id="btn-status" onclick="loadData('status')">📊 Status & Traffic</button>
        <button id="btn-users" onclick="loadData('users')">👥 Users</button>
        <button id="btn-files" onclick="loadData('files')">📂 Files</button>
        <button id="btn-admins" onclick="loadData('admins')">👮 Admins</button>
        <form action="/logout" method="post"><button class="logout">🚪 Logout</button></form>
    </div>
    <div class="content" id="main-view">
        </div>
</body></html>
"""

# --- HANDLERS ---

async def login_page(request):
    return web.Response(text=LOGIN_HTML.format(error=""), content_type='text/html')

async def login_post(request):
    data = await request.post()
    password = data.get('password')
    
    if password == DASHBOARD_PASSWORD:
        # Password Sahi -> Send OTP
        await send_otp_to_owner()
        # Temporary Cookie to allow access to Verify page
        session = await get_session(request)
        session['pre_auth'] = True
        raise web.HTTPFound('/verify')
    else:
        return web.Response(text=LOGIN_HTML.format(error="❌ Wrong Password! Alert Sent."), content_type='text/html')

async def verify_page(request):
    session = await get_session(request)
    if not session.get('pre_auth'):
        raise web.HTTPFound('/login')
    return web.Response(text=VERIFY_HTML.format(error=""), content_type='text/html')

async def verify_post(request):
    session = await get_session(request)
    if not session.get('pre_auth'):
        raise web.HTTPFound('/login')
        
    data = await request.post()
    otp = data.get('otp')
    
    success, msg = verify_otp(otp)
    if success:
        # LOGIN SUCCESS -> Set Full Session
        session['authenticated'] = True
        session['login_time'] = time.time()
        del session['pre_auth'] # Cleanup
        raise web.HTTPFound('/')
    else:
        return web.Response(text=VERIFY_HTML.format(error=msg), content_type='text/html')

async def logout(request):
    session = await get_session(request)
    session.clear()
    raise web.HTTPFound('/login')

async def dashboard(request):
    session = await get_session(request)
    if not session.get('authenticated'):
        raise web.HTTPFound('/login')
        
    # Check Session Timeout
    if time.time() - session.get('login_time', 0) > SESSION_TIME:
        session.clear()
        raise web.HTTPFound('/login')

    response = web.Response(text=DASHBOARD_HTML, content_type='text/html')
    # 🔒 NO CACHE HEADER (Browser data save nahi karega)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

# --- API HANDLERS (Dynamic Data) ---
async def api_handler(request):
    session = await get_session(request)
    if not session.get('authenticated'): return web.Response(text="Unauthorized", status=401)
    
    page = request.match_info['page']
    db = SessionLocal()
    html = ""
    
    try:
        if page == 'status':
            u_count = db.query(BotUser).count()
            f_count = db.query(FileRecord).count()
            ch_count = db.query(Channel).count()
            html = f"""
            <h1>System Status</h1>
            <div style="display:flex; gap:20px">
                <div class="card"><h3>Total Users</h3><h1>{u_count}</h1></div>
                <div class="card"><h3>Files Indexed</h3><h1>{f_count}</h1></div>
                <div class="card"><h3>Channels</h3><h1>{ch_count}</h1></div>
            </div>
            <div class="card"><h3>Network</h3><p>🟢 Bot is Online</p><p>🚀 Response Time: Fast</p></div>
            """
        
        elif page == 'users':
            users = db.query(BotUser).order_by(BotUser.id.desc()).limit(20).all()
            rows = "".join([f"<tr><td>{u.user_id}</td><td>{u.joined_date}</td></tr>" for u in users])
            html = f"<h1>Latest Users</h1><table border='1' width='100%'><tr><th>ID</th><th>Date</th></tr>{rows}</table>"

        elif page == 'admins':
            admins = db.query(BotUser).filter(BotUser.is_admin == True).all()
            rows = "".join([f"<tr><td>{u.user_id}</td><td>Admin</td></tr>" for u in admins])
            html = f"<h1>Admin List</h1><table border='1' width='100%'><tr><th>ID</th><th>Role</th></tr>{rows}</table>"
            
        elif page == 'files':
            files = db.query(FileRecord).order_by(FileRecord.id.desc()).limit(20).all()
            rows = "".join([f"<tr><td>{f.file_name}</td><td>{f.file_type}</td></tr>" for f in files])
            html = f"<h1>Recent Files</h1><table border='1' width='100%'><tr><th>Name</th><th>Type</th></tr>{rows}</table>"

    finally:
        db.close()
        
    return web.Response(text=html, content_type='text/html')

# --- SETUP SERVER ---
async def start_dashboard_server():
    app = web.Application()
    
    # Secret Key for Encryption
    fernet_key = fernet.Fernet.generate_key()
    secret_key = base64.urlsafe_b64decode(fernet_key)
    setup(app, EncryptedCookieStorage(secret_key))

    # Routes
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
