# VNSTOCK — Discovery Summary

> Quét ngày: 2026-07-13 | Phase 1 — Project Discovery (READ ONLY)

---

## Tổng quan dự án

**VNSTOCK** là hệ thống pipeline **end-to-end** cho phân tích thị trường chứng khoán Việt Nam, bao gồm:
1. **Crawl** dữ liệu từ API (vnstock, FRED, Yahoo, RSS, VCB, SJC)
2. **Store** vào SQLite + Parquet/CSV
3. **Process** (chỉ báo kỹ thuật, mẫu nến SMC, BCTC, blacklist)
4. **Analyze** (quant engine 10 chiến lược + AI Claude)
5. **Publish** lên GitHub Pages (dashboard tĩnh, dark mode)

---

## Quy mô

| Chỉ số | Giá trị |
|---|---|
| Python modules | 13 scripts + 1 test |
| SQLite database | 168 MB, 6 bảng chính |
| Dòng giá OHLCV | 1.909.419 |
| Mã chứng khoán | ~1.686 (3 sàn: HSX, HNX, UPCOM) |
| BCTC files | 8.391 (1.494 mã × 3 loại × CSV+Parquet) |
| Chỉ báo kỹ thuật | 30+ (RSI, MACD, Ichimoku, ZigZag, SMC, FVG, OB, BOS, CHoCH...) |
| Chiến lược quant | 10 (value, canslim, momentum, ftse, fscore, smc, breakout, turnaround, rs, sector) |
| Frontend pages | 8 trang HTML |
| Documentation | 10 file trong docs/ + README + CHANGELOG |
| Tổng dung lượng | ~310 MB |

---

## Kiến trúc 2 nửa

### Backend (LOCAL — không lên GitHub)

```
7 chân kiềng + 1 nhánh BCTC:
├── 1. Giá OHLCV (vn_stock_pipeline.py) — hằng ngày
├── 2. Metadata (meta_sync.py + blacklist_sync.py) — hằng quý
├── 3. Chỉ báo + Snapshot (vn_indicators.py + candle_scan.py) — hằng ngày
├── 4. Vĩ mô (macro_sync.py) — hằng ngày
├── 5. Tin tức (news_sync.py) — nhiều lần/ngày
├── 6. Cổ đông (shareholders_sync.py) — hằng tháng
├── 7. Báo cáo AI (ai_analyzer.py) — TỐN PHÍ Claude API
└── BCTC (bctc_sync.py + bctc_processor.py) — hằng quý
```

### Frontend (GitHub Pages — dashboard tĩnh)

```
├── dashboard.html — trang chính: AI report + KPI + watchlist
├── screener.html — bảng lọc CANSLIM/SMC
├── signals.html — tín hiệu nến/SMC phiên
├── analysis.html — quant engine offline
├── macro.html — vĩ mô (sắp ra mắt)
└── ...
```

CDN: Bootstrap 5, jQuery, DataTables, PapaParse, marked.js, Chart.js

---

## Patterns đáng chú ý

### 1. Dual Source Failover (VCI → KBS)
Mọi crawler đều thử nguồn PRIMARY (VCI) trước, fallback sang FAILOVER (KBS) khi lỗi.

### 2. Resume Pattern
Mọi crawler lưu trạng thái `done/empty/failed` per-ticker. Chạy lại = resume từ chỗ dừng.

### 3. Safety Layers
- `publish_dashboard.py`: whitelist tự bóc từ HTML, dry-run mặc định
- `.gitignore`: chặn DB/Parquet/Python/blacklist lên remote
- Không bao giờ `git add .` hay `push -f`

