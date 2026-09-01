# AI Usage Rules

## AI được phép làm gì

- Đọc tài liệu knowledge/metadata và các lát cắt dữ liệu được cấp quyền.
- Tóm tắt, so sánh, tính chỉ tiêu có đủ đầu vào và ghi giả định.
- Phân tích theo kịch bản, xác suất và điều kiện.
- Phát hiện missing, stale, outlier, mâu thuẫn và yêu cầu xác minh.
- Tạo bảng provenance nội bộ cho mọi số liệu quan trọng.

## AI không được làm gì

- Bịa field, schema, số liệu, nguồn, catalyst hoặc ticker linkage.
- Biến missing thành 0 hay dùng `-1` như số thật.
- Nhầm `meta` với `metadata`.
- Dùng snapshot hiện tại cho backtest quá khứ.
- Xem shareholder snapshot là historical holdings.
- Khẳng định giá adjusted khi chưa xác minh.
- Đưa lời khuyên mua/bán hoặc lợi nhuận chắc chắn.
- Xem output AI/Quant là ground truth.
- Sửa code/DB/dữ liệu hoặc chạy crawler nếu không được cấp quyền rõ ràng.
- Với `next_session_decision_brief/v1` (context Consumer `ai_next_session_decision_context/v1`), giữ nguyên nhãn `PARTIAL`/`MISSING_PREVIOUS_CONTEXT`, không suy ra `UNCHANGED`/`NEUTRAL`/`WAIT`/`SELL`; giữ tách biệt `lifecycle_transition` (nhóm so sánh trong Session Bundle) và `tactical_transition` (toàn thị trường `watchlist_tactical_entry_classifier`), không gộp thành một tín hiệu kỹ thuật chung; không tạo forecast, probability, target price hay sizing từ `next_session_watch_conditions`.
- Với `financial_analysis_consumer_context/v1`, chỉ dùng trạng thái và bằng chứng định tính do Producer `financial_analysis_compact/v1` phát hành; không tính lại hay nêu ratio/giá trị thô, score, ranking, valuation, forecast hoặc recommendation. `RESEARCH_PROXY` (đặc biệt `CROSS_PROVIDER_UNRESOLVED_SCALE`) chỉ là research context định hướng, không phải fact có thẩm quyền; `ABSENT`/`BLOCKED`/`UNAVAILABLE` là giới hạn coverage, còn `NOT_APPLICABLE` là giới hạn áp dụng — không được diễn giải thành yếu, bằng không, hoặc trung tính.
- Ghi đè nhãn hoặc readiness do deterministic Producer cung cấp. Với `shadow_security_recommendation`, `AI_NARRATIVE_CANNOT_OVERRIDE_PRODUCER_RECOMMENDATION`: AI chỉ giải thích, nêu phản biện có grounding, và giữ UNKNOWN/authority boundary nguyên trạng; không tạo BUY/SELL/HOLD, target, probability, allocation, sizing hoặc risk budget. Khi có `correlation_concentration_guard/v1`, AI chỉ diễn giải context C2 đã được Producer tính sẵn; không tự tính correlation/ngưỡng, không suy ra diversification/causality, và giữ nguyên trạng thái partial/joint readiness.

## Quy tắc đọc dữ liệu

1. Đọc quality rules trước schema.
2. Xác định grain, key, date/period, unit và missing rule.
3. Lọc theo ticker và khoảng thời gian trước khi nạp context.
4. Với live analysis, loại stale ticker bằng latest market date.
5. Ưu tiên source dataset hơn frontend serialization và derived report.
6. Không bulk-load DB, OHLCV CSV hoặc toàn bộ BCTC raw.

## Quy tắc trả lời

- Mở đầu bằng phạm vi và data cutoff.
- Tách **Fact**, **Derived calculation**, **Inference**, **Opinion/scenario**.
- Nêu missing data và ảnh hưởng tới độ tin cậy.
- Dùng ngôn ngữ xác suất: “cho thấy”, “có thể”, “rủi ro”, “cần xác nhận”.
- Không dùng ngôn ngữ bảo đảm: “chắc chắn tăng”, “nên mua ngay”, “không thể lỗ”.
- Kết thúc bằng rủi ro chính và điều kiện làm thay đổi kết luận.

## Citation / source reference nội bộ

Mỗi số quan trọng nên có dạng: `[dataset: path | ticker/series | date/period | field | unit]`. Ví dụ: `[financial_snapshot.csv | ABC | 2026-Q1 | net_profit | unit not fully confirmed]`.

Không viện dẫn `analysis_latest` như nguồn nguyên thủy; ghi rõ đó là derived Quant output.

## Khi thiếu dữ liệu

- Nói chính xác field/kỳ nào thiếu.
- Không nội suy nếu chưa được yêu cầu và không có phương pháp.
- Có thể đề xuất dataset cần đọc, nhưng không giả định kết quả.
- Hạ mức tin cậy hoặc bỏ phần kết luận phụ thuộc field đó.

## Khi dữ liệu mâu thuẫn

1. Kiểm tra ticker, kỳ, source, unit, scale, consolidated scope và reported/derived.
2. Trình bày cả hai giá trị cùng provenance.
3. Ưu tiên dữ liệu gần nguồn hơn chỉ khi grain/unit tương thích.
4. Nếu chưa giải quyết được, ghi “unresolved conflict”; không lấy trung bình tùy ý.

## Fact, inference và opinion

- **Fact:** giá trị trực tiếp từ dataset, kèm provenance.
- **Derived:** phép tính tái lập được từ facts, kèm công thức.
- **Inference:** kết luận logic có độ bất định, nêu bằng chứng và phản chứng.
- **Opinion/scenario:** đánh giá có điều kiện, không phải dữ kiện.

## UTF-8

Đọc/ghi UTF-8, giữ nguyên dấu tiếng Việt, tên ngành và tiêu đề. Không “sửa” ký tự lỗi bằng cách đoán nội dung nếu chưa đọc lại đúng encoding.

## Checklist phân tích ticker

- [ ] Ticker uppercase và phạm vi thời gian rõ.
- [ ] Availability đã kiểm tra.
- [ ] Latest date và trạng thái active đã xác minh.
- [ ] Không nhầm `meta`/`metadata`.
- [ ] Sentinel/string boolean đã normalize.
- [ ] Unit/kỳ/TTM đã ghi rõ.
- [ ] Metadata/shareholder được gắn nhãn point-in-time.
- [ ] Giá adjustment được cảnh báo khi liên quan.
- [ ] Fact/derived/inference tách biệt.
- [ ] Nguồn nội bộ cho số quan trọng đã ghi.
- [ ] Missing/conflict và mức tin cậy đã nêu.
- [ ] Không có khuyến nghị tuyệt đối.

## Known Limitations

- Bộ luật không tự cưỡng chế quyền truy cập hoặc validation.
- Citation nội bộ là convention, không phải record-level lineage tự động.
- Độ tin cậy cuối cùng vẫn phụ thuộc freshness và chất lượng dữ liệu nguồn.

## How AI Should Use This

Áp dụng như checklist bắt buộc trước và sau mọi câu trả lời phân tích. Nếu yêu cầu người dùng xung đột với quy tắc dữ liệu, AI phải nêu giới hạn và cung cấp phương án an toàn hơn.
