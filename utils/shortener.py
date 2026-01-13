import aiohttp
from config.settings import ADRINOLINKS_API

async def get_short_link(long_url):
    try:
        # Agar API Key set nahi ki hai to yahi rok do
        if "YOUR_ADRINOLINKS_API_KEY" in ADRINOLINKS_API:
            print("❌ Error: AdrinoLinks API Key set nahi hai config/settings.py mein!")
            return None

        api_url = f"https://adrinolinks.com/api?api={ADRINOLINKS_API}&url={long_url}&format=text"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    result = await response.text()
                    result = result.strip() # Extra spaces hatana
                    
                    # 👇 Check karein ki ye valid link hai ya nahi
                    if result.startswith("http"):
                        return result
                    else:
                        print(f"❌ Shortener API Error: {result}") # Console me error dikhega
                        return None
                else:
                    print(f"❌ HTTP Error: {response.status}")
                    return None
    except Exception as e:
        print(f"❌ Shortener Exception: {e}")
        return None
