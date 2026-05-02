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

async def landing_page(request): return web.Response(text=render_template("templates", "landing.html"), content_type='text/html')
async def login_page(request): return web.Response(text=render_template("templates", "login.html", error=""), content_type='text/html')
async def signup_page(request): return web.Response(text=render_template("templates", "signup.html", error=""), content_type='text/html')
async def verify_page(request): return web.Response(text=render_template("templates", "verify.html", error=""), content_type='text/html')

async def login_post(request):
    data = await request.post()
    login_id, password = data.get('login_id'), data.get('passkey')
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
            if not success: return web.Response(text=render_template("templates", "login.html", error=f"❌ {msg}"), content_type='text/html')
            session = await get_session(request)
            session['pre_auth'], session['user_role'], session['target_user_id'] = True, user.role, user.telegram_id
            return web.HTTPFound('/verify')
        return web.Response(text=render_template("templates", "login.html", error="❌ Invalid Credentials!"), content_type='text/html')
    finally: db.close()

async def signup_post(request):
    try:
        data = await request.post()
        full_name, dob, telegram_id, passkey = data.get('full_name'), data.get('dob'), data.get('telegram_id'), data.get('passkey')
        db = SessionLocal()
        if db.query(WebsiteUser).filter(WebsiteUser.telegram_id == int(telegram_id)).first():
            db.close(); return web.json_response({"success": False, "message": "ID already registered."})

        profile_pic_url = "https://i.pinimg.com/736x/8f/33/2d/8f332dd34b6e5114705bd364741db457.jpg"
        profile_pic_file = data.get('profile_pic')
        if profile_pic_file and hasattr(profile_pic_file, 'filename'):
            try:
                url = "https://api.cloudinary.com/v1_1/dordvtopl/image/upload"
                form_data = aiohttp.FormData()
                form_data.add_field('file', profile_pic_file.file.read(), filename=profile_pic_file.filename, content_type=profile_pic_file.content_type)
                form_data.add_field('upload_preset', 'Profile_pictures')
                async with aiohttp.ClientSession() as http_session:
                    async with http_session.post(url, data=form_data) as resp:
                        res = await resp.json()
                        if 'secure_url' in res: profile_pic_url = res['secure_url']
            except Exception: pass

        db.add(WebsiteUser(telegram_id=int(telegram_id), web_password=hashlib.sha256(passkey.encode()).hexdigest(), role='customer', full_name=full_name, dob=dob, profile_pic_url=profile_pic_url))
        db.commit(); db.close()
        session = await get_session(request)
        session['pre_auth'], session['user_role'], session['target_user_id'] = True, 'customer', int(telegram_id)
        return web.json_response({"success": True, "redirect": "/verify"})
    except Exception as e: return web.json_response({"success": False, "message": str(e)})

async def verify_post(request):
    session, data = await get_session(request), await request.post()
    role, target_id = session.get('user_role'), session.get('target_user_id') if session.get('user_role') != 'owner' else 'owner'
    success, msg = verify_otp(target_id, data.get('otp'))
    if success:
        session['authenticated'], session['login_time'] = True, time.time()
        del session['pre_auth']; return web.HTTPFound('/dashboard')
    return web.Response(text=render_template("templates", "verify.html", error=msg), content_type='text/html')

async def logout(request):
    session = await get_session(request)
    session.invalidate(); return web.HTTPFound('/')

# 🎯 SMART ROUTERS (Traffic Controller)
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
    role = session.get('user_role')
    page = request.match_info['page']
    if role == 'admin': return await admin_api_handler(request, page)
    elif role == 'customer': return await user_api_handler(request, page, session.get('target_user_id'))
    return web.Response(status=403)

async def smart_action(request):
    session = await get_session(request)
    if not session.get('authenticated') or session.get('user_role') != 'admin': return web.json_response({"success": False})
    data = await request.json()
    return await admin_action_handler(request, data)

