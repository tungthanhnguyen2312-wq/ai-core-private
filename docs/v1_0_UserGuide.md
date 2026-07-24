# AI ANALYZE v1.0 — User Guide

## 1. AI ANALYZE dùng để làm gì?

AI ANALYZE biến dữ liệu VNSTOCK thành các context package nhỏ, machine-readable và có provenance để ChatGPT, Claude hoặc Codex có thể đọc an toàn hơn. Mỗi package mô tả một ticker, dữ liệu hiện có, dữ liệu thiếu, ngày/kỳ liên quan và nguồn nội bộ. (Gemini deprecated khỏi luồng khuyến nghị từ 2026-07-17 — xem `docs/v1_0_DailyWorkflow.md` mục D và `operating_pack/gemini/`.)

Luồng vận hành:

```text
VNSTOCK chỉ đọc
    -> context builder / export_ai_bundle.py
    -> context package + analysis_bundle.json (provenance + data-quality flags)
    -> ChatGPT / Claude / Codex
    -> người dùng kiểm tra kết quả
```

AI ANALYZE không tự tải dữ liệu mới, không chạy pipeline thị trường, không bảo đảm nguồn upstream hoàn toàn chính xác và không phải hệ thống tư vấn đầu tư.

## 2. Chuẩn bị

Bạn cần:

- Python có thể gọi bằng lệnh `python`.
- PowerShell mở tại thư mục gốc `AI ANALYZE`.
Quyền đọc dashboard runtime được chọn bởi `STOCK_LOOKUP_RUNTIME_ROOT` và quyền ghi trong repository Consumer.
- Một tài khoản ChatGPT hoặc Claude (chat-upload) hoặc Codex/Claude Code (đọc file trực tiếp) nếu muốn dùng context với AI bên ngoài.

Không chạy lệnh từ bên trong `release/v1.0`. Đây là snapshot đã freeze và không được sửa tại chỗ.

## 3. Hiểu các file chính

| Thành phần | Mục đích |
|---|---|
| `exports/context_packages/*_context.json` | Dữ liệu đã đóng gói theo ticker |
| `exports/context_packages/batch_manifest*.json` | Danh sách package trong một batch |
| `exports/context_packages/batch_validation_report*.json` | Kết quả validation theo batch |
| `exports/context_packages/staleness_report.*` | Dấu hiệu package/source có thể cũ hoặc thay đổi |
| `exports/context_packages/rebuild_decision.*` | Quyết định rebuild theo rule, không phải tín hiệu đầu tư |
| `operating_pack/<platform>/` | Project instructions, upload manifest và workflow |
| `prompts/ai_analysis_templates.md` | Template phân tích một mã, so sánh và screening |
| `validation/` | Quy tắc schema, provenance và point-in-time |
| `knowledge/` | Data dictionary, công thức và quy tắc phân tích |
| `release/v1.0/` | Snapshot v1.0 đã freeze |

## 4. Build context package

### 4.1 Một ticker

Luôn chạy dry-run trước:

```powershell
Set-Location <consumer-repository>
python builders/build_ticker_context.py --ticker HPG --dry-run
```

Khi dry-run pass và bạn thật sự cần một file mới, dùng tên output có version/ngày:

```powershell
Set-Location <consumer-repository>
python builders/build_ticker_context.py --ticker HPG --output exports/context_packages/HPG_context_YYYYMMDD.json --no-dry-run
```

Builder sẽ:

- Chuẩn hóa và kiểm tra ticker.
- Chỉ đọc nguồn VNSTOCK.
- Từ chối path output ngoài khu vực được phép.
- Từ chối ghi đè file đã có.
- Ghi warnings, missing sections và provenance vào package.

### 4.2 Nhiều ticker

Builder hỗ trợ tối đa 10 ticker trong một lần. Dry-run:

```powershell
Set-Location <consumer-repository>
python builders/build_ticker_context.py --tickers HPG,FPT,VCB --output exports/context_packages --dry-run
```

Tạo file mới chỉ khi output tương ứng chưa tồn tại:

```powershell
Set-Location <consumer-repository>
python builders/build_ticker_context.py --tickers HPG,FPT,VCB --output exports/context_packages --no-dry-run
```

Nếu tên mặc định đã tồn tại, builder sẽ dừng để bảo vệ file cũ. Khi cần giữ nhiều phiên bản, nên build từng ticker với tên output riêng có ngày/version.

### 4.3 Strict và non-strict

Strict mode:

