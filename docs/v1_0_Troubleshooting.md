# AI ANALYZE v1.0 — Troubleshooting

## Nguyên tắc xử lý lỗi

1. Dừng bước phụ thuộc vào dữ liệu lỗi.
2. Giữ nguyên file nguồn và warnings để có thể truy vết.
3. Chạy lại ở `--dry-run` trước.
4. Không sửa `../VNSTOCK` hoặc `release/v1.0`.
5. Không tự điền số thiếu để làm cho validation pass.

## Lỗi builder và file

### Dry-run pass nhưng không thấy file mới

Đây là hành vi đúng. `--dry-run` chỉ kiểm tra và in kết quả. Muốn tạo file, dùng `--no-dry-run` với một output mới trong `exports/context_packages/`.

### Builder báo output đã tồn tại

Builder bảo vệ file cũ và không ghi đè. Dùng tên có ngày/version, ví dụ:

```powershell
python builders/build_ticker_context.py --ticker HPG --output exports/context_packages/HPG_context_YYYYMMDD.json --no-dry-run
```

Không xóa package cũ chỉ để dùng lại cùng tên.

### Builder từ chối output path

Output phải nằm trong vùng được phép, thường là `exports/context_packages/`. Không dùng path trong `../VNSTOCK`, `release/v1.0` hoặc thư mục hệ thống.

### Ticker bị từ chối

Kiểm tra ticker không rỗng, không chứa path/ký tự lệnh và có định dạng mã hợp lệ. Với batch, tổng số ticker tối đa là 10.

### JSON không parse được

Kiểm tra bằng:

```powershell
Get-Content PATH_TO_FILE.json -Raw -Encoding UTF8 | ConvertFrom-Json
```

Nếu file do builder tạo bị hỏng, giữ file để chẩn đoán và tạo package mới bằng tên khác sau khi dry-run pass. Không sửa tay JSON dữ liệu để che lỗi.

## Lỗi validation và dữ liệu

### Strict validation fail

Strict fail có thể là kết quả dự kiến khi còn `missing_sections` hoặc `not_fully_confirmed`. Đọc danh sách lỗi cụ thể. Chỉ dùng non-strict khi tác vụ không phụ thuộc phần thiếu và mọi cảnh báo được giữ trong output.

Không xóa `news_summary`, shareholder warning hay unit warning để ép strict pass.

### `news_summary` bị missing

Không có canonical ticker mapping an toàn cho news trong v1.0. Để section ở trạng thái missing/unknown. Không yêu cầu AI tự nối tin theo tên công ty hoặc kiến thức ngoài package.

### `shareholder_summary` bị missing

Ghi `Unknown/Unavailable`. Nếu section có dữ liệu, vẫn phải nhớ dữ liệu cổ đông là snapshot và không có lịch sử đầy đủ.

### BCTC không rõ đơn vị hoặc scale

Dừng so sánh/cộng/trừ các số tiền phụ thuộc. Chỉ mô tả coverage hoặc giá trị raw kèm cảnh báo khi phù hợp. Không tự đoán tỷ đồng/triệu đồng và không trộn scale VCI/KBS.

### Giá hoặc return có vẻ không khớp nguồn khác

Kiểm tra ngày, provider, phương pháp return và cảnh báo adjusted-price. Giá có thể chưa fully adjusted cho cổ tức/split. Không tự sửa chuỗi giá hoặc gọi khác biệt là lỗi nếu chưa xác minh định nghĩa.

### Metadata hoặc cổ đông được dùng cho quá khứ

Dừng kết luận lịch sử. Đây là snapshot hiện tại. Muốn backtest cần dữ liệu point-in-time có availability được chứng minh; v1.0 không tự cung cấp lịch sử dimension này.

### Sentinel bị hiểu thành số thật

- `-1`: thường là missing sau query.
- `NULL`: xử lý theo field/context.
- Boolean CSV: có thể là chuỗi.
- `margin_status` rỗng: theo quy ước là không có cờ margin.

Yêu cầu AI đọc `metadata/data_quality_rules.json`; không đổi missing thành 0.

