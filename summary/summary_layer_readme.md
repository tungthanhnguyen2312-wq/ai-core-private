# AI Summary Layer

## Summary layer là gì?

`summary/` là lớp dữ liệu nhẹ mô tả coverage, freshness, rủi ro và mức sẵn sàng cho AI. Nó giúp model quyết định nên đọc dataset nào và cần kiểm tra gì trước khi tạo context package. Summary không thay thế DB/CSV/Parquet gốc và không chứa kết luận đầu tư.

## Khi nào nên dùng?

- Trước khi chọn nguồn cho câu hỏi về ticker, thị trường, BCTC hoặc macro.
- Khi cần biết coverage/freshness quan sát được mà không mở file lớn.
- Khi xây context package và cần ghi provenance/limitations.
- Khi kiểm tra dataset nào cần validation bổ sung.

## Khi nào không nên dùng?

- Không dùng summary count để khẳng định một ticker cụ thể có dữ liệu.
- Không dùng ngày observed như freshness hiện tại nếu pipeline đã chạy sau discovery.
- Không dùng readiness score làm điểm đầu tư.
- Không dùng summary thay số liệu record-level cho phân tích hoặc backtest.

## Kiểm tra provenance

Mỗi JSON có `source_basis`, `generated_at`, `summary_type` và `limitations`. Đọc `summary_manifest.json` để biết file nguồn và update rule. Một số liệu record-level sau này phải trích thêm source file/dataset, key, date/period, field, unit và transformation.

## Tránh nhầm snapshot và historical

- `metadata`, `shareholders`, `screen_snapshot`, `ta_signals` và các file `*_latest` là point-in-time/latest views.
- Phân tích hiện tại phải kiểm tra global latest date và stale ticker.
- Backtest phải dùng dữ liệu đã available tại thời điểm mô phỏng; không dùng metadata/shareholder hiện tại.
- Kỳ BCTC không phải ngày công bố. Backtest nghiêm túc cần publication/availability date, hiện chưa được xác nhận đầy đủ.

## Provenance / Source Basis

Phase 3 dùng các thống kê đã quan sát trong Phase 1 discovery và registry Phase 1.5/knowledge Phase 2. Không thực hiện fresh full-data scan, không chạy crawler và không cập nhật VNSTOCK.

## Known Limitations

- Counts/dates có thể stale sau 2026-07-13.
- Per-ticker coverage chưa được enumerate.
- Null/duplicate/gap statistics chưa được tính.
- Price adjustment, BCTC unit và publication dates còn **not fully confirmed**.
- Readiness score là heuristic về dữ liệu, không phải chất lượng doanh nghiệp.

## How AI Should Use This

Đọc manifest → coverage → freshness → domain summary → validation rules. Nếu cần kết luận record-level, mở dữ liệu nguồn đã lọc và ghi provenance mới; không lặp lại summary observation như một fact hiện tại mà không nêu cutoff.
