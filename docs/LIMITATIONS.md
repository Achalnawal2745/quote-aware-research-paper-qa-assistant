# Known limitations

## Unmeasured
No real Groq API calls were made during reconstruction. Real compatibility, model availability, account-specific quotas/resets, semantic quality and calibrated load behavior remain unestablished. Public defaults are documented, not observed account values. Bundled stand-in timing/tail/concurrency parameters are assumed.

## Safety and evaluation
Citation/quote validity is necessary but not semantic entailment. A retained refusal may be wrong; it requires human grading. An LLM verifier is fallible. Evidence-term phrase coverage can yield false positives and false negatives and is not a quality grade. Seed references require rendered-PDF checks; absence of keywords does not conclusively prove unanswerability. The revised question IDs differ from v1, so hashes must be respected.

## Scheduling and quota accounting
Single-process ledger only; no distributed or per-user fairness. Other apps' usage is visible only through available headers. Budget waits occupy worker slots and can cause head-of-line blocking. Header observations may be stale under concurrency. Bytes/3 is a heuristic, not an upper bound. Daily token and request resets may differ; request resets do not clear token spend. Unknown token-day resets require review and conservative stopping. Never reset a ledger merely to evade a quota.

Cancellation does not guarantee remote cancellation or zero billing. Failed calls can have unknown token usage; reservations remain and incomplete-usage flags are retained. Local queue rejection, local quota rejection and provider throttling have separate attribution. The daily source-excerpt fallback is not a generated answer.

## Stand-in and experiments
Synthetic outputs and random refusals say nothing about real answer quality. Service uses heuristic token counts and a simplified quota window, not Groq's exact implementation. The output cap is not a full simulator tokenizer/maximum-reservation model. Generation piece size and scheduler jitter affect latency. Calibration's linear prefill fit and tail estimates are unstable for small samples; concurrency slowdown is not identified without a dedicated experiment.

The limiter-off ablation deliberately disables header learning and cooldown state; only per-attempt Retry-After/backoff remains. It is not a production policy. Retry comparisons use a seed but are not request-paired: retries change random draw order. A one-seed result is not a universal causal claim. Small samples cannot establish stable p99 behavior; use more samples/replicates when feasible.

Append creates new sessions; it does not resume individual unfinished questions or deduplicate repeated evaluations. Artifact provenance must be retained when collecting runs. Recovery timing is a successful-observation upper bound, not an exact provider reset. Accepted-call overlaps are only concurrency lower bounds. A probe's estimated token budget cannot guarantee actual token consumption.

## Deliberate scope cuts
No reranking, vector database, elaborate UI, auth, distributed orchestration or multi-tenant isolation. Model verification is an explicit cost/assurance policy, not an automatic semantic certainty detector. Personal reflection, Vaani feedback, real measurements and final two-page writing are not fabricated.
