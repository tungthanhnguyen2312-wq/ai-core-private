# Data Dictionary

## Nguyên tắc chung

Grain mô tả một dòng đại diện cho điều gì. Mọi phép join hoặc so sánh chỉ hợp lệ khi grain, khóa thời gian và đơn vị tương thích. `ticker` là khóa trung tâm, nhưng SQLite không enforce foreign key.

## 1. OHLCV / Price

- **Dataset:** `vn_stock.db::ohlcv`, `ohlcv_flat.csv`, `ohlcv_flat.parquet`.
- **Mục đích:** lịch sử giá và khối lượng.
- **Grain:** một ticker trên một ngày giao dịch.
- **Khóa:** `(ticker, date)`.
- **Time field:** `date`, chuẩn `YYYY-MM-DD`.
- **Ticker field:** `ticker`.
- **Fields:** `open`, `high`, `low`, `close` là giá VND đã được pipeline scale ×1000; `volume` là số cổ phiếu; `source` là VCI/KBS.
- **Missing:** NULL là thiếu; không tự thay bằng 0.
- **Hạn chế:** giá có thể chưa fully adjusted; CSV đầy đủ rất lớn, cần query/filter.

## 2. Company Metadata

- **Dataset:** `vn_stock.db::metadata`; các field được join vào `screen_snapshot.csv`.
- **Mục đích:** security master và fundamental snapshot hiện tại.
- **Grain:** một dòng hiện tại trên ticker.
- **Khóa:** `ticker`; **time field:** `updated`.
- **Fields:** `exchange`, `industry`, `foreign_room_pct`, `pe`, `pb`, `roe`, `market_cap`, `shares_outstanding`, `free_float_est`, `dividend_yield`, `margin_status`.
- **Meaning:** `foreign_room_pct` là phần trăm room còn trống; `roe` là trailing bốn quý; `free_float_est` là ước tính 0..1.
- **Missing:** `dividend_yield=-1` nghĩa là đã hỏi nhưng không có số; NULL tùy field; `margin_status` rỗng/NULL là không bị gắn cờ theo quy ước hiện hành.
- **Hạn chế:** point-in-time, không dùng backtest lịch sử.

> `vn_stock.db::meta` hoàn toàn khác: đây chỉ là tiến độ backfill giá gồm `status`, `rows`, `updated`.

## 3. Financial Statements Raw

- **Dataset:** `data_bctc/*.{csv,parquet}`.
- **Mục đích:** dữ liệu BCTC nguồn đã lưu theo file/ticker/report.
- **Grain:** một dòng chỉ tiêu (`item_id`) trong một file ticker/report; kỳ báo cáo nằm ở các cột.
- **Khóa logic:** `ticker`, `report_type`, `item_id`; tên file còn có `period_type`.
- **Time:** các cột như `2026-Q1`, `2025-Q4`; `scraped_at` là thời điểm thu thập.
- **Report types:** `balance_sheet`, `income_statement`, `cash_flow`.
- **Fields:** `ticker`, `report_type`, `source`, `scraped_at`, `item`, `item_en`, `item_id`, các cột kỳ.
- **Missing:** ô trống/NULL là thiếu; không suy ra 0.
- **Hạn chế:** khoảng 8.391 file, không nên bulk-load vào LLM; scale chi tiết từng chỉ tiêu là **not fully confirmed from current metadata**.

## 4. Financial Snapshot

- **Dataset:** `financial_snapshot.csv/.parquet`.
- **Mục đích:** BCTC chuẩn hóa và tỷ số dẫn xuất.
- **Grain:** một ticker trên một kỳ báo cáo.
- **Khóa:** `(ticker, period)`; `period_type` là `quarter` hoặc `year`.
- **Fields chính:** doanh thu/lợi nhuận; tài sản/nợ/vốn; tiền, tồn kho, phải thu; OCF, capex, FCF; cổ phiếu, BVPS/EPS proxy; tăng trưởng, margin, ROE/ROA, đòn bẩy, thanh khoản và turnover.
- **Missing:** empty/NULL là thiếu; tỷ số thiếu đầu vào cũng phải để missing.
- **Hạn chế:** một số chỉ tiêu là proxy hoặc coalesce theo ngành; không đồng nhất grain với raw BCTC.

## 5. Macro

- **Dataset:** `vn_stock.db::macro`, `macro_snapshot.csv`.
- **Mục đích:** bối cảnh lãi suất, CPI, tỷ giá, hàng hóa và chỉ số quốc tế/VN.
- **Grain:** DB là một series/ngày; snapshot là quan sát mới nhất trên series.
- **Khóa:** `(series, date)` trong DB; `series` trong snapshot.
- **Fields:** `value`, `unit`, `freq`, `chg_prev`, `chg_1m`, `chg_1y`.
- **Missing:** NULL/empty là thiếu.
- **Hạn chế:** chuỗi có tần suất khác nhau; với series phần trăm, `chg_*` là chênh lệch điểm phần trăm, còn lại là phần trăm thay đổi.

