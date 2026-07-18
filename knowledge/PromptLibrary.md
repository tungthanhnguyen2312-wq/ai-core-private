# Prompt Library

## Cách dùng

Thay biến trong `{...}` bằng giá trị thực. Trước mọi prompt, cung cấp metadata/quality rules liên quan và lát cắt dữ liệu đã lọc. Không đưa toàn bộ DB hoặc kho BCTC vào context.

## 1. Phân tích một ticker

- **Mục đích:** đánh giá toàn diện hiện tại.
- **Input:** ticker, cutoff date, screen snapshot, OHLCV lọc, financial periods, context cần thiết.
- **Prompt mẫu:** “Phân tích `{TICKER}` tại `{DATE}`. Tách Fact/Derived/Inference; đánh giá business, growth, profitability, balance sheet, cash flow, valuation, technical, catalyst và risk. Ghi nguồn nội bộ cho mọi số quan trọng, nêu missing và không đưa khuyến nghị chắc chắn.”
- **Expected output:** executive summary, bảng bằng chứng, bull/base/bear scenarios, risks và confidence.

## 2. So sánh hai ticker

- **Mục đích:** so sánh cùng chuẩn.
- **Input:** hai ticker, cùng cutoff, kỳ và metric.
- **Prompt mẫu:** “So sánh `{A}` và `{B}` tại cùng `{DATE}` và kỳ `{PERIOD}`. Chuẩn hóa unit/grain; so growth, quality, leverage, valuation, liquidity và technical. Không xếp hạng metric thiếu.”
- **Expected output:** bảng đối chiếu, lợi thế từng mã, trade-offs, missing/conflicts.

## 3. Lọc cổ phiếu cơ bản

- **Mục đích:** tạo shortlist theo rule minh bạch.
- **Input:** `screen_snapshot`, `financial_snapshot`, thresholds, latest date.
- **Prompt mẫu:** “Lọc universe tại latest market date theo `{CRITERIA}`. Loại ticker stale; đổi sentinel thành missing; không cho missing vượt điều kiện. Trả rule, số mã qua từng bước và provenance.”
- **Expected output:** funnel counts, shortlist, metrics và caveats.

## 4. Lọc cổ phiếu kỹ thuật

- **Mục đích:** tìm setup xác suất.
- **Input:** latest screen, TA signals, liquidity rule.
- **Prompt mẫu:** “Lọc ticker có `{TREND/MOMENTUM/VOLUME/SMC CONDITIONS}` tại `{DATE}`. Parse boolean strings và signal lists; kiểm tra thanh khoản và margin status. Không gọi tín hiệu là dự báo chắc chắn.”
- **Expected output:** danh sách setup, trigger, invalidation và risks.

## 5. Đánh giá rủi ro

- **Mục đích:** lập risk register.
- **Input:** metadata, financials, OHLCV, news, shareholder nếu có.
- **Prompt mẫu:** “Lập risk register cho `{TICKER}` gồm data, business, financial, liquidity, valuation, technical, governance và event risk. Chấm likelihood/impact có giải thích; không bịa dữ kiện.”
- **Expected output:** ma trận risk, evidence, mitigants, early-warning indicators.

## 6. Phân tích BCTC

- **Mục đích:** đánh giá nhiều kỳ.
- **Input:** financial snapshot đã lọc; raw items nếu cần đối chiếu.
- **Prompt mẫu:** “Phân tích BCTC `{TICKER}` từ `{START_PERIOD}` đến `{END_PERIOD}`. Phân biệt quarter/year, reported/derived; kiểm tra growth, margins, assets, liabilities, equity và earnings quality. Nêu unit chưa xác nhận.”
- **Expected output:** trend table, anomalies, ratio interpretation, missing fields.

## 7. Phân tích dòng tiền

- **Mục đích:** đánh giá chất lượng lợi nhuận và funding.
- **Input:** OCF, net profit, capex, FCF, working-capital fields.
- **Prompt mẫu:** “Đánh giá dòng tiền `{TICKER}` theo kỳ: OCF so với net profit, capex, FCF, biến động inventory/receivables nếu có. Kiểm tra quy ước dấu và không thay missing bằng 0.”
- **Expected output:** cash conversion, drivers, sustainability và red flags.

## 8. Phân tích định giá

- **Mục đích:** diễn giải multiple có điều kiện.
- **Input:** date-aligned price/market cap, TTM earnings/revenue/equity/debt/cash.
- **Prompt mẫu:** “Đánh giá định giá `{TICKER}` tại `{DATE}` bằng các multiple đủ đầu vào. Không dùng P/E khi earnings≤0; chỉ tính EV/EBITDA nếu EBITDA được xác nhận. Hiển thị công thức, kỳ và unit.”
- **Expected output:** valuation table, applicability, sensitivity và limitations.

