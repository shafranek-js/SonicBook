import asyncio

async def run_scraper_debug():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        page.on("request", lambda r: print(f"REQ: {r.url[:100]}"))
        
        await page.goto("https://akniga.org/kolodzeychak-tomash-poslednee-reshenie", wait_until="domcontentloaded")
        await asyncio.sleep(2)
        await page.evaluate("document.querySelector('.button__player--play, .js-player-play')?.click()")
        await asyncio.sleep(5)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper_debug())
