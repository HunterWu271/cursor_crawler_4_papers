"""自由時報 (LTN) 新聞解析器。"""

import re

from bs4 import BeautifulSoup

from core.base_scraper import BaseScraper

LTN_SECTION_MAP = {
    "politics": "要聞",
    "society": "社會",
    "life": "生活",
    "world": "全球/國際",
    "business": "產經/財經",
    "sports": "運動",
    "entertainment": "娛樂",
    "sport": "運動",
    "3c": "3C",
    "auto": "汽車",
    "health": "健康",
}

_SKIP_PARAGRAPH_KEYWORDS = ("請繼續往下閱讀", "請繼續閱讀", "圖／", "圖左為", "圖右為")


class LtnScraper(BaseScraper):
    """解析 news.ltn.com.tw 新聞內頁。"""

    def parse(self, soup: BeautifulSoup, url: str = "") -> dict[str, str] | None:
        paragraphs = self._collect_paragraphs(soup)
        content = self.clean_content(paragraphs)
        if self.check_paywall(soup, content) or self.is_incomplete_content(content):
            return None

        category = self._resolve_category(soup, url)
        title = self._select_text(soup, ("h1",))
        publish_time = self._resolve_publish_time(soup)
        author = self.extract_author_name(" ".join(paragraphs[:3]))

        if not title or not content:
            return None

        category = self.normalize_category_name(category)

        return {
            "category": self.clean_metadata(category),
            "title": self.clean_metadata(title),
            "publish_time": self.clean_publish_time(publish_time),
            "author": self.clean_metadata(author),
            "content": content,
        }

    def _collect_paragraphs(self, soup: BeautifulSoup) -> list[str]:
        paragraphs = self.collect_paragraphs(
            soup,
            ("div.text.boxText", "div.text", ".text"),
        )
        filtered: list[str] = []
        for text in paragraphs:
            if any(k in text for k in _SKIP_PARAGRAPH_KEYWORDS):
                continue
            if text.endswith("攝）") and len(text) < 40:
                continue
            filtered.append(text)
        return filtered

    def _resolve_category(self, soup: BeautifulSoup, url: str) -> str:
        section = self._meta_content(soup, prop="article:section")
        if section in LTN_SECTION_MAP:
            return LTN_SECTION_MAP[section]
        if section:
            return section

        match = re.search(r"/news/([^/]+)/", url)
        if match:
            key = match.group(1)
            return LTN_SECTION_MAP.get(key, key)
        return ""

    def _resolve_publish_time(self, soup: BeautifulSoup) -> str:
        times = [
            t.get_text(strip=True)
            for t in soup.select(".time, span.time")
            if t.get_text(strip=True)
        ]
        if times:
            return times[-1]
        return self._meta_content(soup, prop="article:published_time")
