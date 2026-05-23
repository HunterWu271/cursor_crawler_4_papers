"""中國時報 (Chinatimes) 新聞解析器。"""

from bs4 import BeautifulSoup

from core.base_scraper import BaseScraper

_SKIP_PARAGRAPH_KEYWORDS = ("請繼續閱讀", "請繼續往下閱讀", "404")


class ChinatimesScraper(BaseScraper):
    """解析 chinatimes.com 即時／分類新聞內頁。"""

    def parse(self, soup: BeautifulSoup) -> dict[str, str] | None:
        h1 = soup.select_one("h1")
        if h1 and "無法找到" in h1.get_text():
            return None

        paragraphs = self.collect_paragraphs(soup, (".article-body",))
        paragraphs = [
            p
            for p in paragraphs
            if not any(k in p for k in _SKIP_PARAGRAPH_KEYWORDS)
        ]
        content = self.clean_content(paragraphs)
        if self.check_paywall(soup, content) or self.is_incomplete_content(content):
            return None

        category = self._meta_content(soup, prop="article:section")
        if not category:
            crumbs = [a.get_text(strip=True) for a in soup.select(".breadcrumb a")]
            category = crumbs[-1] if len(crumbs) > 1 else ""

        title = self._select_text(soup, ("h1.article-title", "h1"))
        publish_time = self._meta_content(
            soup, prop="article:published_time"
        ) or self._select_text(soup, ("time",))
        author = self.extract_author_name(
            self._select_text(soup, (".meta-info-wrapper", ".reporter", ".articlebyline"))
        )

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
