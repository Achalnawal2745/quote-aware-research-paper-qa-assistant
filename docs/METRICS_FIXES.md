# Measurement corrections

This version separates local scheduling delays and records distinct response milestones.

## CSV fields

- `queue_wait_ms`: time waiting to acquire the pipeline semaphore.
- `budget_wait_ms`: time sleeping while waiting for local request/token budget availability.
- `first_token_ms`: end-to-end time from request arrival until the first visible draft content delta. It is populated from the timestamp captured by the streaming adapter.
- `provider_ttft_ms`: provider-side time from model-call dispatch until the first visible content delta.
- `answer_release_ms`: end-to-end time from request arrival until the completed answer is returned after validation/release.
- `validation_hold_ms`: elapsed time from the first visible draft content until answer release.

Historical bundled rows are retained. Their new `budget_wait_ms` and `answer_release_ms` values are blank because those measurements were not recorded at the time; no historical values are fabricated.

## Tests

Run:

```powershell
python -m pytest -q
```

The added tests verify that budget waits do not inflate semaphore queue waits and that first-token latency is distinct from answer-release latency.
