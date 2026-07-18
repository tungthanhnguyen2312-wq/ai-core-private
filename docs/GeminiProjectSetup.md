# Gemini Project / Gem Setup

> **[DEPRECATED 2026-07-17]** Gemini không còn nằm trong luồng khuyến nghị — xem
> `operating_pack/gemini/workflow.md` và `docs/v1_0_DailyWorkflow.md` mục D. File này được giữ
> nguyên làm lịch sử/audit trail, không dùng để thiết lập tác vụ mới.

## File nên đưa vào Project Knowledge

- Các tài liệu cốt lõi trong `knowledge/`: README, DataDictionary, AnalysisGuide, Formula, MarketConvention, DataLineage, AIUsageRules.
- Metadata summary/registry cần thiết, ưu tiên `metadata_summary.md`, datasets/schema/quality registries.
- `summary/summary_layer_readme.md` và các coverage/freshness summaries có cutoff rõ.
- `validation/` và workflow docs.
- Một ticker context package đã validated khi phân tích ticker cụ thể.

Không upload toàn bộ DB, OHLCV CSV, kho BCTC raw hoặc dữ liệu nhạy cảm nếu không cần.

## Instruction gợi ý

“Chỉ dùng facts trong context package và Project Knowledge. Ghi cutoff/provenance, tách fact/derived/inference, giữ missing/warnings, không dùng snapshot cho backtest và không đưa khuyến nghị chắc chắn.”

## Cách hỏi theo context package

“Dựa duy nhất trên package `{FILE}` và Project Knowledge, kiểm tra validation status trước. Nếu package chỉ là scaffold hoặc thiếu section, dừng phần phụ thuộc dữ liệu đó. Trình bày phạm vi, facts có nguồn, risks và limitations; không bịa số.”

## Provenance / Source Basis

Hướng dẫn dựa trên cấu trúc AI ANALYZE; chi tiết UI/tính năng Gemini hiện tại là **not fully confirmed** và có thể thay đổi.

## Known Limitations

- Giới hạn file/token và Project/Gem UI phụ thuộc phiên bản sản phẩm.
- Upload file không tự đảm bảo model tuân thủ validation.
- Phase 4 chưa có context package thật.

## How AI Should Use This

Gemini phải ưu tiên validation/knowledge hơn prompt tùy hứng, và coi context scaffold/sample là không có dữ liệu thật.
