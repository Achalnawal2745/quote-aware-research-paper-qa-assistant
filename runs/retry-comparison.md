# Retry experiment comparison

This report compares two independent stand-in experiment runs. The experiments are not request-paired causal trials. Random failure draws and request scheduling can differ between runs. Stand-in results are synthetic and must not be presented as real Groq API performance or quality measurements.

## Experiment summary
| Metric | v3-retry-0 | v3-retry-1 |
|---|---|---|
| Requests | 40 | 40 |
| Successful requests | 8 | 6 |
| Success rate (%) | 20.0 | 15.0 |
| Rate-limited (%) | 40.0 | 52.5 |
| Timeout (%) | 7.5 | 15.0 |
| Other errors (%) | 32.5 | 17.5 |
| Average retries/request | 0.00 | 0.15 |
| Total latency p50 (ms) | 1203.6 | 1376.9 |
| Total latency p95 (ms) | 1681.8 | 1869.2 |
| Total latency p99 (ms) | 1727.1 | 1961.8 |
| First-token p50/p95 (ms) | 1203.5 / 1681.8 | 1376.8 / 1869.1 |
| Provider TTFT p50/p95 (ms) | 171.4 / 184.7 | 160.6 / 175.3 |
| Validation hold p50/p95 (ms) | 496.8 / 612.3 | 495.5 / 625.9 |
| Queue wait p50/p95 (ms) | 0.1 / 1493.2 | 0.0 / 1790.1 |
| Retry wait p50/p95 (ms) | 0.0 / 0.0 | 0.0 / 322.7 |
| Peak queue | 6 | 6 |
| Provider rejections | 0 | 0 |
| Local rejections | 16 | 21 |
| Complete usage records | 24 | 26 |
| Average tokens/complete record | 522.0 | 303.8 |
| Cost per 1000 successful answers | 0.0000 | 0.0000 |

## Interpretation notes

- Success rate uses all submitted requests as the denominator.
- Latency percentiles use successful requests only.
- Token averages exclude records with incomplete usage.
- Provider rejections are identified by `provider_429`.
- Other rate-limit rejections are classified as local/application rejections, including bounded queue rejection.
- A zero stand-in cost is synthetic and is not a paid-equivalent estimate.
- Compare retries, queue waiting, and latency together; retries can increase load and waiting even when they recover some errors.
