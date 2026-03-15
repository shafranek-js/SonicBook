import asyncio
from playwright.async_api import async_playwright

async def test_scraping(url):
    print(f"Testing URL: {url}")
    async with async_playwright() as p:
        # Запускаем браузер
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        m3u8_url = None

        # Перехватываем запросы
        def handle_request(request):
            nonlocal m3u8_url
            if ".m3u8" in request.url:
                print(f"FOUND M3U8: {request.url}")
                m3u8_url = request.url

        page.on("request", handle_request)

        try:
            print("Loading page...")
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            title = await page.title()
            print(f"Page Title: {title}")

            h1 = await page.query_selector("h1")
            if h1:
                print(f"H1 Title: {await h1.inner_text()}")

            print("Waiting for player button...")
            play_button = page.locator(".js-player-play").first
            if await play_button.is_visible():
                print("Clicking play button...")
                await play_button.click()
                # Ждем появления потока после клика
                await asyncio.sleep(10)
            else:
                print("Play button not found or not visible. Trying alternative method...")
                # Некоторые сайты требуют прокрутки или ожидания
                await asyncio.sleep(5)

            if m3u8_url:
                print(f"SUCCESS: Found stream: {m3u8_url}")
            else:
                print("FAILED: Could not find .m3u8 stream.")

        except Exception as e:
            print(f"ERROR: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    url = "https://akniga.org/dish-tomas-genocid"
    asyncio.run(test_scraping(url))
