import asyncio
import cloudscraper
from config.settings import ADRINOLINKS_API

# 1. Blocking Function (Jo Anti-Bot ko bypass karega)
def _make_request_sync(api_url):
    try:
        # Browser jaisa banne ke liye scraper create karein
        scraper = cloudscraper.create_scraper() 
        response = scraper.get(api_url)
        return response.status_code, response.text
    except Exception as e:
        return 500, str(e)

# 2. Async Function (Jo Bot use karega)
async def get_short_link(long_url):
    try:
        if "YOUR_ADRINOLINKS_API_KEY" in ADRINOLINKS_API:
            print("❌ Error: API Key set nahi hai!")
            return None

        # API Link banayein
        api_url = f"https://adrinolinks.com/api?api={ADRINOLINKS_API}&url={long_url}&format=text"
        
        # Background me request bhejein (Taaki bot ruke nahi)
        loop = asyncio.get_event_loop()
        status_code, result = await loop.run_in_executor(None, _make_request_sync, api_url)

        if status_code == 200:
            result = result.strip()
            
            # Agar result HTTP se shuru hota hai, to wo Link hai
            if result.startswith("http"):
                return result
            else:
                # Agar HTML ya Error message aaya
                print(f"❌ Shortener Blocked: {result[:100]}...") # Log me error dikhega
                return None
        else:
            print(f"❌ HTTP Error: {status_code}")
            return None

    except Exception as e:
        print(f"❌ Shortener Exception: {e}")
        return None
