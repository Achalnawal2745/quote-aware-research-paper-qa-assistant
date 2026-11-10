# Generated results

Latency percentiles use successful requests only; failures are in outcomes. Times are ms. Duration is the arrival window, not drain time. Burst rate is intentionally not a finite RPM. Tokens/answer include measured input and output across attempts; incomplete-usage requests are excluded. Cost is actual free-tier cash charge (or synthetic zero), not a paid-equivalent estimate. Peak queue counts waits of at least 1 ms from CSV spans. Never combine independent runs as one scenario.

## Table 1: Real limits
| Limit | Value found | How found | Confidence |
|---|---|---|---|
| Requests/min | not measured | Await real account and probe | low |
| Tokens/min | not measured | Await real account and probe | low |
| Requests/day | not measured | Await real account and probe | low |
| Tokens/day | not measured | Await real account and probe | low |
| Requests in flight | not measured | Await real account and probe | low |
| Limit response | not measured | Await real account and probe | low |
| Recovery time | not measured | Await real account and probe | low |

## Table 2a: Latency
| Scenario | Source | Requests | Duration s | Offered/min | First p50/p95/p99 | Total p50/p95/p99 |
|---|---|---|---|---|---|---|
| probe | stand-in | 40 | 3.120 | 750.0 | 1349.0 / 1704.6 / 1767.7 | 1349.0 / 1704.6 / 1767.7 |

## Table 2b: Outcomes
| Scenario | OK % | Rate limited % | Timeout/given up % | Retries/request | Peak queue | Tokens/answer | $/1000 successful answers | Other error % |
|---|---|---|---|---|---|---|---|---|
| probe | 30.0 | 52.5 | 7.5 | 0.28 | 6 | 1579.0 | 0.0000 | 10.0 |

## Table 3: Retrieval
| Setting | Questions | Correct+cited % | Wrong % | Correct refusal % | Tokens/answer | First p50/p95 | Total p50/p95 | Wrong refusal % |
|---|---|---|---|---|---|---|---|---|
| small | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured |
| medium | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured |
| large | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured |

Settings are whitespace words (not model tokens): small=180/overlap30/k3; medium=300/50/k4; large=420/70/k5. No reranking.

## Additional timing
| Scenario | Provider TTFT p50/p95 | Validation hold p50/p95 |
|---|---|---|
| probe | 157.7 / 162.3 | 128.5 / 152.7 |

## Slow request trace
Request `97fe1acd5eed` (stand-in, probe): total 1783.5 ms; queue_wait_ms=1280.6 ms; working_ms=229.7 ms; retry_wait_ms=272.7 ms; first_token_ms=1783.5 ms; provider_ttft_ms=134.7 ms; validation_hold_ms=91.2 ms; residual scheduling/validation overhead=0.6 ms. Since release follows validation, almost all user delay is before the first answer token. See matching events.jsonl records.
