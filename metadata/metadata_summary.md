# Phase 1.5 — Metadata Summary

## Kết quả

Đã tạo lớp metadata machine-readable cho hệ thống VNSTOCK gồm registry dataset, schema, module, file, ticker availability, BCTC, quan hệ dữ liệu, quy tắc chất lượng và hướng dẫn sử dụng cho AI. Phase này chỉ mô tả dữ liệu hiện hữu; không sinh dữ liệu phân tích mới, không chạy crawler và không thay đổi VNSTOCK.

## Nguồn sử dụng

Nội dung được tổng hợp từ toàn bộ tám tài liệu Phase 1 trong `project_discovery/`:

- `discovery_summary.md`
- `project_tree.md`
- `file_inventory.md`
- `dataset_inventory.md`
- `python_modules.md`
- `data_relationship.md`
- `schema_summary.md`
- `quality_assessment.md`

## File metadata đã tạo

- `datasets.json`: các dataset chính, grain, khóa và khả năng dùng cho AI.
- `schema_registry.json`: schema chuẩn hóa, semantic type, unit và missing rule.
- `module_registry.json`: 13 Python module và vai trò pipeline.
- `file_registry.json`: nhóm file cùng chính sách đọc cho AI.
- `ticker_registry.json`: summary coverage và contract availability theo ticker.
- `financial_statement_registry.json`: phân biệt BCTC raw và processed.
- `relationship_graph.json`: node/edge và khóa liên kết logic.
- `data_quality_rules.json`: quy tắc chất lượng dữ liệu bắt buộc.
- `ai_context.md`: thứ tự đọc và cách chọn dữ liệu cho AI.
- `metadata_summary.md`: tài liệu tổng kết này.

## Giả định

- Các thống kê phản ánh thời điểm discovery ngày 2026-07-13 và có thể thay đổi khi pipeline chạy về sau.
- `ticker` được chuẩn hóa uppercase và thường dài 3–4 ký tự.
- `margin_status` rỗng được hiểu là sạch theo quy ước discovery.
Đường dẫn trong registry được Consumer diễn giải theo contract cấu hình; dashboard runtime đích được chọn bởi `STOCK_LOOKUP_RUNTIME_ROOT`, không suy diễn từ thư mục sibling.
- Các trường được gom nhóm trong `schema_registry.json` có chung contract kiểu/semantic; danh sách cột đầy đủ vẫn được xác định bởi schema discovery.

## Điểm chưa chắc chắn

- Chưa xác minh trực tiếp mức độ điều chỉnh giá cho cổ tức/chia tách.
- Không có ticker mapping chính thức cho news.
- `free_float_est` là proxy, không phải công bố chính thức.
- Cổ đông không có lịch sử và `shareholder_type` thường NULL.
- Số ticker khác nhau giữa ticker list, OHLCV, snapshot và BCTC do coverage/trạng thái khác nhau.
- Chưa enumerate từng ticker trong Phase 1.5 để tránh quét nguồn lớn; `ticker_registry.json` dùng summary counts.
- Foreign key chỉ là logic, không được SQLite enforce.

## Đề xuất cho phase tiếp theo

Nếu được phê duyệt riêng, phase tiếp theo có thể validate các JSON bằng schema, xây data dictionary chi tiết cho từng cột còn được gom nhóm, tạo quy trình truy vấn/filter context theo ticker và kiểm tra coverage/freshness trực tiếp. Các việc này chưa được thực hiện trong Phase 1.5.
