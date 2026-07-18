# VNSTOCK — Dataset Inventory

> Quét ngày: 2026-07-13 | Phase 1 — Project Discovery

---

## 1. SQLite Database: `vn_stock.db` (~168 MB)

### Bảng `ohlcv` — Giá OHLCV lịch sử

| Cột | Kiểu | Mô tả |
|---|---|---|
| `ticker` | TEXT | Mã chứng khoán (PK cùng date) |
| `date` | TEXT | Ngày giao dịch YYYY-MM-DD (PK cùng ticker) |
| `open` | REAL | Giá mở cửa (đơn vị VND, đã scale ×1000) |
| `high` | REAL | Giá cao nhất |
| `low` | REAL | Giá thấp nhất |
| `close` | REAL | Giá đóng cửa |
| `volume` | INTEGER | Khối lượng giao dịch |
| `source` | TEXT | Nguồn dữ liệu (VCI/KBS) |

- **PK:** `(ticker, date)` | **Index:** `idx_date ON ohlcv(date)`
- **Dữ liệu:** ~1.909.419 dòng, ~1.686 mã, từ 2015 đến 2026

### Bảng `meta` — Tiến độ backfill giá

| Cột | Kiểu | Mô tả |
|---|---|---|
| `ticker` | TEXT PK | Mã chứng khoán |
| `status` | TEXT | done / empty / failed |
| `rows` | INTEGER | Số dòng giá đã có |
| `updated` | TEXT | Thời điểm cập nhật |

### Bảng `metadata` — Metadata cơ bản + luật

| Cột | Kiểu | Mô tả |
|---|---|---|
| `ticker` | TEXT PK | Mã chứng khoán |
| `exchange` | TEXT | Sàn: HSX/HNX/UPCOM/DELISTED |
| `industry` | TEXT | Ngành ICB cấp 2 (~19 nhóm) |
| `foreign_room_pct` | REAL | % room ngoại CÒN TRỐNG (100=chưa mua gì) |
| `pe` | REAL | P/E quý mới nhất (lần) |
| `pb` | REAL | P/B quý mới nhất (lần) |
| `roe` | REAL | ROE trailing 4 quý, đơn vị % |
| `market_cap` | REAL | Vốn hóa (đồng VND) |
| `shares_outstanding` | REAL | Số CP lưu hành |
| `free_float_est` | REAL | Proxy free-float 0..1 |
| `dividend_yield` | REAL | Tỷ suất cổ tức trailing % (-1=không có số) |
| `margin_status` | TEXT | margin_cut/warning/control/suspend |
| `updated` | TEXT | Mốc resume per-ticker |

> ⚠️ **BẪY POINT-IN-TIME**: Snapshot "hôm nay", KHÔNG dùng cho backtest quá khứ.

### Bảng `macro` — Dữ liệu vĩ mô

| Cột | Kiểu | Mô tả |
|---|---|---|
| `series` | TEXT | Mã chuỗi (PK cùng date): us_fedfunds, sp500, vn_cpi_yoy... |
| `date` | TEXT | Ngày YYYY-MM-DD (PK cùng series) |
| `value` | REAL | Giá trị |

- **17 chuỗi:** us_fedfunds, us_10y, us_cpi, dxy, wti, sp500, nasdaq, vix, nikkei, hsi, gold_world, brent, usdvnd_mkt, usdvnd_vcb, gold_sjc, vn_cpi_yoy, vn_gdp_yoy

### Bảng `news` — Tin tức tài chính

| Cột | Kiểu | Mô tả |
|---|---|---|
| `link` | TEXT PK | URL tin (tự chống trùng) |
| `region` | TEXT | world / vn |
| `source` | TEXT | Tên feed (CNBC, BBC, VnExpress...) |
| `title` | TEXT | Tiêu đề |
| `summary` | TEXT | Tóm tắt (strip HTML, ≤500 ký tự) |
| `published_utc` | TEXT | ISO UTC |
| `fetched` | TEXT | Thời điểm cào |

- **8 feed:** CNBC TopNews, CNBC Finance, BBC Business, MarketWatch, VnExpress KD, CafeF CK, VnEconomy CK, Vietstock CK

### Bảng `shareholders` — Cổ đông lớn

| Cột | Kiểu | Mô tả |
|---|---|---|
| `ticker` | TEXT | PK cùng shareholder_name |
| `shareholder_name` | TEXT | Tên cổ đông |
| `shares_owned` | REAL | Số cổ phần |
| `pct` | REAL | Tỷ lệ sở hữu % (0..100), -1=không có số |
| `shareholder_type` | TEXT | Luôn NULL (nguồn không phân loại) |
| `source` | TEXT | VCI/KBS |
| `updated_at` | TEXT | Thời điểm cào |

