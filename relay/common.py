
import csv
import json
import math
import os
import re
import time
import uuid

from email.utils import parsedate_to_datetime
from pathlib import Path


FIELDS = [
    'request_id', 'scenario', 'source', 'start_time', 'first_token_ms',
    'answer_release_ms', 'total_ms', 'status', 'retries', 'tokens_in', 'tokens_out',
    'retrieval_setting', 'answer_grade', 'provider_ttft_ms',
    'validation_hold_ms', 'queue_wait_ms', 'budget_wait_ms', 'working_ms',
    'retry_wait_ms', 'rate_limit_hits', 'queue_enter_ms',
    'queue_exit_ms', 'queue_depth', 'offered_offset_ms', 'run_id',
    'run_duration_s', 'offered_rate_per_min', 'actual_cost_usd',
    'usage_complete', 'retrieved_chunks', 'context_est_tokens',
    'retrieval_degraded', 'verification_policy', 'model_calls',
    'refused', 'answer', 'error', 'question_id', 'rejection_source',
    'provider_first_any_ms', 'expansion_note', 'session_id',
    'question_set_sha256'
]


def estimate_tokens(text):
    """Heuristic token estimate, not a guaranteed upper bound."""
    if text is None:
        text = ""

    if not isinstance(text, str):
        text = str(text)

    return max(1, math.ceil(len(text.encode("utf-8")) / 3))


def parse_duration(value):
    """Parse durations such as 250ms, 2.5s, 3m, or 1h."""
    if value is None:
        return None

    value = str(value).strip().lower()

    if not value:
        return None

    try:
        return max(0.0, float(value))
    except ValueError:
        pass

    units = {
        "ms": 0.001,
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400
    }

    pattern = r"(\d+(?:\.\d+)?)(ms|s|m|h|d)"

    matches = list(re.finditer(pattern, value))

    if not matches:
        return None

    # Reject partially matched or malformed strings.
    reconstructed = "".join(match.group(0) for match in matches)

    if reconstructed != value:
        return None

    return sum(
        float(match.group(1)) * units[match.group(2)]
        for match in matches
    )


class Artifacts:

    def __init__(self, directory, append=False):
        self.path = Path(directory)
        self.path.mkdir(parents=True, exist_ok=True)

        csv_path = self.path / "results.csv"

        fresh = (
            not csv_path.exists()
            or csv_path.stat().st_size == 0
        )

        orphaned = any(
            (self.path / name).exists()
            and (self.path / name).stat().st_size > 0
            for name in ["events.jsonl", "calls.jsonl"]
        )

        if not append and (not fresh or orphaned):
            raise ValueError(
                "Output already contains results; "
                "choose a new directory or use --append"
            )

        if append and not fresh:
            with csv_path.open(
                "r",
                newline="",
                encoding="utf-8-sig"
            ) as file:
                existing = next(csv.reader(file), [])

            if existing != FIELDS:
                raise ValueError(
                    "Cannot append: CSV schema differs; "
                    "use a fresh output directory"
                )

        self.session_id = uuid.uuid4().hex
        self.origin = time.perf_counter()
        self.origin_unix_ms = time.time() * 1000

        mode = "a" if append else "w"

        self.csv = csv_path.open(
            mode,
            newline="",
            encoding="utf-8"
        )

        self.writer = csv.DictWriter(
            self.csv,
            fieldnames=FIELDS
        )

        if fresh:
            self.writer.writeheader()
            self.csv.flush()

        self.trace = (
            self.path / "events.jsonl"
        ).open(mode, encoding="utf-8")

        self.calls = (
            self.path / "calls.jsonl"
        ).open(mode, encoding="utf-8")

        self.event(
            "session",
            "session_start",
            origin_unix_ms=self.origin_unix_ms
        )

    def event(self, rid, name, **extra):
        record = {
            "request_id": rid,
            "event": name,
            "session_id": self.session_id,
            "unix_ms": time.time() * 1000,
            "monotonic_ms": (
                time.perf_counter() - self.origin
            ) * 1000
        }

        record.update(extra)

        self.trace.write(
            json.dumps(record, ensure_ascii=False) + "\n"
        )

        self.trace.flush()

    def call(self, record):
        record = dict(record)

        dispatch_ms = record.get("dispatch_ms", 0)

        record["session_id"] = self.session_id

        record["dispatch_unix_ms"] = (
            self.origin_unix_ms + dispatch_ms
        )

        self.calls.write(
            json.dumps(record, ensure_ascii=False) + "\n"
        )

        self.calls.flush()

    def row(self, row):
        output = {
            field: (
                self.session_id
                if field == "session_id"
                else row.get(field, "")
            )
            for field in FIELDS
        }

        self.writer.writerow(output)
        self.csv.flush()

    def close(self):
        for file in (self.csv, self.trace, self.calls):
            if not file.closed:
                file.close()


def load_dotenv(path=".env"):
    """
    Minimal KEY=VALUE loader.

    Existing shell environment variables take priority.
    Secret values are never logged.
    """
    dotenv_path = Path(path)

    if not dotenv_path.exists():
        return

    for line in dotenv_path.read_text(
        encoding="utf-8"
    ).splitlines():

        line = line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        if line.startswith("export "):
            line = line[7:].strip()

        key, value = line.split("=", 1)

        key = key.strip()
        value = value.strip()

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in ("'", '"')
        ):
            value = value[1:-1]

        valid_key = re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*",
            key
        )

        if valid_key and key not in os.environ:
            os.environ[key] = value


def retry_after_seconds(value, now=None):
    """
    Parse HTTP Retry-After.

    Supports:
    - Delta seconds, e.g. '5'
    - HTTP dates, e.g. 'Wed, 21 Oct 2015 07:28:00 GMT'

    Returns None when the value cannot be parsed.
    """
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    try:
        return max(0.0, float(value))
    except (ValueError, TypeError):
        pass

    try:
        retry_date = parsedate_to_datetime(value)

        if retry_date.tzinfo is None:
            return None

        current_time = time.time() if now is None else now

        return max(
            0.0,
            retry_date.timestamp() - current_time
        )

    except (ValueError, TypeError, OverflowError):
        return None
