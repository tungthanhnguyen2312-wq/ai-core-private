<a id="ai-analyze--consumer-contract-layer"></a>
# AI ANALYZE — Lớp hợp đồng Consumer

AI ANALYZE là Consumer hoạt động theo nguyên tắc fail-closed của Stock Lookup.
Đầu vào thông thường là gói bàn giao bất biến từ Producer
(`ai_research_session_bundle/v1`) cùng các artifact tính toán tất định được tham
chiếu rõ ràng. Consumer kiểm tra và bảo toàn các hợp đồng đã được xác nhận đủ
điều kiện để con người nghiên cứu với AI trong ChatGPT, Codex hoặc một giao diện
AI khác đã được phê duyệt.

`stock-core-private` là Producer, nắm authority về dữ kiện và số liệu. DNSE là
định hướng nguồn dữ liệu thị trường hiện tại chủ đạo của Producer. Repository
này không thu thập dữ liệu thị trường, tạo authority cho nguồn, nâng mức độ mới
của dữ liệu hay biến nội dung do AI viết thành khuyến nghị.

<a id="start-here"></a>
## Bắt đầu tại đây

- Đọc [bản đồ authority hiện tại của Consumer](docs/current_consumer_authority_map.md).
- Với gói bàn giao Daily hiện tại, dùng
  `builders/canonical_daily_producer_session_ingestion.py` với một
  `run_manifest.json` được chỉ định rõ và đã lưu giữ; công cụ chỉ phân giải các
  file bàn giao bất biến nằm cùng vị trí, không bao giờ tự chọn lần chạy “mới nhất”.
- Dùng [thư viện prompt](prompts/ai_analysis_templates.md) và
  [bộ hướng dẫn vận hành](operating_pack/README.md) sau khi có gói bàn giao.
- Chỉ đọc [tài liệu kế hoạch và vận hành lịch sử](docs/HISTORICAL_DOCUMENTS.md)
  khi cần tái hiện hoặc kiểm toán. Các tài liệu này không thay thế trạng thái
  do Producer quản lý.

<a id="authority-boundary"></a>
## Ranh giới authority

Producer → nghiên cứu tất định từ evidence đủ điều kiện → gói bàn giao AI bất
biến → Consumer kiểm tra và chuyển tiếp nguyên trạng → con người nghiên cứu với AI.

- Dữ kiện, danh tính nguồn, trạng thái độ mới, cấp authority, reason code hoặc
  trạng thái không khả dụng từ Producer đều được bảo toàn như khi nhận.
- `macro_presentation_context/v1` là ngữ cảnh trình bày mang tính mô tả, luôn
  tách biệt với `current_macro_regime/v1`.
- Dòng giao dịch nước ngoài/giá trị từ DNSE, vị thế dòng tiền thị trường rộng
  và mức độ sẵn có của dữ liệu tự doanh là các khái niệm riêng; Consumer không
  gộp chúng.
- Evidence kỹ thuật/shadow không có authority. Không được biến evidence đó
  thành khuyến nghị production, xác suất, mục tiêu hay chỉ dẫn quy mô vị thế.
- Authority còn thiếu cho định giá nội tại hoặc xác định quy mô vị thế vẫn
  được giữ ở trạng thái bị chặn/không khả dụng.
- Diễn giải của AI không có authority: không được tạo quyết định mua/bán,
  mục tiêu, xác suất, lợi nhuận kỳ vọng, phân bổ vốn hoặc số lượng cổ phiếu.

<a id="legacy-and-historical-material"></a>
## Tài liệu cũ và lịch sử

Các gói ngữ cảnh, schema mang tên VNStock, hướng dẫn tải lên nền tảng cũ và
bộ tài liệu Gemini được giữ lại để tái hiện khi còn dữ liệu lưu giữ. Chúng
thuộc `HISTORICAL` hoặc `OPTIONAL_FALLBACK`, không phải luồng Daily thông thường.
Tài liệu Gemini là tư liệu lịch sử/kiểm toán đã ngừng khuyến nghị sử dụng;
Gemini không phải bên thực thi được đề xuất.

<a id="repository-guardrails"></a>
## Nguyên tắc bảo vệ repository

- Không sửa runtime được chọn qua `STOCK_LOOKUP_RUNTIME_ROOT`.
- Không coi đầu vào bị thiếu, null, sentinel, cũ, một phần hoặc bị chặn là
  giá trị hiện tại có thể sử dụng.
- Nêu rõ ranh giới point-in-time, nguồn, đơn vị, thang đo và authority.
- Trạng thái và lộ trình do Producer quản lý vẫn có authority; repository này
  không duy trì một lộ trình Stock Lookup cạnh tranh.
