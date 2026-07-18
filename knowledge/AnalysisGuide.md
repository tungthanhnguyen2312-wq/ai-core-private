# Analysis Guide

## Phạm vi

Hướng dẫn này áp dụng cho phân tích đầu tư hiện tại và nghiên cứu lịch sử. Hai mục đích phải được tách rõ để tránh look-ahead bias.

## Quy trình chuẩn

### 1. Xác định ticker và phạm vi thời gian

Chuẩn hóa ticker uppercase. Nêu rõ phân tích tại ngày nào, dùng lịch sử bao lâu, BCTC đến kỳ nào và câu hỏi là hiện tại hay backtest.

### 2. Kiểm tra dữ liệu có sẵn

Kiểm tra lần lượt price, metadata, financial, shareholder và signals. `ticker_registry.json` chỉ là contract summary; availability thực tế cần query dataset. Không coi thiếu dòng là giá trị 0.

### 3. Đọc metadata doanh nghiệp

Lấy sàn, ngành, vốn hóa, định giá, room ngoại, free-float proxy và margin status từ `metadata` hoặc snapshot. Không nhầm với `meta`. Gắn nhãn point-in-time.

### 4. Đọc giá và thanh khoản

Dùng OHLCV đã lọc theo ticker/ngày. Kiểm tra tính liên tục, corporate actions, thanh khoản 20 phiên, relative volume, xu hướng và drawdown. Với phân tích live, yêu cầu ngày của ticker bằng ngày snapshot mới nhất.

### 5. Đọc BCTC / financial snapshot

Ưu tiên `financial_snapshot` cho phân tích nhiều kỳ. Dùng BCTC raw chỉ để đối chiếu một chỉ tiêu hoặc nguồn. Không join hai lớp như cùng grain.

### 6. Đọc chỉ số tài chính

Đánh giá tăng trưởng, margin, ROA/ROE, đòn bẩy, thanh khoản, turnover và chất lượng dòng tiền. Xác minh mẫu số, đơn vị, annual/quarter và TTM trước so sánh.

### 7. Đọc macro khi liên quan

Chọn series theo cơ chế tác động: lãi suất, tỷ giá, giá hàng hóa, CPI hoặc thị trường quốc tế. Căn chỉnh ngày và tần suất; không coi dữ liệu năm là dữ liệu ngày.

### 8. Đọc news khi liên quan

Phân nhóm catalyst, regulation, earnings, corporate action và risk. News không có ticker mapping chính thức; việc liên kết là inference và phải được ghi nhãn.

### 9. Đọc shareholder khi liên quan

Đánh giá mức tập trung hiện tại và free-float proxy. Không suy ra thay đổi sở hữu nếu không có chuỗi lịch sử.

### 10. Đọc technical/quant signals khi liên quan

Dùng technical snapshot và `ta_signals` làm tín hiệu xác suất. Đối chiếu giá/khối lượng thực tế. Quant/AI outputs là dẫn xuất, không thay thế dữ liệu nguồn.

### 11. Khung đánh giá

- **Business:** ngành, mô hình kinh doanh và drivers; thông tin chi tiết ngoài dataset có thể thiếu.
- **Growth:** doanh thu/lợi nhuận YoY, QoQ, CAGR; phân biệt base effect.
- **Profitability:** gross/operating/net margin, ROA, ROE và tính bền vững.
- **Balance sheet:** tiền, nợ, vốn chủ, vốn lưu động và thanh khoản.
- **Cash flow:** OCF, capex, FCF, chuyển đổi lợi nhuận thành tiền.
- **Valuation:** P/E, P/B và chỉ tiêu khác chỉ khi đủ đầu vào, cùng kỳ và unit.
- **Technical:** xu hướng, momentum, volatility, volume, market structure.
- **Catalyst:** BCTC, chính sách, ngành, corporate events; ghi rõ fact/inference.
- **Risk:** dữ liệu, kinh doanh, tài chính, thanh khoản, định giá, kỹ thuật và governance.

### 12. Kết luận xác suất

Tổng hợp bằng kịch bản tích cực/cơ sở/tiêu cực, điều kiện xác nhận và invalidation. Không khẳng định chắc chắn; không đưa lợi nhuận mục tiêu nếu không có phương pháp và đầu vào rõ.

## Phân tích hiện tại và backtest

| Nội dung | Phân tích hiện tại | Backtest lịch sử |
|---|---|---|
| Metadata hiện tại | Có thể dùng, ghi ngày | Không dùng cho ngày quá khứ |
| Shareholder snapshot | Có thể dùng, ghi ngày | Không dùng |
| OHLCV | Dùng đến ngày cutoff | Chỉ dùng dữ liệu có sẵn tại từng thời điểm |
| Financial statements | Dùng kỳ mới nhất công bố | Cần ngày công bố/availability; hiện chưa xác nhận đầy đủ |
| News | Dùng theo `published_utc` | Chỉ dùng tin đã xuất bản trước cutoff |
| Technical signals | Dùng snapshot hiện tại | Phải tính lại point-in-time; không dùng snapshot mới nhất |

## Quy tắc trả lời

- Nêu data cutoff và nguồn nội bộ.
- Không bịa số liệu hay lấp missing.
- Phân biệt reported, derived, proxy và inference.
- Nếu dữ liệu mâu thuẫn, trình bày cả hai giá trị cùng nguồn/kỳ và không tự hòa giải.
- Không khuyến nghị mua/bán chắc chắn; có thể mô tả điều kiện, xác suất và rủi ro.

## Known Limitations

- Chưa có historical metadata/shareholder dimensions.
- Ngày công bố BCTC không hiện diện rõ trong `financial_snapshot`; backtest point-in-time cần xác minh thêm.
- Giá adjusted chưa được xác nhận.
- Dữ liệu business narrative và governance không đầy đủ trong metadata.

## How AI Should Use This

AI nên dùng các bước như checklist bắt buộc, nhưng chỉ mở dataset liên quan câu hỏi. Nếu không hoàn thành được bước vì thiếu dữ liệu, phải ghi rõ thiếu gì và ảnh hưởng tới kết luận.
