from curl_cffi.requests import AsyncSession
from config.settings import SHORTENER_API

async def get_short_link(long_url):
    try:
        # 👇 FIX: Check karein ki Key Environment se load hui ya nahi
        if not SHORTENER_API:
            print("❌ Error: SHORTENER API Key set nahi hai Environment Variables mein!")
            return None

        # GPLinks API URL
        api_url = f"https://gplinks.in/api?api={SHORTENER_API}&url={long_url}&format=text"
        
        # Chrome ban kar request bhejein
        async with AsyncSession(impersonate="chrome110") as session:
            response = await session.get(api_url)
            
            if response.status_code == 200:
                result = response.text.strip()
                
                # Debugging ke liye
                print(f"🔗 gplinks  Response: {result[:50]}") 

                # Agar link 'http' se shuru ho raha hai to sahi hai
                if result.startswith("http"):
                    return result
                else:
                    # Agar koi error message aaya
                    print(f"❌ gplinks Error: {result}")
                    return None
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                return None

    except Exception as e:
        print(f"❌ Shortener Exception: {e}")
        return None
