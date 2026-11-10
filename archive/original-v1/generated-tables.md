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
| steady | stand-in | 10 | 49.500 | 10.9 | 210.9 / 986.8 / 1486.5 | 210.9 / 986.8 / 1486.5 |
| burst | stand-in | 10 | 0.000 | instantaneous batch | 1061.5 / 1788.7 / 1825.0 | 1061.5 / 1788.8 / 1825.0 |
| sustained_overload | stand-in | 60 | 14.750 | 240.0 | 260.3 / 1591.9 / 1597.5 | 260.4 / 1592.0 / 1597.6 |
| per_minute_limit_halved | stand-in | 10 | 0.135 | 4000.0 | 772.5 / 1658.0 / 1798.5 | 772.5 / 1658.0 / 1798.6 |
| daily_budget_exhausted | stand-in | 10 | 0.000 | instantaneous batch | not measured | not measured |
| retry_disabled | stand-in | 40 | 3.120 | 750.0 | 781.4 / 1127.8 / 1635.5 | 781.4 / 1127.8 / 1635.5 |
| retry_enabled | stand-in | 40 | 3.120 | 750.0 | 1344.0 / 1702.9 / 1771.0 | 1344.0 / 1702.9 / 1771.1 |

## Table 2b: Outcomes
| Scenario | OK % | Rate limited % | Timeout/given up % | Retries/request | Peak queue | Tokens/answer | $/1000 successful answers | Other error % |
|---|---|---|---|---|---|---|---|---|
| steady | 100.0 | 0.0 | 0.0 | 0.00 | 0 | 1501.7 | 0.0000 | 0.0 |
| burst | 80.0 | 20.0 | 0.0 | 0.00 | 6 | 1492.2 | 0.0000 | 0.0 |
| sustained_overload | 20.0 | 80.0 | 0.0 | 0.00 | 1 | 1554.2 | 0.0000 | 0.0 |
| per_minute_limit_halved | 60.0 | 40.0 | 0.0 | 0.00 | 6 | 1462.8 | 0.0000 | 0.0 |
| daily_budget_exhausted | 0.0 | 100.0 | 0.0 | 0.00 | 6 | not measured | not measured | 0.0 |
| retry_disabled | 40.0 | 17.5 | 0.0 | 0.00 | 6 | 1557.2 | 0.0000 | 42.5 |
| retry_enabled | 30.0 | 52.5 | 7.5 | 0.28 | 6 | 1579.0 | 0.0000 | 10.0 |

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
| steady | 98.6 / 457.3 | 108.7 / 525.7 |
| burst | 112.1 / 598.1 | 140.1 / 684.6 |
| sustained_overload | 113.7 / 759.3 | 139.3 / 825.7 |
| per_minute_limit_halved | 112.6 / 672.2 | 140.9 / 765.2 |
| daily_budget_exhausted | not measured | not measured |
| retry_disabled | 158.4 / 391.3 | 139.4 / 286.9 |
| retry_enabled | 157.9 / 161.3 | 120.0 / 144.3 |

## Slow request trace
Request `3f62ec50585c` (stand-in, burst): total 1834.1 ms; queue_wait_ms=0.0 ms; working_ms=1833.7 ms; retry_wait_ms=0.0 ms; first_token_ms=1834.0 ms; provider_ttft_ms=858.7 ms; validation_hold_ms=973.6 ms; residual scheduling/validation overhead=0.4 ms. Since release follows validation, almost all user delay is before the first answer token. See matching events.jsonl records.