### Package có vẻ cũ

So sánh `generated_at`, latest price date, financial period và yêu cầu cutoff. Đọc `staleness_report`/`rebuild_decision`, nhưng kiểm tra `generated_at` của chính báo cáo vì chúng cũng có thể cũ. Chạy builder dry-run; chỉ tạo package mới khi có nhu cầu và dùng tên versioned.

## Lỗi khi dùng ChatGPT/Claude/Codex (Gemini deprecated 2026-07-17 — xem docs/v1_0_DailyWorkflow.md mục D)

### Nền tảng báo quá giới hạn file

Ưu tiên các reference bắt buộc trong `upload_manifest.json` và package của task. Giảm file optional hoặc chia Project hợp lý. Không nén/upload raw VNSTOCK để vượt quy trình.

### AI bỏ qua warnings hoặc dữ liệu thiếu

Yêu cầu dừng phân tích và in validation preamble gồm `generated_at`, latest dates, validation, missing, warnings, not-fully-confirmed và provenance. Nếu vẫn sai, mở chat mới với đúng `project_instructions.md`.

### AI bịa số hoặc dùng kiến thức ngoài package

Không chấp nhận câu trả lời. Nhắc AI chỉ dùng Project Knowledge và context package đính kèm, chỉ ra số nào không có provenance, rồi yêu cầu làm lại. Không hợp thức hóa số bịa bằng cách thêm vào package.

### AI đưa khuyến nghị mua/bán hoặc giá mục tiêu

Từ chối output và yêu cầu viết lại thành mô tả dữ liệu, rủi ro, unknown và kịch bản không dự báo chắc chắn. Kiểm tra `operating_pack/common/system_instructions.md` đã được áp dụng.

### AI trộn hai package khác cutoff

Mở chat mới hoặc loại package không đúng. So sánh chỉ khi thời gian/kỳ/đơn vị tương thích; nếu không, đánh dấu `Not comparable`.

### Screening biến thành xếp hạng đầu tư

Nhắc lại universe, tiêu chí và pass/fail/unknown. Xóa yêu cầu “mã tốt nhất”, expected return hoặc buy/sell. Screening là bộ lọc dữ liệu trong các package đính kèm.

## Lỗi QA và release

### Final QA hoặc operating pack validation fail

Đọc issue được in ra, dừng upload/analysis phụ thuộc và không freeze/phát hành artefact mới. Chạy lại dry-run sau khi lỗi được xử lý trong một phiên bản được phê duyệt.

### Checksum `release/v1.0` không khớp

Snapshot không còn giống v1.0 đã freeze. Không cập nhật checksum để che khác biệt. Khôi phục file đúng từ bản sao tin cậy hoặc tạo release/version mới theo quy trình change control.

### Tài liệu v1.0.1 không nằm trong checksum v1.0

Đây là chủ đích: documentation patch nằm ngoài snapshot frozen. Nó không thay đổi manifest, inventory hay checksum của `release/v1.0`.

## Khi nào phải dừng

Dừng tác vụ và không suy luận tiếp khi:

- JSON invalid hoặc provenance không có.
- Field cần thiết missing/unverified.
- Đơn vị, kỳ hoặc định nghĩa không tương thích.
- Yêu cầu đòi sửa nguồn VNSTOCK hoặc snapshot frozen.
- Yêu cầu đòi chạy crawler/pipeline ngoài phạm vi.
- Yêu cầu đòi khuyến nghị mua/bán, giá mục tiêu hay cam kết lợi nhuận.

## Known Limitations

Troubleshooting chỉ bao phủ lỗi đã biết của v1.0 và không thay thế điều tra upstream. Một lỗi mới, side effect không quan sát được hoặc thay đổi UI nền tảng có thể cần quy trình/version mới.

## How AI Should Use This

AI phải nêu symptom, bằng chứng và bước an toàn tương ứng; không tự sửa nguồn, snapshot frozen hoặc dữ liệu để làm lỗi biến mất. Khi bằng chứng không đủ, AI phải dừng và báo unknown.
