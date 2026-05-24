"""各報社分類頁與文章 URL 探索。"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from config.categories import UNIFIED_CATEGORIES

# 每家七個統一新聞種類（名稱, 列表頁 URL）
NEWSPAPER_CATEGORIES: dict[str, list[tuple[str, str]]] = {
    "udn": [
        ("要聞", "https://udn.com/news/cate/2/6638"),
        ("社會", "https://udn.com/news/cate/2/6639"),
        ("生活", "https://udn.com/news/cate/2/6649"),
        ("產經/財經", "https://udn.com/news/cate/2/6644"),
        ("全球/國際", "https://udn.com/news/cate/2/7225"),
        ("運動", "https://udn.com/news/cate/2/7227"),
        ("娛樂", "https://udn.com/news/cate/2/6646"),
    ],
    "chinatimes": [
        ("要聞", "https://www.chinatimes.com/realtimenews/260407/?chdtv"),
        ("社會", "https://www.chinatimes.com/realtimenews/260402/?chdtv"),
        ("生活", "https://www.chinatimes.com/realtimenews/260405/?chdtv"),
        ("產經/財經", "https://www.chinatimes.com/realtimenews/260410/?chdtv"),
        ("全球/國際", "https://www.chinatimes.com/realtimenews/260408/?chdtv"),
        ("運動", "https://www.chinatimes.com/realtimenews/260403/?chdtv"),
        ("娛樂", "https://www.chinatimes.com/realtimenews/260404/?chdtv"),
    ],
    "ltn": [
        ("要聞", "https://news.ltn.com.tw/list/breakingnews"),
        ("社會", "https://news.ltn.com.tw/list/breakingnews/society"),
        ("生活", "https://news.ltn.com.tw/list/breakingnews/life"),
        ("產經/財經", "https://news.ltn.com.tw/list/breakingnews/business"),
        ("全球/國際", "https://news.ltn.com.tw/list/breakingnews/world"),
        ("運動", "https://news.ltn.com.tw/list/breakingnews/sports"),
        ("娛樂", "https://news.ltn.com.tw/list/breakingnews/entertainment"),
    ],
    "nextapple": [
        ("要聞", "https://news.nextapple.com/realtime/politics"),
        ("社會", "https://news.nextapple.com/realtime/local"),
        ("生活", "https://news.nextapple.com/realtime/life"),
        ("產經/財經", "https://news.nextapple.com/realtime/finance"),
        ("全球/國際", "https://news.nextapple.com/realtime/international"),
        ("運動", "https://news.nextapple.com/realtime/sports"),
        ("娛樂", "https://news.nextapple.com/realtime/entertainment"),
    ],
}

ARTICLES_PER_CATEGORY = 40
CATEGORIES_PER_PAPER = len(UNIFIED_CATEGORIES)
# 列表頁可能重複頭條，掃描上限需大於每類所需則數
ARTICLE_SCAN_LIMIT = 80

NEWSPAPER_DISPLAY_NAMES: dict[str, str] = {
    "udn": "聯合報",
    "chinatimes": "中國時報",
    "ltn": "自由時報",
    "nextapple": "壹蘋新聞網",
}

ALL_NEWSPAPER_KEYS: tuple[str, ...] = tuple(NEWSPAPER_DISPLAY_NAMES.keys())


async def fetch_listing_html(url: str) -> BeautifulSoup:
    """載入分類／列表頁（domcontentloaded，較不易逾時）。"""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            html = await page.content()
        finally:
            await browser.close()
    return BeautifulSoup(html, "lxml")


def _normalize_url(base: str, href: str) -> str:
    full = urljoin(base, href)
    return full.split("#")[0].split("?")[0]


def extract_article_urls(
    newspaper: str,
    soup: BeautifulSoup,
    page_url: str,
    limit: int,
    exclude: set[str] | None = None,
) -> list[str]:
    """從列表頁擷取文章 URL，每家報社規則不同。"""
    skip = exclude or set()
    seen: set[str] = set()
    urls: list[str] = []

    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if not href:
            continue

        if newspaper == "udn":
            if "/news/story/" not in href:
                continue
            full = _normalize_url(page_url, href)
            if "udn.com/news/story/" not in full:
                continue
        elif newspaper == "chinatimes":
            if "/realtimenews/20" not in href:
                continue
            full = _normalize_url(page_url, href)
            if "chinatimes.com/realtimenews/" not in full:
                continue
        elif newspaper == "ltn":
            if "/breakingnews/" not in href or "/news/" not in href:
                continue
            full = _normalize_url(page_url, href)
            if "news.ltn.com.tw/news/" not in full:
                continue
        elif newspaper == "nextapple":
            full = _normalize_url(page_url, href)
            parsed = urlparse(full)
            if parsed.netloc != "news.nextapple.com":
                continue
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) < 3:
                continue
            if parts[0] in ("realtime", "collection", "column", "gallery"):
                continue
            if not re.fullmatch(r"\d{8}", parts[1]):
                continue
        else:
            continue

        if full in seen or full in skip:
            continue
        seen.add(full)
        urls.append(full)
        if len(urls) >= limit:
            break

    return urls


async def collect_article_urls_by_category(
    newspaper: str,
    *,
    articles_per_category: int | None = None,
    article_scan_limit: int | None = None,
) -> list[tuple[str, list[str]]]:
    """
    依報社設定取得 7 類 × 每類最多 articles_per_category 則文章 URL。
    回傳 [(新聞種類名稱, [url, ...]), ...]。
    """
    per_category = articles_per_category or ARTICLES_PER_CATEGORY
    scan_limit = article_scan_limit or max(ARTICLE_SCAN_LIMIT, per_category + 10)

    newspaper = newspaper.lower().strip()
    categories = NEWSPAPER_CATEGORIES.get(newspaper)
    if not categories:
        raise ValueError(
            f"不支援的報社：{newspaper}，請使用 udn, chinatimes, ltn, nextapple"
        )

    by_category: list[tuple[str, list[str]]] = []
    global_seen: set[str] = set()

    for category_name, category_url in categories[:CATEGORIES_PER_PAPER]:
        soup = await fetch_listing_html(category_url)
        batch = extract_article_urls(
            newspaper,
            soup,
            category_url,
            scan_limit,
            exclude=global_seen,
        )
        picked = batch[:per_category]
        global_seen.update(picked)
        by_category.append((category_name, picked))

    return by_category


async def collect_article_urls(
    newspaper: str,
    *,
    articles_per_category: int | None = None,
    article_scan_limit: int | None = None,
) -> list[str]:
    """依報社設定取得 7 類 × 每類最多 articles_per_category 則文章 URL（扁平列表）。"""
    by_category = await collect_article_urls_by_category(
        newspaper,
        articles_per_category=articles_per_category,
        article_scan_limit=article_scan_limit,
    )
    return [url for _, urls in by_category for url in urls]


async def collect_all_newspapers_urls(
    newspapers: tuple[str, ...] | None = None,
    *,
    articles_per_category: int | None = None,
    article_scan_limit: int | None = None,
) -> list[str]:
    """
    探索四家報社分類列表頁，彙整文章內頁 URL。
    預設每家 7 類 × 每類最多 ARTICLES_PER_CATEGORY 則。
    """
    per_category = articles_per_category or ARTICLES_PER_CATEGORY
    papers = newspapers or ALL_NEWSPAPER_KEYS
    all_urls: list[str] = []
    for paper in papers:
        paper = paper.lower().strip()
        batch = await collect_article_urls(
            paper,
            articles_per_category=per_category,
            article_scan_limit=article_scan_limit,
        )
        all_urls.extend(batch)
    return all_urls
