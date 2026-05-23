"""非同步爬蟲基底：共用欄位清洗、付費牆偵測與正文段落重組。"""

import re
from abc import ABC

from bs4 import BeautifulSoup

# 正文需過濾的廣告／導流關鍵字（含 PRD 常見錯字「延申閱讀」）
CONTENT_AD_KEYWORDS = (
    "延伸閱讀",
    "延申閱讀",
    "相關新聞",
    "點我下載APP",
    "點我下載 App",
    "訂閱看更多",
    "加入會員",
    "廣告",
)

PAYWALL_CSS_SELECTORS = (
    ".paywall",
    "#paywall",
    ".premium",
    ".premium-content",
    ".locked-content",
    ".subscriber-only",
    ".article-mask",
    ".member-only",
    ".login-modal",
    "[class*='paywall']",
    "[id*='paywall']",
)

# 正文擷取時排除的雜質節點
CONTENT_NOISE_SELECTORS = (
    "script",
    "style",
    "noscript",
    "aside",
    ".ad",
    ".advertisement",
    ".related",
    ".recommend",
    ".extend",
    ".extend-news",
)

# 不完整正文特徵（付費牆預覽、省略結尾）
INCOMPLETE_CONTENT_MARKERS = (
    "請繼續往下閱讀",
    "請繼續閱讀",
    "閱讀更多",
    "看全文",
    "訂閱看更多",
)

# 記者姓名擷取（僅保留姓名，排除綜合報導、地方報導等）
AUTHOR_PATTERNS = (
    r"【記者\s*([^／\s,，、\d]+)",
    r"〔記者\s*([^／\s,，、\d]+)",
    r"（記者\s*([^／\s,，、\d]+)",
    r"【([^／\s,，、\d]+)／(?:綜合)?報導",
    r"記者\s*([^／\s,，、\d]+)",
    r"文／\s*([^／\s,，、\d]+)",
    r"中時新聞網\s*([^／\s,，、\d]+)",
    r"聯合報[/／]?\s*記者\s*([^／\s,，、\d]+)",
)

AUTHOR_NOISE_WORDS = frozenset(
    {
        "記者",
        "綜合報導",
        "報導",
        "即時報導",
        "電子報",
        "聯合報",
        "中時新聞網",
        "自由時報電子報",
        "壹蘋新聞網",
    }
)

PAYWALL_PAGE_PHRASES = (
    "訂閱限定",
    "會員限定",
    "訂閱看更多",
    "加入會員",
    "登入後閱讀",
    "請登入",
    "請繼續往下閱讀",
    "請繼續閱讀",
    "訂閱數位報",
)


