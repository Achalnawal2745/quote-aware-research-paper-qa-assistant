# Reconstruction validation

All measurements below are uncalibrated stand-in data. No hosted Groq calls were made.

| Scenario | Requests | OK | Rate limited | Timeout | Error | Model calls | Provider 429 encounters | Retries |
|---|---|---|---|---|---|---|---|---|
| steady | 8 | 8 | 0 | 0 | 0 | 10 | 0 | 0 |
| burst | 12 | 3 | 9 | 0 | 0 | 4 | 0 | 0 |
| sustained_overload | 40 | 19 | 21 | 0 | 0 | 21 | 0 | 0 |
| per_minute_limit_halved | 12 | 7 | 4 | 1 | 0 | 7 | 0 | 0 |
| daily_budget_exhausted | 20 | 8 | 12 | 0 | 0 | 10 | 0 | 0 |
| overload_limiter_off | 40 | 12 | 28 | 0 | 0 | 67 | 53 | 23 |
| retry_disabled | 40 | 15 | 8 | 0 | 17 | 32 | 0 | 0 |
| retry_enabled | 40 | 12 | 21 | 3 | 4 | 30 | 0 | 11 |

Tests: 35 passed. Raw trace and prompt/response/usage logs are retained per run. The full generated latency/outcome/retrieval tables are in `generated-tables.md`.

This comparison is one seeded synthetic operational run, not a general causal conclusion. Retry decisions change random draw order. The halved-limit scenario includes one actual deadline timeout; it has not been removed.

Raw historical v1 results remain archived separately. The original generated personal report is archived, not offered as a current write-up.
