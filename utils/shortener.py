import aiohttp
from config.settings import ADRINOLINKS_API

async def get_short_link(long_url):
    try:
        # Check API Key
        if "YOUR_ADRINOLINKS_API_KEY" in ADRINOLINKS_API:
            print("❌ Error: AdrinoLinks API Key set nahi hai!")
            return None

        # API URL
        api_url = f"https://adrinolinks.com/api?api={ADRINOLINKS_API}&url={long_url}&format=text"
        
        # 👇 MAGIC FIX: Fake Browser Headers
        # Isse website ko lagega ki request Computer ke Chrome browser se aa rahi hai
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }

        async with aiohttp.ClientSession() as session:
            # 👇 yahan headers pass kiye hain
            async with session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    result = await response.text()
                    result = result.strip()
                    
                    # Debugging ke liye print (Logs me dikhega kya aaya)
                    print(f"🔗 API Response: {result[:50]}...") 

                    # Agar link http se shuru hota hai to sahi hai
                    if result.startswith("http"):
                        return result
                    else:
                        print(f"❌ Shortener Blocked/Error: {result}")
                        return None
                else:
                    print(f"❌ HTTP Error: {response.status}")
                    return None
    except Exception as e:
        print(f"❌ Shortener Exception: {e}")
        return None
