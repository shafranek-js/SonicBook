import asyncio
from playwright.async_api import async_playwright

async def check_server():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            print("Attempting to connect to http://127.0.0.1:8000 ...")
            response = await page.goto("http://127.0.0.1:8000", timeout=10000)
            print(f"Status code: {response.status}")
            print(f"Title: {await page.title()}")
        except Exception as e:
            print(f"FAILED to connect: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(check_server())
