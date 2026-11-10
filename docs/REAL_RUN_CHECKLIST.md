# Real-run checklist

1. Set `GROQ_API_KEY` privately in the shell or `.env`. Never paste it into chat. Revoke only if actually exposed.
2. Verify current model availability and your account's RPM/TPM/RPD/TPD; check separate input/output limits if applicable. Shared organization usage matters.
3. Run `relay.retrieval_audit` and `relay.budget_plan`. Budget for repairs, refusals, verifiers, probes and reruns. Estimates are not actual tokens. Split across days if needed.
4. Run ONE `relay.run ask --source real --confirm-real --deadline 60 --output runs/real-ask`. Inspect content, finish reason, actual usage, reasoning/content TTFT and headers. Fix output cap or model before spending more.
5. Collect modest paced probes across prompt lengths. Keep failures and usage uncertainty. Inspect documentation and observed reset headers; do not assume midnight IST/UTC.
6. Optional `relay.limit_probe --confirm-real`: small sequential probe with call/token/time bounds. It stops on 429 and only recovers after a valid Retry-After that fits its wait budget. It skips daily exhaustion. Check current terms first; never create accounts or rotate keys to bypass limits.
7. Generate limits with `relay.limits_from_calls`; distinguish documented fallback, observed response values, accepted concurrency lower bounds, and recovery upper bounds.
8. Run quality evaluation for all three settings and 15 questions, using `--settings` / `--append` across sessions if needed. Do not silently mix old and new question sets. Inspect PDFs manually before grading.
9. Export manual grades and evidence-based notes; do not grade synthetic fixtures. Audit the verifier-off policy against an always-verify subset if budget permits.
10. Fit calibration from real calls with usage; label unidentifiable slowdown/tail assumptions. Rerun synthetic load scenarios in a fresh directory using the fitted parameters and explicitly configured observed quotas.
11. Collect current-schema rows, regenerate tables, inspect the slow trace and verify totals/denominators. Run tests AFTER rebuilding root results.csv.
12. Write your own two-page report and feedback; export the actual conversations. Scan for secrets, remove private ledgers/keys from sharing, and verify Drive permissions before the deadline.
