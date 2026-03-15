import asyncio
from playwright.async_api import async_playwright

async def get_m3u8_url(book_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        m3u8_url = None

        def handle_request(request):
            nonlocal m3u8_url
            if ".m3u8" in request.url:
                print(f"Found m3u8: {request.url}")
                m3u8_url = request.url

        page.on("request", handle_request)
        try:
            print(f"Loading {book_url}...")
            await page.goto(book_url, wait_until="networkidle", timeout=60000)
            print("Page loaded. Checking for play button...")
            # Попробуем кликнуть play, если ссылка не появилась
            try:
                play_button = page.locator(".js-player-play").first
                await play_button.click()
                print("Play button clicked.")
                await asyncio.sleep(10)
            except Exception as e:
                print(f"Play button not found or error: {e}")
        except Exception as e:
            print(f"Ошибка при загрузке страницы: {e}")
        finally:
            await browser.close()
        
        return m3u8_url

if __name__ == "__main__":
    url = "https://akniga.org/dish-tomas-genocid"
    result = asyncio.run(get_m3u8_url(url))
    print(f"Final result: {result}")
