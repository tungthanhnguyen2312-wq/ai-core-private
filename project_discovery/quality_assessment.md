# VNSTOCK — Quality Assessment

> Quét ngày: 2026-07-13 | Phase 1 — Project Discovery

---

## 1. Code Quality

### 1.1 Strengths (Điểm mạnh)

| Tiêu chí | Đánh giá | Ghi chú |
|---|---|---|
| **Documentation** | ⭐⭐⭐⭐⭐ | Cực kỳ chi tiết, mỗi module có header comment dài giải thích BẪY, quy ước, lý do. 10 file docs/ riêng biệt. |
| **Error Handling** | ⭐⭐⭐⭐ | Mọi module đều try/except, 1 mã lỗi không crash cả pipeline. RetryError bóc đúng. |
| **Resume / Idempotent** | ⭐⭐⭐⭐⭐ | Mọi crawler hỗ trợ resume: bảng progress, `--resume`, `--refresh`. Chạy lại bao nhiêu lần cũng an toàn. |
| **Safety** | ⭐⭐⭐⭐⭐ | 2 lớp phòng thủ publish: whitelist auto-extract + gitignore. Không bao giờ `git add .` hay `push -f`. Dry-run mặc định. |
| **Testing** | ⭐⭐⭐ | 17 fixture mã bịa cho stock_analyzer (3 "bẫy"). Chưa có test cho các crawler. |
| **Consistency** | ⭐⭐⭐⭐ | Cùng pattern call_api/retry/backoff/resume xuyên suốt. UTF-8 fix ở đầu mỗi file. |
| **Separation of Concerns** | ⭐⭐⭐⭐ | Mỗi module 1 nhiệm vụ rõ ràng. DB ghi/đọc phân tách tốt. LLM chỉ làm phần xác suất. |

### 1.2 Weaknesses (Điểm yếu)

| Tiêu chí | Đánh giá | Ghi chú |
|---|---|---|
| **Code Duplication** | ⚠️ Trung bình | `call_api()` copy-paste qua 5 module (chỉ khác hằng số). Nên extract thành shared util. |
| **Constants Management** | ⚠️ Trung bình | `DB_PATH`, `INDEX_SYMBOLS`, `MAX_RETRY` khai báo riêng trong mỗi module. blacklist_sync.py import từ meta_sync.py là ngoại lệ. |
| **Type Safety** | ⚠️ Thấp | Không có type hints (trừ vài chỗ rải rác). Không dùng dataclass/Pydantic. |
| **Test Coverage** | ⚠️ Thấp | Chỉ có test cho stock_analyzer. Không test cho crawler, processor, hay indicator. |
| **Config Management** | ⚠️ Cơ bản | `config.json` chỉ cho BCTC (4 mã demo). Phần lớn config hardcode trong source. |
| **Logging** | ⚠️ Tự viết | Mỗi module tự viết `log()` function (print + append file). Không dùng Python `logging` module. |
| **No CI/CD** | ⚠️ | Không có GitHub Actions, pre-commit, linting tự động. |

---

## 2. Data Quality

### 2.1 Completeness (Tính đầy đủ)

| Dataset | Completeness | Ghi chú |
|---|---|---|
| OHLCV (giá) | ⭐⭐⭐⭐⭐ | 1.909.419 dòng, ~1.686 mã, 2015→2026. Hệ thống backfill đầy đủ. |
| Metadata | ⭐⭐⭐⭐ | PE/PB/ROE/room ngoại/market_cap đầy đủ. Thiếu ROA, D/E (dùng proxy). |
| Macro | ⭐⭐⭐⭐ | 17 chuỗi vĩ mô quốc tế + VN. Đầy đủ cho phân tích cơ bản. |
| News | ⭐⭐⭐ | 8 feed RSS (4 world + 4 VN). Đủ breadth nhưng thiếu chiều sâu (chỉ tiêu đề + summary). |
| BCTC | ⭐⭐⭐⭐ | 1.494 mã × 3 báo cáo × 8 quý. Chuẩn hóa item_id tốt. |
| Cổ đông | ⭐⭐⭐ | Snapshot point-in-time, không có lịch sử. VCI đầy đủ hơn KBS. |
| Chỉ báo kỹ thuật | ⭐⭐⭐⭐⭐ | 30+ chỉ báo tự viết + 31 cột snapshot. Phong phú. |

### 2.2 Accuracy (Tính chính xác)

| Rủi ro | Mức độ | Mô tả |
|---|---|---|
| **Giá chưa điều chỉnh** | ⚠️ Trung bình | Code ghi chú: "nếu nguồn trả giá THÔ, ret_12m & MA200 sẽ gãy tại ngày chia" — chưa xác nhận 100% VCI đã adjust. |
| **BẪY ĐƠN VỊ BCTC** | ✅ Đã xử lý | VCI trả pct dạng 0..1 vs KBS dạng 0..100 — đã normalize trong `shareholders_sync.py` & `bctc_processor.py`. |
| **Mã chết trong snapshot** | ⚠️ Đã biết | ASA (DELISTED 2022) vẫn nằm trong screen_snapshot.csv — mọi scan phải lọc `date = max(date)`. |
| **free_float_est** | ⚠️ Proxy | Ước tính từ shareholders top, không phải con số chính thức. |
| **dividend_yield sentinel** | ✅ Quy ước rõ | -1 = "đã hỏi, không có số". NULL = "chưa cào". |