async def smart_profile_update(request):
    session = await get_session(request)
    if not session.get('authenticated') or session.get('user_role') != 'customer': return web.json_response({"success": False})
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
        session = await get_session(request)
        session['pre_auth'], session['user_role'], session['target_user_id'] = True, 'customer', int(telegram_id)
        return web.json_response({"success": True, "redirect": "/verify"})
    except ValueError:
        return web.json_response({"success": False, "message": "Telegram ID must be numbers only!"})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})

async def verify_page(request):
    session = await get_session(request)
    if session.get('authenticated'): return web.HTTPFound('/dashboard')
    if not session.get('pre_auth'): return web.HTTPFound('/login')
    return web.Response(text=render_template("verify.html", error=""), content_type='text/html')

async def verify_post(request):
    session = await get_session(request)
    if not session.get('pre_auth'): return web.HTTPFound('/login')

    data = await request.post()
    otp = data.get('otp')
    role = session.get('user_role')
    target_id = session.get('target_user_id') if role != 'owner' else 'owner'

    success, msg = verify_otp(target_id, otp)

    if success:
        session['authenticated'], session['login_time'] = True, time.time()
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

    role = session.get('user_role', 'customer')
    
    if role == 'owner':
        lock_html = """<body style="background:#e5e7eb; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif; margin:0;"><div style="background:white; padding:40px; border-radius:12px; text-align:center; box-shadow:0 10px 25px rgba(0,0,0,0.1); max-width:400px;"><h1 style="font-size:50px; margin:0;">🚧</h1><h2 style="color:#374151;">Owner Panel Locked</h2><p style="color:#6b7280; margin-bottom:25px;">The Super-Admin system is currently undergoing complex security upgrades. Access is temporarily disabled.</p><form action="/logout" method="post"><button style="background:#ef4444; color:white; border:none; padding:12px 25px; border-radius:8px; cursor:pointer; font-weight:bold;">Log Out</button></form></div></body>"""
        return web.Response(text=lock_html, content_type='text/html')
        
    elif role == 'admin':
        resp = web.Response(text=render_template("admin_dashboard.html", error=""), content_type='text/html')
        
    else: 
        # Customer ke liye profile picture nikalna
        db = SessionLocal()
        user = db.query(WebsiteUser).filter(WebsiteUser.telegram_id == session.get('target_user_id')).first()
        pic_url = user.profile_pic_url if user else "https://ui-avatars.com/api/?name=User"
        db.close()
        resp = web.Response(text=render_template("customer_dashboard.html", profile_pic=pic_url), content_type='text/html')
        
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp

async def action_handler(request):
    session = await get_session(request)
    if not session.get('authenticated') or session.get('user_role') != 'admin':
        return web.json_response({"success": False, "message": "Unauthorized"})

    data = await request.json()
    action, target_id = data.get('action'), data.get('id')
    db = SessionLocal()
    try:
        if action == 'make_admin':
            u = db.query(BotUser).filter(BotUser.user_id == target_id).first()
            if u: u.is_admin, u.role = True, 'admin'
        elif action == 'remove_admin':
            u = db.query(BotUser).filter(BotUser.user_id == target_id).first()
            if u: u.is_admin, u.role = False, 'user'
        elif action == 'ban_user':
            u = db.query(BotUser).filter(BotUser.user_id == target_id).first()
            if u: u.is_global_banned = True
        elif action == 'delete_file':
            f = db.query(FileRecord).filter(FileRecord.id == target_id).first()
            if f: db.delete(f)
        db.commit()
        return web.json_response({"success": True})
    except Exception as e: return web.json_response({"success": False, "message": str(e)})
    finally: db.close()

