# VNSTOCK — Schema Summary

> Quét ngày: 2026-07-13 | Phase 1 — Project Discovery

---

## 1. SQLite `vn_stock.db` — Table Schemas

### 1.1 Table `ohlcv`
```sql
CREATE TABLE ohlcv(
    ticker TEXT,
    date TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    source TEXT,
    PRIMARY KEY(ticker, date)
);
CREATE INDEX idx_date ON ohlcv(date);
```
- **~1.909.419 rows** | ~1.686 tickers | 2015–2026

### 1.2 Table `meta`
```sql
CREATE TABLE meta(
    ticker TEXT PRIMARY KEY,
    status TEXT,    -- done | empty | failed
    rows INTEGER,
    updated TEXT
);
```
- Tiến độ backfill giá. ⚠️ ĐỪNG nhầm với bảng `metadata`.

### 1.3 Table `metadata`
```sql
CREATE TABLE metadata(
    ticker TEXT PRIMARY KEY,
    exchange TEXT,           -- HSX | HNX | UPCOM | DELISTED
    industry TEXT,           -- ICB cấp 2 (~19 nhóm tiếng Việt)
    foreign_room_pct REAL,   -- % room ngoại CÒN TRỐNG (100 = chưa ai mua)
    pe REAL,                 -- P/E quý mới nhất
    pb REAL,                 -- P/B quý mới nhất
    roe REAL,                -- ROE trailing 4 quý, đơn vị %
    market_cap REAL,         -- Vốn hóa (đồng VND)
    shares_outstanding REAL, -- Số CP lưu hành
    free_float_est REAL,     -- Proxy free-float 0..1
    dividend_yield REAL,     -- Tỷ suất cổ tức %. Sentinel: -1 = "không có số"
    margin_status TEXT,      -- margin_cut | warning | control | suspend | NULL
    updated TEXT             -- mốc resume per-ticker
);
```

### 1.4 Table `macro`
```sql
CREATE TABLE IF NOT EXISTS macro(
    series TEXT,
    date TEXT,
    value REAL,
    PRIMARY KEY(series, date)
);
```
- 17 chuỗi: us_fedfunds, us_10y, us_cpi, dxy, wti, sp500, nasdaq, vix, nikkei, hsi, gold_world, brent, usdvnd_mkt, usdvnd_vcb, gold_sjc, vn_cpi_yoy, vn_gdp_yoy

### 1.5 Table `news`
```sql
CREATE TABLE IF NOT EXISTS news(
    link TEXT PRIMARY KEY,
    region TEXT,          -- world | vn
    source TEXT,
    title TEXT,
    summary TEXT,
    published_utc TEXT,
    fetched TEXT
);
```

### 1.6 Table `shareholders`
```sql
CREATE TABLE IF NOT EXISTS shareholders(
    ticker TEXT,
    shareholder_name TEXT,
    shares_owned REAL,
    pct REAL,                -- % (0..100), -1 = không có số
    shareholder_type TEXT,    -- LUÔN NULL (nguồn không phân loại)
    source TEXT,
    updated_at TEXT,
    PRIMARY KEY(ticker, shareholder_name)
);
```

### 1.7 Table `shareholders_progress`
```sql
CREATE TABLE IF NOT EXISTS shareholders_progress(
    ticker TEXT PRIMARY KEY,
    status TEXT,    -- done | empty | failed
    rows INTEGER,
    updated TEXT
);
```

---

## 2. CSV Schemas

### 2.1 `screen_snapshot.csv` (31 columns)
```
ticker, date, close, chg_today_pct, gtgd20_ty, rel_vol, rsi14,
macd_hist, bb_pctb, atr_pct, above_sma50, above_sma200, golden_cross,
pct_from_52w_high, near_52w_high, pct_above_52w_low,
ret_1m, ret_3m, ret_6m, ret_12m,
structure, dist_swing_low_pct, rs_rating,
exchange, industry, foreign_room_pct, pe, pb, roe, free_float_est,
margin_status
```

**Đặc biệt:**
- Cột boolean lưu dạng text: `"True"/"False"`
- `structure`: `"up"/"side"/"down"` (lowercase)
- `margin_status`: NULL = sạch (không hiện gì trong CSV)
- Chứa cả mã đã chết (VD: ASA phiên 2022-01-21) → scan live phải lọc `date = max(date)`

### 2.2 `market_breadth.csv` (8 columns)
```
group, date, n_symbols, n_up, n_down, n_flat,
pct_above_ma200, avg_rs_rating, avg_ret_1m
```
- Dòng `ALL` = toàn thị trường, còn lại = 19 ngành ICB

### 2.3 `macro_snapshot.csv` (9 columns)
```
series, name, unit, freq, date, value, chg_prev, chg_1m, chg_1y
```
- `chg_*`: đơn vị %% là hiệu số điểm %%, còn lại là %% thay đổi

### 2.4 `news_latest.csv` (5 columns)
```
published_utc, region, source, title, link
```

