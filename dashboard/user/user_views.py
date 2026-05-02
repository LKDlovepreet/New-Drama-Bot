import aiohttp
from aiohttp import web
from aiohttp_session import get_session
from database.db import SessionLocal
from database.models import WebsiteUser
from dashboard.utils import render_template

async def user_dashboard(request):
    session = await get_session(request)
    db = SessionLocal()
    user = db.query(WebsiteUser).filter(WebsiteUser.telegram_id == session.get('target_user_id')).first()
    pic_url = user.profile_pic_url if user else "https://ui-avatars.com/api/?name=User"
    db.close()
    
    resp = web.Response(text=render_template("user/templates", "customer_dashboard.html", profile_pic=pic_url), content_type='text/html')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp

async def user_api_handler(request, page, target_id):
    db = SessionLocal()
    try:
        if page == 'store':
            html = """<div class="welcome-msg" style="text-align: center; margin-bottom: 50px;"><h1 style="font-size: 32px; color: var(--bg-header); margin-bottom: 10px;">Welcome to your Dashboard! 🎉</h1><p style="font-size: 16px; color: var(--text-muted);">Explore our premium bots.</p></div><div class="bot-cards-grid" style="grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 30px;"><div class="bot-card" style="box-shadow: 0 4px 15px rgba(0,0,0,0.05);"><div class="card-header"><h3>🔗 Smart Link Manager Bot</h3><span style="background: var(--success); padding: 4px 10px; border-radius: 6px; font-size: 12px; color: white;">Premium</span></div><div class="card-body"><button style="width: 100%; padding: 14px; background: var(--bg-header); color: white; border: none; border-radius: 8px;">🛍️ Buy & Connect</button></div></div></div>"""
            return web.Response(text=html, content_type='text/html')
        elif page == 'profile':
            user = db.query(WebsiteUser).filter(WebsiteUser.telegram_id == target_id).first()
            html = f"""<div style="max-width: 600px; margin: 0 auto; background: var(--bg-panel); padding: 30px; border-radius: 12px; border: 1px solid var(--border);"><h2 style="color: var(--bg-header); margin-bottom: 25px; border-bottom: 1px solid var(--border); padding-bottom: 10px;">👤 My Profile</h2><form id="profile-update-form" enctype="multipart/form-data"><div style="text-align: center; margin-bottom: 30px;"><img src="{user.profile_pic_url}" id="preview-pic" style="width: 120px; height: 120px; border-radius: 50%; object-fit: cover; border: 4px solid var(--success); margin-bottom: 15px;"><label style="border: 2px dashed var(--border); padding: 15px; border-radius: 8px; cursor: pointer; display: block;"><input type="file" name="profile_pic" accept="image/*" style="display: none;" onchange="document.getElementById('preview-pic').src = window.URL.createObjectURL(this.files[0])">🖼️ Tap to Change Picture</label></div><div class="input-group" style="text-align: left;"><label style="font-size: 13px; color: var(--text-muted);">Full Name</label><input type="text" name="full_name" value="{user.full_name}" required style="width: 100%; padding: 12px; border-radius: 8px; margin-bottom: 15px;"><label style="font-size: 13px; color: var(--text-muted);">Date of Birth</label><input type="date" name="dob" value="{user.dob}" required style="width: 100%; padding: 12px; border-radius: 8px; margin-bottom: 15px;"></div><button type="submit" id="update-btn" style="width: 100%; padding: 14px; background: var(--success); color: white; border: none; border-radius: 8px;">Save Changes 💾</button></form></div>
            <script>document.getElementById("profile-update-form").addEventListener("submit", async function(e) {{ e.preventDefault(); const formData = new FormData(this); const btn = document.getElementById('update-btn'); btn.innerText = "Saving..."; btn.disabled = true; try {{ const res = await fetch('/api/update_profile', {{ method: 'POST', body: formData }}); const data = await res.json(); if(data.success) {{ window.location.reload(); }} else {{ alert(data.message); }} }} catch(err) {{ alert("Error"); }} btn.innerText = "Save Changes 💾"; btn.disabled = false; }});</script>"""
            return web.Response(text=html, content_type='text/html')
    finally: db.close()

async def update_profile_handler(request, target_id):
    data = await request.post()
    db = SessionLocal()
    try:
        user = db.query(WebsiteUser).filter(WebsiteUser.telegram_id == target_id).first()
        user.full_name, user.dob = data.get('full_name'), data.get('dob')
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
                        if 'secure_url' in res_json: user.profile_pic_url = res_json['secure_url']
            except Exception: pass
        db.commit()
        return web.json_response({"success": True})
    except Exception as e: return web.json_response({"success": False, "message": str(e)})
    finally: db.close()
