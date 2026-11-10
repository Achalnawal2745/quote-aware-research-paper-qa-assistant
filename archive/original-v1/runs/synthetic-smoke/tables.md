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
| steady | stand-in | 16 | 6.000 | 150.0 | 227.4 / 1595.9 / 1603.7 | 227.4 / 1595.9 / 1603.8 |
| burst | stand-in | 16 | 0.000 | instantaneous batch | 1074.8 / 1794.7 / 1830.2 | 1074.8 / 1794.7 / 1830.2 |
| sustained_overload | stand-in | 48 | 1.410 | 2000.0 | 1266.5 / 1772.9 / 1825.3 | 1266.6 / 1772.9 / 1825.3 |
| per_minute_limit_halved | stand-in | 16 | 0.225 | 4000.0 | 771.8 / 1659.2 / 1800.4 | 771.8 / 1659.3 / 1800.5 |
| daily_budget_exhausted | stand-in | 16 | 0.000 | instantaneous batch | not measured | not measured |

## Table 2b: Outcomes
| Scenario | OK % | Rate limited % | Timeout/given up % | Retries/request | Peak queue | Tokens/answer | $/1000 successful answers | Other error % |
|---|---|---|---|---|---|---|---|---|
| steady | 75.0 | 25.0 | 0.0 | 0.00 | 0 | 1554.2 | 0.0000 | 0.0 |
| burst | 50.0 | 50.0 | 0.0 | 0.00 | 6 | 1492.2 | 0.0000 | 0.0 |
| sustained_overload | 22.9 | 75.0 | 2.1 | 0.00 | 6 | 1444.3 | 0.0000 | 0.0 |
| per_minute_limit_halved | 37.5 | 62.5 | 0.0 | 0.00 | 6 | 1462.8 | 0.0000 | 0.0 |
| daily_budget_exhausted | 0.0 | 100.0 | 0.0 | 0.00 | 6 | not measured | not measured | 0.0 |

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
| steady | 110.7 / 759.0 | 117.8 / 831.4 |
| burst | 114.0 / 599.3 | 141.2 / 684.5 |
| sustained_overload | 112.3 / 486.5 | 138.5 / 561.2 |
| per_minute_limit_halved | 113.0 / 672.1 | 141.2 / 766.5 |
| daily_budget_exhausted | not measured | not measured |

## Slow request trace
Request `d72c6fbb24aa` (stand-in, burst): total 1839.1 ms; queue_wait_ms=0.0 ms; working_ms=1838.7 ms; retry_wait_ms=0.0 ms; first_token_ms=1839.1 ms; provider_ttft_ms=860.3 ms; validation_hold_ms=975.6 ms; residual scheduling/validation overhead=0.4 ms. Since release follows validation, almost all user delay is before the first answer token. See matching events.jsonl records.