```powershell
Set-Location <consumer-repository>
python builders/build_ticker_context.py --ticker HPG --strict --dry-run
```

Strict có thể fail hợp lệ khi còn `missing_sections` hoặc `not_fully_confirmed`. Không được xóa cảnh báo để ép pass. Non-strict cho phép sử dụng package có kiểm soát nếu người dùng giữ nguyên missing/warnings và không đưa kết luận phụ thuộc vào phần thiếu.

## 5. Đọc context package đúng cách

Trước mọi phân tích, kiểm tra theo thứ tự:

1. **Identity:** ticker và loại package có đúng không.
2. **Cutoff:** `generated_at`, ngày giá mới nhất, kỳ BCTC và các trường thời gian liên quan.
3. **Validation:** package parse được và `validation_status` cho phép dùng theo mục đích hiện tại.
4. **Missing:** `missing_sections` cho biết section nào không có dữ liệu.
5. **Warnings:** giới hạn phải xuất hiện lại trong câu trả lời.
6. **Not fully confirmed:** đơn vị, mapping, adjustment hoặc availability chưa đủ chắc chắn.
7. **Provenance:** nguồn, key ticker, transformation và giới hạn của từng lát cắt.

Các quy tắc dữ liệu quan trọng:

- `-1` thường là missing sau khi đã query, không phải số âm thực tế.
- `NULL` phụ thuộc ngữ cảnh; không tự đổi thành 0.
- Boolean trong CSV có thể là chuỗi `True`/`False`.
- `margin_status` rỗng theo quy ước dự án nghĩa là không có cờ margin, không phải dữ liệu chưa query.
- Snapshot phải dùng ngày mới nhất cho phân tích hiện tại nhưng không được giả làm dữ liệu lịch sử.
- `free_float_est` là proxy.
- Cổ đông và metadata là snapshot hiện tại, không có lịch sử đầy đủ.
- Giá có thể chưa được điều chỉnh đầy đủ cho cổ tức/split.
- Scale phần trăm giữa nguồn VCI/KBS có thể khác nhau.
- BCTC raw theo kỳ làm cột khác `financial_snapshot` dạng wide theo ticker/period.

## 6. Dùng với ChatGPT, Claude hoặc Codex

**[DEPRECATED 2026-07-17]** Gemini không còn nằm trong luồng khuyến nghị (2 lần kiểm toán độc lập
phát hiện lỗi tự bịa/bỏ sót dữ liệu lặp lại dù input đúng chuẩn — xem `docs/v1_0_DailyWorkflow.md`
mục D). `operating_pack/gemini/` vẫn còn nguyên trên đĩa làm lịch sử/audit trail, không dùng cho
tác vụ mới.

### 6.1 Thiết lập Project/workspace (ChatGPT, Claude)

Mỗi nền tảng chat-upload có ba file chính:

- `operating_pack/<platform>/upload_manifest.json`
- `operating_pack/<platform>/project_instructions.md`
- `operating_pack/<platform>/workflow.md`

Trong đó `<platform>` là `chatgpt` hoặc `claude`. Với Codex/Claude Code (đọc file trực tiếp, không
qua chat upload), xem `docs/v1_0_DailyWorkflow.md` mục D phần "Codex".

Thực hiện:

1. Tạo một Project/workspace riêng cho AI ANALYZE.
2. Upload đúng `reference_files` trong upload manifest, tùy giới hạn tài khoản.
3. Đặt `project_instructions.md` vào vùng hướng dẫn của Project.
4. Giữ `operator_only_files` để người vận hành kiểm tra; chỉ upload khi workflow yêu cầu.
5. Với mỗi tác vụ, gắn context package và validation/manifest cần thiết.
6. Dùng một cuộc hội thoại mới khi đổi loại tác vụ hoặc cutoff để tránh trộn context cũ.

Không upload database VNSTOCK, full OHLCV, BCTC raw hoặc dữ liệu danh mục cá nhân.

### 6.2 Validation preamble

Yêu cầu AI bắt đầu bằng:

- Ticker/phạm vi package.
- `generated_at` và ngày/kỳ mới nhất.
- Validation status.
- Missing sections.
- Warnings và not-fully-confirmed.
- Mode: current, historical research hay backtest.
- Provenance chính.

Nếu AI bỏ qua bước này, yêu cầu làm lại trước khi đọc phần phân tích.

## 7. Workflow phân tích một mã

Input: một context package.

