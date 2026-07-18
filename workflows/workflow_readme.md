# AI Workflow Scaffolding

## Chọn workflow

- Dùng `ticker_analysis_workflow.json` khi chuẩn bị phân tích một mã: validate → coverage → context → validation → AI response.
- Dùng `screening_workflow.json` để thiết kế fundamental, technical, data-readiness hoặc risk screen; Phase 4 không chạy screen.
- Dùng `data_audit_workflow.json` để lập kế hoạch kiểm tra chất lượng read-only.

## Validation không được bỏ qua

Workflow chỉ được chuyển bước khi validation bắt buộc đã pass hoặc được ghi `unknown/partial` cùng warning. Không được xóa missing, conflict hoặc point-in-time warning để làm context “sạch” hơn.

## An toàn

Mọi workflow cấm ghi VNSTOCK, chạy crawler/pipeline, cập nhật DB, bịa số và tạo khuyến nghị mua/bán chắc chắn. Builder Phase 4 chỉ tạo skeleton nếu chưa có adapter dữ liệu thật.

## Provenance / Source Basis

Các workflow dựa trên Phase 2 AnalysisGuide/AIUsageRules và Phase 3 context/validation specifications.

## Known Limitations

- Đây là JSON workflow specification, chưa có orchestrator.
- Per-ticker coverage và real-data adapters chưa triển khai.
- Screening/audit không được thực thi trong Phase 4.

## How AI Should Use This

AI chọn đúng workflow theo mục tiêu, thực hiện theo thứ tự và giữ nguyên validation status. Không xem `status=scaffold_only/design_only` là một workflow đã chạy thành công.
