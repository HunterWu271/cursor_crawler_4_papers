# 台灣四大報新聞爬蟲

- 這是一個利用 Cursor 學習 Vibe Coding 的專題。
- 以 **Playwright** 非同步載入新聞內頁、**BeautifulSoup** 解析 DOM，抓取聯合報、中國時報、自由時報、壹蘋新聞網的結構化新聞資料，輸出 UTF-8 CSV。內建付費牆偵測、正文清洗、去重與隨機延遲，適合研究或批次建料用途。

- 詳細需求說明見 [`docs/PRD.md`](docs/PRD.md)。

---

## 目標媒體

| 代碼 | 媒體 | 網域 |
|------|------|------|
| `udn` | 聯合報 | `udn.com` |
| `chinatimes` | 中國時報 | `chinatimes.com` |
| `ltn` | 自由時報 | `news.ltn.com.tw` |
| `nextapple` | 壹蘋新聞網 | `news.nextapple.com` |

---

## 功能摘要

- **統一擷取七類新聞種類**：要聞、社會、生活、產經/財經、全球/國際、運動、娛樂（見 `config/categories.py`）
- **自動探索**：從各報分類列表頁收集文章內頁 URL（`scrapers/discovery.py`）
- **工廠分流**：依 URL 網域選擇解析器（`scrapers/factory.py`）
- **動態正文**：`domcontentloaded` + 正文段落等待，共用瀏覽器工作階段以加速批次爬取
- **品質過濾**：付費牆／不完整正文自動略過；依 URL 與標題+正文指紋去重
- **輸出**：`pandas` 聚合後寫入 `./data/YYYYMMDD_HH_MM_SS_news_data.csv`

---

## 專案結構

```
cursor_crawler_4_papers/
├── config/
│   ├── settings.py          # 延遲、輸出目錄、測試用 NEWS_URLS
│   └── categories.py        # 統一新聞種類與別名對照
├── core/
│   ├── base_scraper.py      # 正文清洗、付費牆、記者擷取、段落重組
│   └── playwright_engine.py # Playwright 下載、共用 session
├── scrapers/
│   ├── factory.py           # URL → 解析器
│   ├── discovery.py         # 列表頁探索、每類篇數上限
│   ├── udn.py
│   ├── chinatimes.py
│   ├── ltn.py
│   └── nextApple.py
├── main.py                  # 總調度、CSV 輸出、main / main_crawl_all
├── test_scraper.py          # 單報社測試（7 類 × 每類最多 40 則）
├── requirements.txt
├── docs/PRD.md
└── data/                    # CSV 輸出目錄（執行後產生）
```

---

## 流程概覽

```mermaid
flowchart LR
    A[main_crawl_all] --> B[discovery 探索列表頁]
    B --> C[文章內頁 URL 列表]
    C --> D[playwright_session]
    D --> E[fetch_html]
    E --> F[ScraperFactory.parse]
    F --> G[去重 + DataFrame]
    G --> H[data/*.csv]
```

1. **探索階段**：每家報社 7 個分類列表頁 → 擷取文章連結（預設每類最多 40 則）
2. **爬取階段**：共用 Chromium，逐則載入內頁 → 解析欄位
3. **輸出階段**：過濾失敗與重複 → 寫入 CSV

---

## 環境需求

- Python 3.10+
- Windows / macOS / Linux（需能執行 Playwright Chromium）

---

## 安裝

```bash
cd cursor_crawler_4_papers

python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
playwright install chromium
```

---

## 使用方式

### 1. 批次爬取四家（建議）

探索四家 × 七類 × 每類最多 **40** 則（探索階段最多約 **1120** 則 URL；實際成功筆數受付費牆、列表頁可抓連結數影響）。

```bash
python main.py
```

或在程式中：

```python
import asyncio
from main import main_crawl_all

asyncio.run(main_crawl_all())
```

### 2. 單報社測試

