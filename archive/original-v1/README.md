# The Relay
### Evidence-first paper QA under API quotas

**Status: working local implementation; real Groq measurement and human answer grading are pending. Not yet a complete assignment submission.**

This project implements a bounded research-paper assistant, a streaming OpenAI-compatible HTTP stand-in, open-loop experiments, raw traces, and reproducible tables. All bundled model results are **stand-in data with assumed parameters**, not Groq measurements. No API key is included.

## Start here

```bash
python -m venv .venv
source .venv/bin/activate             # Windows: .venv\Scripts\activate
pip install -e '.[test]'
# Optional: pip install -r requirements-tested.txt  # exact sandbox-tested versions
pytest -q
python -m relay.budget_plan
```

The exact PDFs and extracted page text are bundled. Rebuild with:

```bash
python -m relay.retrieval --fetch
python -m relay.retrieval --query 'How does decoder masking work?' --setting small
```

`data/manifest.json` contains pinned URLs, SHA-256 hashes and page counts. The arXiv version identifiers were also checked in the extracted first pages. Chunk IDs preserve PDF page numbers (not necessarily printed article page labels). Splits never cross pages. Chunk sizes are **whitespace words, not model tokens**.

## Run the synthetic service

In terminal A:

```bash
export RELAY_ADMIN_TOKEN='choose-a-local-test-token'
python -m uvicorn relay.standin:app --host 0.0.0.0 --port 8001
```

In terminal B, set the same admin token, then:

```bash
export RELAY_ADMIN_TOKEN='choose-a-local-test-token'
python -m relay.run ask --source stand-in --output runs/my-ask
python -m relay.run suite --source stand-in --output runs/my-suite \
  --n 10 --interval 5.5 --concurrency 2 --queue 6 --deadline 3 \
  --rpm 10000 --tpm 10000000 --rpd 100000 --tpd 10000000
python -m relay.report runs/my-suite/results.csv --output runs/my-suite/tables.md
python -m relay.retry_experiment
```

The deliberately permissive **client** quota flags in the synthetic suite allow us to observe **server** 429 behavior. They are not Groq limits. Suite service RPM is an explicitly assumed 12, halved to 6 in the quota-change scenario. The service uses real 60-second windows. Steady traffic is below that synthetic quota; overload lasts several request deadlines. It is a small demonstration, not a robust tail-capacity estimate.

The server has SSE, usage chunks, `[DONE]`, 429 + retry headers, per-minute request/token counters, day counters, transient failures, long-tail slow success, and in-flight-dependent slowdown. Admin reconfiguration requires its token and rejects changes during active work. Do not expose this test admin endpoint in production.

**Synthetic responses are extractive fixtures. They do not answer questions semantically.** Their `answer_grade` is blank. Their reported tokens are a byte-based simulation, not a real model tokenizer. Timings also include local HTTP, scheduling, and retrieval overhead.

## Real Groq runs — do this privately

Read `docs/REAL_RUN_CHECKLIST.md` first. Inspect your organization's current Limits page; the public defaults in this project are not a promise about your account. The default candidate model is `openai/gpt-oss-20b`; verify that it is available to you.

```bash
# Enter the secret without adding its value to command history (bash):
read -rs -p 'Groq key: ' GROQ_API_KEY; echo
export GROQ_API_KEY

python -m relay.run probe --source real --confirm-real --n 5 --interval 12 \
  --deadline 60 --output runs/real-probe

# Inspect calls.jsonl and headers, then budget and run the quality experiment.
# Set quota flags to the limits confirmed for your account/model.
python -m relay.budget_plan
python -m relay.run eval --source real --confirm-real --interval 35 \
  --deadline 90 --output runs/real-eval

python -m relay.calibrate runs/real-probe --output runs/calibration.json
python -m relay.grade runs/real-eval/results.csv --output runs/review.csv
# Manually inspect answers against papers, fill grade + evidence-based review_notes.
python -m relay.grade runs/real-eval/results.csv --grades runs/review.csv \
  --output runs/real-eval/graded.csv
```

Do not blindly execute all these commands: choose the number of real calls and pacing after checking the budget. Draft-only evaluation needs 45 calls. The single expansion/repair budget can double draft calls; LLM verification adds calls. Conservatively estimated draft reservations currently total about 140k tokens; **this is not measured usage**. Allowance is shared with other usage.

If a reasoning model returns only reasoning or truncated/invalid JSON at the configured output cap, inspect the raw response and adjust the cap/model, then recompute reservations. No successful real-provider compatibility test has been possible without a key. Never silently turn off error logging to make results look better.

The optional verifier policies are `off`, `always`, and `audit` (every fifth request). These are explicit ablation choices, not a claim that a heuristic can reliably detect semantic uncertainty. Run a small `--verifier always` audit and compare manual grades before adopting the cheaper policy.

## Architecture and safety trade-off

