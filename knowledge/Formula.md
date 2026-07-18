# Financial and Market Formula Reference

## Quy ước áp dụng

Mọi công thức yêu cầu cùng unit, cùng scope hợp nhất/riêng lẻ và kỳ thời gian tương thích. Không tính khi mẫu số bằng 0 hoặc đầu vào thiếu. `-1` sentinel phải đổi thành missing trước phép tính. “TTM” là tổng bốn quý gần nhất khi dữ liệu quý đầy đủ.

## Tăng trưởng và khả năng sinh lời

| Chỉ tiêu | Công thức | Đầu vào | Ý nghĩa và điều kiện | Missing / cảnh báo |
|---|---|---|---|---|
| Revenue Growth | `(Revenue_t / Revenue_base) - 1` | `revenue` cùng kỳ | Tăng trưởng QoQ/YoY theo base phù hợp | Không tính nếu base thiếu/0; base âm làm tỷ lệ khó diễn giải. |
| Net Profit Growth | `(NP_t / NP_base) - 1` | `net_profit` | Tăng trưởng lợi nhuận | Lợi nhuận đổi dấu cần báo số tuyệt đối thay vì chỉ %. |
| CAGR | `(Ending / Beginning)^(1/n) - 1` | giá trị đầu/cuối, số năm `n` | Tốc độ tăng trưởng kép | Chỉ phù hợp khi hai giá trị dương, `n>0`; che giấu biến động giữa kỳ. |
| Gross Margin | `Gross Profit / Revenue` | `gross_profit`, `revenue` | Hiệu quả sau giá vốn | Doanh thu phải khác 0; ngân hàng có thể không phù hợp. |
| Operating Margin | `Operating Profit / Revenue` | `operating_profit`, `revenue` | Hiệu quả hoạt động | Định nghĩa operating profit có thể khác theo ngành/nguồn. |
| Net Margin | `Net Profit / Revenue` | `net_profit`, `revenue` | Lợi nhuận ròng trên doanh thu | Không so ngành có cấu trúc khác nhau một cách máy móc. |
| ROA | `Net Profit / Average Total Assets` | `net_profit`, `total_assets` đầu/cuối kỳ | Sinh lời trên tài sản | Snapshot có thể dùng proxy mẫu số cuối kỳ; ghi rõ nếu không có bình quân. |
| ROE | `Net Profit / Average Equity` | `net_profit`, `equity` đầu/cuối kỳ | Sinh lời cho cổ đông | Equity âm/nhỏ làm chỉ tiêu vô nghĩa hoặc phóng đại; metadata ROE là TTM. |
| ROIC | `NOPAT / Average Invested Capital`; `NOPAT=EBIT×(1-tax rate)` | EBIT, tax, debt, equity, excess cash | Hiệu quả vốn đầu tư | EBIT/tax/invested capital chưa được xác nhận đầy đủ; chỉ tính khi mapping được kiểm chứng. |

## Chỉ tiêu trên cổ phiếu và định giá

| Chỉ tiêu | Công thức | Đầu vào | Ý nghĩa và điều kiện | Missing / cảnh báo |
|---|---|---|---|---|
| EPS | `Net Profit attributable / Weighted Avg Shares` | lợi nhuận thuộc cổ đông, số CP bình quân | Lợi nhuận mỗi CP | `eps_calc` là proxy; shares cuối kỳ không bằng bình quân pha loãng. |
| BVPS | `Equity attributable / Shares Outstanding` | equity, shares | Giá trị sổ sách mỗi CP | Xác minh quyền lợi thiểu số và unit; `book_value` có sẵn nhưng có thể dẫn xuất. |
| P/E | `Price / EPS` hoặc `Market Cap / TTM Earnings` | giá, EPS hoặc vốn hóa/lợi nhuận | Giá trên lợi nhuận | Không có ý nghĩa khi EPS ≤0; đồng bộ ngày giá và kỳ earnings. |
| P/B | `Price / BVPS` hoặc `Market Cap / Equity` | giá/BVPS | Giá trên sổ sách | Equity âm làm chỉ tiêu vô nghĩa; khác biệt ngành lớn. |
| P/S | `Market Cap / TTM Revenue` | market cap, revenue | Giá trên doanh thu | Chưa có field P/S trực tiếp; kiểm tra cùng unit và TTM. |
| EV/EBITDA | `(Market Cap + Debt - Cash) / EBITDA` | vốn hóa, debt, cash, EBITDA | Định giá trước cấu trúc vốn | EBITDA không được xác nhận trong snapshot; chỉ tính khi đủ mapping, tránh EBITDA≤0. |
| Dividend Yield | `Dividend per Share / Price` | DPS và giá | Thu nhập cổ tức | Field hiện hữu là trailing yield; `-1` là missing. DPS raw chưa được xác nhận đầy đủ. |

## Đòn bẩy, thanh khoản và dòng tiền

