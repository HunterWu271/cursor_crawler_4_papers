"""爬蟲設定：測試 URL、延遲區間與輸出目錄。"""

from pathlib import Path

# 每次請求（每則新聞）與每家報社切換間的隨機延遲（秒）
DELAY_MIN_SECONDS = 1.0
DELAY_MAX_SECONDS = 3.0

# CSV 輸出目錄（PRD / .cursorrules）
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# 待爬取的新聞 URL（可依需求替換或擴充）
NEWS_URLS: list[str] = [
    "https://udn.com/news/story/6656/9507808",
    "https://www.chinatimes.com/realtimenews/20260521004523-260407",
    "https://news.ltn.com.tw/news/politics/breakingnews/5445562",
    "https://news.nextapple.com/politics/20260521/5FE7078C5811A591FAB1A12B15F04812",
]
