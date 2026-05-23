"""
單報社測試爬蟲：7 個類別 × 每類最多 40 則，回傳 PRD 欄位 DataFrame。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any

import pandas as pd

from core.playwright_engine import playwright_session
from main import random_delay, records_to_dataframe, scrape_category_articles
from scrapers.discovery import (
    ARTICLES_PER_CATEGORY,
    NEWSPAPER_DISPLAY_NAMES,
    collect_article_urls_by_category,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

VALID_NEWSPAPERS = frozenset({"udn", "chinatimes", "ltn", "nextapple"})


async def test_scraper_async(newspaper: str) -> pd.DataFrame:
    paper = newspaper.lower().strip()
    if paper not in VALID_NEWSPAPERS:
        raise ValueError(
            f"不支援的報社：{newspaper}，請使用 {', '.join(sorted(VALID_NEWSPAPERS))}"
        )

    source_label = NEWSPAPER_DISPLAY_NAMES[paper]
    logger.info(
        "探索 %s 文章 URL（7 類 × 每類最多 %d 則）…",
        source_label,
        ARTICLES_PER_CATEGORY,
    )
    by_category = await collect_article_urls_by_category(paper)
    total_urls = sum(len(urls) for _, urls in by_category)
    logger.info("共取得 %d 則待爬 URL", total_urls)

    records: list[dict[str, Any]] = []
    async with playwright_session():
        first_category = True
        for category, urls in by_category:
            if not first_category:
                await random_delay()
            first_category = False

            batch = await scrape_category_articles(
                urls,
                source_label=source_label,
                category=category,
            )
            records.extend(batch)

    return records_to_dataframe(records)


def test_scraper(newspaper: str) -> pd.DataFrame:
    """
    指定報社（udn / chinatimes / ltn / nextapple），
    抓取七個統一類別、每類最多 40 則新聞，回傳 PRD 欄位之 pandas DataFrame。

    一般 Python 腳本可直接呼叫。若在 Jupyter / IPython 已有事件迴圈，
    請改用：``df = await test_scraper_async("ltn")``
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(test_scraper_async(newspaper))

    # Notebook 內已有 running loop，改在獨立執行緒執行 asyncio.run
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, test_scraper_async(newspaper))
        return future.result()


if __name__ == "__main__":
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else "ltn"
    df = test_scraper(name)
    print(df)
