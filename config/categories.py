"""統一新聞種類名稱與各報原始分類對照。"""

from __future__ import annotations

# 四家報社共同爬取的分類（CSV「新聞種類」欄位）
UNIFIED_CATEGORIES: tuple[str, ...] = (
    "要聞",
    "社會",
    "生活",
    "產經/財經",
    "全球/國際",
    "運動",
    "娛樂",
)

# 各報頁面／麵包屑可能出現的名稱 -> 統一欄位
CATEGORY_ALIASES: dict[str, str] = {
    "政治": "要聞",
    "焦點": "要聞",
    "即時": "要聞",
    "產經": "產經/財經",
    "財經": "產經/財經",
    "全球": "全球/國際",
    "國際": "全球/國際",
    "體育": "運動",
    "運動": "運動",
    "sport": "運動",
    "sports": "運動",
    "娛樂時尚": "娛樂",
    "演藝": "娛樂",
    "寶島": "社會",
    "地方": "社會",
    "local": "社會",
    "business": "產經/財經",
    "finance": "產經/財經",
    "world": "全球/國際",
    "international": "全球/國際",
    "politics": "要聞",
    "entertainment": "娛樂",
    "life": "生活",
    "society": "社會",
}


def normalize_category(raw: str) -> str:
    """將報社原始分類名稱對應為統一欄位；已是統一名稱則原樣回傳。"""
    if not raw:
        return ""
    name = raw.strip()
    if name in UNIFIED_CATEGORIES:
        return name
    return CATEGORY_ALIASES.get(name, name)