### Bảng `shareholders_progress` — Tiến độ cào cổ đông

| Cột | Kiểu | Mô tả |
|---|---|---|
| `ticker` | TEXT PK | Mã chứng khoán |
| `status` | TEXT | done / empty / failed |
| `rows` | INTEGER | Số dòng cổ đông |
| `updated` | TEXT | Thời điểm |

---

## 2. CSV Files — Root Level

### `ohlcv_flat.csv` (~108 MB, 1.909.419 dòng)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `ticker` | string | Mã CK |
| `date` | string | YYYY-MM-DD |
| `open` | float | Giá mở cửa VND |
| `high` | float | Giá cao nhất |
| `low` | float | Giá thấp nhất |
| `close` | float | Giá đóng cửa |
| `volume` | int | Khối lượng |
| `source` | string | VCI/KBS |

- **PK ẩn:** (ticker, date) | **Khoảng thời gian:** 2015-01-01 → 2026-07-10

### `screen_snapshot.csv` (~293 KB)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `ticker` | string | Mã CK |
| `date` | string | Phiên cuối |
| `close` | float | Giá đóng cửa |
| `chg_today_pct` | float | % thay đổi phiên |
| `gtgd20_ty` | float | GTGD bình quân 20 phiên (tỷ/phiên) |
| `rel_vol` | float | Relative volume |
| `rsi14` | float | RSI 14 |
| `macd_hist` | float | MACD histogram |
| `bb_pctb` | float | Bollinger %B |
| `atr_pct` | float | ATR % |
| `above_sma50` | bool (text) | Trên SMA50 |
| `above_sma200` | bool (text) | Trên SMA200 |
| `golden_cross` | bool (text) | Golden cross |
| `pct_from_52w_high` | float | % từ đỉnh 52 tuần |
| `near_52w_high` | bool (text) | Gần đỉnh 52 tuần |
| `pct_above_52w_low` | float | % trên đáy 52 tuần |
| `ret_1m/3m/6m/12m` | float | Return 1/3/6/12 tháng |
| `structure` | string | up/side/down (SMC) |
| `dist_swing_low_pct` | float | Khoảng cách swing low % |
| `rs_rating` | int | Relative Strength rating (0-99) |
| `exchange` | string | HSX/HNX/UPCOM/DELISTED |
| `industry` | string | Tên ngành ICB cấp 2 |
| `foreign_room_pct` | float | % room ngoại còn trống |
| `pe/pb/roe` | float | P/E, P/B, ROE% |
| `free_float_est` | float | Proxy free-float 0..1 |
| `margin_status` | string | margin_cut/warning/control/suspend |

- **31 cột** | ~1.500+ mã

### `financial_snapshot.csv` (~4 MB)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `ticker` | string | Mã CK |
| `period` | string | Kỳ báo cáo (2024-Q1, 2025-Q3...) |
| `period_type` | string | quarter / year |
| `revenue` | float | Doanh thu (đã coalesce theo ngành) |
| `net_profit` | float | Lợi nhuận sau thuế |
| `gross_profit` | float | Lợi nhuận gộp |
| `operating_profit` | float | Lợi nhuận hoạt động |
| `total_assets` | float | Tổng tài sản |
| `total_liabilities` | float | Tổng nợ |
| `equity` | float | Vốn chủ sở hữu |
| `cash` | float | Tiền và tương đương tiền |
| `inventory` | float | Hàng tồn kho |
| `receivables` | float | Khoản phải thu |
| `current_assets` | float | Tài sản ngắn hạn |
| `current_liabilities` | float | Nợ ngắn hạn |
| `cost_of_goods_sold` | float | Giá vốn hàng bán |
| `operating_cash_flow` | float | Dòng tiền hoạt động |
| `debt` | float | Tổng nợ vay |
| `shares_outstanding` | float | Số CP lưu hành |
| `book_value` | float | Giá trị sổ sách/CP |
| `eps_calc` | float | EPS tự tính (proxy) |
| `capex` | float | Chi đầu tư TSCĐ |
| `free_cash_flow` | float | Dòng tiền tự do |
| `revenue_growth_yoy/qoq` | float | Tăng trưởng DT YoY/QoQ |
| `profit_growth_yoy/qoq` | float | Tăng trưởng LN YoY/QoQ |
| `gross_margin/operating_margin/net_margin` | float | Biên lợi nhuận |
| `roe/roa` | float | Tỷ suất sinh lời |
| `debt_to_equity/debt_ratio` | float | Đòn bẩy |
| `current_ratio/quick_ratio/cash_ratio` | float | Thanh khoản |
| `asset_turnover/inventory_turnover/receivable_turnover` | float | Hiệu quả |
| `operating_cash_flow_ratio` | float | OCF/CL |

