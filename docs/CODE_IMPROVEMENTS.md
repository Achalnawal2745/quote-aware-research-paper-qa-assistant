# Code improvements applied

## Retrieval (`relay/retrieval.py`)
- Replaced raw word matching with conservative token normalization and stop-word removal.
- Added a small, explicit technical synonym map for terms found in the three-paper library.
- Added low-weight query expansion, exact-near-phrase scoring, and paper-title term bonus.
- Added mild page-level diversity to avoid spending all top-k slots on overlapping chunks from one page.
- Exposed score components (`score_bm25`, `score_phrase`, `score_title`) for debugging.
- Added `--expand` and `--top-k` CLI options.
- Scores remain ranking signals, not confidence or answer correctness.

## Calibration (`relay/calibrate.py`)
- Rejects non-real runs and requires five successful real streaming calls with usage.
- Reports p50/p95/p99 TTFT and output token rate.
- Separates measured timing estimates from assumptions such as concurrency slowdown and quota limits.
- Does not claim to infer RPM/TPM/RPD/TPD from latency probes.

## Stand-in (`relay/standin.py`)
- Preserves provider-like daily request/token headers used by the existing tests.
- Adds explicit `x-relay-*` headers for simulated minute and daily budgets, avoiding confusion between the two windows.

## Secrets
- Removed the local `.env` from this working copy.
- Expanded `.gitignore` and kept an empty `.env.example`.
- The key previously included in the original archive must be revoked. A new key should only live in the user's local `.env`.

## Verification performed
- `pytest -q`: 37 passed.
- `python -m relay.retrieval_audit`: medium setting lexical first-pass hits 11/12 and after optional +2 retrieval hits 12/12. This is phrase coverage only, not semantic answer accuracy.