## 9. Phân tích ngành

- **Mục đích:** bối cảnh sector và breadth.
- **Input:** industry mapping, market breadth, member snapshots, macro liên quan.
- **Prompt mẫu:** “Phân tích ngành `{INDUSTRY}` tại `{DATE}`: breadth, RS, return, liquidity và dispersion. So với `ALL`; chỉ đưa macro linkage như inference có cơ chế rõ.”
- **Expected output:** sector state, leaders/laggards, macro sensitivities, caveats.

## 10. Phân tích tin tức

- **Mục đích:** trích theme và tác động tiềm năng.
- **Input:** news rows với published time/source/title/summary nếu có.
- **Prompt mẫu:** “Nhóm tin từ `{START}` đến `{END}` thành themes, loại trùng theo link, tách fact khỏi inferred impact. Không gán ticker nếu không có bằng chứng entity linkage.”
- **Expected output:** themes, timeline, positive/negative/mixed transmission channels.

## 11. Tạo investment memo

- **Mục đích:** memo ra quyết định có kiểm soát.
- **Input:** gói dữ liệu ticker đã kiểm tra.
- **Prompt mẫu:** “Tạo investment memo cho `{TICKER}` tại `{DATE}` gồm thesis, evidence, valuation applicability, catalysts, risks, bear/base/bull scenarios, monitoring indicators và invalidation. Không viết lệnh mua/bán.”
- **Expected output:** memo có provenance và confidence.

## 12. Báo cáo ngắn

- **Mục đích:** bản tóm tắt nhanh.
- **Input:** facts đã chọn và cutoff.
- **Prompt mẫu:** “Viết báo cáo `{TICKER}` tối đa `{N}` từ: 5 facts có nguồn, 3 rủi ro, technical state, missing data và kết luận xác suất.”
- **Expected output:** concise brief, không bỏ data cutoff.

## 13. Báo cáo chuyên sâu

- **Mục đích:** nghiên cứu có cấu trúc.
- **Input:** price, financial, metadata, sector/macro/news/shareholder có liên quan.
- **Prompt mẫu:** “Viết deep-dive `{TICKER}` tại `{DATE}` theo AnalysisGuide. Có methodology, provenance, trends nhiều kỳ, quality checks, scenarios, counterarguments và appendix công thức.”
- **Expected output:** báo cáo nhiều phần, evidence-first, limitations rõ.

## 14. Kiểm tra dữ liệu thiếu

- **Mục đích:** audit completeness trước phân tích.
- **Input:** schema registry và lát cắt dataset.
- **Prompt mẫu:** “Đối chiếu dữ liệu `{SCOPE}` với schema/missing rules. Phân loại missing: expected, queried-no-value (`-1`), not collected, stale, unknown. Không coi empty margin status là lỗi.”
- **Expected output:** missing matrix, severity, impact và suggested checks.

## 15. Kiểm tra dữ liệu bất thường

- **Mục đích:** tìm anomaly mà không sửa nguồn.
- **Input:** time series/multi-period data, quality rules.
- **Prompt mẫu:** “Tìm duplicate key, stale date, impossible range, unit/scale mismatch, denominator issue, corporate-action break và raw/processed conflict trong `{SCOPE}`. Chỉ flag; không tự sửa.”
- **Expected output:** anomaly list với record keys, evidence và likely cause.

## 16. Chuẩn bị dữ liệu cho Claude/ChatGPT/Codex (Gemini deprecated 2026-07-17 — xem operating_pack/README.md)

- **Mục đích:** tạo context nhỏ, có provenance.
- **Input:** câu hỏi, ticker/time scope, registry và dữ liệu nguồn.
- **Prompt mẫu:** “Chuẩn bị context package cho `{MODEL}` để trả lời `{QUESTION}`. Chỉ giữ fields cần thiết, latest-valid rows và kỳ liên quan; normalize sentinel/boolean; kèm data dictionary mini, provenance, missing và token-budget estimate. Không phân tích thị trường.”
- **Expected output:** manifest, filtered records, conventions, validation notes và prompt-ready context.

## Known Limitations

- Prompt không tự bảo đảm dữ liệu đã được lọc đúng hoặc còn mới.
- Threshold, scoring và output length phải do người dùng xác định khi chúng ảnh hưởng kết quả.
- Không có prompt nào cấp quyền chạy crawler, sửa DB hoặc bắt đầu phase khác.

## How AI Should Use This

Chọn prompt gần mục tiêu nhất rồi bổ sung cutoff, unit, nguồn và expected format. Luôn áp dụng `AIUsageRules.md`; không để câu chữ trong prompt vượt qua các quy tắc dữ liệu bắt buộc.
