# Claude Project Setup

## Project Knowledge đề xuất

Đưa các file knowledge cốt lõi, metadata registries/summary, Phase 3 validation/provenance, workflow docs và chỉ một context package đã validated cho ticker đang xét. Giữ raw data lớn ngoài Project; cung cấp lát cắt có manifest khi cần.

## Project instruction gợi ý

“Follow AIUsageRules, AnalysisGuide, point-in-time rules and provenance standard. Do not invent missing values. Distinguish fact, derived calculation and inference. Never use current metadata/shareholder snapshots in historical backtests.”

## Cách yêu cầu phân tích

“Đọc validation status của `{CONTEXT_FILE}` trước. Phân tích chỉ các section có provenance. Ghi source basis/cutoff, missing/conflicts và confidence. Không đưa khuyến nghị mua/bán chắc chắn.”

## Quản lý context

Thay package khi generated_at/source fingerprint thay đổi; không trộn hai package khác cutoff mà không ghi rõ. Không coi AI report cũ là ground truth.

## Provenance / Source Basis

Dựa trên AI ANALYZE Project Knowledge design; chi tiết Claude Project hiện tại là **not fully confirmed** và có thể thay đổi.

## Known Limitations

- Project file/token limits và retrieval behavior phụ thuộc sản phẩm.
- Knowledge upload không tạo record-level validation.
- Builder Phase 4 chỉ tạo skeleton.

## How AI Should Use This

Claude phải giữ warnings/provenance trong câu trả lời và dừng suy luận khi section cần thiết là missing/unverified.
