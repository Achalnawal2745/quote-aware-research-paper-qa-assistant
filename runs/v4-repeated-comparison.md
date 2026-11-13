# Repeated synthetic retry experiment

**Source:** Synthetic stand-in only. These measurements are not real Groq API results.

**Design:** Five repetitions per configuration, 40 requests per repetition, with matching seeds across configurations. Retries can change random draw order and request scheduling, so this is not request-level causal pairing.

## 1. Individual run results

| Retries | Run | Seed | Requests | Successes | Success rate | Rate limited | Timeouts | Errors | Latency p95 ms | Queue p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 1 | 31 | 40 | 9/40 | 22.5% | 16 | 2 | 13 | 1704.3 | 1468.6 |
| 0 | 2 | 32 | 40 | 5/40 | 12.5% | 18 | 5 | 12 | 1757.1 | 1691.1 |
| 0 | 3 | 33 | 40 | 10/40 | 25.0% | 21 | 5 | 4 | 1865.5 | 1628.9 |
| 0 | 4 | 34 | 40 | 11/40 | 27.5% | 19 | 2 | 8 | 1885.2 | 1303.3 |
| 0 | 5 | 35 | 40 | 9/40 | 22.5% | 17 | 4 | 10 | 1952.7 | 1668.5 |
| 1 | 1 | 31 | 40 | 6/40 | 15.0% | 21 | 7 | 6 | 1800.2 | 1774.9 |
| 1 | 2 | 32 | 40 | 4/40 | 10.0% | 22 | 7 | 7 | 1935.8 | 1768.7 |
| 1 | 3 | 33 | 40 | 8/40 | 20.0% | 22 | 8 | 2 | 1930.4 | 1710.9 |
| 1 | 4 | 34 | 40 | 6/40 | 15.0% | 22 | 8 | 4 | 1781.7 | 1766.2 |
| 1 | 5 | 35 | 40 | 6/40 | 15.0% | 21 | 9 | 4 | 1933.2 | 1715.7 |

## 2. Aggregate results across five repetitions

| Metric (mean ± sample SD) | Retries disabled | Retries enabled |
|---|---|---|
| Success rate (%) | 22.00 ± 5.70 | 15.00 ± 3.54 |
| Rate-limited requests | 18.20 ± 1.92 | 21.60 ± 0.55 |
| Timeouts | 3.60 ± 1.52 | 7.80 ± 0.84 |
| Other errors | 9.40 ± 3.58 | 4.60 ± 1.95 |
| Average retries/request | 0.00 ± 0.00 | 0.12 ± 0.05 |
| Successful latency p50 (ms) | 1267.80 ± 191.33 | 1356.36 ± 128.58 |
| Successful latency p95 (ms) | 1832.96 ± 100.54 | 1876.26 ± 78.17 |
| Queue wait p95 (ms) | 1552.08 ± 164.04 | 1747.28 ± 31.21 |
| Retry wait p95 (ms) | 0.00 ± 0.00 | 277.27 ± 146.41 |
| Average tokens/complete record | 505.98 ± 87.79 | 317.28 ± 63.14 |
| Peak queue | 6.00 ± 0.00 | 6.20 ± 0.45 |

## 3. Pooled outcome totals

| Configuration | Requests | Successful | Success rate | Rate limited | Timeouts | Errors |
|---|---|---|---|---|---|---|
| Retries disabled | 200 | 44 | 22.0% | 91 | 18 | 47 |
| Retries enabled | 200 | 30 | 15.0% | 108 | 39 | 23 |

## 4. Seed-level comparison

| Seed | Retries disabled | Retries enabled | Difference (enabled - disabled) |
|---|---|---|---|
| 31 | 22.5% | 15.0% | -7.5 percentage points |
| 32 | 12.5% | 10.0% | -2.5 percentage points |
| 33 | 25.0% | 20.0% | -5.0 percentage points |
| 34 | 27.5% | 15.0% | -12.5 percentage points |
| 35 | 22.5% | 15.0% | -7.5 percentage points |

## 5. Interpretation

- Mean success-rate difference (enabled minus disabled): **-7.00 percentage points**.
- Retries disabled mean success rate: **22.00%**.
- Retries enabled mean success rate: **15.00%**.
- The standard deviation describes variation across five runs; it is not a confidence interval.
- Seed-level comparisons are operational comparisons, not request-paired causal estimates.
- Retry behaviour must be assessed alongside timeouts, rate limits, latency, queue waiting and model calls.
- A lower generic error count does not automatically mean a better outcome if timeouts or rate limits increase.
- Synthetic stand-in results cannot establish real provider performance, real API cost, or answer quality.