```bash
python test_scraper.py ltn
```

支援：`udn`、`chinatimes`、`ltn`、`nextapple`。

在 Jupyter 若已有事件迴圈：

```python
from test_scraper import test_scraper_async

df = await test_scraper_async("ltn")
df.head()
```

### 3. 手動指定文章 URL（快速驗證）

僅適用**單篇新聞內頁**，勿傳入報社首頁或分類列表頁。

```python
import asyncio
from main import main

urls = [
    "https://udn.com/news/story/6656/9507808",
    "https://news.ltn.com.tw/news/politics/breakingnews/5445562",
]
asyncio.run(main(urls))
```

未傳 `urls` 時，預設使用 `config/settings.py` 的 `NEWS_URLS`（四家各 1 則測試稿）。

---

## 輸出欄位（CSV）

| 欄位 | 說明 |
|------|------|
| 媒體 | 報社顯示名稱 |
| 網址 | 文章內頁 URL |
| 新聞種類 | 統一七類名稱 |
| 新聞標題 | 已移除多餘空白 |
| 刊出時間 | 已標準化清洗 |
| 記者 | 僅保留姓名（排除「綜合報導」等） |
| 新聞文本 | 段落以換行保留，已過濾廣告／延伸閱讀 |

檔名範例：`data/20260522_15_50_18_news_data.csv`（UTF-8，無 BOM）。

---

## 設定調整

| 檔案 | 常數 | 說明 |
|------|------|------|
| `scrapers/discovery.py` | `ARTICLES_PER_CATEGORY` | 每類最多抓取篇數（目前 **40**） |
| `scrapers/discovery.py` | `ARTICLE_SCAN_LIMIT` | 列表頁掃描連結上限（需 ≥ 每類篇數） |
| `scrapers/discovery.py` | `NEWSPAPER_CATEGORIES` | 各報分類列表頁 URL |
| `config/settings.py` | `DELAY_MIN/MAX_SECONDS` | 則與則、報社間隨機延遲（秒） |
| `config/settings.py` | `NEWS_URLS` | `main()` 預設測試 URL |
| `config/settings.py` | `DATA_DIR` | CSV 輸出目錄 |

---

## 兩種入口差異

| 函式 | 用途 | URL 來源 |
|------|------|----------|
| **`main_crawl_all()`** | 四家、七類、多篇批次爬取 | `discovery` 自動探索 |
| **`main(urls)`** | 自訂或少量測試 | 手動傳入或 `NEWS_URLS` |

**常見錯誤**：對 `main()` 傳入 `https://udn.com` 等**首頁**，程式會當成一篇文章解析，多半被略過或失敗。批次請用 `main_crawl_all()`。

---

## 注意事項

- **付費牆**：偵測到訂閱限定、正文過短或「請繼續閱讀」等特徵時會略過該則，不寫入 CSV。
- **執行時間**：完整批次可能需數十分鐘至數小時（篇數 × 延遲 × 網路狀況）。`test_scraper` 會依類別印出擷取耗時（`x小時 y分鐘 z秒`）。
- **聯合報娛樂**：列表頁可探索的 `/news/story/` 連結較少，該類實際篇數可能低於 `ARTICLES_PER_CATEGORY`。
- **合法與禮貌**：請遵守各站服務條款與 robots 規範；本專案已內建延遲，請勿再大幅縮短以免對目標站造成壓力。

---

## 擴充新報社（概要）

1. 在 `scrapers/` 新增解析器（繼承 `BaseScraper`）
2. 於 `scrapers/factory.py` 註冊網域
3. 於 `scrapers/discovery.py` 的 `NEWSPAPER_CATEGORIES` 與 `extract_article_urls` 加入列表頁規則
4. 視需要在 `config/categories.py` 補充別名對照

---

## 授權與免責

本專案供學習與研究使用。抓取之內容版權屬各新聞媒體所有，使用者應自行確保符合相關法令與網站政策。