### 4. CANSLIM + SMC
Kết hợp phong cách:
- **CANSLIM** (William O'Neil): RS rating, thanh khoản, trend, growth
- **SMC** (Smart Money Concepts): BOS, CHoCH, FVG, OB, market structure

### 5. Phân công Python vs LLM
- **Python**: phép tính TẤT ĐỊNH (chỉ báo, RS, swing, lọc top N, breadth)
- **LLM**: phần XÁC SUẤT (đọc tin, liên kết macro, nhận định regime, viết kế hoạch)
- **Validate ngược**: mã LLM nhắc phải nằm trong danh sách Python gửi đi

---

## Bẫy dữ liệu cần nhớ

| # | Bẫy | Cách xử lý đã có |
|---|---|---|
| 1 | Bảng `meta` ≠ `metadata` | Tên khác nhau, docs cảnh báo mục 4.2 |
| 2 | `dividend_yield = -1` = "đã hỏi, không có số" | Sentinel quy ước, cần coi như NaN |
| 3 | Boolean lưu dạng text `"True"/"False"` | Không dùng Python bool trực tiếp |
| 4 | Mã chết (ASA) vẫn trong snapshot | Phải lọc `date = max(date)` |
| 5 | VCI vs KBS trả đơn vị % khác nhau | Normalize trong code |
| 6 | Cổ đông = snapshot, KHÔNG có lịch sử | Đừng backtest |
| 7 | `free_float_est` = proxy, không chính thức | Tính từ top shareholders |
| 8 | Giá có thể chưa điều chỉnh cổ tức/chia tách | Cảnh báo trong vn_indicators.py |

---

## Deliverables đã tạo

| File | Nội dung |
|---|---|
| `project_tree.md` | Cây thư mục đầy đủ + thống kê |
| `file_inventory.md` | Danh sách file chi tiết theo nhóm |
| `dataset_inventory.md` | Schema tất cả dataset (DB + CSV + Parquet + JSON) |
| `python_modules.md` | Phân loại module + dependency graph + execution order |
| `data_relationship.md` | Luồng dữ liệu + ERD logic + khóa liên kết |
| `schema_summary.md` | SQL DDL + CSV schema + JSON schema + sentinel values |
| `quality_assessment.md` | Đánh giá code quality, data quality, architecture, security |
| `discovery_summary.md` | Tài liệu tổng hợp này |

---

## Gợi ý cho Phase tiếp theo (AI Knowledge)

### Dữ liệu sẵn sàng cho AI ingestion
1. **screen_snapshot.csv** — 31 cột, ~1.500 mã, trọng tâm phân tích
2. **market_breadth.csv** — 20 dòng breadth ngành
3. **macro_snapshot.csv** — 17 chuỗi vĩ mô
4. **financial_snapshot.csv** — ~40 cột ratio BCTC
5. **ta_signals.csv** — tín hiệu nến/SMC + confluence
6. **news_latest.csv** — 100 tin mới nhất
7. **analysis_latest.json** — output quant engine 10 chiến lược
8. **ai_report_latest.json** — báo cáo AI chiến lược

### Cần giải quyết
1. **Encoding**: CSV đọc bằng tool khác cần force UTF-8 (tiếng Việt trong industry/news)
2. **Boolean normalization**: `"True"/"False"` → bool thật
3. **Sentinel handling**: -1 → NaN cho dividend_yield, pct
4. **Dead ticker filter**: lọc theo date mới nhất
5. **BCTC pivot**: data_bctc lưu dạng long (item_id × period columns) → cần pivot nếu AI cần wide format

### Khối lượng token ước tính (nếu gửi cho LLM)
| File | Ước tính token |
|---|---|
| screen_snapshot.csv (full) | ~50-80K token → TỐI ĐA top N |
| financial_snapshot.csv (full) | ~100K+ token → cần filter |
| market_breadth.csv | ~500 token ✅ |
| macro_snapshot.csv | ~600 token ✅ |
| ta_signals.csv | ~10-15K token |
| news_latest.csv | ~3-5K token |

Cách tiếp cận của `ai_analyzer.py` hiện tại (~6-9K token payload) là mẫu tốt: lọc top N + chỉ tiêu đề tin, không gửi dữ liệu thô.
