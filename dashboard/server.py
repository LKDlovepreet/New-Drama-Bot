import os
import time
import base64
from aiohttp import web
import aiohttp_session
from aiohttp_session import setup, get_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography import fernet

from config.settings import DASHBOARD_PASSWORD, SESSION_TIME
from database.db import SessionLocal
from database.models import BotUser, FileRecord, Channel
from .otp_service import send_otp_to_owner, verify_otp

# --- HTML TEMPLATES (Link to CSS) ---
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Login</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
<div class="auth-container">
    <div class="auth-box">
        <h2>🔒 Owner Access</h2>
        <form action="/login" method="post">
            <input type="password" name="passkey" placeholder="Enter Password" required>
            <br>
            <button type="submit">Next ➡️</button>
        </form>
        <p class="error-msg">{error}</p>
    </div>
</div>
</body>
</html>
"""

VERIFY_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>2FA Verification</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
<div class="auth-container">
    <div class="auth-box">
        <h2>📲 Verification</h2>
        <p style="color:#ccc">OTP sent on your phone</p>
        <form action="/verify" method="post">
            <input type="text" name="otp" placeholder="xxx.com" required maxlength="6">
            <br>
            <button type="submit" style="background:#28a745">Verify 🔓</button>
        </form>
        <p class="error-msg">{error}</p>
    </div>
</div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Bot Dashboard</title>
    <link rel="stylesheet" href="/static/style.css">
    <script>
    async function loadData(page) {
        document.getElementById('main-view').innerHTML = '<p>Loading...</p>';
        document.querySelectorAll('.sidebar button').forEach(b => b.classList.remove('active'));
        document.getElementById('btn-'+page).classList.add('active');

        const res = await fetch('/api/' + page);
        const html = await res.text();
        document.getElementById('main-view').innerHTML = html;
    }
    </script>
</head>
<body class="dashboard-body" onload="loadData('status')">
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
</body>
</html>
"""

# --- HANDLERS ---
async def login_page(request):
    return web.Response(text=LOGIN_HTML.format(error=""), content_type='text/html')

async def login_post(request):
    data = await request.post()
    password = data.get('password')
    if password == DASHBOARD_PASSWORD:
        await send_otp_to_owner()
        session = await get_session(request)
        session['pre_auth'] = True
        raise web.HTTPFound('/verify')
    else:
        return web.Response(text=LOGIN_HTML.format(error="❌ Wrong Password!"), content_type='text/html')

async def verify_page(request):
    session = await get_session(request)
    if not session.get('pre_auth'): raise web.HTTPFound('/login')
    return web.Response(text=VERIFY_HTML.format(error=""), content_type='text/html')

async def verify_post(request):
    session = await get_session(request)
    if not session.get('pre_auth'): raise web.HTTPFound('/login')
    data = await request.post()
    success, msg = verify_otp(data.get('otp'))
    if success:
        session['authenticated'] = True
        session['login_time'] = time.time()
        del session['pre_auth']
        raise web.HTTPFound('/')
    else:
        return web.Response(text=VERIFY_HTML.format(error=msg), content_type='text/html')

async def logout(request):
    session = await get_session(request)
    session.clear()
    raise web.HTTPFound('/login')

async def dashboard(request):
    session = await get_session(request)
    if not session.get('authenticated') or (time.time() - session.get('login_time', 0) > SESSION_TIME):
        session.clear(); raise web.HTTPFound('/login')
    resp = web.Response(text=DASHBOARD_HTML, content_type='text/html')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp

# --- API HANDLERS (Same Logic, Updated HTML Structure for API responses) ---
async def api_handler(request):
    session = await get_session(request)
    if not session.get('authenticated'): return web.Response(text="Unauthorized", status=401)
    
    page = request.match_info['page']
    db = SessionLocal()
    html = ""
    try:
        if page == 'status':
            u = db.query(BotUser).count()
            f = db.query(FileRecord).count()
            c = db.query(Channel).count()
            html = f"""
            <h1>System Status</h1>
            <div class="stats-grid">
                <div class="card"><h3>Total Users</h3><h1>{u}</h1></div>
                <div class="card"><h3>Files Indexed</h3><h1>{f}</h1></div>
                <div class="card"><h3>Channels</h3><h1>{c}</h1></div>
            </div>
            <div class="card" style="text-align:left">
                <h3>Network Status</h3>
                <p style="color:green; font-weight:bold; margin-top:10px">🟢 All Systems Operational</p>
                <p>Dashboard Security: <span style="color:blue">Active (2FA)</span></p>
            </div>
            """
        elif page == 'users':
            users = db.query(BotUser).order_by(BotUser.id.desc()).limit(20).all()
            rows = "".join([f"<tr><td>{u.user_id}</td><td>{u.joined_date.strftime('%Y-%m-%d %H:%M')}</td></tr>" for u in users])
            html = f"<h1>Latest Users</h1><table><tr><th>User ID</th><th>Joined Date</th></tr>{rows}</table>"
        elif page == 'files':
            files = db.query(FileRecord).order_by(FileRecord.id.desc()).limit(20).all()
            rows = "".join([f"<tr><td>{f.file_name}</td><td>{f.file_type}</td></tr>" for f in files])
            html = f"<h1>Recent Files</h1><table><tr><th>Name</th><th>Type</th></tr>{rows}</table>"
        elif page == 'admins':
            admins = db.query(BotUser).filter(BotUser.is_admin == True).all()
            rows = "".join([f"<tr><td>{u.user_id}</td><td>Super Admin</td></tr>" for u in admins])
            html = f"<h1>Admin List</h1><table><tr><th>ID</th><th>Role</th></tr>{rows}</table>"
    finally: db.close()
    return web.Response(text=html, content_type='text/html')

# --- SERVER STARTUP ---
async def start_dashboard_server():
    app = web.Application()
    
    # Secure Cookies
    fernet_key = fernet.Fernet.generate_key()
    setup(app, EncryptedCookieStorage(base64.urlsafe_b64decode(fernet_key)))

    # 👇 STATIC FILES ROUTE (Bahut Zaroori)
    # Ye batata hai ki "/static" URL par "dashboard/static" folder dikhana hai
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