# 👇 NAYA HANDLER: Profile Edit karne ke liye
async def update_profile_handler(request):
    session = await get_session(request)
    if not session.get('authenticated') or session.get('user_role') != 'customer':
        return web.json_response({"success": False, "message": "Unauthorized"})

    data = await request.post()
    target_id = session.get('target_user_id')
    
    db = SessionLocal()
    try:
        user = db.query(WebsiteUser).filter(WebsiteUser.telegram_id == target_id).first()
        if not user:
            return web.json_response({"success": False, "message": "User not found!"})

        user.full_name = data.get('full_name')
        user.dob = data.get('dob')
        user.email = data.get('email')
        user.mobile_number = data.get('mobile_number')

        profile_pic_file = data.get('profile_pic')
        if profile_pic_file and hasattr(profile_pic_file, 'filename') and profile_pic_file.filename:
            try:
                url = "https://api.cloudinary.com/v1_1/dordvtopl/image/upload"
                form_data = aiohttp.FormData()
                form_data.add_field('file', profile_pic_file.file.read(), filename=profile_pic_file.filename, content_type=profile_pic_file.content_type)
                form_data.add_field('upload_preset', 'Profile_pictures')

                async with aiohttp.ClientSession() as http_session:
                    async with http_session.post(url, data=form_data) as resp:
                        res_json = await resp.json()
                        if 'secure_url' in res_json:
                            user.profile_pic_url = res_json['secure_url']
            except Exception: pass
        
        db.commit()
        return web.json_response({"success": True})
    except Exception as e:
        db.rollback()
        return web.json_response({"success": False, "message": str(e)})
    finally:
        db.close()

