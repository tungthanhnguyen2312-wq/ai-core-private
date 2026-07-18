# Phase 2 — Knowledge Summary

## Kết quả

Phase 2 đã tạo bộ Project Knowledge chính thức giúp AI hiểu kiến trúc VNSTOCK, chọn dataset, áp dụng công thức, xử lý snapshot/missing và trả lời theo provenance. Không sinh phân tích thị trường mới và không thay đổi VNSTOCK.

## File đã tạo

1. `README.md` — tổng quan AI ANALYZE và cách dùng các lớp tri thức.
2. `DataDictionary.md` — từ điển cấp cao cho price, metadata, financial, macro, news, ownership, technical và outputs.
3. `AnalysisGuide.md` — quy trình phân tích ticker và phân biệt current/backtest.
4. `Formula.md` — công thức tài chính, forensic, kỹ thuật và risk metrics.
5. `MarketConvention.md` — quy ước ticker, sàn, ngày/kỳ, VND, phần trăm, snapshot và adjusted price.
6. `FolderStructure.md` — vai trò, read/write policy và rủi ro theo thư mục.
7. `DataLineage.md` — nguồn → crawler → storage → processor → output.
8. `AIUsageRules.md` — luật đọc dữ liệu, trả lời, provenance và checklist.
9. `PromptLibrary.md` — 16 prompt mẫu cho phân tích, screening, audit và chuẩn bị context.
10. `KnowledgeSummary.md` — tổng kết Phase 2.

## Nguồn đã dùng

- Tám tài liệu trong `project_discovery/`: discovery summary, project tree, file/dataset inventory, module analysis, data relationship, schema summary và quality assessment.
- Mười file Phase 1.5 trong `metadata/`: dataset/schema/module/file/ticker/financial/relationship/quality registries cùng AI context và metadata summary.
- Không cần đọc thêm hoặc sửa bất kỳ file nào trong `../VNSTOCK` cho nội dung Phase 2.

## Giả định

- Metadata và thống kê phản ánh discovery ngày 2026-07-13.
- Đường dẫn VNSTOCK được diễn giải tương đối từ workspace AI ANALYZE.
- `HSX` được giữ nguyên như giá trị exchange trong nguồn; HOSE chỉ là tên gọi diễn giải.
- Công thức trong `Formula.md` là chuẩn tham khảo; không khẳng định implementation của code dùng đúng biến thể nếu chưa được audit.
- AI luôn được cung cấp hoặc được phép đọc lát cắt dữ liệu cần thiết trước phân tích.

## Điểm chưa chắc chắn

- Giá đã fully adjusted hay chưa.
- Unit chi tiết của mọi chỉ tiêu BCTC raw.
- Mapping đầy đủ cho EBIT, EBITDA, interest expense, retained earnings, depreciation và SG&A.
- Ngày công bố/availability point-in-time của BCTC cho backtest.
- Canonical ticker mapping của news.
- Lịch sử metadata doanh nghiệp và cổ đông hiện không có.
- Chi tiết nested schema của một số output Quant/AI là **not fully confirmed from current metadata**.

## Cần kiểm tra thủ công

- Corporate actions trước khi tính return dài hạn/backtest.
- Scale và unit khi đối chiếu VCI/KBS hoặc raw/processed BCTC.
- Mã stale/delisted trước phân tích live.
- Các chỉ tiêu forensic/valuation nâng cao chỉ khi mapping đầu vào đầy đủ.
- Mâu thuẫn giữa raw source, snapshot, dashboard và derived report.

## Đề xuất Phase 3

Nếu được duyệt riêng, Phase 3 có thể tạo summary layer có manifest/provenance, validation schema tự động, context package theo ticker và kiểm tra coverage/freshness. Nên thiết kế point-in-time discipline trước mọi chức năng backtest. Phase 3 chưa được bắt đầu.

## Known Limitations

- Tài liệu là semantic guidance, không tự validate record hoặc freshness.
- Không có kết quả phân tích ticker cụ thể trong Phase 2.
- Đề xuất Phase 3 không phải authorization để tạo thêm file hoặc chạy pipeline.

## How AI Should Use This

Dùng file này để xác định phạm vi và trạng thái hoàn thành; dùng các tài liệu chuyên biệt cho quyết định thực tế. Khi có yêu cầu mới, AI phải kiểm tra phase/quyền được cấp thay vì tự tiếp tục Phase 3.
