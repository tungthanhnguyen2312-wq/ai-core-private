# Ticker Context Builder Plan

## Trạng thái

Đây là kế hoạch thiết kế; Phase 3 không viết hoặc chạy builder code.

## Input

- Ticker uppercase.
- Analysis cutoff và mode: `current`, `historical_research` hoặc `backtest`.
- Danh sách section cần thiết.
- Registry metadata/validation rules.
- Quyền đọc source và token/size budget.

## Output

Một JSON theo `ticker_context_template.json`, kèm validation status, missing sections, warnings và record-level provenance. Builder không tạo recommendation hoặc narrative analysis.

## Thứ tự đọc dataset

1. Đọc validation/quality rules và context template.
2. Xác nhận ticker bằng OHLCV/metadata availability.
3. Lấy global latest price date; xác định stale/active status.
4. Query OHLCV đã lọc và tính price summary có transformation log.
5. Đọc current metadata; gắn point-in-time.
6. Đọc financial snapshot theo ticker/kỳ; raw BCTC chỉ khi cần reconcile.
7. Đọc technical snapshot/signals đúng latest valid date.
8. Đọc shareholder cùng progress, gắn no-history.
9. Chọn news theo cutoff; entity linking là bước riêng có confidence.
10. Đọc macro chỉ khi package spec/consumer yêu cầu; không mặc định nhồi toàn bộ.
11. Chạy validation, lập missing/warnings/provenance rồi serialize UTF-8.

## Validation bắt buộc

- Ticker không rỗng và normalized.
- Date/period parse được và không vượt cutoff.
- OHLCV numeric, volume không âm, high/low hợp lý.
- `-1`, NULL, empty và string boolean xử lý đúng context.
- Latest snapshot/global date và stale ticker kiểm tra.
- Financial raw/processed không bị trộn grain.
- Unit/scale và quarter/year được ghi.
- Point-in-time rules theo mode.
- Provenance cho mọi field/section.
- Kích thước package trong budget; không cắt mất warnings.

## Lỗi cần chặn

- Ticker không tồn tại hoặc chỉ có stale data nhưng bị gắn active.
- Dữ liệu sau cutoff lọt vào historical/backtest package.
- Current metadata/shareholder được dùng trong backtest.
- Kỳ BCTC được coi là ngày công bố.
- Sentinel `-1` thành giá trị thật; `"False"` thành true.
- Unit conflict chưa giải quyết nhưng vẫn tính valuation/ratio.
- News được gán ticker không có linkage evidence.
- Derived output ghi đè reported source.
- Package không có provenance hoặc generated_at.

## Update / Cache Rule

Cache key tối thiểu gồm ticker, cutoff, mode, requested sections và source fingerprints. Rebuild khi source latest/update thay đổi hoặc validation rules tăng version.

## Provenance / Source Basis

Dựa trên Phase 1.5 registries, Phase 2 knowledge và Phase 3 validation design.

## Known Limitations

- Chưa chọn implementation language, query engine hay storage.
- Chưa có canonical publication calendar, corporate-action table hoặc news entity map.
- Không có code, test hay performance benchmark trong Phase 3.

## How AI Should Use This

AI dùng plan để review/implement ở phase được duyệt sau; không giả định builder đã tồn tại. Mọi package hiện tại phải được xem là template/sample trừ khi có provenance record-level thực.
