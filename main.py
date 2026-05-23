"""
台灣四大報爬蟲總調度：非同步排程、工廠分流、DataFrame 聚合與 CSV 輸出。
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import time
from collections import defaultdict
from datetime import datetime
from typing import Any

import pandas as pd

from config.settings import (
    DATA_DIR,
    DELAY_MAX_SECONDS,
    DELAY_MIN_SECONDS,
    NEWS_URLS,
)
from core.playwright_engine import fetch_html, playwright_session
from scrapers.discovery import collect_all_newspapers_urls
from scrapers.factory import ScraperFactory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def format_elapsed_hms(seconds: float) -> str:
    """將秒數轉為「x小時 y分鐘 z秒」字串，秒保留小數。"""
    total = max(0.0, seconds)
    hours = int(total // 3600)
    minutes = int((total % 3600) // 60)
    secs = total % 60
    return f"{hours}小時 {minutes}分鐘 {secs:.2f}秒"


# PRD 欄位對應（scraper 內部鍵 -> CSV 欄名）
CSV_COLUMNS = {
    "source": "媒體",
    "url": "網址",
    "category": "新聞種類",
    "title": "新聞標題",
    "publish_time": "刊出時間",
    "author": "記者",
    "content": "新聞文本",
}


async def random_delay() -> None:
    """每則新聞與報社切換間的隨機延遲（1–3 秒）。"""
    seconds = random.uniform(DELAY_MIN_SECONDS, DELAY_MAX_SECONDS)
    await asyncio.sleep(seconds)


async def scrape_one(url: str) -> dict[str, Any] | None:
    """下載並解析單一 URL，失敗或付費牆回傳 None。"""
    try:
        soup = await fetch_html(url)
        article = ScraperFactory.parse(url, soup)
    except ValueError as exc:
        logger.warning("略過不支援的 URL：%s (%s)", url, exc)
        return None
    except Exception as exc:
        logger.warning("抓取失敗：%s (%s)", url, exc)
        return None

    if article is None:
        logger.info("略過（付費牆、不完整正文或無有效內容）：%s", url)
        return None

    _, source_name, _ = ScraperFactory.resolve(url)
    return {
        "source": source_name,
        "url": url,
        **article,
    }


async def scrape_category_articles(
    urls: list[str],
    *,
    source_label: str,
    category: str,
) -> list[dict[str, Any]]:
    """
    擷取單一新聞種類下的多則正文，並印出該類別總耗時。
    """
    if not urls:
        logger.info(
            "[%s] %s：擷取文本 %s（0 則，成功 0 則）",
            source_label,
            category,
            format_elapsed_hms(0),
        )
        return []

    started = time.perf_counter()
    records: list[dict[str, Any]] = []
    first = True
    for url in urls:
        if not first:
            await random_delay()
        first = False

        record = await scrape_one(url)
        if record:
            records.append(record)
            logger.info("成功：%s", record.get("title", url)[:40])

    elapsed = time.perf_counter() - started
    logger.info(
        "[%s] %s：擷取文本 %s（%d 則，成功 %d 則）",
        source_label,
        category,
        format_elapsed_hms(elapsed),
        len(urls),
        len(records),
    )
    return records


def group_urls_by_source(urls: list[str]) -> dict[str, list[str]]:
    """依報社分組，無法辨識的 URL 單獨放在「未知」群組。"""
    groups: dict[str, list[str]] = defaultdict(list)
    for url in urls:
        try:
            key = ScraperFactory.source_key(url)
        except ValueError:
            key = "未知"
        groups[key].append(url)
    return dict(groups)


async def run_crawl(urls: list[str]) -> list[dict[str, Any]]:
    """
    非同步排程：先依報社分組，組內逐則抓取並延遲，組間再延遲。
    """
    records: list[dict[str, Any]] = []
    groups = group_urls_by_source(urls)
    first_group = True

    for source_name, source_urls in groups.items():
        if not first_group:
            logger.info("報社切換延遲：%s", source_name)
            await random_delay()
        first_group = False

        logger.info("開始爬取 %s（%d 則）", source_name, len(source_urls))
        first_url = True
        for url in source_urls:
            if not first_url:
                await random_delay()
            first_url = False

            record = await scrape_one(url)
            if record:
                records.append(record)
                logger.info("成功：%s", record.get("title", url)[:40])

    return deduplicate_records(records)


def deduplicate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """依 URL 與標題+正文指紋去除重複新聞。"""
    seen_urls: set[str] = set()
    seen_fingerprints: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []

    for record in records:
        url = record.get("url", "").split("?")[0].rstrip("/")
        if url in seen_urls:
            logger.info("去重（相同 URL）：%s", url)
            continue

        title = record.get("title", "")
        content_norm = re.sub(r"\s+", "", record.get("content", ""))
        fingerprint = (title, content_norm[:500])
        if content_norm and fingerprint in seen_fingerprints:
            logger.info("去重（相同標題與正文）：%s", title[:40])
            continue

        seen_urls.add(url)
        if content_norm:
            seen_fingerprints.add(fingerprint)
        unique.append(record)

    if len(records) != len(unique):
        logger.info("去重：%d 筆 -> %d 筆", len(records), len(unique))
    return unique


def records_to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    """將成功紀錄轉為 DataFrame，欄位名稱對應 PRD。"""
    records = deduplicate_records(records)
    if not records:
        return pd.DataFrame(columns=list(CSV_COLUMNS.values()))

    df = pd.DataFrame(records)
    rename = {k: v for k, v in CSV_COLUMNS.items() if k in df.columns}
    return df.rename(columns=rename)[list(CSV_COLUMNS.values())]


def save_csv(df: pd.DataFrame) -> str:
    """
    存檔至 ./data/，檔名 YYYYMMDD_HH_MM_SS_news_data.csv，UTF-8。
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H_%M_%S")
    filename = f"{timestamp}_news_data.csv"
    path = DATA_DIR / filename
    df.to_csv(path, index=False, encoding="utf-8")
    return str(path)


