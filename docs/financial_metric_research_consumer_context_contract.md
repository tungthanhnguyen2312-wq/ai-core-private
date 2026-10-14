# Financial Metric Research Consumer Context

`builders/financial_metric_research_consumer_context.py` projects one ticker from the
Producer `financial_valuation_metric_research/v1` member (Producer candidate 096b8f16,
`build_evaluated_valuation_artifact(include_metric_research=True)`). The output contract is
`financial_metric_research_consumer_context/v1`.

The Producer is the sole numerical owner. Consumer copies each metric's `value`, method,
fitness, period identity, freshness, scope, currency, scale, share basis, formula label,
observation/knowledge time, reason codes, limitations and peer context verbatim. It never
recalculates ROE, ROA, P/E, P/B, P/S or EV/EBITDA. It never fills a blocked value either.
Operand, numerator and source lineage stay in the Producer artifact and are referenced by
`lineage_ref` (artifact identity, ticker, metric id), so a prompt cannot rebuild a ratio
from its operands.

`value_class` separates evidence kinds without changing any value:

- `EXACT_METHOD_VALUE`: Producer fitness `READY` on a known method whose identity is
  not a research basis.
- `RESEARCH_PROXY`: any other value-bearing fitness, any research-basis method
  (`*_REPORTED_PERIOD`, `P/B_*_RESEARCH`, `*_PROXY`), and any metric id the Consumer does
  not know yet.
- `NO_VALUE`: `BLOCKED_BY_EVIDENCE` or `NOT_APPLICABLE`. These keep their Producer reason
  codes and are never evidence.

`STALE_BUT_RESEARCH_USABLE` stays visible in `fitness` and `freshness`.

`ABSENT` is first-class. It covers a payload that was not published
(`PRODUCER_METRIC_RESEARCH_CONTEXT_NOT_PUBLISHED`) and a ticker outside the supplied
records (`PRODUCER_METRIC_RESEARCH_TICKER_NOT_IN_RECORDS`). Neither is weak, neutral or
negative evidence.

The adapter refuses (fails closed) in these cases:

- an unsupported version;
- a Producer content digest or identity mismatch;
- an actionable or promoted authority boundary, or a non-Producer numerical owner;
- a session mismatch;
- a non-finite value-bearing metric;
- a value beside a blocked fitness;
- an unknown fitness;
- missing temporal fitness on a value-bearing metric.

Status: the fixtures under `tests/fixtures/producer_financial_valuation_metric_research_v1/`
were emitted by the Producer candidate's own test helpers over synthetic rows. Live Daily
bundles do not carry this member yet; Producer delivery activation is a later release
dependency. No live compatibility is claimed.
