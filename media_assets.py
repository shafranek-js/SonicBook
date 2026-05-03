import logging
import os

import aiofiles
import httpx

from media_helpers import resolve_cover_extension

logger = logging.getLogger(__name__)


def log_debug(message):
    logger.info(message)


async def download_cover(cover_url, task_work_dir, title_base):
    if not cover_url:
        return None

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(cover_url, follow_redirects=True, timeout=30)
            if response.status_code == 200 and response.headers.get("content-type", "").lower().startswith("image/"):
                cover_ext = resolve_cover_extension(cover_url, response.headers.get("content-type"))
                cover_path = os.path.join(task_work_dir, f"{title_base}{cover_ext}")
                async with aiofiles.open(cover_path, "wb") as f:
                    await f.write(response.content)
                return cover_path
    except (httpx.HTTPError, OSError) as e:
        log_debug(f"Failed to download cover: {e}")

    return None
