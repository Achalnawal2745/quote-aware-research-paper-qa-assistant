# Reconstruction from the supplied Claude history

Implemented in this workspace from the visible commands, not by claiming access to Claude's filesystem.

## Reconstructed changes
- `common.py`: dotenv, extra rejection/reasoning/expansion fields, append mode.
- `retrieval.py`: at most two additional expansion passages, rather than doubling.
- `adapter.py`: configurable completion cap, optional reasoning effort, reasoning-vs-content timing, finish-reason detection, error attribution.
- `pipeline.py`: TPM-fitted expansion, retained first-pass refusal on optional failure, honest daily-exhaustion source excerpts.
- `budget.py`: daily-exhaustion checks and experiment-only header-learning disable switch.
- `run.py`: selective settings, append, suite scale/scenario selection, documented-quota defaults and limiter-off ablation.
- `budget_plan.py`: first/expanded context estimates and refusal-expansion planning.
- `report.py`: local/provider rejection split.
- `calibrate.py`: generation rate includes the reasoning interval.
- `retry_experiment.py`: revised runner arguments.
- New: `retrieval_audit.py`, `limit_probe.py`, `limits_from_calls.py` and regression tests.
- Revised questions: plausible unanswerables, related-work trap, cross-paper item, evidence-term metadata.

## Fixes beyond the history
- Append validates schema before opening files and refuses accidental overwrite.
- Every session has separate configuration, ID and absolute call dispatch timestamps. Queue/concurrency calculations do not combine unrelated monotonic clocks.
- `.env` is loaded BEFORE resolving model defaults; shell values still win.
- Optional expansion/verifier work has a release margin so an available refusal survives a deadline.
- Probe wall-clock deadlines are enforced; missing, excessive or daily Retry-After situations skip recovery rather than retry early.
- Probe attempts add to the shared real-run spend ledger; no hidden unlimited daily probing.
- Daily request reset never silently clears token-day spend, and a known request reset is checked before admission blocks forever.
- Token estimates are explicitly not upper bounds. Phrase coverage is not a semantic quality measure or guaranteed recall bound.
- New question-set hashes prevent silent mixing of reassigned question IDs in quality reports.
- Synthetic-only inputs are rejected by the real-limits extractor. Accepted-call concurrency is labeled a lower bound; recovery timing is labeled an upper bound.
- Quantitative outcomes are rerun here rather than copied from Claude's log. Different timing/scheduling can produce different results.

## Preserved provenance
Old PDFs are unchanged. Old raw runs, old questions, the original results and generated write-up are archived under `archive/original-v1/`; they are not relabeled as new-schema results. The old ZIP was also retained separately in the workspace. No original run was silently deleted to hide an inconvenient outcome.

The personal write-up generator is no longer active. The two-page final report, personal Vaani feedback and actual conversation exports remain the candidate's work. No real provider measurement or key exposure is claimed.
