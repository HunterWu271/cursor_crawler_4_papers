"""聯合報 (UDN) 新聞解析器。"""

from bs4 import BeautifulSoup

from core.base_scraper import BaseScraper


class UdnScraper(BaseScraper):
    """解析 udn.com 新聞內頁。"""

    def parse(self, soup: BeautifulSoup) -> dict[str, str] | None:
        paragraphs = self.collect_paragraphs(
            soup,
            (".article-content__editor", ".article-content__paragraph"),
        )
        content = self.clean_content(paragraphs)
        if self.check_paywall(soup, content) or self.is_incomplete_content(content):
            return None

        category = self._meta_content(soup, prop="article:section")
        if not category:
            crumbs = [
                a.get_text(strip=True)
                for a in soup.select(".article-content__breadcrumb a")
                if a.get_text(strip=True) and a.get_text(strip=True).lower() != "udn"
            ]
            category = crumbs[-1] if crumbs else ""

        title = self._select_text(
            soup,
            ("h1", ".article-content__title"),
        )
        publish_time = self._select_text(
            soup,
            (".article-content__time",),
        ) or self._meta_content(soup, prop="article:published_time")
        author = self.extract_author_name(
            self._select_text(soup, (".article-content__author",))
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
