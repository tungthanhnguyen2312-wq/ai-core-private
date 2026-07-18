# v1.0.1 Documentation Patch Summary

## Mục tiêu

Bổ sung lớp hướng dẫn người dùng cuối cho AI ANALYZE v1.0, tập trung vào vận hành hằng ngày với context package và Gemini, ChatGPT hoặc Claude.

Đây là documentation-only patch. Nó không thay đổi code, database, context package, metadata, schema, workflow machine-readable hoặc snapshot `release/v1.0`.

## File được bổ sung

- `README.md`: trang bắt đầu và bản đồ tài liệu.
- `docs/v1_0_UserGuide.md`: hướng dẫn đầy đủ từ build context đến review output AI.
- `docs/v1_0_QuickStart.md`: quy trình thử nhanh một ticker.
- `docs/v1_0_DailyWorkflow.md`: checklist vận hành hằng ngày.
- `docs/v1_0_Troubleshooting.md`: xử lý lỗi builder, validation, dữ liệu, nền tảng AI và release.
- `docs/v1_0_1_DocumentationPatchSummary.md`: phạm vi và thay đổi của patch này.

## Nội dung bao phủ

- Build một hoặc nhiều context package bằng dry-run trước và output versioned.
- Cách dùng upload manifest/project instructions cho Gemini, ChatGPT và Claude.
- Workflow phân tích một mã, so sánh và screening.
- Cách đọc `warnings`, `missing_sections`, `not_fully_confirmed` và `provenance`.
- Cách review output theo Fact/Derived/Inference/Unknown.
- Troubleshooting các lỗi phổ biến và điều kiện phải dừng.

## Tương thích với v1.0

Tài liệu dựa trên CLI, operating pack, validation rules và context package hiện có của v1.0. `release/v1.0` tiếp tục là snapshot frozen; documentation patch được đặt ngoài snapshot và không thay đổi checksum v1.0.

## Known Limitations

- Giao diện, retrieval behavior và giới hạn upload của nền tảng AI có thể thay đổi.
- Tài liệu không chạy crawler/pipeline hoặc làm mới dữ liệu VNSTOCK.
- Context package và output AI không phải khuyến nghị đầu tư.
- Người vận hành vẫn phải kiểm tra validation, provenance và warnings cho mỗi tác vụ.

## How AI Should Use This

AI dùng patch này như hướng dẫn thao tác, không dùng nó làm nguồn fact theo ticker. Context package, validation rules và provenance vẫn là nguồn kiểm soát cho mọi tác vụ dữ liệu.