async def main(urls: list[str] | None = None) -> None:
    """
    依給定的「單篇新聞內頁 URL」列表爬取並輸出 CSV。

    適用的網址（四家各一篇為一則，可混合多家）：
    - 聯合報：``https://udn.com/news/story/{分類碼}/{文章ID}``
    - 中國時報：``https://www.chinatimes.com/realtimenews/{YYYYMMDDHHMMSS}-{分類碼}``
    - 自由時報：``https://news.ltn.com.tw/news/{版別}/breakingnews/{文章ID}``
    - 壹蘋新聞網：``https://news.nextapple.com/{版別}/{YYYYMMDD}/{文章ID}``

    不適用（請勿傳入，會略過或抓取失敗）：
    - 報社首頁、分類列表頁、搜尋頁（如 ``https://udn.com``、``https://www.ltn.com.tw``）
    - 非上述四家網域的連結

    ``urls`` 為 ``None`` 時使用 ``config/settings.py`` 的 ``NEWS_URLS``（預設四家各 1 則測試稿）。
    若要自動探索多家、多類別、多篇，請改呼叫 ``main_crawl_all()``。
    """
    target_urls = urls if urls is not None else NEWS_URLS
    logger.info("共 %d 則 URL 待爬取", len(target_urls))

    async with playwright_session():
        records = await run_crawl(target_urls)
    df = records_to_dataframe(records)

    if df.empty:
        logger.warning("無成功資料，不寫入 CSV")
        return

    output_path = save_csv(df)
    logger.info("完成：%d 筆寫入 %s", len(df), output_path)


async def main_crawl_all() -> None:
    """
    探索四家報社分類列表頁，抓取各類文章內頁（7 類 × 每類最多 40 則，最多約 1120 則）。
    統一種類：要聞、社會、生活、產經/財經、全球/國際、運動、娛樂。
    請使用此入口批次爬取，勿傳入首頁 URL。
    """
    from scrapers.discovery import ARTICLES_PER_CATEGORY, CATEGORIES_PER_PAPER

    logger.info(
        "探索四家報社文章 URL（每家 %d 類 × 每類 %d 則）…",
        CATEGORIES_PER_PAPER,
        ARTICLES_PER_CATEGORY,
    )
    target_urls = await collect_all_newspapers_urls()
    logger.info("探索完成，共 %d 則文章 URL", len(target_urls))
    await main(target_urls)


if __name__ == "__main__":
    #asyncio.run(main())
    asyncio.run(main_crawl_all())