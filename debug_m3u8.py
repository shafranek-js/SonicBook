import asyncio
from playwright.async_api import async_playwright

async def debug_m3u8(url):
    print(f"Debugging M3U8 for: {url}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        m3u8_url = None
        def handle_req(r):
            nonlocal m3u8_url
            if ".m3u8" in r.url:
                m3u8_url = r.url
                print(f"FOUND M3U8 IN REQUEST: {r.url}")
        
        page.on("request", handle_req)
        
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        
        # Настоящий клик
        print("Clicking play button...")
        try:
            await page.locator(".button__player--play").first.click(force=True)
            print("Click successful")
        except Exception as e:
            print(f"Click failed: {e}")
            
        await asyncio.sleep(5)
        
        # Пытаемся достать из аудио плеера
        audio_src = await page.evaluate("() => { let a = document.querySelector('audio'); return a ? a.src : null; }")
        print(f"Audio src from DOM: {audio_src}")
        
        # Пытаемся достать из HLS объекта
        hls_url = await page.evaluate("() => { return window.Hls ? 'Hls defined' : 'No Hls'; }")
        print(f"HLS Status: {hls_url}")
        
        await browser.close()
        print(f"Final M3U8: {m3u8_url}")

if __name__ == "__main__":
    asyncio.run(debug_m3u8("https://akniga.org/kolodzeychak-tomash-poslednee-reshenie"))
