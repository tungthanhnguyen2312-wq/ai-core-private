# Ticker Context Package Specification

## Định nghĩa

Ticker context package là một JSON nhỏ, có thời điểm và provenance, gom đúng lát cắt dữ liệu cần thiết cho một ticker trước khi gửi cho Claude/ChatGPT/Codex (Gemini deprecated khỏi luồng khuyến nghị từ 2026-07-17). Package không thay thế dữ liệu nguồn, không phải báo cáo đầu tư và không được chứa dữ liệu không xác minh.

## Mục tiêu

- Giảm context/token so với đọc DB hoặc CSV đầy đủ.
- Đồng bộ ticker, cutoff date, kỳ BCTC và missing rules.
- Tách fact, derived field, proxy và warning.
- Cho phép truy ngược nguồn và transformation.

## Sections

### `identity`

Ticker chuẩn hóa, exchange, industry, trạng thái active/delisted nếu xác minh được và analysis cutoff.

### `metadata`

Current point-in-time metadata: vốn hóa, room ngoại, free-float proxy, margin status và updated time. Không dùng section này làm historical dimension.

### `price_summary`

Latest valid OHLCV date, close, liquidity, return windows, range/coverage và adjustment warning. Không cần chứa toàn bộ time series.

### `financial_summary`

Các kỳ được chọn, reported/processed measures, ratios, period type, unit status và latest financial period. Ghi riêng derived/proxy.

### `valuation_inputs`

Chỉ chứa inputs đủ provenance: price/market cap, earnings, equity, debt, cash, shares. Không tự tính multiple nếu đầu vào thiếu hoặc sai kỳ.

### `technical_summary`

RSI/MACD/MA flags, returns, structure, volume và candle/SMC signals tại ngày hợp lệ. Parse boolean string/list trước khi đóng gói.

### `news_summary`

Tin đã chọn theo thời gian và source. Mọi ticker linkage phải có method/confidence hoặc ghi `unlinked`.

### `shareholder_summary`

Snapshot hiện tại, `updated_at`, source `as_of_date`, coverage/progress và cảnh báo no-history. Phase 6 bổ sung `status`, `reason`, `attempts`, `sources_attempted`, `freshness`, `manual_override_count` và provenance trên từng holder; các trường cũ như `major_shareholders_count`, `top_holders`, `progress_status` vẫn giữ nguyên. `source_empty`/`not_queried` không được chuyển thành số cổ đông bằng 0.

### `risks`

Chỉ là data/business risk facts hoặc flags đã có nguồn; không tạo investment thesis.

### `data_quality`

Missing sections, stale checks, conflicts, unit uncertainties, sentinel normalization và validation status.

Từ schema `1.4.0`, validation theo mục đích có `validation_profile` và `profile_validation_status`. Field `validation_status`/`valid` cũ tiếp tục mang nghĩa structural compatibility; consumer mới phải dùng `schema_valid` và `profile_valid` trong coverage report. Xem `docs/context_validation.md` và `docs/context_coverage.md`.

### `provenance`

Một record cho mỗi source/transformation: source file/dataset, keys, cutoff, generated_at, assumptions và limitations.

## Provenance / Source Basis

Specification dựa trên `metadata/datasets.json`, `metadata/schema_registry.json`, `metadata/data_quality_rules.json`, `knowledge/AIUsageRules.md` và Phase 3 summary files.

## Known Limitations

- Spec không xác nhận availability cho ticker cụ thể.
- News entity linking và BCTC publication date chưa có canonical source.
- Context package có thể stale; phải rebuild theo update rule.

## How AI Should Use This

AI chỉ đọc package sau khi validation pass/partial status được ghi rõ. Mọi section missing phải giữ missing, không được model tự bổ sung. Khi cần chi tiết ngoài package, truy vấn nguồn theo provenance thay vì đoán.
