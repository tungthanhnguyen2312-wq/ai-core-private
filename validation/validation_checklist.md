# Ticker Analysis Validation Checklist

## Trước khi đọc số liệu

- [ ] Ticker không rỗng, uppercase và được tìm thấy trong nguồn phù hợp.
- [ ] Mục đích là current analysis, historical research hay backtest.
- [ ] Analysis cutoff và timezone được ghi.

## Price

- [ ] Có dữ liệu giá không?
- [ ] Latest price date là ngày nào?
- [ ] Latest date của ticker có bằng global latest market date không?
- [ ] Có dấu hiệu stale/delisted/suspend không?
- [ ] OHLCV numeric, volume không âm và OHLC bounds hợp lệ?
- [ ] Adjusted/unadjusted đã xác minh chưa? Nếu chưa, warning đã ghi?

## Metadata

- [ ] Có `metadata` không và không nhầm với `meta`?
- [ ] `updated` là khi nào?
- [ ] `margin_status` empty được hiểu đúng là no flag?
- [ ] `free_float_est` được gắn nhãn proxy?
- [ ] Metadata point-in-time được loại khỏi backtest?

## Financial

- [ ] Có BCTC/financial snapshot không?
- [ ] Latest financial period là kỳ nào, quarter hay year?
- [ ] Kỳ có nằm trước cutoff nhưng ngày công bố/availability đã biết chưa?
- [ ] Unit/scale có cảnh báo không?
- [ ] Raw BCTC và processed snapshot có bị trộn grain không?
- [ ] Các field mapping cần thiết (EBIT/EBITDA/interest...) đã được xác nhận?
- [ ] Mẫu số 0/âm và missing được xử lý đúng?

## News và shareholder

- [ ] Có news trong window không? Ticker linkage có evidence/confidence?
- [ ] News `published_utc` không vượt cutoff?
- [ ] Có shareholder data không và progress status là gì?
- [ ] Shareholder được gắn nhãn point-in-time/no-history?

## Technical và output dẫn xuất

- [ ] Technical date đúng latest valid date?
- [ ] Boolean strings và signal lists đã parse?
- [ ] Quant/AI outputs chỉ dùng như derived context?

## Data quality và provenance

- [ ] `-1`, NULL và empty được xử lý theo field?
- [ ] Có conflict giữa source/raw/processed/dashboard không?
- [ ] Mỗi số quan trọng có source, key, date/period, field và unit?
- [ ] Missing sections/warnings được giữ trong output?
- [ ] Không có investment recommendation hoặc claim chắc chắn?

## Provenance / Source Basis

Checklist này được tổng hợp từ `validation_rules.json`, Phase 1.5 quality registry và Phase 2 AI usage/market conventions.

## Known Limitations

- Checklist không tự truy vấn hoặc validate dữ liệu.
- “Có news” không đồng nghĩa news liên quan ticker.
- Ngày công bố BCTC và corporate-action source chưa được xác nhận đầy đủ.

## How AI Should Use This

Hoàn thành checklist trước khi phân tích. Mục không kiểm tra được phải trở thành warning/missing limitation, không được model tự đánh dấu pass.
