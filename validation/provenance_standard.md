# Internal Provenance Standard

## Trường bắt buộc

Mỗi summary/context package phải ghi:

- `source_file`: đường dẫn file hoặc DB.
- `source_dataset`: table/view/logical dataset.
- `source_keys`: ticker/series/link và date/period khi có.
- `generated_at`: ISO 8601 có timezone.
- `transformation`: filter, join, parse, aggregate hoặc formula đã dùng.
- `assumptions`: unit, cutoff, provider scale, proxy/TTM assumptions.
- `limitations`: freshness, missing, point-in-time và uncertainty.

Record summary nên ghi thêm `field`, `unit`, `reported_or_derived`, `rules_version` và source update/date.

## Dạng citation nội bộ

`[source_file::source_dataset | keys | field | date/period | unit | reported/derived]`

Ví dụ cấu trúc, không phải dữ liệu thật:

`[vn_stock.db::ohlcv | ticker=SAMPLE,date=YYYY-MM-DD | close | YYYY-MM-DD | VND | reported]`

## Transformation chain

Không ghi đơn giản “VNSTOCK” nếu số đã đi qua processor. Ghi chuỗi tối thiểu, ví dụ: `raw BCTC item → item_id mapping → ticker-period reshape → derived ratio`.

## Khi dữ liệu mâu thuẫn

1. Kiểm tra key, grain, kỳ, unit, provider và reported/derived.
2. Ưu tiên raw/source gần nhất chỉ khi cùng định nghĩa và grain.
3. Processed value có thể được ưu tiên cho sử dụng chuẩn hóa nhưng phải giữ raw discrepancy.
4. Dashboard/AI/Quant output không thắng dữ liệu nguồn chỉ vì mới hoặc dễ đọc.
5. Nếu chưa giải quyết, lưu cả hai giá trị và ghi `unresolved_conflict`.
6. Không lấy trung bình, không chọn số “đẹp hơn”, không xóa conflict.

## Freshness và version

`generated_at` không thay cho source date. Artifact phải ghi cả hai. Khi source thay đổi, provenance cũ vẫn mô tả phiên bản cũ; builder tương lai nên dùng fingerprints/checksums hoặc run IDs.

## Provenance / Source Basis

Chuẩn này tổng hợp từ Phase 1 lineage, Phase 1.5 registries và Phase 2 AI usage rules.

## Known Limitations

- VNSTOCK hiện chưa có record-level run ID/checksum lineage xuyên pipeline.
- Effective dates và publication dates còn thiếu ở một số domain.
- Citation convention không tự kiểm chứng nội dung source.

## How AI Should Use This

AI phải giữ provenance sát claim/số liệu. Nếu package thiếu provenance cho một field, coi field đó là unverified và không dùng cho kết luận quan trọng.
