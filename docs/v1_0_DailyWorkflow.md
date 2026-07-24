# AI ANALYZE v1.0 — Daily Workflow

Tài liệu này là checklist vận hành hằng ngày. Mọi lệnh được chạy từ PowerShell tại thư mục gốc `AI ANALYZE`.

## A. Mở phiên làm việc

### 1. Xác nhận đúng thư mục

```powershell
Set-Location <consumer-repository>
Get-Location
```

PowerShell phải được mở tại thư mục gốc của repository Consumer. Không chạy builder từ dashboard runtime được chọn bởi `STOCK_LOOKUP_RUNTIME_ROOT` hoặc từ `release/v1.0`.

### 2. Chạy kiểm tra chỉ đọc

```powershell
Set-Location <consumer-repository>
python builders/run_final_qa.py --dry-run
python builders/validate_operating_pack.py --dry-run
```

Nếu một kiểm tra fail, dừng tác vụ và xử lý theo `docs/v1_0_Troubleshooting.md`.

### 3. Xác định yêu cầu

Ghi rõ trước khi chọn file:

- Tác vụ: một mã, so sánh hay screening.
- Ticker hoặc tập ticker.
- Mode: hiện tại, nghiên cứu quá khứ hay backtest.
- Cutoff/ngày hoặc kỳ cần dùng.
- Section cần thiết: giá, BCTC, metadata, kỹ thuật, cổ đông, tin tức.

Không gọi một phân tích là backtest nếu chưa chứng minh availability theo thời điểm.

## B. Chọn hoặc build context

### 1. Ưu tiên package hiện có khi phù hợp

Kiểm tra file trong `exports/context_packages/`. Đọc `generated_at`, ngày giá mới nhất, kỳ BCTC, warnings và missing trước khi tái sử dụng.

Các báo cáo `staleness_report` và `rebuild_decision` là snapshot tại thời điểm chúng được tạo. Không mặc định chúng phản ánh dữ liệu hôm nay nếu `generated_at` đã cũ.

### 2. Dry-run trước khi build

Một ticker:

```powershell
Set-Location <consumer-repository>
python builders/build_ticker_context.py --ticker HPG --dry-run
```

Tối đa 10 ticker:

```powershell
Set-Location <consumer-repository>
python builders/build_ticker_context.py --tickers HPG,FPT,VCB --output exports/context_packages --dry-run
```

### 3. Chỉ ghi file mới khi cần

Ví dụ một ticker với tên versioned:

```powershell
Set-Location <consumer-repository>
python builders/build_ticker_context.py --ticker HPG --output exports/context_packages/HPG_context_YYYYMMDD.json --no-dry-run
```

Không xóa hoặc ghi đè package cũ để “làm mới”. Không sửa trực tiếp JSON nhằm loại warnings.

## C. Preflight context package

Trước khi upload, đánh dấu từng mục:

- [ ] Ticker đúng.
- [ ] JSON mở/parse được.
- [ ] `generated_at` và latest dates phù hợp với câu hỏi.
- [ ] Validation status đã được đọc.
- [ ] `missing_sections` đã được ghi nhận.
- [ ] `warnings` và `not_fully_confirmed` đã được ghi nhận.
- [ ] Provenance tồn tại.
- [ ] Không có raw VNSTOCK hoặc dữ liệu cá nhân trong tập upload.
- [ ] Mục tiêu không yêu cầu khuyến nghị mua/bán.

Có thể kiểm tra nhanh JSON bằng PowerShell:

```powershell
Set-Location <consumer-repository>
Get-Content exports/context_packages/HPG_context.json -Raw -Encoding UTF8 | ConvertFrom-Json | Select-Object ticker, generated_at
```

Đổi tên file theo package thực tế.

## D. Chuẩn bị ChatGPT, Claude hoặc Codex

**[DEPRECATED 2026-07-17] Gemini đã bị loại khỏi luồng khuyến nghị.** Hai lần kiểm toán độc lập
(`STOCK_ANALYSIS_MASTER_PLAN.md` và `FINAL_STOCK_ANALYSIS_20260717.md`, được lưu ngoài repository trong hồ sơ vận hành nội bộ)
phát hiện Gemini Deep Research lặp lại lỗi tự bịa/bỏ sót dữ liệu dù input đã đúng chuẩn (tuyên bố
sai dữ liệu HPG/OHLCV 30 phiên "khuyết thiếu" trong khi có đầy đủ). `operating_pack/gemini/` được
**giữ nguyên làm lịch sử/audit trail** (không xóa) nhưng không còn nằm trong quy trình khuyến nghị
— xem banner deprecated ở đầu các file đó. Workflow hiện hành: **Python (tự động, miễn phí) →
ChatGPT/Claude/Codex (diễn giải, có kiểm toán chéo)**.

