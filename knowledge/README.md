# AI ANALYZE — Project Knowledge

## Mục tiêu

AI ANALYZE là lớp tri thức và quản trị ngữ nghĩa bao quanh dữ liệu VNSTOCK. Mục tiêu là giúp Claude, ChatGPT và Codex chọn đúng dataset, hiểu đúng grain, đơn vị, thời gian và giới hạn dữ liệu trước khi phân tích chứng khoán Việt Nam. (Gemini deprecated khỏi luồng khuyến nghị từ 2026-07-17 — xem `operating_pack/README.md`.)

AI ANALYZE không thay thế pipeline VNSTOCK, không phải kho dữ liệu giao dịch mới và không tự động xác nhận tính đúng của dữ liệu nguồn.

## Quan hệ giữa VNSTOCK và AI ANALYZE

- Dashboard runtime được chọn bởi `STOCK_LOOKUP_RUNTIME_ROOT` là nguồn runtime: SQLite, CSV/Parquet đã materialize, Quant/AI output và dashboard; crawler cùng source code thuộc Producer repository, không thuộc runtime này.
- `project_discovery/` là ảnh chụp khám phá read-only về cấu trúc, schema, module, lineage và chất lượng.
- `metadata/` là lớp machine-readable: registry dataset, schema, quan hệ và quy tắc chất lượng.
- `knowledge/` là lớp hướng dẫn dùng cho AI và con người: từ điển, quy trình phân tích, công thức, quy ước và prompt.
- `summary/` trong tương lai có thể chứa context đã lọc theo ticker/ngày/kỳ. Thư mục này chưa được tạo trong Phase 2.

```text
VNSTOCK data/code
      ↓ discovery and semantic mapping
project_discovery → metadata → knowledge
                              ↓ future
                        filtered summary layer
```

## Cách AI nên sử dụng thư mục này

1. Đọc `AIUsageRules.md` và `MarketConvention.md` để nắm giới hạn bắt buộc.
2. Dùng `DataDictionary.md` để chọn dataset và hiểu grain.
3. Dùng `AnalysisGuide.md` cho trình tự phân tích.
4. Dùng `Formula.md` khi cần tính hoặc kiểm tra chỉ tiêu.
5. Dùng `DataLineage.md` để truy ngược nguồn và phát hiện sai lệch.
6. Đối chiếu registry JSON trong `metadata/` trước khi lập trình hoặc tự động hóa.
7. Chỉ nạp lát cắt dữ liệu cần thiết; không đưa toàn bộ DB, OHLCV CSV hoặc kho BCTC vào context LLM.

## Nguyên tắc an toàn dữ liệu

- Chỉ đọc VNSTOCK khi được phép; không sửa code, DB hay dữ liệu nguồn trong quy trình phân tích.
- Luôn nêu ticker, ngày snapshot, kỳ BCTC và nguồn dataset của số liệu.
- Phân biệt fact, phép tính dẫn xuất, inference và opinion.
- Không biến missing thành 0; áp dụng sentinel theo từng field.
- Không dùng snapshot hiện tại làm dữ liệu lịch sử.
- Không khẳng định khuyến nghị mua/bán hoặc lợi nhuận chắc chắn.
- Bảo toàn UTF-8 và tiếng Việt.

## Known Limitations

- Metadata phản ánh discovery ngày 2026-07-13; coverage và freshness có thể thay đổi sau đó.
- Chưa xác minh trực tiếp giá đã fully adjusted cho cổ tức/chia tách.
- News không có ticker mapping chính thức.
- Cổ đông và metadata doanh nghiệp là point-in-time.
- `free_float_est` là proxy.
- Một số schema trong registry được mô tả theo nhóm field; chi tiết ngoài discovery là **not fully confirmed from current metadata**.

## How AI Should Use This

Xem bộ tài liệu này là hợp đồng sử dụng dữ liệu, không phải dữ liệu thị trường. Khi tài liệu và dữ liệu thực tế mâu thuẫn, AI phải dừng suy diễn, nêu mâu thuẫn, trích đường dẫn/tên dataset nội bộ và yêu cầu kiểm tra thay vì tự chọn kết quả thuận tiện.