### 2.3 Consistency (Tính nhất quán)

| Kiểm tra | Kết quả | Ghi chú |
|---|---|---|
| Tên bảng `meta` vs `metadata` | ⚠️ Confusing | `meta` = tiến độ backfill giá; `metadata` = PE/PB/ROE. README cảnh báo mục 4.2. |
| Sentinel values | ✅ Nhất quán | -1 cho "không có số", NULL cho "chưa cào". Áp dụng đúng qua dividend_yield + shareholders.pct. |
| Boolean storage | ⚠️ Text | screen_snapshot lưu "True"/"False" dạng text (không phải bool). |
| Date format | ✅ Nhất quán | ISO 8601 YYYY-MM-DD cho mọi date. |
| Encoding | ⚠️ cp1252 → UTF-8 | Windows console cp1252. Mọi file ghi UTF-8 nhưng CSV đọc trong Excel có thể lỗi tiếng Việt. |

### 2.4 Freshness (Tính cập nhật)

| Dataset | Phiên mới nhất (observed) | Tần suất |
|---|---|---|
| OHLCV | 2026-07-10 | Hằng ngày (15h15) |
| Metadata | Per-ticker resume | Hằng quý (batch nặng) |
| Macro | 2026-07-12 | Hằng ngày |
| News | 2026-07-12 | Nhiều lần/ngày |
| BCTC | 2026-Q1 | Hằng quý |
| Blacklist | 2026-07-12 | Khi chạy |
| Snapshot | 2026-07-10 | Hằng ngày (sau pipeline) |

---

## 3. Architecture Quality

### 3.1 Strengths

| Tiêu chí | Đánh giá |
|---|---|
| **Loose coupling** | Mỗi module chạy độc lập, giao tiếp qua DB/file. Không cần import chain dài. |
| **Clear data tiers** | 4 tầng rõ ràng: Kho (DB) → Truyền tải (CSV/Parquet) → Báo cáo (AI/Quant) → Web. |
| **Dual-format safety** | data/*.json (fetch) + data/*.js (file:// fallback) — GitHub Pages chạy đúng cả 2 context. |
| **Whitelist publish** | Tự bóc whitelist từ HTML, không hardcode danh sách file — thêm trang mới tự có. |

### 3.2 Concerns

| Tiêu chí | Mức độ | Ghi chú |
|---|---|---|
| **Single DB** | ⚠️ | vn_stock.db chứa MỌI THỨ (giá + meta + macro + news + cổ đông) — 168 MB, WAL contention nếu chạy song song. |
| **No ORM** | ℹ️ | Dùng raw SQL string. Đơn giản nhưng dễ typo, khó refactor schema. |
| **Flat file structure** | ℹ️ | 69 file ở root (13 .py + 9 .csv + 15 .html + ...) — có thể tổ chức vào src/. |
| **Shared nothing between modules** | ⚠️ | Mỗi module tự khai báo hằng số. Chỉ 1 ngoại lệ: blacklist_sync import từ meta_sync. |
| **No virtual environment** | ⚠️ | requirements.txt có nhưng không có venv/conda config. |
| **OneDrive workspace** | ⚠️ | Thư mục nằm trong OneDrive → index.lock conflicts, file sync issues. publish_dashboard.py đã handle. |

---

## 4. Security Assessment

| Tiêu chí | Đánh giá |
|---|---|
| **API keys** | ✅ ANTHROPIC_API_KEY qua env var, không hardcode. |
| **gitignore** | ✅ 2 lớp phòng thủ: .gitignore + whitelist publish. vn_stock.db, *.py, *.parquet KHÔNG bao giờ lên remote. |
| **HTML escape** | ✅ Docs yêu cầu escape HTML mọi dữ liệu động trước khi chèn DOM (chống XSS). |
| **No push -f** | ✅ Cấm force push, cấm git add . |
| **Tickers/data local** | ✅ Dữ liệu nhạy cảm (danh mục, ghi chú cá nhân) giữ local. |

---

## 5. Maintainability Score

| Khía cạnh | Score | Ghi chú |
|---|---|---|
| Readability | 9/10 | Comment tiếng Việt rất chi tiết, giải thích WHY không chỉ WHAT |
| Modularity | 7/10 | Mỗi module rõ nhiệm vụ, nhưng thiếu shared utils |
| Testability | 5/10 | Chỉ stock_analyzer có test; các module khác khó test do phụ thuộc DB/API |
| Extensibility | 7/10 | Thêm chân kiềng mới dễ (copy pattern), nhưng phải copy-paste khá nhiều |
| Operability | 8/10 | Resume, dry-run, --status, logging đầy đủ. Pipeline tay (chưa có orchestrator). |
