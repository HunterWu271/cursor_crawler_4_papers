"""依 URL 網域自動分流至對應報社解析器。"""

from urllib.parse import urlparse

from bs4 import BeautifulSoup

from core.base_scraper import BaseScraper
from scrapers.chinatimes import ChinatimesScraper
from scrapers.ltn import LtnScraper
from scrapers.nextApple import NextAppleScraper
from scrapers.udn import UdnScraper

_SOURCE_BY_HOST = (
    ("news.nextapple.com", "壹蘋新聞網", NextAppleScraper, True),
    ("nextapple.com", "壹蘋新聞網", NextAppleScraper, True),
    ("udn.com", "聯合報", UdnScraper, False),
    ("chinatimes.com", "中國時報", ChinatimesScraper, False),
    ("news.ltn.com.tw", "自由時報", LtnScraper, True),
    ("ltn.com.tw", "自由時報", LtnScraper, True),
)


class ScraperFactory:
    """根據 URL 選擇解析器並執行 parse。"""

    @staticmethod
    def resolve(url: str) -> tuple[BaseScraper, str, bool]:
        """
        回傳 (解析器實例, 媒體名稱, 是否需要傳入 url 參數)。
        無法辨識時拋出 ValueError。
        """
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]

        for domain, source_name, scraper_cls, needs_url in _SOURCE_BY_HOST:
            if host == domain or host.endswith(f".{domain}"):
                return scraper_cls(), source_name, needs_url

        raise ValueError(f"不支援的媒體 URL：{url}")

    @staticmethod
    def source_key(url: str) -> str:
        """用於 main 依報社分組的鍵值。"""
        _, source_name, _ = ScraperFactory.resolve(url)
        return source_name

    @classmethod
    def parse(cls, url: str, soup: BeautifulSoup) -> dict[str, str] | None:
        scraper, _, needs_url = cls.resolve(url)
        if needs_url:
            return scraper.parse(soup, url=url)
        return scraper.parse(soup)
