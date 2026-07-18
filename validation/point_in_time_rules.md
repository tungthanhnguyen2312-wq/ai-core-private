# Point-in-Time Rules

## Mục tiêu

Point-in-time discipline bảo đảm mọi dữ liệu dùng cho một quyết định giả định đã thực sự available tại cutoff đó. “Kỳ báo cáo” hoặc “latest hiện tại” không tự chứng minh availability trong quá khứ.

## Current analysis

- Có thể dùng current metadata/shareholder nếu ghi `updated`/`updated_at` và data cutoff.
- Phải kiểm tra latest price/global market date và trạng thái stale.
- Latest của macro/news/financial có thể khác ngày; ghi từng cutoff riêng.

## Historical analysis

- Chỉ dùng observations có date/published time không vượt cutoff.
- Nếu mục tiêu chỉ mô tả lịch sử với hindsight, phải ghi rõ “retrospective”, không mô phỏng quyết định point-in-time.
- Current metadata/shareholder có thể dùng để mô tả hiện trạng, nhưng không được gán ngược vào quá khứ.

## Backtest

- Cấm dùng current `metadata` như historical dimension nếu không có effective-date history.
- Cấm dùng shareholder snapshot như historical holdings.
- Cấm dùng latest screen/technical/AI/Quant output để tạo signal quá khứ; phải tính lại tại từng cutoff.
- BCTC cần publication/availability date. Chỉ có `period=2026-Q1` không chứng minh dữ liệu đã available ngày 2026-03-31.
- News chỉ được dùng khi `published_utc <= cutoff`.
- Macro phải tôn trọng release lag/revisions nếu backtest nghiêm túc; thông tin này hiện **not fully confirmed**.
- Corporate actions và adjusted price phải được xử lý trước tính return.

## Cutoff contract

Mỗi artifact historical/backtest phải ghi: `analysis_cutoff`, timezone, source record date, publication/update availability nếu có, transformation time và rules version. Dữ liệu không xác định được availability phải bị loại hoặc gắn `not_point_in_time_safe`.

## Snapshot rules

- `metadata`, `shareholders`, `screen_snapshot`, `ta_signals`, `macro_snapshot`, `news_latest` và `*_latest` đều không phải historical dimension chỉ vì có date.
- `updated` thường là crawl/update time, không nhất thiết effective time.
- Không backfill giá trị hiện tại vào mọi ngày lịch sử.

## Provenance / Source Basis

Dựa trên `knowledge/AnalysisGuide.md`, `knowledge/MarketConvention.md`, metadata quality rules và limitations từ discovery.

## Known Limitations

- Chưa có filing publication calendar, macro release vintage hoặc metadata effective-date table.
- Price adjustment chưa fully confirmed.
- Vì vậy VNSTOCK hiện chưa được xác nhận là point-in-time safe cho backtest nghiêm túc.

## How AI Should Use This

AI phải hỏi mode/cutoff trước phân tích lịch sử. Nếu không chứng minh được availability, không được gọi kết quả là backtest không-look-ahead; hãy gọi là retrospective analysis và nêu hạn chế.
