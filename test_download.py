import asyncio
import httpx

async def main():
    url = "https://archive.org/compress/19_20251125/formats=VBR MP3&file=/19_20251125.zip"
    print(f"Downloading from {url}")
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        async with client.stream("GET", url, timeout=httpx.Timeout(30.0, read=300.0)) as response:
            print(f"Status: {response.status_code}")
            print(f"Headers: {response.headers}")
            
            # Read first 100 bytes
            first_chunk = await response.aread()
            print(f"First 100 bytes: {first_chunk[:100]}")
            
if __name__ == "__main__":
    asyncio.run(main())