### ChatGPT

1. Mở/tạo Project.
2. Dùng `operating_pack/chatgpt/project_instructions.md`.
3. Theo `operating_pack/chatgpt/upload_manifest.json`.
4. Gắn package của tác vụ và mở chat mới khi đổi cutoff/task.

### Claude

1. Mở/tạo Project.
2. Dùng `operating_pack/claude/project_instructions.md`.
3. Theo `operating_pack/claude/upload_manifest.json`.
4. Gắn context theo task; Project Knowledge không thay thế validation của package.

### Codex (hoặc Claude Code — đọc file trực tiếp, không qua chat upload)

Codex/Claude Code chạy trong terminal/IDE với quyền đọc file trực tiếp trên máy — **không cần**
`upload_manifest.json` kiểu chat-paste (đó là cơ chế cho ChatGPT/Claude web Project). Thay vào đó:

1. Chạy `python export_ai_bundle.py` (thư mục `VNSTOCK`) để có `analysis_bundle.json` mới nhất —
   bundle đầy đủ (market breadth + macro + context package + provenance + data-quality flags), tự
   chứa, không cần đính kèm thêm file rời.
2. Yêu cầu Codex/Claude Code đọc trực tiếp `VNSTOCK/analysis_bundle.json` +
   `VNSTOCK/bundle_manifest.json` — không đọc `screen_snapshot.csv`/`ta_signals.csv` gốc (dễ bị cắt
   ngắn với file lớn, xem `STOCK_ANALYSIS_MASTER_PLAN.md`).
3. Kiểm tra `freshness.status`, `data_quality_flags` và `canonical_rs_rating` trước khi dùng số
   liệu — không dùng `ta_signal.rs_rating` làm căn cứ (có thể là bản sao cũ hơn, xem
   `rs_rating_reconciliation` từng mã trong bundle).

Với ChatGPT/Claude (chat-upload), kiểm tra giới hạn file hiện tại của tài khoản trước khi upload.

## E. Chạy tác vụ AI

### Một ticker

- Gắn một `*_context.json`.
- Dùng Single-ticker template.
- Yêu cầu validation preamble trước phần mô tả.

### So sánh

- Gắn hai package.
- Kiểm tra cutoff, period, field definition và unit compatibility.
- Dùng Two-ticker comparison template.
- Cho phép `Unknown/Not comparable`; không ép AI chọn mã thắng.

### Screening

- Gắn batch manifest, batch validation và các package liên quan.
- Nêu tiêu chí và missing policy cụ thể.
- Dùng pass/fail/unknown cho từng rule.
- Nhắc rõ universe chỉ là tập package được cung cấp.

Các template nằm trong `prompts/ai_analysis_templates.md`.

## F. Duyệt câu trả lời

Dùng `operating_pack/common/operator_checklist.md`. Tối thiểu phải thấy:

- Cutoff/latest dates.
- Validation status, missing và warnings.
- Provenance gần số liệu quan trọng.
- Fact/Derived/Inference/Unknown tách biệt.
- Không có suy đoán dữ liệu thiếu.
- Không có recommendation, target price hoặc promised return.

Nếu không đạt, không chỉnh tay câu trả lời để che lỗi. Yêu cầu AI làm lại với validation preamble hoặc bắt đầu chat mới bằng đúng instructions/context.

## G. Kết thúc phiên

- Giữ package mới bằng tên có version/ngày; không ghi đè.
- Không lưu câu trả lời AI như ground truth của dữ liệu.
- Không sửa `release/v1.0`.
- Không chạy crawler/pipeline hoặc cập nhật VNSTOCK từ workflow này.
- Ghi lại package, cutoff và template đã dùng nếu cần tái lập tác vụ.

## Known Limitations

Checklist hằng ngày không chứng minh dữ liệu upstream chính xác hoặc mới theo thời gian thực. Các báo cáo staleness/rebuild chỉ có giá trị tại `generated_at` của chúng, và nền tảng AI vẫn cần người vận hành duyệt output.

## How AI Should Use This

AI có thể nhắc từng checkpoint và dừng khi checkpoint không đạt. AI không được tự chạy bước ghi file, bỏ qua phê duyệt của người dùng hoặc diễn giải rebuild/validation như tín hiệu đầu tư.
