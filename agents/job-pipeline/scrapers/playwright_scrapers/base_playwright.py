"""
Shared Playwright browser management for all JS-heavy scrapers.
Applies stealth settings to reduce bot detection.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from config.settings import PLAYWRIGHT_HEADLESS, PLAYWRIGHT_SLOW_MO, SCRAPER_PROXY

log = logging.getLogger(__name__)


async def get_browser(playwright):
    """Launch a stealth Chromium browser."""
    launch_kwargs: dict = {
        "headless": PLAYWRIGHT_HEADLESS,
        "slow_mo": PLAYWRIGHT_SLOW_MO,
        "args": [
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--disable-setuid-sandbox",
        ],
    }
    if SCRAPER_PROXY:
        # Playwright needs username/password as separate fields, not embedded in URL
        from urllib.parse import urlparse
        parsed = urlparse(SCRAPER_PROXY)
        proxy_config: dict = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
        if parsed.username:
            proxy_config["username"] = parsed.username
        if parsed.password:
            proxy_config["password"] = parsed.password
        launch_kwargs["proxy"] = proxy_config
    return await playwright.chromium.launch(**launch_kwargs)


async def get_page(browser, url: str, wait_for: str = "networkidle", timeout: int = 30000):
    """
    Open a new page with stealth settings and navigate to url.
    Returns the page object. Caller is responsible for closing.
    """
    ctx = await browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
        locale="en-US",
        timezone_id="America/Chicago",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120"',
        },
    )
    # Apply playwright-stealth if available
    try:
        from playwright_stealth import stealth_async
        page = await ctx.new_page()
        await stealth_async(page)
    except ImportError:
        page = await ctx.new_page()

    # Block tracking pixels and ads to speed up page loads
    await page.route(
        "**/{ads,analytics,tracking,gtm,hotjar}**",
        lambda route: route.abort(),
    )

    try:
        await page.goto(url, wait_until=wait_for, timeout=timeout)
    except Exception as e:
        log.debug(f"[playwright] goto {url} raised: {e} — attempting to continue")

    return page


@asynccontextmanager
async def playwright_page(url: str, wait_for: str = "networkidle") -> AsyncGenerator:
    """Async context manager: yields a ready Playwright page, cleans up after."""
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = await get_browser(pw)
        try:
            page = await get_page(browser, url, wait_for)
            yield page
        finally:
            await browser.close()
