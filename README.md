# AI ANALYZE v1.0

Codex is the active executor. Consumer is the fail-closed context, AI-contract, and validation layer; it must not infer missing source semantics. Canonical governance is maintained by Producer at `../stock-core-private/docs/`.

AI ANALYZE chuẩn bị các **context package có kiểm soát** từ nguồn VNSTOCK để người dùng làm việc với ChatGPT, Claude hoặc Codex. Hệ thống giúp AI biết dữ liệu nào đang có, dữ liệu nào thiếu, nguồn ở đâu và giới hạn nào phải giữ.

> **[DEPRECATED 2026-07-17]** Gemini đã bị loại khỏi luồng khuyến nghị sau 2 lần kiểm toán độc lập phát hiện lỗi tự bịa/bỏ sót dữ liệu lặp lại dù input đúng chuẩn (`STOCK_ANALYSIS_MASTER_PLAN.md`, `FINAL_STOCK_ANALYSIS_20260717.md`, được lưu ngoài repository trong hồ sơ vận hành nội bộ). `operating_pack/gemini/` vẫn giữ nguyên trên đĩa làm lịch sử/audit trail, không dùng cho tác vụ mới — xem `docs/v1_0_DailyWorkflow.md` mục D.

AI ANALYZE không chạy crawler, không tự cập nhật thị trường và không tạo khuyến nghị mua/bán. Dashboard runtime được chọn bởi `STOCK_LOOKUP_RUNTIME_ROOT` luôn là nguồn chỉ đọc.

## Bắt đầu ở đây

- Muốn thử nhanh: đọc [docs/v1_0_QuickStart.md](docs/v1_0_QuickStart.md).
- Muốn hiểu toàn bộ quy trình: đọc [docs/v1_0_UserGuide.md](docs/v1_0_UserGuide.md).
- Vận hành mỗi ngày: dùng [docs/v1_0_DailyWorkflow.md](docs/v1_0_DailyWorkflow.md).
- Gặp lỗi: tra [docs/v1_0_Troubleshooting.md](docs/v1_0_Troubleshooting.md).
- Các giới hạn đã biết: đọc [docs/v1_0_KnownLimitations.md](docs/v1_0_KnownLimitations.md).
- Financial Analysis V2 Consumer boundary: đọc [docs/financial_analysis_consumer_context_contract.md](docs/financial_analysis_consumer_context_contract.md).

## Quy trình ngắn

1. Mở PowerShell tại thư mục `AI ANALYZE`.
2. Chọn context package đã có hoặc chạy builder ở chế độ `--dry-run`.
3. Nếu cần file mới, dùng `--no-dry-run` với tên output mới trong `exports/context_packages/`.
4. Kiểm tra `generated_at`, ngày dữ liệu mới nhất, `missing_sections`, `warnings`, `not_fully_confirmed` và `provenance`.
5. Use the approved Project Knowledge and context package through Codex; do not treat any assistant workflow as a source of truth.
6. Chọn template phân tích một mã, so sánh hoặc screening trong `prompts/ai_analysis_templates.md`.
7. Chỉ chấp nhận câu trả lời khi AI nêu cutoff, nguồn, dữ liệu thiếu và tách rõ Fact/Derived/Inference/Unknown.

## Ba loại tác vụ

| Nhu cầu | File dữ liệu cần gắn | Template |
|---|---|---|
| Phân tích một mã | Một file `*_context.json` | Single-ticker |
| So sánh | Hai context package có kỳ, ngày và đơn vị tương thích | Two-ticker comparison |
| Screening | Batch manifest, batch validation và tối đa 10 context package | Context-package screening |

Screening chỉ lọc trong tập package được cung cấp, không phải quét toàn thị trường và không phải xếp hạng cơ hội đầu tư.

## Các thư mục quan trọng

- `exports/context_packages/`: context package và báo cáo batch hiện có.
- `operating_pack/`: hướng dẫn và upload manifest cho từng nền tảng AI.
- `prompts/`: template yêu cầu phân tích.
- `validation/`: quy tắc validation, provenance và point-in-time.
- `knowledge/` và `metadata/`: định nghĩa dữ liệu và quy tắc sử dụng.
- `release/v1.0/`: snapshot v1.0 đã đóng băng; không sửa tại chỗ.
- `docs/`: hướng dẫn người dùng và tài liệu vận hành.

## Quy tắc an toàn bắt buộc

- Không sửa, di chuyển, đổi tên hoặc xóa file trong dashboard runtime được chọn bởi `STOCK_LOOKUP_RUNTIME_ROOT`.
- Không upload database, raw OHLCV, kho BCTC raw hoặc dữ liệu cá nhân lên nền tảng AI.
- Không coi `-1`, `NULL`, chuỗi rỗng hoặc section thiếu là số 0.
- Không suy đoán tin tức theo ticker khi mapping chưa được xác nhận.
- Không dùng metadata/cổ đông hiện tại như dữ liệu lịch sử.
- Không so sánh số tiền BCTC khi đơn vị hoặc scale chưa tương thích.
- Không yêu cầu hoặc chấp nhận khuyến nghị mua/bán, giá mục tiêu hay cam kết lợi nhuận.

## Phiên bản

- `release/v1.0`: snapshot dữ liệu, metadata, builder, validation và operating pack đã freeze.
- `v1.0.1 Documentation Patch`: bổ sung hướng dẫn người dùng cuối bên ngoài snapshot; không thay đổi `release/v1.0`, code hay dữ liệu VNSTOCK.