### 2.5 `ta_signals.csv` (13 columns)
```
ticker, date, close, volume, patterns, smc, confluence,
direction, industry, rs_rating, rel_vol, gtgd20_ty, margin_status
```
- `patterns`: `;` separated (VD: `bullish_engulfing`)
- `smc`: `;` separated (VD: `fvg_bull;fvg_bear;ob_bear`)
- `confluence`: `True/False`
- `direction`: `bullish/bearish/neutral`

### 2.6 `blacklist.csv` (4 columns)
```
ticker, status, note, updated
```
- `status`: margin_cut | warning | control | suspend
- `note`: bắt đầu "Auto:" = máy tự sinh; khác = nhập tay (thắng khi trùng)

### 2.7 `ohlcv_flat.csv` (8 columns)
```
ticker, date, open, high, low, close, volume, source
```

### 2.8 `financial_snapshot.csv` (~40 columns)
```
ticker, period, period_type,
revenue, net_profit, gross_profit, operating_profit,
total_assets, total_liabilities, equity, cash, inventory, receivables,
current_assets, current_liabilities, cost_of_goods_sold,
operating_cash_flow, debt, shares_outstanding, book_value, eps_calc,
capex, free_cash_flow,
revenue_growth_yoy, revenue_growth_qoq, profit_growth_yoy, profit_growth_qoq,
gross_margin, operating_margin, net_margin, roe, roa,
debt_to_equity, debt_ratio, current_ratio, quick_ratio, cash_ratio,
asset_turnover, inventory_turnover, receivable_turnover,
operating_cash_flow_ratio
```

---

## 3. BCTC Raw Schema (data_bctc/*.csv)

```
ticker, report_type, source, scraped_at, item, item_en, item_id,
{period_columns...}  -- VD: 2026-Q1, 2025-Q4, 2025-Q3, ..., 2024-Q2
```

**3 report_type:**
- `balance_sheet` — Bảng cân đối kế toán
- `income_statement` — Kết quả kinh doanh
- `cash_flow` — Lưu chuyển tiền tệ

**item_id** (chuẩn hóa bởi bctc_processor.py): `current_assets`, `cash_and_cash_equivalents`, `total_assets`, `equity`, `revenue`, `cogs`, `gross_profit`, `net_profit`, ...

---

## 4. JSON Schemas

### 4.1 `ai_report_*.json` (structured output từ Claude API)
```json
{
  "market_regime": "risk_on|neutral|risk_off",
  "regime_reason": "string",
  "macro_summary": "string",
  "news_themes": [
    { "theme": "string", "impact_vn": "positive|negative|mixed|neutral", "note": "string" }
  ],
  "sector_view": "string",
  "stock_notes": [
    {
      "ticker": "string",
      "stance": "mua_tham_do|cho_setup|theo_doi|tranh",
      "entry_logic": "string",
      "risk_flags": ["string"]
    }
  ],
  "portfolio_risk": "low|medium|high",
  "action_plan": ["string"]
}
```

### 4.2 `analysis_latest.json` (stock_analyzer output)
```json
{
  "summary": {...},
  "market": {...},
  "top_stocks": [...],
  "scores": {...},
  "strategies": {...},
  "risks": {...},
  "portfolio": {...}
}
```

### 4.3 `data/candle_signals.json`
```json
[
  {
    "ticker": "string", "date": "string", "close": number,
    "patterns": "string", "smc": "string", "confluence": boolean,
    "direction": "string", "industry": "string",
    "rs_rating": number, "rel_vol": number, "gtgd20_ty": number
  }
]
```

### 4.4 `data/sector_heatmap.json`
```json
[
  {
    "group": "string", "n_symbols": number,
    "n_up": number, "n_down": number, "n_flat": number,
    "pct_above_ma200": number, "avg_rs_rating": number
  }
]
```

---

## 5. Sentinel Values & Conventions

| Giá trị | Ý nghĩa | Cột áp dụng |
|---|---|---|
| `NULL` (trong DB) | Chưa từng cào/không có dữ liệu | `dividend_yield`, `margin_status`, `shareholder_type` |
| `-1` (số) | Đã hỏi nguồn nhưng không có số | `dividend_yield`, `pct` (shareholders) |
| `"True"/"False"` (text) | Boolean lưu dạng text | `above_sma50`, `above_sma200`, `golden_cross`, `near_52w_high` |
| `"done"/"empty"/"failed"` | Trạng thái resume | `meta.status`, `shareholders_progress.status`, `scrape_meta.status` |
| `"VCI"/"KBS"` | Nguồn dữ liệu (API provider) | `source` trong nhiều bảng |
| `"HSX"/"HNX"/"UPCOM"/"DELISTED"` | Sàn giao dịch | `exchange` |
| `"up"/"side"/"down"` | Cấu trúc thị trường SMC | `structure` |
| `"risk_on"/"neutral"/"risk_off"` | Market regime | AI report |
| `"mua_tham_do"/"cho_setup"/"theo_doi"/"tranh"` | Stance LLM | AI report |
