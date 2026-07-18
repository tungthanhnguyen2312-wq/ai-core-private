# Proposed Phase 5 Plan

## Mục tiêu đề xuất

Phase 5 nên triển khai adapter read-only để builder đọc dữ liệu thật có chọn lọc, tạo context package cho ba ticker test được người dùng chỉ định và validate output. Không tạo khuyến nghị đầu tư.

## Phạm vi đề xuất

1. Chọn ba ticker test và analysis cutoff.
2. Implement adapters read-only cho metadata, OHLCV lọc, financial snapshot và technical snapshot; news/shareholder chỉ khi linkage/coverage rõ.
3. Thêm validation engine dựa trên `validation_rules.json`.
4. Tạo package vào `exports/` với record-level provenance.
5. Kiểm tra stale, missing, sentinel, unit, point-in-time và file-size/token budget.
6. Đối chiếu thủ công một số field với source.
7. Báo cáo pass/fail/unknown, không phân tích mua/bán.

## Điều kiện phê duyệt

Cần duyệt riêng ticker test, nguồn được đọc, quyền tạo test/code mới, output naming và việc có được query SQLite/Parquet hay không.

## Tiêu chí hoàn thành đề xuất

Builder chạy dry-run/write an toàn; ba package valid; provenance đầy đủ; không có write VNSTOCK; validation results tái lập được; TODO/gap được ghi rõ.

## Provenance / Source Basis

Kế hoạch xuất phát từ các TODO/limitations của Phase 4 và Phase 3 validation design.

## Known Limitations

- Chưa xác định ticker test.
- Publication dates, corporate actions và news mapping vẫn not fully confirmed.
- Đây chỉ là đề xuất, chưa phải authorization.

## How AI Should Use This

Không tự bắt đầu Phase 5. Chỉ dùng tài liệu để xin/phân tích phạm vi phê duyệt tiếp theo.