- **~40 cột** | Multi-index (ticker, period)

### `market_breadth.csv` (~1.2 KB)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `group` | string | ALL hoặc tên ngành ICB |
| `date` | string | Phiên giao dịch |
| `n_symbols` | int | Số mã trong nhóm |
| `n_up/n_down/n_flat` | int | Số mã tăng/giảm/đứng |
| `pct_above_ma200` | float | % mã trên MA200 |
| `avg_rs_rating` | float | RS trung bình |
| `avg_ret_1m` | float | Return 1 tháng trung bình |

- **20 dòng** (1 ALL + 19 ngành)

### `macro_snapshot.csv` (~1.4 KB)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `series` | string | Mã chuỗi |
| `name` | string | Tên hiển thị |
| `unit` | string | Đơn vị |
| `freq` | string | Tần suất: ngày/tháng/năm |
| `date` | string | Ngày mới nhất |
| `value` | float | Giá trị mới nhất |
| `chg_prev` | float | Thay đổi so với điểm trước |
| `chg_1m` | float | Thay đổi 1 tháng |
| `chg_1y` | float | Thay đổi 1 năm |

- **17 chuỗi**

### `ta_signals.csv` (~66 KB)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `ticker` | string | Mã CK |
| `date` | string | Phiên quét |
| `close` | float | Giá đóng cửa |
| `volume` | int | Khối lượng |
| `patterns` | string | Mẫu nến (`;` separated) |
| `smc` | string | Vùng SMC (`;` separated) |
| `confluence` | bool | Có confluence hay không |
| `direction` | string | bullish/bearish/neutral |
| `industry` | string | Ngành |
| `rs_rating` | float | RS rating |
| `rel_vol` | float | Relative volume |
| `gtgd20_ty` | float | GTGD 20 phiên (tỷ) |
| `margin_status` | string | Trạng thái margin |

### `news_latest.csv` (~22 KB)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `published_utc` | string | ISO UTC timestamp |
| `region` | string | world / vn |
| `source` | string | Tên feed |
| `title` | string | Tiêu đề tin |
| `link` | string | URL tin |

- **~100 dòng**

### `blacklist.csv` (~32 KB)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `ticker` | string | Mã CK |
| `status` | string | margin_cut/warning/control/suspend |
| `note` | string | "Auto: ..." (máy) hoặc ghi chú tay |
| `updated` | string | Ngày cập nhật |

---

## 3. BCTC Files — `data_bctc/`

### Schema file thô (CSV/Parquet)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `ticker` | string | Mã CK |
| `report_type` | string | balance_sheet / income_statement / cash_flow |
| `source` | string | VCI / KBS |
| `scraped_at` | string | Thời điểm cào |
| `item` | string | Tên chỉ tiêu tiếng Việt |
| `item_en` | string | Tên chỉ tiêu tiếng Anh |
| `item_id` | string | Mã chỉ tiêu chuẩn hóa |
| `2026-Q1` ... `2024-Q2` | float | Giá trị từng kỳ (cột = kỳ) |

- **1.494 mã** × 3 loại báo cáo × 2 format (CSV + Parquet) = ~8.391 file
- Mỗi file chứa nhiều hàng (items) × nhiều cột (quarters)

### `scrape_meta.csv` (trong data_bctc/)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `ticker` | string | Mã CK |
| `report_type` | string | balance_sheet/income_statement/cash_flow |
| `period_type` | string | quarter/year |
| `status` | string | done/empty/failed |
| `rows` | int | Số dòng |
| `start_period` | string | Kỳ đầu tiên |
| `end_period` | string | Kỳ cuối cùng |
| `source` | string | VCI/KBS |
| `updated` | string | Thời điểm |

---

## 4. Parquet Files (Root)

### `ohlcv_flat.parquet` (~23 MB)
- Schema giống `ohlcv_flat.csv` — nén ~5x

### `financial_snapshot.parquet` (~2 MB)
- Schema giống `financial_snapshot.csv`
