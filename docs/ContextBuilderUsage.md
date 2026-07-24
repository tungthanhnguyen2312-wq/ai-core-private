# Context Builder Usage

## Dry-run một ticker

```powershell
Set-Location <consumer-repository>
python builders/build_ticker_context.py --ticker HPG --dry-run
```

## Tạo context HPG

```powershell
Set-Location <consumer-repository>
python builders/build_ticker_context.py --ticker HPG --no-dry-run
```

Builder từ chối ghi đè file đã tồn tại. Để tạo phiên bản mới, chỉ định tên mới trong thư mục approved:

```powershell
Set-Location <consumer-repository>
python builders/build_ticker_context.py --ticker HPG --output exports/context_packages/HPG_context_v2.json --no-dry-run
```

## Nhiều ticker

```powershell
Set-Location <consumer-repository>
python builders/build_ticker_context.py --ticker HPG --ticker FPT --ticker VCB --output exports/context_packages --dry-run
```

Đổi sang `--no-dry-run` chỉ khi các tên output chưa tồn tại.

## Strict mode

```powershell
Set-Location <consumer-repository>
python builders/build_ticker_context.py --ticker HPG --strict --dry-run
```

Hiện strict mode dự kiến fail do news mapping thiếu và các mục not fully confirmed. Non-strict mode giữ những gap này trong `data_quality`.

## Output

Package gồm identity, metadata, price, financial, valuation inputs, technical, news, shareholder, data quality và provenance. Nó không chứa khuyến nghị đầu tư.

## Warnings và provenance

Đọc `data_quality.missing_sections`, `warnings`, `not_fully_confirmed` trước. Mỗi source adapter thêm source file/dataset, key ticker và transformation. News không được gán ticker bằng suy đoán.

## An toàn

SQLite mở `mode=ro` và `PRAGMA query_only`. CSV được stream/filter. Output chỉ được phép trong `exports/context_packages/`, không ghi đè và không bao giờ ghi VNSTOCK.

## Known Limitations

- Chưa hỗ trợ calendar-exact returns, corporate actions hoặc filing availability dates.
- Không có canonical news entity mapping.
- Unit/scale BCTC chưa fully confirmed.

## How AI Should Use This

Dùng builder để chuẩn bị context data. AI phải phân tích riêng theo knowledge/workflow, giữ distinction fact/derived/inference và không biến output thành khuyến nghị chắc chắn.
