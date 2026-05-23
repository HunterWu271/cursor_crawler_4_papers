"""壹蘋新聞網 (news.nextapple.com) 新聞解析器。"""

import re

from bs4 import BeautifulSoup

from core.base_scraper import BaseScraper

NEXTAPPLE_SECTION_MAP = {
    "politics": "要聞",
    "entertainment": "娛樂",
    "society": "社會",
    "life": "生活",
    "international": "全球/國際",
    "business": "產經/財經",
    "finance": "產經/財經",
    "sports": "運動",
    "sport": "運動",
    "local": "社會",
    "technology": "科技",
    "tech": "科技",
    "health": "健康",
    "local": "寶島",
    "opinion": "言論",
    "gallery": "圖片",
}

_SKIP_PARAGRAPH_KEYWORDS = (
    "走入油墨的世界",
    "遊盪網路的領域",
    "贊助壹蘋",
    "我要爆料",
)

_NOT_FOUND_MARKERS = ("頁面不存在", "page not found", "Sorry, page not found")


class NextAppleScraper(BaseScraper):
    """解析 https://news.nextapple.com/ 新聞內頁。"""

    def parse(self, soup: BeautifulSoup, url: str = "") -> dict[str, str] | None:
        if self._is_not_found(soup):
            return None

        paragraphs = self._collect_paragraphs(soup)
        content = self.clean_content(paragraphs)
        if self.check_paywall(soup, content) or self.is_incomplete_content(content):
            return None

        category = self._resolve_category(soup, url)
        title = self._resolve_title(soup)
        publish_time = self._resolve_publish_time(soup)
        author = self._extract_author(soup, paragraphs)

        if not title or not content:
            return None

        category = self.normalize_category_name(category)

        return {
            "category": self.clean_metadata(category),
            "title": self.clean_metadata(title),
            "publish_time": self.clean_metadata(publish_time),
            "author": self.clean_metadata(author),
            "content": content,
        }

    @staticmethod
    def _is_not_found(soup: BeautifulSoup) -> bool:
        text = soup.get_text(separator=" ", strip=True)
        return any(marker in text for marker in _NOT_FOUND_MARKERS)

    def _collect_paragraphs(self, soup: BeautifulSoup) -> list[str]:
        paragraphs = self.collect_paragraphs(
            soup,
            (".infScroll .post-content", ".post-content", ".infScroll"),
        )
        return [
            p
            for p in paragraphs
            if not any(keyword in p for keyword in _SKIP_PARAGRAPH_KEYWORDS)
        ]

    def _resolve_category(self, soup: BeautifulSoup, url: str) -> str:
        scroll = soup.select_one(".infScroll")
        if scroll:
            crumbs = [
                a.get_text(strip=True)
                for a in scroll.select("ul.breadcrumb a, .breadcrumb a")
                if a.get_text(strip=True) and a.get_text(strip=True) != "壹蘋新聞網"
            ]
            if crumbs:
                return crumbs[-1]

        section = self._meta_content(soup, prop="article:section")
        if section in NEXTAPPLE_SECTION_MAP:
            return NEXTAPPLE_SECTION_MAP[section]
        if section:
            return section

        match = re.search(r"news\.nextapple\.com/([^/]+)/", url)
        if match:
            key = match.group(1).lower()
            return NEXTAPPLE_SECTION_MAP.get(key, key)
        return ""

    def _resolve_title(self, soup: BeautifulSoup) -> str:
        scroll = soup.select_one(".infScroll")
        if scroll:
            h1 = scroll.select_one("h1")
            if h1:
                return h1.get_text(strip=True)

        title = self._select_text(soup, ("h1",))
        if title:
            return title

        og = self._meta_content(soup, prop="og:title")
        return og.split("｜")[0].split("|")[0].strip()

    def _resolve_publish_time(self, soup: BeautifulSoup) -> str:
        scroll = soup.select_one(".infScroll")
        if scroll:
            for time_node in scroll.select("time"):
                text = time_node.get_text(strip=True)
                if text and re.search(r"\d{4}/\d{2}/\d{2}", text):
                    return text

        return self._meta_content(soup, prop="article:published_time")

    def _extract_author(self, soup: BeautifulSoup, paragraphs: list[str]) -> str:
        author_node = soup.select_one(".infScroll .author")
        if author_node:
            name = self.extract_author_name(author_node.get_text(strip=True))
            if name:
                return name

        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author and meta_author.get("content"):
            name = self.extract_author_name(meta_author["content"])
            if name:
                return name

        return self.extract_author_name(" ".join(paragraphs[:2]))