1. Admission and deadline checks, bounded semaphore queue.
2. Heuristic query expansion (no hosted call).
3. BM25 passage retrieval tool.
4. Hosted-model JSON draft with per-claim quote and citation.
5. Deterministic schema/citation/quote checks; optional model verification.
6. One shared evidence-expansion/repair allowance, otherwise an explicit refusal.

The output is buffered until the validation policy finishes. `first_token_ms` is **user-visible answer TTFT**; `provider_ttft_ms` is the first content token of the first draft attempt that emits one, measured from that attempt's dispatch. All attempts retain their own timing in `calls.jsonl`. `validation_hold_ms` includes remaining draft generation and verification, not purely verifier compute. Progress messages are not answer tokens.

A quote can exist and still not entail the claim. Deterministic validation is NOT a semantic guarantee. Human quality grading is required; the optional LLM judge is also fallible. Refusals are successful service responses but must be separately judged for correctness.

Under token/day pressure, normal QA reduces initial passages; retrieval-evaluation runs do not silently change their configured setting. Actual passage count and degradation are logged. Expansion may still exceed the configured per-call reservation budget and be rejected rather than bypass the quota.

## Rate limits, retries and daily spend

- Local rolling-minute reservations cover estimated input plus maximum output; observed usage reconciles reservations.
- Daily spend is persisted for real runs in `runs/private-budget.json`. Use only one experiment process per ledger; this is not a distributed limiter.
- Limits and remaining availability from provider headers can tighten the client policy.
- Request headers refer to **RPD**, token headers to **TPM**, per current Groq docs.
- No reset at local midnight is assumed. Observed request-reset headers can advance the daily ledger; otherwise stop and investigate before manually resetting it.
- Token-day accounting remains conservative: it is not automatically reset on a separately observed token-day schedule.
- A shared cooldown prevents immediate repeated calls after a 429. Daily exhaustion opens a stop condition, not a retry storm.
- Only eligible transient errors receive bounded backoff+jitter retries if the remaining deadline permits. `Retry-After` is honored.
- Unknown usage (errors, cancellation, truncated streams) retains reservations and sets `usage_complete=False`. The provider might keep working after client abandonment.
- `rate_limited` includes local admission rejection and unrecovered provider throttling. `rate_limit_hits` counts observed provider 429s; a recovered request has final status `ok`.

There is no background worker that survives abandoned requests. Local cancellation is propagated to HTTP streaming, but remote cancellation/billing is not guaranteed.

## Results and reproducibility

`results.csv` currently contains **180 synthetic requests**: five baseline scenarios plus two retry comparisons. The earlier exploratory run remains in `runs/synthetic-smoke/` but is excluded from the root CSV. `docs/generated-tables.md` is generated from the root CSV.

```bash
python -m relay.collect runs/synthetic-baseline/results.csv \
  runs/retry-0/results.csv runs/retry-1/results.csv --output results.csv
python -m relay.report results.csv --output docs/generated-tables.md
```

For the final submission, collect real graded results plus **newly calibrated** stand-in runs, retaining provenance for every scenario. Never relabel the bundled assumed runs as calibrated. A `--calibration` file can update suite timing parameters; service quotas still require a deliberate documented configuration change in `run.py` (the built-in smoke quota is 12 RPM).

Each run retains:
- `results.csv`: one row per request, all brief-required columns plus reconstruction metadata.
- `calls.jsonl`: prompts, content, usage, relevant rate-limit headers, status and attempt timings. No Authorization header.
- `events.jsonl`: monotonic event traces and scenario configuration.
- `config.json`: arguments without keys.

Percentiles use NumPy's default linear interpolation, successful requests only. Error percentages are separate. Failed requests have blank TTFT. Offer duration is last scheduled arrival minus first; a burst has zero arrival duration and no finite offered RPM. Queue peak comes from CSV wait intervals of at least 1 ms. Successful-answer token means use only requests with complete usage, including measured attempts. Zero cash cost reflects free-tier/synthetic execution, not paid-equivalent value. Tail estimates from small samples are unstable.

`--limits reviewed-limits.json` can fill Table 1 with reviewed observations: JSON keys are the table's limit labels; values are `[label,value,evidence,confidence]`. The script does not promote documentation or concurrency lower bounds into measured provider limits.

## Submission still to finish

- [ ] Real Groq latency, usage, headers, and a compliant observed limit/recovery experiment.
- [ ] Human review of reference answers and all real quality outputs.
- [ ] Real-data calibration; rerun load scenarios and retrieval/verifier ablations.
- [ ] Choose and defend the retrieval setting; no winner is claimed yet.
- [ ] Complete the two-page write-up using real tables; `docs/writeup-draft.pdf` is visibly unfinished.
- [ ] Export this actual conversation into `conversation-history/`; no fabricated transcript.
- [ ] Personalize the assistant-use reflection and Vaani feedback.
- [ ] Scan for secrets, create the Drive folder, verify incognito access, and submit before 14 Nov 2026, 08:59 IST.

See `docs/LIMITATIONS.md` for important scope limitations and `docs/extraction-audit.md` for paper-specific retrieval traps.
