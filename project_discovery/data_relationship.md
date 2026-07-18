# VNSTOCK — Data Flow & Data Relationship

> Quét ngày: 2026-07-13 | Phase 1 — Project Discovery

---

## 1. Data Flow (Luồng dữ liệu)

```
┌─────────────────────── EXTERNAL APIs ───────────────────────────────┐
│                                                                      │
│  vnstock Quote API (VCI/KBS)    FRED   Yahoo Finance   World Bank   │
│  vnstock Listing/Finance/       RSS    VCB Exchange    SJC Gold     │
│  Company/Trading API                                                 │
└──────────┬──────────────────────────────────────────────────────────┘
           │
           ▼ [CRAWL LAYER — 6 crawlers]
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  vn_stock_pipeline.py ──► ohlcv + meta                              │
│  meta_sync.py ──────────► metadata                                  │
│  macro_sync.py ─────────► macro                                     │
│  news_sync.py ──────────► news                                      │
│  shareholders_sync.py ──► shareholders + shareholders_progress      │
│  bctc_sync.py ──────────► data_bctc/*.parquet+csv                   │
│                                                                      │
└──────────┬──────────────────────────────────────────────────────────┘
           │
           ▼ [STORAGE LAYER — SQLite + File]
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  vn_stock.db (168 MB)                    data_bctc/ (8.391 files)   │
│  ├── ohlcv (1.9M rows)                  ├── {TK}_balance_sheet_*    │
│  ├── meta (tiến độ)                     ├── {TK}_income_statement_* │
│  ├── metadata (~1.686 rows)             ├── {TK}_cash_flow_*        │
│  ├── macro (~数千 rows)                  └── scrape_meta.csv         │
│  ├── news                                                            │
│  ├── shareholders                        blacklist.csv (nhập tay)    │
│  └── shareholders_progress               tickers.txt (universe)      │
│                                                                      │
└──────────┬──────────────────────────────────────────────────────────┘
           │
           ▼ [PROCESSING LAYER — mixer + processor]
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  vn_indicators.py ──► screen_snapshot.csv (31 cột, ~1.500 mã)       │
│                   ──► market_breadth.csv (20 dòng breadth ngành)     │
│  blacklist_sync.py ─► blacklist.csv (Auto + tay merged)             │
│  bctc_processor.py ─► financial_snapshot.csv/.parquet (~40 cột)     │
│  candle_scan.py ────► ta_signals.csv/.json                          │
│                  ──► data/candle_signals.json+js                     │
│                  ──► data/screener_data.js                           │
│                  ──► data/sector_heatmap.json+js                     │
│  vn_stock_pipeline.py export ──► ohlcv_flat.csv/.parquet            │
│                                                                      │
└──────────┬──────────────────────────────────────────────────────────┘
           │
           ▼ [ANALYSIS LAYER — offline, 0 network request]
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  stock_analyzer.py ──► analysis_latest.json/.md (10 chiến lược)     │
│                    ──► Focus_Analysis.md (phân tích mã cụ thể)      │
│                    ──► Market_Scan.md/.csv (quét thị trường)        │
│                    ──► watchlist_history (bảng trong DB)             │
│                                                                      │
│  ai_analyzer.py ────► ai_report_YYYYMMDD.json/.md (Claude API)     │
│                                                                      │
└──────────┬──────────────────────────────────────────────────────────┘
           │
           ▼ [PUBLISH LAYER — GitHub Pages]
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  publish_dashboard.py ──► git push (whitelist auto-extract)         │
│                                                                      │
│  Published files:                                                    │
│  ├── *.html (8 trang)                                                │
│  ├── app.js, analysis.js, style.css, nav.css                        │
│  ├── assets/css/shell.css + assets/js/*                              │
│  ├── data/*.json + data/*.js                                         │
│  ├── screen_snapshot.csv, market_breadth.csv                         │
│  ├── analysis_latest.json                                            │
│  └── ai_report_latest.md/.json                                       │
│                                                                      │
│  NOT published: vn_stock.db, *.py, *.parquet, ohlcv_flat.csv,       │
│                 data_bctc/, financial_snapshot.*, blacklist.csv,      │
│                 tickers*.txt, logs/, NOTES_FOR_TUNG*.md              │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Relationship (Quan hệ dữ liệu)

### 2.1 Khóa liên kết chính: `ticker`

`ticker` là **khóa liên kết xuyên suốt** toàn bộ hệ thống. Mọi bảng/file đều JOIN qua cột này.

```
ohlcv.ticker ──────────────┐
meta.ticker ───────────────┤
metadata.ticker ───────────┤
shareholders.ticker ───────┤──── ticker (mã CK, 3-4 ký tự, uppercase)
shareholders_progress.ticker┤
screen_snapshot.ticker ────┤
ta_signals.ticker ─────────┤
financial_snapshot.ticker ──┤
data_bctc/*.ticker ────────┤
blacklist.ticker ──────────┘
```

### 2.2 Khóa liên kết: `date` / thời gian

| Tên cột | Format | Bảng/file dùng |
|---|---|---|
| `date` | YYYY-MM-DD | `ohlcv`, `ohlcv_flat.*`, `screen_snapshot`, `ta_signals`, `market_breadth`, `macro_snapshot` |
| `period` | YYYY-QX / YYYY | `financial_snapshot`, `data_bctc/*` (tên cột) |
| `published_utc` | ISO 8601 | `news`, `news_latest` |
| `updated` / `updated_at` | YYYY-MM-DD HH:MM | `meta`, `metadata`, `shareholders`, `shareholders_progress`, `scrape_meta` |
| `scraped_at` | YYYY-MM-DD HH:MM | `data_bctc/*` |

### 2.3 Khóa liên kết: `industry` / ngành

| Cột | Nguồn | Dùng ở |
|---|---|---|
| `metadata.industry` | vnstock Listing API (ICB cấp 2) | `screen_snapshot.industry`, `ta_signals.industry` |
| `market_breadth.group` | Tính từ `metadata.industry` | Breadth theo ngành |

### 2.4 Khóa liên kết: `exchange` / sàn

| Cột | Giá trị | Dùng ở |
|---|---|---|
| `metadata.exchange` | HSX/HNX/UPCOM/DELISTED | `screen_snapshot.exchange` |

### 2.5 Quan hệ giữa các bảng (ERD logic)

```
                        ┌──────────────┐
                        │   tickers.txt │ (danh sách universe)
                        └──────┬───────┘
                               │ (feed vào)
                               ▼
┌─────────┐  ticker   ┌──────────────┐  ticker   ┌────────────┐
│  meta   │◄──────────│    ohlcv     │──────────►│  metadata  │
│ (tiến   │           │  (giá OHLCV) │           │ (PE/PB/ROE │
│  độ)    │           │  PK: ticker  │           │  room,etc) │
└─────────┘           │       +date  │           └──────┬─────┘
                      └──────┬───────┘                  │
                             │                          │ ticker+industry+exchange
                             │ (đọc bởi)                │ (JOIN vào)
                             ▼                          ▼
                      ┌──────────────┐           ┌───────────────┐
                      │ vn_indicators│           │screen_snapshot│
                      │   .py        │──────────►│  (31 cột)    │
                      └──────────────┘           └───────┬───────┘
                                                         │
                              ┌───────────────────────────┤
                              │                           │
                              ▼                           ▼
                       ┌─────────────┐            ┌──────────────┐
                       │ candle_scan │            │stock_analyzer│
                       │  ta_signals │            │ analysis_*   │
                       └─────────────┘            └──────────────┘

┌────────────┐  ticker   ┌──────────────┐
│shareholders│◄──────────│shareholders_ │
│  (dữ liệu)│           │   progress   │
│PK: ticker  │           │ (tiến độ)    │
│+shareholder│           └──────────────┘
│    _name   │
└────────────┘

┌──────┐  series+date   ┌────────────────┐
│macro │◄───────────────│macro_snapshot  │
│(DB)  │                │   (CSV view)   │
└──────┘                └────────────────┘

┌──────┐  link (PK)     ┌────────────────┐
│news  │◄───────────────│ news_latest    │
│(DB)  │                │   (CSV view)   │
└──────┘                └────────────────┘

┌──────────┐  ticker+report_type   ┌──────────────────┐
│data_bctc/│◄──────────────────────│financial_snapshot│
│(thô, per │     bctc_processor    │  (chuẩn hóa)     │
│  file)   │────────────────────►  │  PK: ticker      │
└──────────┘                       │       +period     │
                                   └──────────────────┘

┌────────────┐  ticker   ┌──────────────┐
│blacklist   │──────────►│metadata      │
│   .csv     │  (merge)  │.margin_status│
└────────────┘           └──────────────┘
```

### 2.6 Chi tiết quan hệ ticker/date/quarter/year

| Khóa | Cách dùng | Ở đâu |
|---|---|---|
| `ticker` | Mã CK uppercase, 3-4 ký tự | TOÀN BỘ bảng/file |
| `date` (ngày GD) | YYYY-MM-DD, PK cùng ticker | `ohlcv`, `macro` |
| `date` (phiên cuối) | YYYY-MM-DD, 1 giá trị/ticker | `screen_snapshot`, `ta_signals` |
| `period` (quý) | YYYY-QX (VD: 2025-Q3) | `financial_snapshot`, cột tên trong `data_bctc/*` |
| `period_type` | "quarter" / "year" | `financial_snapshot` |
| Không có FK chính thức | SQLite không enforce FK | Toàn bộ |

### 2.7 Foreign Key Logic (không enforce, chỉ quy ước)

| Quan hệ | Mô tả |
|---|---|
| `ohlcv.ticker` → `metadata.ticker` | JOIN để lấy ngành/sàn/PE/PB/ROE |
| `ohlcv.ticker` → `meta.ticker` | Tiến độ backfill |
| `metadata.ticker` ← `blacklist.ticker` | Merge margin_status |
| `screen_snapshot.ticker` ← `ohlcv.ticker` + `metadata.ticker` | Mixer trộn chỉ báo + metadata |
| `ta_signals.ticker` ← `screen_snapshot.ticker` | Tái sử dụng rs_rating/rel_vol/industry |
| `financial_snapshot.ticker` ← `data_bctc/{TICKER}_*` | Chuẩn hóa item_id |
| `shareholders.ticker` → `ohlcv.ticker` (universe) | Chỉ cào mã đã có giá |
