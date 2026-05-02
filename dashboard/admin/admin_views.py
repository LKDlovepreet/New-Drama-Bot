from aiohttp import web
from database.db import SessionLocal
from database.models import BotUser, FileRecord, Channel
from dashboard.utils import render_template

async def admin_dashboard(request):
    return web.Response(text=render_template("admin/templates", "admin_dashboard.html"), content_type='text/html')

async def admin_api_handler(request, page):
    db = SessionLocal()
    html = ""
    try:
        if page == 'status':
            u, f = db.query(BotUser).count(), db.query(FileRecord).count()
            html = f"<h1>System Status</h1><p>Users: {u}</p><p>Files: {f}</p>"
        elif page == 'users':
            users = db.query(BotUser).limit(20).all()
            rows = "".join([f"<tr><td>{u.user_id}</td><td><button onclick='performAction(\"ban\", {u.user_id})'>Ban</button></td></tr>" for u in users])
            html = f"<table>{rows}</table>"
    finally: db.close()
    return web.Response(text=html, content_type='text/html')

async def admin_action_handler(request, data):
    # Add your ban/make_admin logic here
    return web.json_response({"success": True})
