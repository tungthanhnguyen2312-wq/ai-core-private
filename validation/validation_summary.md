# Phase 3 Validation Summary

## File validation đã tạo

- `validation_rules.json`: 20 rule machine-readable về key/date/period/OHLCV/sentinel/snapshot/point-in-time/provenance.
- `validation_checklist.md`: checklist trước phân tích ticker.
- `point_in_time_rules.md`: discipline cho current, historical và backtest.
- `provenance_standard.md`: contract nguồn, transformation và conflict handling.
- `validation_summary.md`: tổng kết này.

## Nguồn đã dùng

Phase 1 discovery, Phase 1.5 metadata registries, Phase 2 knowledge documents và specification Phase 3. Không chạy validation trên toàn bộ dữ liệu VNSTOCK.

## Rule quan trọng nhất

Không dùng thông tin chưa available tại cutoff. Điều này cấm current metadata/shareholder và latest snapshots trong backtest, đồng thời yêu cầu publication availability của BCTC và cutoff của news/macro.

## Điểm chưa chắc chắn

- Price adjustment/corporate-action coverage.
- BCTC unit, một số item mappings và publication dates.
- Macro vintage/release lag.
- News ticker entity mapping.
- Per-ticker coverage và source fingerprints chưa được tạo.

## Đề xuất Phase 4

Nếu được duyệt riêng: triển khai validator/builder read-only, test JSON Schema, tính fresh coverage bằng truy vấn an toàn, thêm source fingerprints và tạo context package thật cho một ticker thử nghiệm không kèm khuyến nghị. Phase 4 chưa được bắt đầu.

## Provenance / Source Basis

Tài liệu này mô tả artifacts Phase 3 được tạo ngày 2026-07-13, dựa trên observed discovery summaries và semantic rules, không phải fresh empirical audit.

## Known Limitations

- Rules chưa được thực thi nên không có pass/fail record-level.
- Không có automated test, code hoặc corrected source output.
- Đề xuất Phase 4 không cấp quyền thực hiện.

## How AI Should Use This

Dùng để hiểu validation coverage và các gap còn lại. Không gọi Phase 3 là “dữ liệu đã validated”; chỉ có bộ quy tắc và summary có provenance đã được thiết kế.
