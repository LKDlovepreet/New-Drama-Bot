import os, time, base64, hashlib, aiohttp
from aiohttp import web
from aiohttp_session import setup, get_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from config.settings import DASHBOARD_PASSWORD, SESSION_TIME
from dashboard.utils import render_template
from dashboard.owner.owner_views import owner_dashboard
from dashboard.admin.admin_views import admin_dashboard, admin_api_handler, admin_action_handler
from dashboard.user.user_views import user_dashboard, user_api_handler, update_profile_handler

async def smart_dashboard(request):
    session = await get_session(request)
    if not session.get('authenticated'): return web.HTTPFound('/login')
    role = session.get('user_role')
    if role == 'owner': return await owner_dashboard(request)
    if role == 'admin': return await admin_dashboard(request)
    return await user_dashboard(request)

async def smart_api(request):
    session = await get_session(request)
    role, page = session.get('user_role'), request.match_info['page']
    if role == 'admin': return await admin_api_handler(request, page)
    return await user_api_handler(request, page, session.get('target_user_id'))

async def start_dashboard_server():
    app = web.Application()
    secret_key = base64.urlsafe_b64encode(hashlib.sha256(DASHBOARD_PASSWORD.encode()).digest())
    setup(app, EncryptedCookieStorage(base64.urlsafe_b64decode(secret_key), max_age=SESSION_TIME))

    # Static Folders Create & Mount
    for f in ['dashboard/owner/static', 'dashboard/admin/static', 'dashboard/user/static', 'dashboard/static']:
        os.makedirs(f, exist_ok=True)

    app.router.add_static('/static/admin/', 'dashboard/admin/static')
    app.router.add_static('/static/user/', 'dashboard/user/static')
    app.router.add_static('/static/', 'dashboard/static')

    # Routes
    app.router.add_get('/dashboard', smart_dashboard)
    app.router.add_get('/api/{page}', smart_api)
    # Login/Signup routes yahan purane wale hi rahenge...

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 8000).start()
    print("🌍 Server started at port 8000")