| Chỉ tiêu | Công thức | Đầu vào | Ý nghĩa và điều kiện | Missing / cảnh báo |
|---|---|---|---|---|
| Debt/Equity | `Debt / Equity` | `debt`, `equity` | Đòn bẩy tài chính | Equity ≤0 cần cảnh báo; định nghĩa debt có thể khác total liabilities. |
| Current Ratio | `Current Assets / Current Liabilities` | hai field tương ứng | Thanh khoản ngắn hạn | CL=0 thì không tính; ít phù hợp một số định chế tài chính. |
| Quick Ratio | `(Current Assets - Inventory) / Current Liabilities` | CA, inventory, CL | Thanh khoản không dựa tồn kho | Không thay missing inventory bằng 0. |
| Interest Coverage | `EBIT / Interest Expense` | EBIT, chi phí lãi vay | Khả năng trả lãi | Interest expense chưa được xác nhận trong snapshot; chỉ tính khi raw mapping rõ. |
| Operating Cash Flow | Dòng tiền thuần từ HĐKD | `operating_cash_flow` | Tiền tạo ra từ hoạt động | Không phải công thức duy nhất; dấu/định nghĩa nguồn phải kiểm tra. |
| Free Cash Flow | `Operating Cash Flow - Capex` | OCF, capex | Tiền sau đầu tư duy trì/mở rộng | Snapshot có `free_cash_flow`; kiểm tra quy ước dấu capex trước tính lại. |
| FCF Margin | `Free Cash Flow / Revenue` | FCF, revenue | Chuyển doanh thu thành dòng tiền tự do | Revenue=0/thiếu thì không tính; FCF dễ biến động theo capex. |

## Mô hình chất lượng và rủi ro kế toán

### Piotroski F-Score

Tổng 9 tín hiệu nhị phân: ROA dương, CFO dương, ROA tăng, CFO>net income, leverage giảm, current ratio tăng, không phát hành thêm cổ phiếu, gross margin tăng, asset turnover tăng.

- **Đầu vào:** nhiều kỳ ROA, OCF, net income, debt/assets, current ratio, shares, gross margin, turnover.
- **Áp dụng:** chấm từng tiêu chí 0/1 chỉ khi định nghĩa và kỳ nhất quán.
- **Missing:** không tự chấm 0 cho field thiếu; báo “không tính đủ”.
- **Cảnh báo:** `stock_analyzer` có chiến lược fscore nhưng implementation chi tiết không được suy ra từ tên; công thức chuẩn và output dự án có thể khác.

### Altman Z-Score

Mô hình public manufacturing cổ điển: `Z = 1.2X1 + 1.4X2 + 3.3X3 + 0.6X4 + 1.0X5`, với `X1=Working Capital/Total Assets`, `X2=Retained Earnings/Total Assets`, `X3=EBIT/Total Assets`, `X4=Market Value Equity/Total Liabilities`, `X5=Sales/Total Assets`.

- **Đầu vào:** retained earnings và EBIT chưa được xác nhận đầy đủ.
- **Áp dụng:** chọn đúng biến thể cho loại doanh nghiệp/thị trường.
- **Missing:** không tính nếu thiếu thành phần.
- **Cảnh báo:** ngưỡng gốc không nên áp dụng máy móc cho ngân hàng hoặc Việt Nam.

### Beneish M-Score

Mô hình chuẩn dùng tám chỉ số DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA rồi tổ hợp theo hệ số của phiên bản nghiên cứu.

- **Đầu vào:** cần receivables, sales, COGS, assets, depreciation, SG&A, liabilities, accruals ở hai kỳ.
- **Áp dụng:** chỉ khi mapping raw đầy đủ và cùng chuẩn kế toán.
- **Missing:** không tính từng proxy tùy tiện.
- **Cảnh báo:** depreciation và SG&A chưa được xác nhận trong metadata; hiện **not fully confirmed from current metadata**.

## Chỉ báo kỹ thuật và rủi ro thị trường

| Chỉ tiêu | Công thức | Đầu vào | Ý nghĩa và điều kiện | Missing / cảnh báo |
|---|---|---|---|---|
| Moving Average | `SMA_n = mean(Close over n periods)`; EMA dùng trọng số mũ | close liên tục | Làm mượt xu hướng | Cần đủ lookback; corporate action có thể gây gãy giả. |
| RSI | `100 - 100/(1+RS)`; `RS=avg gain/avg loss` | close changes, thường n=14 | Momentum 0–100 | Cách smoothing phải nhất quán; RSI cao không tự động là bán. |
| MACD | `EMA_12 - EMA_26`; signal=`EMA_9(MACD)`; hist=`MACD-signal` | close | Xu hướng/momentum | Tham số có thể khác; snapshot chỉ có histogram. |
| Volume Breakout | Ví dụ `Volume_t / AvgVolume_n > threshold` kèm điều kiện giá | volume, close, n, threshold | Bất thường thanh khoản | Threshold không có chuẩn duy nhất; dùng `rel_vol` và ghi ngưỡng. |
| Drawdown | `Price_t / RunningPeak_t - 1`; Max DD là min | adjusted price series | Mức giảm từ đỉnh | Giá chưa adjusted có thể tạo drawdown giả. |
| Volatility | `StdDev(periodic returns) × sqrt(periods/year)` | return series | Biến động annualized | Nêu log/simple return, cửa sổ và annualization factor. |
| Sharpe Ratio | `(Annualized Return - RiskFreeRate) / Annualized Volatility` | returns, risk-free | Lợi nhuận điều chỉnh rủi ro | Nếu không có risk-free, ghi rõ giả định (ví dụ 0), không giấu giả định; không tính khi volatility=0. |

## Known Limitations

- Công thức mô tả chuẩn phân tích, không đảm bảo project đã triển khai đúng biến thể đó.
- Unit BCTC và mapping một số field raw chưa được xác nhận đầy đủ.
- ROIC, EV/EBITDA, Interest Coverage, Altman và Beneish chưa đủ đầu vào đã xác nhận trong snapshot.
- EPS/BVPS/FCF có thể là proxy và cần kiểm tra quy ước nguồn.

## How AI Should Use This

AI chỉ tính khi liệt kê được field nguồn, kỳ, unit và cách xử lý missing. Mọi kết quả tự tính phải gắn nhãn “derived”, hiển thị công thức/giả định và không ghi đè số reported.
