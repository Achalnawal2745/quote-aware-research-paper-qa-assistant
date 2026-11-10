# The Relay — Bounded, Quota-Aware Research Paper QA Assistant

A production-grade Python research-paper QA system with quota-aware scheduling, dual execution (real Groq API + local calibrated stand-in simulator), verbatim citation verification, and reproducible open-loop load experiments.

Evaluated over three arXiv foundation papers:
1. **Attention Is All You Need** (`arXiv:1706.03762v7`)
2. **Moshi: a speech-text foundation model for real-time dialogue** (`arXiv:2410.00037v1`)
3. **Dynamic Chunking for End-to-End Hierarchical Sequence Modeling** (`arXiv:2507.07955v2`)

---

## 📦 Key Deliverables

* **`writeup.pdf`**: The official **2-page final engineering report**, covering architectural design, Table 1–3 findings, latency breakdowns, retrieval trade-offs, production failure modes, Vaani feedback, and programming assistant reflection.
* **`results.csv`**: Complete raw dataset with **258 requests** across all 40 schema columns (212 simulated stress-test requests + 46 real Groq API requests).
* **`docs/generated-tables.md`**: Fully calculated Tables 1, 2a, 2b, 3, and the slow-request trace (`851aade854f0`).
* **`conversation-history/antigravity-coding-session.md`**: Unedited export of coding interactions, error diagnoses, and decisions.

---

## 🚀 Quickstart & Installation

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements-tested.txt

# 3. Run regression and reconstruction tests
pytest -q
```

---

## 🔑 Configuration (`.env`)

To run real Groq queries, copy `.env.example` to `.env`:

```env
GROQ_API_KEY=gsk_your_actual_key_here
RELAY_MODEL=openai/gpt-oss-20b
```

> **Security Note:** `.env` is explicitly gitignored and excluded from version control.

---

## 📊 Summary of Experimental Results

### Table 1: Real Measured Groq Limits
* **Tokens/min (TPM)**: `8,000` *(observed via `x-ratelimit-limit-tokens` header)*
* **Requests/day (RPD)**: `1,000` *(observed via `x-ratelimit-limit-requests` header)*
* **Requests/min (RPM)**: `30` *(documented fallback)*
* **Time To First Token (TTFT)**: ~`1,400 ms` on real Groq streaming

### Table 2a & 2b: Load Scenarios (Stand-in Simulator)
* **Steady (3 RPM)**: 100% OK, p50 total latency 242.9 ms, 0 queue depth.
* **Burst (12 batch)**: 25% OK, 75% shed cleanly by local queue capacity without remote crashes.
* **Sustained Overload (20 RPM)**: 47.5% OK, 52.5% rate-limited locally; queue wait inflates p50 latency to 18,475 ms.
* **Limiter Disabled Ablation**: Without client-side admission control, **70% of requests crash with upstream provider HTTP 429s**.

### Table 3: Retrieval Ablation (Real Groq API, 15 Questions)
| Setting | Questions | Correct+Cited % | Wrong % | Correct Refusal % | Wrong Refusal % | Tokens/Answer | Total Latency (p50 / p95) |
|---|---|---|---|---|---|---|---|
| **Small (180w, k=3)** | 15 | **40.0%** | **0.0%** | **20.0%** | **40.0%** | 2,292.6 | 2,677 ms / 7,069 ms |
| **Medium (300w, k=4)** | 15 | **40.0%** | **0.0%** | **20.0%** | **40.0%** | 3,824.9 | 33,956 ms / 35,768 ms |
| **Large (420w, k=5)** | 15 | **46.7%** | **13.3%** | **20.0%** | **20.0%** | 4,401.5 | 34,815 ms / 75,205 ms |

* **Key Trade-off**: Large chunks boost answer accuracy by providing sufficient context for complex definitions (e.g. Mimi neural codec), but prompt reservations grow to 4,401 tokens/ans, causing 13.3% of consecutive requests to be shed by the local 8,000 TPM rate limiter before outer deadlines.

---

## 🛠 Reproducing Experiments & Tables

```powershell
# 1. Audit retrieval phrase coverage across chunk settings
python -m relay.retrieval_audit

# 2. Check token budget estimates
python -m relay.budget_plan

# 3. Run single question on real Groq
python -m relay.run ask --source real --confirm-real --deadline 60 --output runs/real-ask

# 4. Run 15-question evaluation on real Groq
python -m relay.run eval --source real --confirm-real --settings small,medium,large --interval 25 --deadline 90 --output runs/real-eval --append

# 5. Extract measured limits
python -m relay.limits_from_calls runs/real-ask runs/real-eval --out docs/measured-limits.json

# 6. Merge datasets and regenerate markdown tables
python -m relay.collect runs/v2-suite/results.csv runs/v2-retry-0/results.csv runs/v2-retry-1/results.csv runs/real-ask/results.csv runs/real-eval/results.csv --output results.csv
python -m relay.report results.csv --limits docs/measured-limits.json --output docs/generated-tables.md

# 7. Rebuild publication-grade 2-page PDF writeup
python build_writeup_pdf.py
```

---

## 📁 Repository Structure

```text
relay/
├── build_writeup_pdf.py     # ReportLab generator for strict 2-page PDF
├── writeup.pdf              # Final 2-page submitted writeup
├── results.csv              # Master results dataset (258 rows)
├── requirements-tested.txt  # Pinned dependencies
├── pyproject.toml           # Build & tool configuration
├── data/                    # Raw arXiv papers, chunk manifests & 15 verified questions
├── docs/                    # Measured limits, generated tables & audits
├── conversation-history/    # Unedited conversation transcripts (secrets redacted)
├── relay/                   # Core Python package:
│   ├── pipeline.py          # 5-stage pipeline, validation & graceful fallback
│   ├── retrieval.py         # Inverted index, synonym map & diversity ranking
│   ├── budget.py            # Rolling window TPM/RPD reservation & admission control
│   ├── adapter.py           # SSE streaming client, TTFT measurement & retry logic
│   ├── standin.py           # Calibrated local mock model server (FastAPI)
│   ├── run.py               # CLI runner for ask/probe/eval/suite
│   ├── report.py            # Table 1, 2a, 2b, 3 generation logic
│   └── common.py            # Monotonic clock tracking, UTF-8 artifacts & schema
├── runs/                    # Raw telemetry traces (calls.jsonl, events.jsonl)
└── tests/                   # 37 unit and regression tests
```