## 6. News

- **Dataset:** `vn_stock.db::news`, `news_latest.csv`.
- **Mục đích:** context tin tài chính thế giới và Việt Nam.
- **Grain:** một bài viết theo URL duy nhất.
- **Khóa:** `link`; **time:** `published_utc`; không có ticker field.
- **Fields:** `region`, `source`, `title`; DB có thêm `summary`, `fetched`.
- **Missing:** không có summary không đồng nghĩa tin không quan trọng.
- **Hạn chế:** không có entity mapping chuẩn và nội dung chỉ ở mức tiêu đề/summary ngắn.

## 7. Shareholder

- **Dataset:** `vn_stock.db::shareholders`, `shareholders_progress`.
- **Mục đích:** cơ cấu cổ đông lớn hiện tại và trạng thái thu thập.
- **Grain:** một ticker/cổ đông.
- **Khóa:** `(ticker, shareholder_name)`; **time:** `updated_at`.
- **Fields:** `shares_owned`, `pct`, `shareholder_type`, `source`.
- **Missing:** `pct=-1` là đã hỏi nhưng không có số; `shareholder_type` thường NULL. Thiếu dòng không chứng minh không có cổ đông; cần kiểm tra progress.
- **Hạn chế:** không có lịch sử.

## 8. Technical Snapshot and Signals

- **Dataset:** `screen_snapshot.csv`, `market_breadth.csv`, `ta_signals.csv`.
- **Mục đích:** chỉ báo, thanh khoản, RS, cấu trúc, breadth, mẫu nến và SMC.
- **Grain:** ticker/ngày snapshot; breadth là group/ngày.
- **Khóa:** `(ticker,date)` hoặc `(group,date)`.
- **Fields:** RSI, MACD histogram, Bollinger %B, ATR%, SMA flags, return, structure, RS; signals có `patterns`, `smc`, `confluence`, `direction`.
- **Missing:** boolean là chuỗi `True`/`False`; empty signal có thể nghĩa không phát hiện mẫu; `margin_status` empty là sạch.
- **Hạn chế:** snapshot có thể chứa mã chết/ngày cũ; phải lọc ngày mới nhất.

## 9. Quant / AI Outputs

- **Dataset:** `analysis_latest.json/.md`, `Market_Scan.*`, `Focus_Analysis.md`, `ai_report_latest.*`.
- **Mục đích:** kết quả Quant 10 chiến lược và nhận định AI.
- **Grain:** tài liệu phân tích dẫn xuất, có cấu trúc nested.
- **Ticker/time:** tùy output; cần đọc timestamp/kỳ bên trong nếu có.
- **Missing:** không tự suy ra field nested ngoài schema registry; chi tiết đầy đủ là **not fully confirmed from current metadata**.
- **Hạn chế:** không phải ground truth; AI report là xác suất.

## 10. Dashboard / Frontend Outputs

- **Dataset:** HTML/JS/CSS và `data/*.json/.js`.
- **Mục đích:** hiển thị GitHub Pages và fallback `file://`.
- **Grain:** presentation artifacts; JSON/JS là bản xuất từ snapshot.
- **Hạn chế:** có thể trùng dữ liệu nguồn, bị stale hoặc mất kiểu dữ liệu qua serialization. Không dùng frontend làm nguồn ưu tiên khi CSV/DB tương ứng có sẵn.

## Sentinel và Missing Rules

| Giá trị | Cách hiểu |
|---|---|
| `-1` | Đã truy vấn nguồn nhưng không có số; chuyển thành missing cho phân tích. |
| `NULL` | Nghĩa theo ngữ cảnh: chưa thu thập, không có dữ liệu hoặc trạng thái sạch ở field cụ thể. |
| Empty string | Thường là missing; riêng `margin_status` nghĩa là sạch, còn signal list có thể nghĩa không có tín hiệu. |
| `"True"` / `"False"` | Chuỗi boolean; phải parse chính xác, không dùng truthiness của chuỗi. |

## Known Limitations

- Coverage khác nhau giữa price, metadata, snapshot và BCTC.
- Unit BCTC chi tiết chưa được xác nhận đầy đủ từ metadata hiện tại.
- Không có lịch sử dimension cho metadata/cổ đông.
- Không có canonical ticker mapping cho news.

## How AI Should Use This

Trước khi trả lời, AI phải xác định dataset, grain, ngày/kỳ, unit và missing rule. Khi cần một field chưa có trong tài liệu, ghi **not fully confirmed from current metadata** và không tự tạo định nghĩa.
