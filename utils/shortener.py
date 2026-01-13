from curl_cffi.requests import AsyncSession
from config.settings import ADRINOLINKS_API

async def get_short_link(long_url):
    try:
        # Check API Key
        if "YOUR_ADRINOLINKS_API_KEY" in ADRINOLINKS_API:
            print("❌ Error: AdrinoLinks API Key set nahi hai!")
            return None

        # API URL
        api_url = f"https://adrinolinks.com/api?api={ADRINOLINKS_API}&url={long_url}&format=text"
        
        # 👇 BRAHMASTRA FIX: curl_cffi use kar rahe hain
        # impersonate="chrome110" server ko confuse kar dega
        async with AsyncSession(impersonate="chrome110") as session:
            response = await session.get(api_url)
            
            if response.status_code == 200:
                result = response.text.strip()
                
                # Debugging ke liye logs mein print karein
                print(f"🔗 API Response: {result[:100]}") 

                if result.startswith("http"):
                    return result
                else:
                    # Agar abhi bhi HTML page aaye
                    print(f"❌ Shortener Blocked (HTML received): {result[:50]}...")
                    return None
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                return None

    except Exception as e:
        print(f"❌ Shortener Exception: {e}")
        return None
