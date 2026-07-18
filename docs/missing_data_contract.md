# Missing Data Contract v1

Phase 1 giữ nguyên scalar và section cũ, đồng thời thêm metadata song song. Ví dụ:

```json
{
  "operating_cash_flow": null,
  "operating_cash_flow_meta": {
    "value": null,
    "status": "stale",
    "reason": "selected_period_value_missing",
    "source": "financial_snapshot",
    "period": "2026-Q1",
    "basis": "quarter"
  }
}
```

## Trạng thái

`reported`, `derived`, `proxy`, `source_empty`, `mapping_missing`,
`insufficient_periods`, `parse_failed`, `stale`, `not_applicable`,
`not_queried`, `network_failed`, `derivation_not_implemented`,
`unit_unknown`, `period_basis_unknown`.

- Missing không được chuyển thành `0`.
- `derived` bắt buộc có `formula` và `inputs`.
- `not_applicable` không được tính vào mẫu số coverage.
- `not_queried` khác `source_empty`: chưa chạy source không đồng nghĩa source đã xác nhận rỗng.
- Giá trị reported vẫn có thể mang `details.unit_status=unit_unknown`; không được so sánh đơn vị cho đến khi xác nhận.

## Coverage

Mỗi section có `coverage`, gồm số metric available/expected, danh sách missing và
not-applicable. `data_quality.section_coverage` tổng hợp coverage của financial,
news và shareholders. Consumer cũ tiếp tục đọc scalar; consumer mới phải kiểm tra
`*_meta.status` hoặc `section.meta.status` trước khi phân tích.

`financial_summary.coverage_scope` liệt kê rõ 7 metric đang thuộc contract Phase 1;
coverage này chưa đại diện cho toàn bộ chỉ tiêu tài chính trong snapshot.

## Snapshot schema v2 migration

Phase 9 retains every scalar and reads parallel `*_status`, `*_formula`, `*_inputs`, `*_source`, and `*_period` fields from `financial_snapshot` schema `2.0`. Context packages expose the source version as `financial_summary.snapshot_schema_version`. Legacy snapshots without the column remain readable as `1.0-legacy`.
