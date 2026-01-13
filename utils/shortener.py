import aiohttp
from config.settings import ADRINOLINKS_API

async def get_short_link(long_url):
    try:
        # AdrinoLinks API Format: https://adrinolinks.com/api?api=APIKEY&url=URL
        api_url = f"https://adrinolinks.com/api?api={ADRINOLINKS_API}&url={long_url}&format=text"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    return None
    except Exception as e:
        print(f"Shortener Error: {e}")
        return None
