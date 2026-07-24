# AI ANALYZE v1.0 — Quick Start

Hướng dẫn này giúp người dùng tạo hoặc chọn một context package và dùng nó với ChatGPT, Claude hoặc Codex. Thực hiện lệnh từ PowerShell tại thư mục gốc `AI ANALYZE`. (Gemini deprecated khỏi luồng khuyến nghị từ 2026-07-17 — xem `docs/v1_0_DailyWorkflow.md` mục D.)

## 1. Kiểm tra hệ thống

Chạy hai kiểm tra chỉ đọc:

```powershell
Set-Location <consumer-repository>
python builders/run_final_qa.py --dry-run
python builders/validate_operating_pack.py --dry-run
```

Chỉ tiếp tục khi cả hai trả về trạng thái `pass`. Nếu fail, xem `docs/v1_0_Troubleshooting.md`.

## 2. Chọn một mã

Ví dụ dùng `HPG`. Nếu file `exports/context_packages/HPG_context.json` đã tồn tại và ngày dữ liệu phù hợp với câu hỏi, có thể dùng ngay.

Muốn kiểm tra khả năng build mà không ghi file:

```powershell
Set-Location <consumer-repository>
python builders/build_ticker_context.py --ticker HPG --dry-run
```

Dry-run thành công **không tạo file**. Nếu cần package mới, đặt tên mới để không ghi đè:

```powershell
Set-Location <consumer-repository>
python builders/build_ticker_context.py --ticker HPG --output exports/context_packages/HPG_context_YYYYMMDD.json --no-dry-run
```

Thay `YYYYMMDD` bằng ngày tạo thực tế. Builder chỉ được phép ghi file mới trong `exports/context_packages/` và sẽ từ chối ghi đè.

## 3. Đọc kiểm tra trước khi dùng

Mở context package và kiểm tra tối thiểu:

- `ticker`: đúng mã cần phân tích.
- `generated_at`: thời điểm package được tạo.
- Ngày giá mới nhất và kỳ BCTC mới nhất: phù hợp với câu hỏi.
- `data_quality.validation_status`: trạng thái validation.
- `data_quality.missing_sections`: phần không có dữ liệu.
- `data_quality.warnings`: cảnh báo phải giữ trong kết quả.
- `data_quality.not_fully_confirmed`: định nghĩa, đơn vị hoặc mapping chưa chắc chắn.
- `provenance`: nguồn và phép biến đổi của dữ liệu.

Không dùng một section cho kết luận phụ thuộc nếu section đó đang missing hoặc unverified.

## 4. Chuẩn bị nền tảng AI

Chọn đúng thư mục:

- ChatGPT: `operating_pack/chatgpt/`
- Claude: `operating_pack/claude/`
- Codex/Claude Code (đọc file trực tiếp, không cần upload manifest): xem `docs/v1_0_DailyWorkflow.md` mục D.
- ~~Gemini: `operating_pack/gemini/`~~ — **deprecated 2026-07-17**, giữ lại làm lịch sử/audit, không dùng cho tác vụ mới.

Sau đó:

1. Tạo Project/workspace trên nền tảng.
2. Đưa nội dung `project_instructions.md` vào phần hướng dẫn của Project.
3. Upload đúng các file trong `upload_manifest.json`, trong giới hạn hiện tại của tài khoản.
4. Không upload toàn bộ dashboard runtime được chọn bởi `STOCK_LOOKUP_RUNTIME_ROOT`, database, raw OHLCV hoặc kho BCTC raw.
5. Gắn context package của tác vụ hiện tại vào cuộc hội thoại.

Chi tiết giao diện có thể thay đổi theo nền tảng; nếu một tính năng không tồn tại, không thay thế bằng cách upload raw data.

## 5. Yêu cầu phân tích một mã

Dùng template Single-ticker trong `prompts/ai_analysis_templates.md`, hoặc yêu cầu ngắn sau:

```text
Dựa duy nhất trên context package đính kèm, trước tiên hãy báo generated_at,
ngày dữ liệu mới nhất, validation status, missing_sections, warnings,
not_fully_confirmed và provenance. Sau đó mô tả các phần có dữ liệu,
tách Fact, Derived, Inference và Unknown. Không bịa số liệu, không đưa
khuyến nghị mua/bán, giá mục tiêu hoặc cam kết lợi nhuận.
```

## 6. Kiểm tra câu trả lời

Không chấp nhận kết quả nếu thiếu một trong các điểm sau:

- Cutoff/ngày dữ liệu.
- Nguồn nội bộ gần số liệu quan trọng.
- Dữ liệu thiếu và cảnh báo.
- Phân biệt fact với suy luận.
- Giới hạn point-in-time và đơn vị BCTC khi liên quan.

Checklist đầy đủ nằm tại `operating_pack/common/operator_checklist.md`.

## Bước tiếp theo

- So sánh hoặc screening: xem `docs/v1_0_UserGuide.md`.
- Quy trình mỗi ngày: xem `docs/v1_0_DailyWorkflow.md`.
- Lỗi thường gặp: xem `docs/v1_0_Troubleshooting.md`.

## Known Limitations

Quick Start chỉ bao phủ quy trình cơ bản. Nó không xác nhận dữ liệu đã mới theo thời gian thực, không thay thế validation chi tiết và không bảo đảm giao diện của nền tảng AI giống tài liệu tại mọi thời điểm.

## How AI Should Use This

AI phải thực hiện validation preamble trước khi mô tả ticker, chỉ dùng package được gắn, giữ nguyên missing/warnings/provenance và không tạo khuyến nghị đầu tư.
