from aiohttp import web
from database.db import SessionLocal
from database.models import BotUser, FileRecord, Channel
from dashboard.utils import render_template

async def admin_dashboard(request):
    resp = web.Response(text=render_template("admin/templates", "admin_dashboard.html", error=""), content_type='text/html')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp

async def admin_action_handler(request, data):
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

async def admin_api_handler(request, page):
    db = SessionLocal()
    html = ""
    try:
        if page == 'status':
            u, f, c = db.query(BotUser).count(), db.query(FileRecord).count(), db.query(Channel).count()
            html = f"""<div class="welcome-msg"><h1>Welcome back, Admin! 👋</h1><p>System is running smoothly.</p></div>
            <div class="bot-cards-grid"><a href="#bot1" class="bot-card"><div class="card-header"><h3>Link Manager Bot</h3><span class="live-dot"></span></div><div class="card-body"><p>Handling Deep Linking.</p><div class="bot-stats">📁 Indexed Files: {f}</div></div></a></div>"""
        elif page == 'users':
            users = db.query(BotUser).order_by(BotUser.id.desc()).limit(20).all()
            rows = "".join([f"<tr><td><code>{u.user_id}</code></td><td>{u.joined_date.strftime('%Y-%m-%d')}</td><td><button class='action-btn' style='background:var(--success);' onclick='performAction(\"make_admin\", {u.user_id})'>Make Admin</button></td></tr>" for u in users])
            html = f"<h1>Manage Users</h1><table><tr><th>User ID</th><th>Joined Date</th><th>Actions</th></tr>{rows}</table>"
        elif page == 'files':
            files = db.query(FileRecord).order_by(FileRecord.id.desc()).limit(20).all()
            rows = "".join([f"<tr><td>{f.file_name}</td><td>{f.file_type}</td><td><button class='action-btn' style='background:var(--danger);' onclick='performAction(\"delete_file\", {f.id})'>Delete</button></td></tr>" for f in files])
            html = f"<h1>Manage Files</h1><table><tr><th>File Name</th><th>Type</th><th>Actions</th></tr>{rows}</table>"
    finally: db.close()
    return web.Response(text=html, content_type='text/html')
