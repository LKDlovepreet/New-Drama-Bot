from aiohttp import web

async def owner_dashboard(request):
    lock_html = """
    <body style="background:#e5e7eb; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif; margin:0;">
        <div style="background:white; padding:40px; border-radius:12px; text-align:center; box-shadow:0 10px 25px rgba(0,0,0,0.1); max-width:400px;">
            <h1 style="font-size:50px; margin:0;">🚧</h1>
            <h2 style="color:#374151;">Owner Panel Locked</h2>
            <p style="color:#6b7280; margin-bottom:25px;">The Super-Admin system is currently undergoing complex security upgrades. Access is temporarily disabled.</p>
            <form action="/logout" method="post"><button style="background:#ef4444; color:white; border:none; padding:12px 25px; border-radius:8px; cursor:pointer; font-weight:bold;">Log Out</button></form>
        </div>
    </body>
    """
    resp = web.Response(text=lock_html, content_type='text/html')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp
