# VNSTOCK — Python Modules Analysis

> Quét ngày: 2026-07-13 | Phase 1 — Project Discovery

---

## 1. Module Classification

### Crawler / Downloader (API → DB/File)

| Module | Vai trò | Nguồn dữ liệu | Đích ghi | Tần suất |
|---|---|---|---|---|
| `vn_stock_pipeline.py` | Crawler giá OHLCV | vnstock Quote API (VCI/KBS) | `vn_stock.db` bảng `ohlcv` + `meta` | Hằng ngày |
| `meta_sync.py` | Crawler metadata cơ bản | vnstock Listing/Finance/Company API | `vn_stock.db` bảng `metadata` | Hằng quý (per-ticker nặng) |
| `macro_sync.py` | Crawler vĩ mô | FRED, Yahoo, World Bank, VCB, SJC | `vn_stock.db` bảng `macro` | Hằng ngày |
| `news_sync.py` | Crawler tin tức | RSS feeds (8 nguồn) | `vn_stock.db` bảng `news` | Nhiều lần/ngày |
| `shareholders_sync.py` | Crawler cổ đông lớn | vnstock Company API (VCI/KBS) | `vn_stock.db` bảng `shareholders` + `shareholders_progress` | Hằng tháng |
| `bctc_sync.py` | Crawler BCTC quý | vnstock Finance API (KBS/VCI) | `data_bctc/*.csv` + `*.parquet` | Hằng quý |

### Parser / Processor

| Module | Vai trò | Input | Output |
|---|---|---|---|
| `bctc_processor.py` | Xử lý + chuẩn hóa BCTC | `data_bctc/*.parquet+csv` | `financial_snapshot.csv/.parquet` |
| `vn_indicators.py` | Thư viện chỉ báo + mixer | `vn_stock.db` (ohlcv+metadata) | `screen_snapshot.csv` + `market_breadth.csv` |
| `candle_scan.py` | Quét mẫu nến + SMC | `vn_stock.db` + `screen_snapshot.csv` | `ta_signals.csv/.json` + `data/*.json+js` |
| `blacklist_sync.py` | Tự động hóa blacklist | `vn_stock.db` (price_board) + `blacklist.csv` | `blacklist.csv` (merge Auto+tay) |

### Analyzer

| Module | Vai trò | Input | Output |
|---|---|---|---|
| `stock_analyzer.py` | Quant engine offline (10 chiến lược) | `screen_snapshot.csv` + `ohlcv_flat.parquet` + `vn_stock.db` | `analysis_latest.json/.md` + `Focus_Analysis.md` + `Market_Scan.*` |
| `ai_analyzer.py` | Báo cáo AI (Claude API) | `screen_snapshot.csv` + `market_breadth.csv` + `macro_snapshot.csv` + `news_latest.csv` | `ai_report_YYYYMMDD.json/.md` |

### Exporter / Publisher

| Module | Vai trò | Input | Output |
|---|---|---|---|
| `publish_dashboard.py` | Đẩy web GitHub Pages | Tất cả file web | git push → GitHub Pages |
| `sync_and_push.bat` | Legacy sync (bị thay thế) | File dữ liệu | git push |

### Utils / Config

| Module | Vai trò |
|---|---|
| `config.json` | Config BCTC (tickers demo, reports, period) |
| `requirements.txt` | Python dependencies |
| `tickers.txt` | Universe giá (~1.745 mã) |
| `tickers_bctc.txt` | Universe BCTC (copy từ tickers.txt) |

### Test

| Module | Vai trò |
|---|---|
| `tests/test_selftest.py` | Hồi quy 17 mã fixture cho stock_analyzer.py |

---

## 2. Module Dependencies (Import Graph)

