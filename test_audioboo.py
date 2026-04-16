import asyncio
import scraper

async def main():
    await scraper.init_browser()
    try:
        res = await scraper.get_book_info('https://audioboo.org/fenezi/108102-ivanov-aleksej-nevjanskaja-bashnja.html')
        print(res)
    finally:
        await scraper.close_browser()

if __name__ == "__main__":
    asyncio.run(main())
