"""Playwright 非同步下載引擎：共用瀏覽器、domcontentloaded、輸出 BeautifulSoup。"""

from __future__ import annotations

import random
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import AsyncIterator

from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page, Playwright
from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 "
        "Firefox/123.0"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.3 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
]

GOTO_WAIT_UNTIL = "domcontentloaded"
GOTO_TIMEOUT_MS = 30_000
ARTICLE_READY_TIMEOUT_MS = 15_000

# 等待動態注入的正文段落載入完成
ARTICLE_READY_SCRIPT = """() => {
    const selectors = [
        'div.text.boxText p',
        'div.text p',
        '.article-content__editor p',
        '.article-body p',
        '.post-content p',
    ];
    for (const sel of selectors) {
        const nodes = document.querySelectorAll(sel);
        if (nodes.length >= 2) {
            let len = 0;
            nodes.forEach(n => len += (n.innerText || '').length);
            if (len > 200) return true;
        }
    }
    return false;
}"""

_active_session: ContextVar[PlaywrightSession | None] = ContextVar(
    "_active_session", default=None
)


async def _load_page_html(page: Page, url: str) -> str:
    await page.goto(url, wait_until=GOTO_WAIT_UNTIL, timeout=GOTO_TIMEOUT_MS)
    try:
        await page.wait_for_function(
            ARTICLE_READY_SCRIPT,
            timeout=ARTICLE_READY_TIMEOUT_MS,
        )
    except PlaywrightTimeout:
        pass
    return await page.content()


class PlaywrightSession:
    """共用 Chromium 實例，批次抓取時避免每則都啟動瀏覽器。"""

    def __init__(self, *, user_agent: str | None = None) -> None:
        self._user_agent = user_agent or random.choice(USER_AGENTS)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._context = await self._browser.new_context(user_agent=self._user_agent)

    async def close(self) -> None:
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def fetch_html(self, url: str) -> BeautifulSoup:
        if not self._context:
            raise RuntimeError("PlaywrightSession 尚未 start()")
        page = await self._context.new_page()
        try:
            html = await _load_page_html(page, url)
        finally:
            await page.close()
        return BeautifulSoup(html, "lxml")

    async def __aenter__(self) -> PlaywrightSession:
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()


@asynccontextmanager
async def playwright_session(
    *, user_agent: str | None = None
) -> AsyncIterator[PlaywrightSession]:
    """
    建立共用瀏覽器工作階段；區塊內 ``fetch_html`` 會自動複用。
    """
    session = PlaywrightSession(user_agent=user_agent)
    await session.start()
    token = _active_session.set(session)
    try:
        yield session
    finally:
        _active_session.reset(token)
        await session.close()


async def fetch_html(url: str) -> BeautifulSoup:
    """
    載入 URL 並回傳 BeautifulSoup。
    若外層使用 ``async with playwright_session():`` 則共用瀏覽器；
    否則為單次請求（仍使用 domcontentloaded，不再等待 networkidle）。
    """
    session = _active_session.get()
    if session is not None:
        return await session.fetch_html(url)

    async with PlaywrightSession() as one_shot:
        return await one_shot.fetch_html(url)