1. Xác định ticker, mục đích và cutoff.
2. Kiểm tra package theo mục 5.
3. Chọn Single-ticker template trong `prompts/ai_analysis_templates.md`.
4. Gắn một package duy nhất cùng Project Knowledge.
5. Yêu cầu AI chỉ mô tả section có dữ liệu.
6. Kiểm tra AI đã tách Fact, Derived, Inference và Unknown.
7. Loại bỏ kết luận dùng section missing, đơn vị chưa xác nhận hoặc snapshot sai thời điểm.

Output phù hợp là bản mô tả có bằng chứng và giới hạn, không phải quyết định mua/bán.

## 8. Workflow so sánh nhiều mã

Template chuẩn trực tiếp hỗ trợ hai ticker. Với nhiều hơn hai ticker, nên dùng screening hoặc chia thành các cặp có kiểm soát.

Trước khi so sánh hai mã:

- Kiểm tra ngày giá/cutoff có tương thích.
- Kiểm tra kỳ BCTC và loại báo cáo.
- Chỉ so sánh số tiền khi unit/scale tương thích.
- Kiểm tra định nghĩa field và provider.
- Giữ một cột `Unknown/Not comparable` thay vì ép so sánh.

Gắn hai context package và dùng Two-ticker comparison template. Không yêu cầu AI chọn “mã tốt hơn”, xếp hạng lợi nhuận kỳ vọng hoặc đưa khuyến nghị.

## 9. Workflow screening

Screening của AI ANALYZE chỉ lọc trong tập package được cung cấp, tối đa 10 ticker trong batch test. Nó không đại diện toàn thị trường.

Input tối thiểu:

- Batch manifest hiện hành.
- Batch validation report tương ứng.
- Các context package được manifest tham chiếu.
- Loại screen và tiêu chí rõ ràng.

Dry-run tạo lại batch artifacts khi cần kiểm tra:

```powershell
Set-Location <consumer-repository>
python builders/build_batch_artifacts.py --tickers HPG,FPT,VCB --dry-run
```

Trong AI, dùng Context-package screening template và bắt buộc:

- Missing không được tự động pass điều kiện số.
- Mỗi ticker phải có trạng thái pass, fail hoặc unknown cho từng rule.
- Không so sánh BCTC khi kỳ/đơn vị không tương thích.
- Kết quả là bộ lọc dữ liệu, không phải danh sách khuyến nghị.
- Mỗi quyết định lọc phải nêu field và provenance.

## 10. Review kết quả AI

Chỉ chấp nhận kết quả khi:

- Không có số liệu ngoài package/Project Knowledge.
- Cutoff và source nội bộ được nêu rõ.
- Missing, conflict và uncertainty không bị giấu.
- Không đổi sentinel/missing thành 0.
- Không gán tin tức cho ticker bằng suy đoán.
- Không dùng metadata/cổ đông hiện tại trong backtest.
- Không có giá mục tiêu, cam kết lợi nhuận hoặc khuyến nghị mua/bán.

Nếu hai nguồn xung đột, AI phải ghi `unresolved_conflict` và dừng phép tính phụ thuộc; không được lấy trung bình hoặc chọn con số thuận lợi hơn.

## 11. Freeze và documentation patch

`release/v1.0` là snapshot đã freeze. Xác minh integrity bằng `release/v1.0/checksums.sha256` và `FREEZE_COMPLETE.json`; không sửa các file trong đó.

Các tài liệu người dùng v1.0.1 nằm ở root và `docs/`. Đây là documentation-only patch, không đổi code, context package đã freeze, database hoặc dữ liệu nguồn.

## 12. Khi cần trợ giúp

- Thao tác nhanh: `docs/v1_0_QuickStart.md`.
- Công việc hằng ngày: `docs/v1_0_DailyWorkflow.md`.
- Lỗi thường gặp: `docs/v1_0_Troubleshooting.md`.
- Giới hạn dữ liệu: `docs/v1_0_KnownLimitations.md`.
- Checklist duyệt output: `operating_pack/common/operator_checklist.md`.

## Known Limitations

User Guide mô tả workflow của v1.0 nhưng không làm mới nguồn dữ liệu, không xác nhận UI/giới hạn hiện tại của nền tảng AI và không loại bỏ các giới hạn upstream đã ghi trong `docs/v1_0_KnownLimitations.md`.

## How AI Should Use This

AI dùng tài liệu này để chọn đúng workflow và giải thích thao tác cho người dùng. Mọi fact theo ticker vẫn phải đến từ context package có validation/provenance; tài liệu hướng dẫn không phải nguồn số liệu thị trường.
