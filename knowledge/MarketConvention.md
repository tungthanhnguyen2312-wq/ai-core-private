# Vietnam Market Conventions

## Ticker và sàn

- Ticker được chuẩn hóa uppercase, thường 3–4 ký tự.
- Giá trị exchange trong metadata: `HSX`, `HNX`, `UPCOM`, `DELISTED`.
- HSX trong dữ liệu tương ứng HOSE theo cách gọi phổ biến. Không tự đổi mã sàn trong dữ liệu nguồn.
- Tồn tại trong OHLCV không chứng minh ticker còn giao dịch.

## Thời gian

- Ngày giao dịch: `YYYY-MM-DD`.
- Kỳ quý: `YYYY-QX`, ví dụ `2026-Q1`.
- `period_type`: `quarter` hoặc `year`.
- News dùng `published_utc`; cần đổi timezone rõ ràng nếu trình bày giờ Việt Nam.
- `updated`, `updated_at`, `scraped_at` là thời điểm vận hành/thu thập, không nhất thiết là ngày hiệu lực kinh tế.

## Tiền tệ và đơn vị

- OHLCV được mô tả là VND và pipeline đã scale giá ×1000.
- BCTC có thể dùng đồng, nghìn, triệu hoặc tỷ đồng tùy nguồn/field. AI phải kiểm tra unit trước khi cộng, chia hoặc so sánh.
- `gtgd20_ty` là tỷ VND mỗi phiên.
- `market_cap` được mô tả là VND.
- Nếu unit chi tiết không có trong metadata, ghi **not fully confirmed from current metadata**.

## Phần trăm và tỷ lệ

- Các field tên `_pct`, margin, growth, ROE/ROA thường biểu diễn phần trăm, nhưng phải kiểm tra registry.
- `free_float_est` là fraction 0..1, không phải percent 0..100.
- `foreign_room_pct` là phần trăm room còn trống; 100 nghĩa là chưa sử dụng room theo mô tả nguồn, không phải tỷ lệ sở hữu ngoại.
- VCI/KBS có thể trả phần trăm raw theo scale 0..1 và 0..100; chỉ dùng dữ liệu đã normalize hoặc xác minh nguồn.
- Với macro series có unit percent, `chg_*` là chênh lệch điểm phần trăm; series khác dùng phần trăm thay đổi.

## Margin status

| Giá trị | Ý nghĩa sử dụng |
|---|---|
| `margin_cut` | Bị cắt margin |
| `warning` | Cảnh báo |
| `control` | Kiểm soát |
| `suspend` | Đình chỉ |
| empty / NULL | Sạch, không có cờ theo quy ước hiện tại |

Đây là cờ rủi ro/trạng thái, không tự động là khuyến nghị mua/bán.

## Free float

`free_float_est` được ước tính từ nhóm cổ đông lớn, không phải free float chính thức. Dùng để định tính/tham khảo thanh khoản và luôn gắn nhãn proxy.

## Adjusted và unadjusted price

Chưa xác nhận 100% nguồn giá đã điều chỉnh cho cổ tức/chia tách. AI phải cảnh báo khi dùng return dài hạn, MA200, drawdown, breakout hoặc backtest quanh corporate actions.

## Snapshot và latest

- `screen_snapshot`, `market_breadth`, `macro_snapshot`, `ta_signals`, `news_latest`, metadata và shareholder đều là các dạng snapshot.
- “Latest” của mỗi ticker/series có thể khác nhau; không lấy max riêng từng ticker rồi mặc nhiên coi cùng market date.
- Phân tích live phải lọc ticker có `date` bằng ngày snapshot thị trường mới nhất.

## Cổ phiếu ngừng giao dịch

Mã chết có thể còn trong snapshot; ASA với ngày 2022-01-21 là ví dụ đã biết. Kiểm tra `date`, `exchange=DELISTED`, margin/trading status và thanh khoản trước khi coi ticker là active.

## Phân tích hiện tại và backtest

- Hiện tại: có thể dùng metadata/shareholder snapshot nếu ghi rõ ngày.
- Backtest: không dùng snapshot hiện tại để mô phỏng quyết định quá khứ; cần point-in-time data.
- BCTC trong backtest phải dùng ngày thông tin thực sự có sẵn, không chỉ kỳ báo cáo. Ngày công bố chưa được xác nhận đầy đủ trong snapshot.
- Technical indicators lịch sử phải được tính lại tại từng cutoff.

## Known Limitations

- Quy tắc biên độ giá, lot size, ngày thanh toán và lịch giao dịch không được xác nhận trong metadata hiện tại nên không được tự bổ sung.
- Mapping HOSE/HSX chỉ là diễn giải tên gọi; giữ nguyên giá trị source khi xử lý.
- Đơn vị chi tiết của BCTC cần kiểm tra theo nguồn.

## How AI Should Use This

AI phải nêu đơn vị, ngày/kỳ và trạng thái snapshot bên cạnh số liệu quan trọng. Không áp dụng kiến thức thị trường bên ngoài như một fact của project nếu metadata chưa xác nhận.
