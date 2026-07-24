# Folder Structure and Access Policy

## Cấu trúc hiện tại

| Thư mục | Vai trò | AI nên đọc? | Ghi? | Rủi ro dùng sai |
|---|---|---|---|---|
| Dashboard runtime được chọn bởi `STOCK_LOOKUP_RUNTIME_ROOT` | Runtime DB, dữ liệu đã materialize, reports, generated artifacts và frontend đã publish | Chỉ đọc có chọn lọc khi được phép | Không trong workflow knowledge | Sửa runtime, chạy crawler, bulk-load dữ liệu lớn hoặc dùng output stale. |
| `project_discovery/` | Tám tài liệu discovery read-only | Có, để hiểu hệ thống | Không | Thống kê là snapshot tại ngày discovery, có thể không còn mới. |
| `metadata/` | Registry JSON và context machine-readable | Có, đọc trước dữ liệu | Không trong Phase 2 | Bỏ qua missing rule hoặc coi summary ticker là enumeration đầy đủ. |
| `knowledge/` | Project Knowledge chính thức cho AI | Có | Chỉ tạo file theo phase được duyệt | Tài liệu không phải market data hoặc ground truth. |

## Các thư mục tương lai đề xuất

Các thư mục dưới đây chưa được tạo và không thuộc Phase 2:

| Thư mục | Vai trò dự kiến | Chính sách đề xuất | Rủi ro |
|---|---|---|---|
| `summary/` | Context đã lọc theo ticker/ngày/kỳ | AI đọc; pipeline kiểm soát ghi | Stale snapshot, mất provenance. |
| `company/` | Hồ sơ chuẩn hóa theo ticker | Đọc theo ticker; versioned write | Trộn point-in-time với lịch sử. |
| `reports/` | Báo cáo AI/analyst có timestamp | Đọc như derived output | Nhầm opinion với fact. |
| `prompts/` | Prompt templates dạng file | Đọc và version | Prompt không thay thế validation. |
| `exports/` | Gói dữ liệu xuất cho model/tool | Chỉ đọc export có manifest | Lộ dữ liệu không cần thiết, mất unit hoặc encoding. |

## Các vùng chính trong VNSTOCK

- `vn_stock.db`: query chọn lọc, không nạp nguyên file.
- Root CSV/Parquet: ưu tiên Parquet cho lọc cục bộ; snapshot CSV cho context nhỏ.
- `data_bctc/`: chỉ đọc theo ticker/report cần thiết.
- `data/` và frontend: presentation output, không phải nguồn ưu tiên.
- `docs/`: tài liệu kỹ thuật, không phải dữ liệu thị trường.
- `logs/`: chỉ dùng chẩn đoán vận hành.

## Known Limitations

- Cấu trúc tương lai chỉ là đề xuất, chưa tồn tại.
- Policy ghi có thể thay đổi theo phase sau; tài liệu này không cấp quyền filesystem.
- Cây VNSTOCK có thể thay đổi sau discovery.

## How AI Should Use This

AI phải kiểm tra quyền được cấp trong yêu cầu hiện tại. Biết vị trí file không đồng nghĩa được phép ghi hoặc chạy nó. Ưu tiên metadata/knowledge để chọn nguồn rồi mới đọc lát cắt VNSTOCK thật sự cần.