```
                                    vnstock (package)
                                         │
        ┌────────────────┬───────────────┼───────────────┬────────────────────┐
        │                │               │               │                    │
vn_stock_pipeline  meta_sync    macro_sync     news_sync      shareholders_sync
  (Quote API)     (Listing/     (requests       (requests       (Company API)
                 Finance/       raw HTTP)        raw HTTP)
                 Company/
                 Trading)
        │                │                                                    │
        └────────────────┤                                                    │
                         │                                                    │
                    blacklist_sync ←──── (imports from meta_sync:              │
                    (Trading API)        call_api, get_universe,               │
                                         DB_PATH, BLACKLIST_FILE,             │
                                         PRICE_BOARD_BATCH)                   │
                                                                              │
                                                                              │
        ┌─────────────────────────────────────────────────────────────────────┘
        │
        ▼
   vn_stock.db ──────────────────────────────────────────────────────────────┐
        │                                                                    │
        ├──► vn_indicators.py ──► screen_snapshot.csv + market_breadth.csv   │
        │                              │                                     │
        │    ┌─────────────────────────┘                                     │
        │    │                                                               │
        │    ├──► candle_scan.py ──► ta_signals.* + data/*.json+js           │
        │    │                                                               │
        │    ├──► stock_analyzer.py ──► analysis_latest.* + Focus/Scan       │
        │    │    (imports vn_indicators as vi)                               │
        │    │                                                               │
        │    └──► ai_analyzer.py ──► ai_report_YYYYMMDD.*                    │
        │                                                                    │
        └──────────────────────────────────────────────────────────────────┘

   bctc_sync.py ──► data_bctc/*.parquet+csv ──► bctc_processor.py
   (vnstock Finance)                            ──► financial_snapshot.*
                                                (imports numpy, pandas)

   publish_dashboard.py ──► git push ──► GitHub Pages
   (reads *.html + app.js to auto-extract whitelist)
```

---

## 3. Shared Patterns Across Modules

### API Call Pattern (copy-paste across 6 modules)
```python
def call_api(fn, label):
    for attempt in range(1, MAX_RETRY + 1):
        try:
            res = fn()
            time.sleep(REQUEST_DELAY)
            ...
        except Exception as e:
            # Bóc RetryError (tenacity) → phân loại rate-limit / network / empty
            inner = getattr(getattr(e, "last_attempt", None), "exception", lambda: None)()
            ...
    return NET_FAIL
```

Xuất hiện trong: `vn_stock_pipeline.py`, `meta_sync.py`, `bctc_sync.py`, `shareholders_sync.py`, `blacklist_sync.py` (import từ meta_sync), `macro_sync.py` (biến thể http_get).

### Shared Constants
| Hằng số | Giá trị | Dùng bởi |
|---|---|---|
| `DB_PATH` | `"vn_stock.db"` | 8 modules |
| `REQUEST_DELAY` | 1.0–1.1 | 6 modules |
| `MAX_RETRY` | 3 | 6 modules |
| `BACKOFF_BASE` | 5 | 6 modules |
| `BACKOFF_RATE` | 15 | 5 modules |
| `INDEX_SYMBOLS` | 3 chỉ số | 5 modules |
| `PRIMARY_SRC` / `FAILOVER_SRC` | VCI/KBS | 4 modules |
| `NET_FAIL` | sentinel string | 4 modules |

### Resume Pattern
Mọi crawler đều hỗ trợ resume:
- **Giá:** bảng `meta` (status done/empty/failed)
- **Metadata:** cột `updated` trong bảng `metadata`
- **BCTC:** `scrape_meta.csv` (status done/empty/failed)
- **Cổ đông:** bảng `shareholders_progress`
- **Blacklist:** chạy lại = tái sinh dòng Auto

### Console UTF-8 Fix
```python
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
```
Xuất hiện ở đầu 11/13 module Python (trừ `vn_stock_pipeline.py` và `vn_indicators.py` không cần).

---

## 4. Execution Order (Pipeline hằng ngày)

```
1. vn_stock_pipeline.py update      → cập nhật giá mới
2. macro_sync.py                    → cập nhật vĩ mô
3. news_sync.py                     → cào tin tức RSS
4. vn_indicators.py                 → trộn chỉ báo → screen_snapshot.csv + market_breadth.csv
5. candle_scan.py                   → quét mẫu nến → ta_signals.* + data/*
6. ai_analyzer.py [--dry-run]       → báo cáo AI (TỐN PHÍ nếu không --dry-run)
7. stock_analyzer.py --strategy all → quant engine → analysis_latest.*
8. publish_dashboard.py --live      → đẩy web
```

### Pipeline hằng quý (BCTC)
```
1. bctc_sync.py scrape              → cào BCTC quý mới
2. bctc_processor.py                → xử lý → financial_snapshot.*
```

### Pipeline hằng tháng
```
1. shareholders_sync.py             → cào cổ đông lớn
2. meta_sync.py [--refresh]         → cập nhật PE/PB/ROE/room
3. blacklist_sync.py                → cập nhật blacklist từ trading_status
4. meta_sync.py --blacklist-only    → đẩy cờ margin vào DB
```
