# AI Context for VNSTOCK Metadata

## Mục đích

Thư mục `metadata/` mô tả dữ liệu VNSTOCK theo dạng machine-readable để Claude, ChatGPT hoặc Codex có thể chọn đúng nguồn, hiểu đúng grain và tránh diễn giải sai sentinel. Metadata không chứa phân tích thị trường mới và không thay thế dữ liệu nguồn. (Gemini deprecated khỏi luồng khuyến nghị từ 2026-07-17.)

## Chọn dữ liệu khi phân tích một ticker

1. Xác nhận ticker và tính hiện hành bằng `screen_snapshot.csv`: chỉ dùng dòng có `date` bằng ngày snapshot thị trường mới nhất. Kiểm tra `exchange` và `margin_status`.
2. Dùng `ohlcv` hoặc phần đã lọc từ `ohlcv_flat.parquet` cho lịch sử giá, khối lượng và kiểm chứng xu hướng. Không nạp toàn bộ lịch sử vào LLM.
3. Dùng `screen_snapshot.csv` cho chỉ báo, thanh khoản, RS, cấu trúc và metadata hiện tại.
4. Dùng `ta_signals.csv` cho mẫu nến/SMC của phiên; tách `patterns` và `smc` theo dấu chấm phẩy.
5. Dùng `financial_snapshot.csv` hoặc Parquet, lọc đúng ticker và các kỳ cần thiết, để phân tích BCTC và tỷ số. Chỉ đọc `data_bctc/` khi cần đối chiếu một chỉ tiêu raw cụ thể.
6. Dùng `shareholders` nếu cần cơ cấu cổ đông hiện tại, nhưng phải ghi rõ đây là snapshot không có lịch sử.
7. Dùng `market_breadth.csv` cho bối cảnh toàn thị trường/ngành và `macro_snapshot.csv` cho vĩ mô.
8. Dùng `news_latest.csv` cho chủ đề tin mới. Không tự gán tin cho ticker nếu chưa có bước entity linking đáng tin cậy.
9. Có thể đọc `analysis_latest.json` và `ai_report_latest.json` như output dẫn xuất, nhưng phải kiểm chứng kết luận quan trọng bằng dữ liệu nguồn.

## Thứ tự đọc metadata

Đọc `data_quality_rules.json` trước, sau đó `datasets.json`, `schema_registry.json`, `relationship_graph.json` và registry chuyên biệt tương ứng. `ticker_registry.json` chỉ là summary availability, không phải danh sách ticker đầy đủ.

## Những lỗi AI không được mắc

- Không nhầm bảng `meta` với `metadata`.
- Không coi `-1` là giá trị kinh tế thật; đó là đã hỏi nguồn nhưng không có số.
- Không áp dụng một nghĩa duy nhất cho mọi `NULL`; phải đọc `missing_rule` theo field.
- Không coi chuỗi `"False"` là true chỉ vì chuỗi không rỗng.
- Không coi `margin_status` rỗng là một cảnh báo.
- Không đưa mã có ngày cũ vào phân tích live.
- Không trình bày `free_float_est` như số chính thức.
- Không dùng snapshot cổ đông hoặc metadata hiện tại để backtest lịch sử.
- Không giả định giá đã fully adjusted khi chưa xác minh.
- Không trộn phần trăm raw VCI/KBS khi chưa chuẩn hóa scale.
- Không trộn trực tiếp BCTC raw với `financial_snapshot` vì khác grain và shape.
- Không nạp nguyên DB, `ohlcv_flat.csv` hoặc toàn bộ `data_bctc/` vào context LLM; phải lọc trước.
- Không xem output Quant/AI là ground truth.

## Nguyên tắc trình bày

Mọi nhận định phải ghi rõ ngày/kỳ dữ liệu, phân biệt dữ liệu báo cáo với chỉ tiêu dẫn xuất, nêu hạn chế liên quan và bảo toàn UTF-8 cho tiếng Việt.
