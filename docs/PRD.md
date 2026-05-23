# PRD：台灣四大報智慧爬蟲系統

## 1. 專案目標 <br><br>
自動化抓取台灣四大報紙(聯合報、中國時報、自由時報、壹蘋新聞網)的內容，排除付費牆，並進行高度結構化與清洗。

## 2. 抓取目標與欄位
- 目標媒體：聯合報 (UDN)、中國時報 (Chinatimes)、自由時報 (LTN)、壹蘋新聞網 (Next Apple / news.nextapple.com)。
- 核心欄位：
    1. 新聞種類 (Category)：移除所有白字元。
    2. 新聞標題 (Title)：移除所有白字元。
    3. 刊出時間 (Publish Times)：標準化為 ``YYYY-MM-DD-HH:MM``（例：``2026-05-23-09:43``）。
    4. 記者 (Author)：移除所有白字元。
    5. 新聞文本 (Content)：刪除空白行、廣告、延申閱讀，**保留段落換行**。

## 3. 進階邏輯
- 智慧付費牆偵測：偵測到「訂閱限定」或正文長度 < 150 個字元且含關鍵字時，自動跳過該URL。
- 動態加載處理：優先使用Firecrawl (Markdown 轉換)，若失敗，則退回至Playwright等待元素加載。
- 輸出：聚合為pandas DataFrame，最終產出"{time}_news_data.csv"，以 UTF8 標碼。

## 4. 技術約束
- 必須處理非同步請求 (Asyncio)。
- 必須包含隨機延遲 (random delay)，以防封鎖。
  
## 5. 專案檔案架構
taiwan-news-vibe-scraper/ <br>
│<br>
├── .cursorrules                # 中文版規則：定義本地下載、BS4 選取標準與付費牆防禦<br>
├── .gitignore                  # Git 忽略檔案<br>
├── README.md                   # 專案導覽地圖<br>
├── requirements.txt            # 本地依賴套件（playwright, beautifulsoup4, lxml, pandas）<br>
│<br>
├── docs/<br>
│   └── PRD.md                  # 產品需求文件（需同步更新此結構至 PRD 中）<br>
│<br>
├── config/<br>
│   ├── __init__.py<br>
│   └── settings.py             # 存放本地爬蟲 Headers、隨機延遲區間與測試用 URL<br>
│
├── core/                       # 本地端核心引擎<br>
│   ├── __init__.py<br>
│   ├── base_scraper.py         # 抽象基底類別（包含通用的白字元清洗與正文段落重組邏輯）<br>
│   └── playwright_engine.py    # 核心下載器：封裝 Playwright 非同步載入、等待元素、反爬防禦<br>
│
├── scrapers/                   # 媒體解析工廠（專注於 HTML 標籤拆解）<br>
│   ├── __init__.py<br>
│   ├── factory.py              # 爬蟲工廠類別：根據網址自動分流<br>
│   ├── chinatimes.py           # 中時解析器（純 BeautifulSoup4 語法）<br>
│   ├── ltn.py                  # 自由時報解析器（純 BeautifulSoup4 語法）<br>
│   └── udn.py                  # 聯合報解析器（純 BeautifulSoup4 語法）<br>
│   └── nextApple.py            # 壹蘋新聞網解析器 (純 BeautifulSoup4 語法)<br>
│<br>
└── main.py                     # 專案總調度入口：排程、併發、DataFrame 聚合與 CSV 輸出