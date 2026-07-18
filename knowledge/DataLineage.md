# Data Lineage

## Luồng tổng thể

```text
vnstock APIs / FRED / Yahoo / World Bank / RSS / VCB / SJC
                              ↓
                        crawler scripts
                              ↓
               SQLite / CSV / Parquet / BCTC raw
                              ↓
                       processing scripts
                              ↓
              snapshots / normalized financial data
                              ↓
                    Quant and AI analysis outputs
                              ↓
                    dashboard / downstream AI use
```

## Lineage theo nhánh

| Nguồn | Module | Kho/output trung gian | Processor/output | Metadata liên quan | Rủi ro |
|---|---|---|---|---|---|
| vnstock Quote VCI/KBS | `vn_stock_pipeline.py` | `ohlcv`, `meta`, OHLCV flat | `vn_indicators.py` → screen/breadth | dataset/schema/quality registry | Failover nguồn, adjustment chưa chắc chắn, stale ticker. |
| vnstock Listing/Finance/Company/Trading | `meta_sync.py`, `blacklist_sync.py` | `metadata`, `blacklist.csv` | Join vào screen/signals | sentinel và margin rules | Point-in-time, provider percentage scale, manual-vs-auto merge. |
| vnstock Company VCI/KBS | `shareholders_sync.py` | `shareholders`, progress | free-float proxy trong metadata | ownership rules | Không có lịch sử, empty khác not queried. |
| vnstock Finance KBS/VCI | `bctc_sync.py` | `data_bctc/*`, scrape progress | `bctc_processor.py` → financial snapshot | financial statement registry | Raw/processed khác grain, mapping item, unit/scale. |
| FRED/Yahoo/WB/VCB/SJC | `macro_sync.py` | `macro` | `macro_snapshot.csv` | macro schema | Tần suất, timezone/date và unit không đồng nhất. |
| 8 RSS feeds | `news_sync.py` | `news` | `news_latest.csv` | news dataset | Trùng/thiếu summary, không ticker mapping, publication time. |
| OHLCV + screen | `candle_scan.py` | `ta_signals.*`, web JSON/JS | dashboard signals | technical schema | Lookback, stale row, string boolean/list serialization. |
| Screen/OHLCV/DB | `stock_analyzer.py` | `analysis_latest.*`, scans | dashboard analysis | derived output policy | Model/strategy assumptions, output không phải ground truth. |
| Screen/breadth/macro/news | `ai_analyzer.py` | `ai_report_*` | dashboard report | AI output schema | LLM inference, paid call, cần validate ticker. |
| Web artifacts | `publish_dashboard.py` | whitelist | GitHub Pages | file registry | Stale publish, không publish dữ liệu local nhạy cảm. |

## Điểm kiểm tra khi dữ liệu bất thường

1. **Sai/thiếu giá:** kiểm tra `source`, date continuity, duplicate PK, corporate action và `meta.status`.
2. **Metadata lạ:** xác nhận đang đọc `metadata`, không phải `meta`; kiểm tra `updated`, sentinel và provider scale.
3. **Ticker biến mất:** so sánh universe, OHLCV, latest date, exchange và progress; không suy ra delisted chỉ từ missing.
4. **BCTC lệch:** kiểm tra ticker/report/period, `item_id`, source, unit, raw period column và transformation.
5. **Tỷ số cực đoan:** kiểm tra mẫu số 0/âm, annual-vs-quarter, TTM và dấu.
6. **Macro lệch ngày:** kiểm tra `freq`, observation date, unit và cách tính change.
7. **News không khớp ticker:** coi linkage là inference, kiểm tra tên công ty/mã và nguồn.
8. **Dashboard khác CSV:** ưu tiên dataset gần nguồn hơn, kiểm tra thời điểm publish và serialization.

## Provenance tối thiểu khi trích số

Ghi `dataset/path`, ticker/series, date/period, field, unit, và trạng thái reported/derived/proxy. Nếu từ output Quant/AI, ghi thêm tên output và không gọi đó là dữ liệu gốc.

## Known Limitations

- Lineage mô tả logic từ discovery, chưa phải hệ thống lineage tự động theo từng record.
- Không có checksum/run-id xuyên pipeline trong metadata hiện tại.
- Ngày công bố BCTC và lịch sử metadata/shareholder chưa được xác nhận đầy đủ.

## How AI Should Use This

Khi gặp số liệu đáng ngờ, AI phải truy ngược một tầng tại một thời điểm và so sánh grain/unit/date. Không sửa dữ liệu hoặc chọn nguồn thuận lợi hơn mà không giải thích.
