# Generated results

Input file: `results.csv`

Latency percentiles use successful requests only; failures are reported separately. Times are milliseconds. Duration is the arrival window, not drain time. Burst rate is not interpreted as a finite RPM. Token averages use records with complete usage only. Synthetic stand-in costs are not real API cost measurements.

## Table 1: Real limits
| Limit | Value found | How found | Confidence |
|---|---|---|---|
| Requests/min | 30 (documented, not observed) | Public documentation for openai/gpt-oss-20b, not account measurement | low |
| Tokens/min | 8000 | Real x-ratelimit-limit-tokens header; request 16b27e74efca | medium |
| Requests/day | 1000 | Real x-ratelimit-limit-requests header; request 16b27e74efca | medium |
| Tokens/day | 200000 (documented, not observed) | Public documentation for openai/gpt-oss-20b, not account measurement | low |
| Requests in flight | >= 1 overlapping accepted calls (not a provider cap) | Accepted-call spans compared only within a single clock session | low |
| Limit response | not measured | 0 observed real 429s; raw bodies preserved | low |
| Recovery time | not measured | Successful recovery probe includes response time; not an exact reset measurement | low |

## Table 2a: Latency
| Scenario | Source | Requests | Duration s | Offered/min | First p50/p95/p99 | Total p50/p95/p99 |
|---|---|---|---|---|---|---|
| steady [115c27db0d] | stand-in | 8 | 140.000 | 3.0 | 242.9 / 745.0 / 949.0 | 242.9 / 745.1 / 949.1 |
| burst [115c27db0d] | stand-in | 12 | 0.000 | not measured | 630.8 / 1064.6 / 1103.2 | 630.8 / 1064.7 / 1103.2 |
| sustained_overload [115c27db0d] | stand-in | 40 | 117.000 | 20.0 | 18474.9 / 24559.2 / 26703.7 | 18475.0 / 24559.2 / 26703.8 |
| per_minute_limit_halved [115c27db0d] | stand-in | 12 | 165.000 | 4.0 | 15011.2 / 15259.1 / 15262.1 | 15011.2 / 15259.1 / 15262.1 |
| daily_budget_exhausted [115c27db0d] | stand-in | 20 | 28.500 | 40.0 | 214.3 / 729.2 / 940.8 | 214.3 / 729.3 / 940.9 |
| overload_limiter_off [115c27db0d] | stand-in | 40 | 117.000 | 20.0 | 10795.5 / 23889.0 / 26443.6 | 10795.5 / 23889.1 / 26443.6 |
| retry_disabled [d434de11a7] | stand-in | 40 | 3.120 | 750.0 | 806.9 / 1241.6 / 1730.3 | 807.0 / 1241.7 / 1730.3 |
| retry_enabled [664c63466d] | stand-in | 40 | 3.120 | 750.0 | 1447.7 / 1746.7 / 1802.1 | 1447.7 / 1746.8 / 1802.2 |
| ask [65e18a2967] | real | 1 | 0.000 | 200.0 | 3284.2 / 3284.2 / 3284.2 | 3284.3 / 3284.3 / 3284.3 |
| retrieval_eval [c1df428b59] | real | 15 | not measured | not measured | 2677.1 / 7069.4 / 7185.8 | 2677.2 / 7069.4 / 7185.9 |
| retrieval_eval [1f5d860c09] | real | 30 | not measured | not measured | 34641.5 / 65805.3 / 81122.7 | 34641.8 / 65805.3 / 81122.9 |