async def api_handler(request):
    session = await get_session(request)
    if not session.get('authenticated'): return web.Response(text="Unauthorized", status=401)

    role = session.get('user_role')
    page = request.match_info['page']
    db = SessionLocal()
    html = ""
    try:
        # 👮 ADMIN PAGES
        if page in ['status', 'users', 'files', 'admins']:
            if role != 'admin': return web.Response(text="Access Denied: Admin Only", status=403)
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
                
        # 🛍️ CUSTOMER PAGES
        elif page == 'store':
            if role != 'customer': return web.Response(text="Access Denied", status=403)
            html = """
            <div class="welcome-msg" style="text-align: center; margin-bottom: 50px;">
                <h1 style="font-size: 32px; color: var(--bg-header); margin-bottom: 10px;">Welcome to your Dashboard! 🎉</h1>
                <p style="font-size: 16px; color: var(--text-muted);">Explore our premium bots, watch tutorials, and supercharge your Telegram communities.</p>
            </div>
            <div class="bot-cards-grid" style="grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 30px;">
                <div class="bot-card" style="cursor: default; transform: none; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                    <div class="card-header">
                        <h3>🔗 Smart Link Manager Bot</h3>
                        <span style="background: var(--success); padding: 4px 10px; border-radius: 6px; font-size: 12px; color: white; font-weight: 600;">Premium Service</span>
                    </div>
                    <div class="card-body">
                        <p style="margin-bottom: 20px;">Store files securely, generate auto-expiring deep links, and enforce force-subscribe channels effortlessly.</p>
                        <div style="background: #111; height: 200px; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; margin-bottom: 20px; position: relative;">
                            <span style="font-size: 40px;">▶️</span><p style="position: absolute; bottom: 10px; font-size: 12px; color: #aaa;">Watch Demo Tutorial</p>
                        </div>
                        <button style="width: 100%; padding: 14px; background: var(--bg-header); color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer;">🛍️ Buy & Connect Bot</button>
                    </div>
                </div>
            </div>
            """
        elif page == 'profile':
            if role != 'customer': return web.Response(text="Access Denied", status=403)
            user = db.query(WebsiteUser).filter(WebsiteUser.telegram_id == session.get('target_user_id')).first()
            # Yahan edit form banaya gaya hai
            html = f"""
            <div style="max-width: 600px; margin: 0 auto; background: var(--bg-panel); padding: 30px; border-radius: 12px; border: 1px solid var(--border);">
                <h2 style="color: var(--bg-header); margin-bottom: 25px; border-bottom: 1px solid var(--border); padding-bottom: 10px;">👤 My Profile</h2>
                <form id="profile-update-form" enctype="multipart/form-data">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <img src="{user.profile_pic_url}" id="preview-pic" style="width: 120px; height: 120px; border-radius: 50%; object-fit: cover; border: 4px solid var(--success); margin-bottom: 15px;">
                        <label style="border: 2px dashed var(--border); padding: 15px; text-align: center; border-radius: 8px; background: var(--bg-main); cursor: pointer; display: block;">
                            <input type="file" name="profile_pic" accept="image/*" style="display: none;" onchange="document.getElementById('preview-pic').src = window.URL.createObjectURL(this.files[0])">
                            🖼️ Tap to Change Picture
                        </label>
                    </div>
                    <div class="input-group" style="text-align: left;">
                        <label style="font-size: 13px; color: var(--text-muted); display: block; margin-bottom: 5px; font-weight: 500;">Full Name</label>
                        <input type="text" name="full_name" value="{user.full_name}" required style="width: 100%; padding: 12px; background: var(--bg-main); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 15px; outline: none;">
                        
                        <label style="font-size: 13px; color: var(--text-muted); display: block; margin-bottom: 5px; font-weight: 500;">Date of Birth</label>
                        <input type="date" name="dob" value="{user.dob}" required style="width: 100%; padding: 12px; background: var(--bg-main); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 15px; outline: none;">
                        
                        <label style="font-size: 13px; color: var(--text-muted); display: block; margin-bottom: 5px; font-weight: 500;">Email Address</label>
                        <input type="email" name="email" value="{user.email}" style="width: 100%; padding: 12px; background: var(--bg-main); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 15px; outline: none;">
                        
                        <label style="font-size: 13px; color: var(--text-muted); display: block; margin-bottom: 5px; font-weight: 500;">Mobile Number</label>
                        <input type="tel" name="mobile_number" value="{user.mobile_number}" style="width: 100%; padding: 12px; background: var(--bg-main); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 15px; outline: none;">
                        
                        <label style="font-size: 13px; color: var(--danger); display: block; margin-bottom: 5px; font-weight: 500;">Telegram ID (Cannot be changed)</label>
                        <input type="text" value="{user.telegram_id}" disabled style="width: 100%; padding: 12px; background: #e5e7eb; border: 1px solid var(--border); border-radius: 8px; margin-bottom: 25px; cursor: not-allowed; color: var(--text-muted);">
                    </div>
                    <button type="submit" id="update-btn" style="width: 100%; padding: 14px; background: var(--success); color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 16px;">Save Changes 💾</button>
                </form>
            </div>
            <script>
                document.getElementById("profile-update-form").addEventListener("submit", async function(e) {{
                    e.preventDefault();
                    const formData = new FormData(this);
                    const btn = document.getElementById('update-btn');
                    btn.innerText = "Saving Details..."; btn.disabled = true;
                    try {{
                        const res = await fetch('/api/update_profile', {{ method: 'POST', body: formData }});
                        const data = await res.json();
                        if(data.success) {{
                            alert("Profile Updated Successfully!");
                            // Page refresh taaki top navbar ki DP bhi update ho jaye
                            window.location.reload(); 
                        }} else {{
                            alert("Error: " + data.message);
                        }}
                    }} catch(err) {{ alert("Network Error!"); }}
                    btn.innerText = "Save Changes 💾"; btn.disabled = false;
                }});
            </script>
            """
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
    # Naya route for profile update
    app.router.add_post('/api/update_profile', update_profile_handler)
    app.router.add_get('/api/{page}', api_handler)
    app.router.add_get('/signup', signup_page)
    app.router.add_post('/signup', signup_post)

    port = int(os.environ.get("PORT", 8000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌍 SECURE Dashboard running on port {port}")
