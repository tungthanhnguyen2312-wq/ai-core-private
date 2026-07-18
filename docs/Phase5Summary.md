# Phase 5 Summary

## File đã sửa

- `builders/build_ticker_context.py`: thêm adapter read-only cho SQLite và CSV streaming.
- `builders/build_ticker_context_config.json`: chuyển output mặc định sang `exports/context_packages/` và ghi source/limitations.

## File đã tạo

- `exports/context_packages/HPG_context.json`
- `exports/context_packages/FPT_context.json`
- `exports/context_packages/VCB_context.json`
- `exports/context_packages/context_validation_report.json`
- `exports/context_packages/context_validation_report.md`
- `docs/Phase5Summary.md`
- `docs/ContextBuilderUsage.md`
- `docs/Phase6Plan.md`

## Dữ liệu đọc được thật

- OHLCV theo ticker từ SQLite read-only.
- Metadata hiện tại theo ticker từ SQLite read-only.
- Shareholder và progress theo ticker từ SQLite read-only.
- `financial_snapshot.csv` bằng streaming filter.
- `screen_snapshot.csv` và `ta_signals.csv` bằng streaming filter.

News ticker-specific không được đọc thành facts vì nguồn không có canonical ticker field. Builder ghi section missing và warning thay vì đoán.

## Validation

Ba package parse hợp lệ, có đủ required sections và provenance. Non-strict pass; strict fail đúng thiết kế vì `news_summary` missing và còn uncertainty được khai báo.

## Những gì chưa chắc chắn

Price adjustment, corporate actions, financial monetary unit/scale, filing publication dates, explicit current trading status và news entity mapping.

## Provenance / Source Basis

Context được tạo ngày 2026-07-13 từ VNSTOCK read-only và Phase 1–4 registries/rules. Không chạy crawler hoặc pipeline.

## Known Limitations

- Return 1m/3m/1y dùng 21/63/252 trading observations, không phải calendar-period matching.
- Financial latest period không đồng nghĩa ngày công bố.
- Context là dữ liệu, không phải investment thesis.

## How AI Should Use This

Dùng package để thử workflow phân tích có kiểm soát, luôn giữ warnings/provenance và không dùng cho backtest nghiêm túc hoặc khuyến nghị chắc chắn.

Phase 6 chưa được bắt đầu.