class BaseScrape(ABC):
    """各報社 Scraper 的抽象基底，提供 metadata 與正文清洗。"""

    @staticmethod
    def normalize_category_name(raw: str) -> str:
        """對應 config.categories 的統一新聞種類名稱。"""
        from config.categories import normalize_category

        return normalize_category(raw)

    @staticmethod
    def clean_metadata(text: str) -> str:
        """移除所有白字元（空白、換行、Tab 等），僅保留純文字。"""
        if not text:
            return ""
        return re.sub(r"\s+", "", text)

    @staticmethod
    def _normalize_author_name(name: str) -> str:
        """將擷取片段整理為純記者姓名。"""
        if not name:
            return ""
        name = name.strip()
        name = re.sub(r"[／/].*$", "", name)
        name = re.sub(r"\d{2}:\d{2}.*$", "", name)
        name = re.sub(r"\d{4}/\d{2}/\d{2}.*$", "", name)
        for noise in ("綜合報導", "即時報導", "電子報"):
            name = name.replace(noise, "")
        name = re.sub(r".*?報導$", "", name)
        name = re.sub(r"[^一-龥a-zA-Z·．.]", "", name)
        if not name or name in AUTHOR_NOISE_WORDS:
            return ""
        match = re.match(r"^[\u4e00-\u9fff]{2,8}", name)
        if match:
            return match.group(0)
        match = re.match(r"^[a-zA-Z·．.]{2,30}", name)
        if match:
            return match.group(0)
        return name if len(name) >= 2 else ""

    @classmethod
    def extract_author_name(cls, raw: str) -> str:
        """
        從 byline 或 meta 字串中只擷取記者姓名。
        排除「綜合報導」、「台北報導」等資訊。
        """
        if not raw:
            return ""

        for pattern in AUTHOR_PATTERNS:
            match = re.search(pattern, raw)
            if match:
                name = cls._normalize_author_name(match.group(1))
                if name:
                    return name

        cleaned = raw
        for prefix in (
            "聯合報",
            "中時新聞網",
            "自由時報電子報",
            "壹蘋新聞網",
            "記者",
        ):
            cleaned = cleaned.replace(prefix, "")
        cleaned = re.sub(r"\d{2}:\d{2}.*", "", cleaned)
        cleaned = re.sub(r"\d{4}/\d{2}/\d{2}.*", "", cleaned)
        cleaned = re.sub(r"[／/].*", "", cleaned)
        return cls._normalize_author_name(cleaned)

    @staticmethod
    def collect_paragraphs(
        soup: BeautifulSoup,
        container_selectors: tuple[str, ...],
    ) -> list[str]:
        """
        從正文容器擷取完整段落（優先 p 標籤，必要時以換行切分區塊）。
        """
        container = None
        for selector in container_selectors:
            container = soup.select_one(selector)
            if container:
                break
        if not container:
            return []

        for noise_sel in CONTENT_NOISE_SELECTORS:
            for node in container.select(noise_sel):
                node.decompose()

        paragraphs: list[str] = []
        for node in container.find_all("p"):
            text = node.get_text(separator=" ", strip=True)
            if text:
                paragraphs.append(text)

        if len(paragraphs) < 2:
            for block in re.split(r"\n{2,}", container.get_text("\n", strip=True)):
                block = block.strip()
                if block and len(block) > 20:
                    paragraphs.append(block)

        deduped: list[str] = []
        for paragraph in paragraphs:
            if deduped and deduped[-1] == paragraph:
                continue
            deduped.append(paragraph)
        return deduped

    @staticmethod
    def clean_content(paragraphs: list[str]) -> str:
        """
        過濾空行與廣告段落，以單一換行符保留段落分隔。
        """
        cleaned: list[str] = []
        for raw in paragraphs:
            if raw is None:
                continue
            paragraph = raw.strip()
            if not paragraph:
                continue
            if any(keyword in paragraph for keyword in CONTENT_AD_KEYWORDS):
                continue
            if re.fullmatch(r"[\.…\s]+", paragraph):
                continue
            cleaned.append(paragraph)
        return "\n".join(cleaned)

    @classmethod
    def is_incomplete_content(cls, content: str) -> bool:
        """偵測付費預覽或省略結尾等不完整正文。"""
        if not content:
            return True
        if any(marker in content for marker in INCOMPLETE_CONTENT_MARKERS):
            return True
        plain = re.sub(r"\s+", "", content)
        if len(plain) < 150:
            return True
        if re.search(r"(\.{3}|…)\s*$", content.strip()) and len(plain) < 500:
            return True
        return False

    @classmethod
    def check_paywall(cls, soup: BeautifulSoup, content: str = "") -> bool:
        """
        偵測付費牆／登入阻擋：CSS 遮罩、頁面關鍵字，或正文過短且含「訂閱」。
        """
        for selector in PAYWALL_CSS_SELECTORS:
            if soup.select_one(selector):
                return True

        plain_len = cls._plain_length(content)
        if plain_len >= 150:
            return False

        page_text = soup.get_text(separator=" ", strip=True)
        if any(phrase in page_text for phrase in PAYWALL_PAGE_PHRASES):
            return True

        if content and "訂閱" in content:
            return True
        return False

    @staticmethod
    def _meta_content(soup: BeautifulSoup, *, prop: str | None = None, name: str | None = None) -> str:
        if prop:
            tag = soup.find("meta", property=prop)
        else:
            tag = soup.find("meta", attrs={"name": name})
        return (tag.get("content") or "").strip() if tag else ""

    @staticmethod
    def _select_text(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str:
        for selector in selectors:
            node = soup.select_one(selector)
            if node:
                text = node.get_text(separator=" ", strip=True)
                if text:
                    return text
        return ""

    @staticmethod
    def _plain_length(text: str) -> int:
        return len(re.sub(r"\s+", "", text))


# PRD / scrapers 慣用別名
BaseScraper = BaseScrape