## Table 2b: Outcomes
| Scenario | OK % | Rate limited % | Timeout % | Retries/request | Peak queue | Tokens/request | $/1000 successful answers | Other error % | Provider rejection % | Local rejection % |
|---|---|---|---|---|---|---|---|---|---|---|
| steady [115c27db0d] | 100.0 | 0.0 | 0.0 | 0.00 | 0 | 1869.6 | 0.0000 | 0.0 | 0.0 | 0.0 |
| burst [115c27db0d] | 25.0 | 75.0 | 0.0 | 0.00 | 8 | 507.4 | 0.0000 | 0.0 | 0.0 | 75.0 |
| sustained_overload [115c27db0d] | 47.5 | 52.5 | 0.0 | 0.00 | 7 | 524.0 | 0.0000 | 0.0 | 0.0 | 52.5 |
| per_minute_limit_halved [115c27db0d] | 58.3 | 33.3 | 8.3 | 0.00 | 0 | 862.5 | 0.0000 | 0.0 | 0.0 | 33.3 |
| daily_budget_exhausted [115c27db0d] | 40.0 | 60.0 | 0.0 | 0.00 | 0 | 756.8 | 0.0000 | 0.0 | 0.0 | 60.0 |
| overload_limiter_off [115c27db0d] | 30.0 | 70.0 | 0.0 | 0.57 | 7 | 1894.5 | 0.0000 | 0.0 | 70.0 | 0.0 |
| retry_disabled [d434de11a7] | 37.5 | 20.0 | 0.0 | 0.00 | 6 | 993.4 | 0.0000 | 42.5 | 0.0 | 20.0 |
| retry_enabled [664c63466d] | 30.0 | 52.5 | 7.5 | 0.28 | 6 | 351.6 | 0.0000 | 10.0 | 0.0 | 52.5 |
| ask [65e18a2967] | 100.0 | 0.0 | 0.0 | 0.00 | 0 | 2779.0 | 0.0000 | 0.0 | 0.0 | 0.0 |
| retrieval_eval [c1df428b59] | 100.0 | 0.0 | 0.0 | 0.00 | 0 | 2292.6 | 0.0000 | 0.0 | 0.0 | 0.0 |
| retrieval_eval [1f5d860c09] | 93.3 | 6.7 | 0.0 | 0.00 | 1 | 4100.9 | 0.0000 | 0.0 | 0.0 | 6.7 |

## Table 3: Retrieval
| Setting | Questions | Correct+cited % | Wrong % | Correct refusal % | Tokens/answer | First p50/p95 | Total p50/p95 | Wrong refusal % |
|---|---|---|---|---|---|---|---|---|
| small | 15 | 40.0 | 0.0 | 20.0 | 2292.6 | 2677.1 / 7069.4 | 2677.2 / 7069.4 | 40.0 |
| medium | 15 | 40.0 | 0.0 | 20.0 | 3824.9 | 33956.0 / 35767.6 | 33956.5 / 35767.9 | 40.0 |
| large | 15 | 46.7 | 13.3 | 20.0 | 4376.8 | 34815.0 / 75204.7 | 34815.3 / 75204.9 | 20.0 |

Settings are whitespace words (not model tokens): small=180/overlap30/k3; medium=300/50/k4; large=420/70/k5; expansion adds two passages, fitted to TPM. No reranking.

## Additional timing
| Scenario | End-to-end first token p50/p95 | Provider TTFT p50/p95 | Answer release p50/p95 | Validation hold p50/p95 |
|---|---|---|---|---|
| steady [115c27db0d] | 242.9 / 745.0 | 101.0 / 124.6 | not measured | 128.0 / 638.2 |
| burst [115c27db0d] | 630.8 / 1064.6 | 145.7 / 925.7 | not measured | 119.0 / 442.9 |
| sustained_overload [115c27db0d] | 18474.9 / 24559.2 | 100.9 / 184.1 | not measured | 131.3 / 4039.8 |
| per_minute_limit_halved [115c27db0d] | 15011.2 / 15259.1 | 101.2 / 569.3 | not measured | 108.3 / 10003.8 |
| daily_budget_exhausted [115c27db0d] | 214.3 / 729.2 | 99.8 / 100.5 | not measured | 111.6 / 624.2 |
| overload_limiter_off [115c27db0d] | 10795.5 / 23889.0 | 99.9 / 406.1 | not measured | 121.0 / 1827.3 |
| retry_disabled [d434de11a7] | 806.9 / 1241.6 | 159.5 / 440.6 | not measured | 151.9 / 352.4 |
| retry_enabled [664c63466d] | 1447.7 / 1746.7 | 159.4 / 165.3 | not measured | 134.0 / 177.0 |
| ask [65e18a2967] | 3284.2 / 3284.2 | 1446.5 / 1446.5 | not measured | 1827.8 / 1827.8 |
| retrieval_eval [c1df428b59] | 2677.1 / 7069.4 | 1167.3 / 1520.5 | not measured | 1469.3 / 5624.5 |
| retrieval_eval [1f5d860c09] | 34641.5 / 65805.3 | 1053.6 / 1962.0 | not measured | 12915.0 / 60116.7 |

## Slow successful request trace
Request `851aade854f0` (real, retrieval_eval): total 85965.0 ms; queue_wait_ms=83577.4 ms; budget_wait_ms=not measured; working_ms=2377.7 ms; retry_wait_ms=0.0 ms; first_token_ms=85964.6 ms; provider_ttft_ms=820.1 ms; answer_release_ms=not measured; validation_hold_ms=60484.0 ms; residual scheduling/validation overhead=9.9 ms. See matching events.jsonl records.
