# Proposed Phase 6 Plan

## Phạm vi đề xuất

1. Mở rộng builder cho danh sách ticker/batch manifest có giới hạn.
2. Thêm source fingerprints, generated run manifest và incremental rebuild.
3. Implement validation engine đầy đủ và test tự động.
4. Tạo AI analysis templates chỉ dùng context package đã validated.
5. Test cùng Gemini, Claude và ChatGPT, so sánh mức tuân thủ provenance/missing rules.
6. Không tạo hoặc tự động hóa khuyến nghị đầu tư.

## Điều kiện cần duyệt riêng

Batch size, ticker universe, quyền đọc nguồn, naming/version policy, model/provider được test, token/data privacy constraints và tiêu chí đánh giá output.

## Provenance / Source Basis

Đề xuất dựa trên gap của Phase 5: news mapping, strict validation, fingerprints, batch orchestration và model testing.

## Known Limitations

- Chưa có approval, code hoặc test cho Phase 6.
- Publication dates/corporate actions vẫn cần nguồn được xác nhận.
- Model product behavior có thể thay đổi.

## How AI Should Use This

Chỉ dùng để lập kế hoạch và xin duyệt. Không tự bắt đầu batch build, model testing hoặc Phase 6.
