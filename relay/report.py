
"""Generate evidence-based Relay experiment reports.

Supports:
1. Single CSV reports.
2. Two-file comparisons.
3. Repeated synthetic experiment analysis across multiple runs.

Synthetic stand-in results must never be interpreted as real API measurements.
"""

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np


REQUIRED_COLUMNS = {
    "request_id", "scenario", "source", "status", "total_ms",
    "first_token_ms", "retries", "tokens_in", "tokens_out",
    "usage_complete", "actual_cost_usd", "run_id",
    "run_duration_s", "offered_rate_per_min", "queue_wait_ms",
    "working_ms", "retry_wait_ms", "provider_ttft_ms",
    "validation_hold_ms", "rejection_source", "session_id",
    "answer_grade", "retrieval_setting",
}

STATUS_ORDER = ["ok", "rate_limited", "timeout", "error"]

REPEATED_PREFIX = "v4-retry-"


def read_csv(path):
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")

        missing = REQUIRED_COLUMNS - set(reader.fieldnames)

        if missing:
            raise ValueError(
                f"{path} is missing required columns: "
                + ", ".join(sorted(missing))
            )

        return list(reader)


def number(value):
    if value in ("", None):
        return None

    try:
        result = float(value)

        if math.isfinite(result):
            return result

    except (TypeError, ValueError):
        pass

    return None


def numeric(rows, field):
    return [
        value
        for row in rows
        if (value := number(row.get(field))) is not None
    ]


def percentile(values, percentiles=(50, 95, 99)):
    if not values:
        return "not measured"

    result = np.percentile(values, percentiles)

    return " / ".join(f"{value:.1f}" for value in result)


def mean_value(values, digits=2):
    return (
        f"{np.mean(values):.{digits}f}"
        if values else "not measured"
    )


def mean_std(values, digits=2):
    if not values:
        return "not measured"

    mean = np.mean(values)
    std = np.std(values, ddof=1) if len(values) > 1 else 0.0

    return f"{mean:.{digits}f} ± {std:.{digits}f}"


def mdtable(headers, rows):
    result = "| " + " | ".join(headers) + " |\n"
    result += "|" + "|".join(["---"] * len(headers)) + "|\n"

    for row in rows:
        result += (
            "| "
            + " | ".join(
                str(value).replace("|", "/")
                for value in row
            )
            + " |\n"
        )

    return result


def percentage(count, total):
    if total == 0:
        return "not measured"

    return f"{count / total * 100:.1f}"


def peak_queue(rows):
    groups = defaultdict(list)

    for row in rows:
        enter = number(row.get("queue_enter_ms"))
        leave = number(row.get("queue_exit_ms"))

        if enter is None or leave is None or leave - enter < 1:
            continue

        session = (
            row.get("session_id")
            or row.get("run_id")
            or "legacy"
        )

        groups[session].extend([
            (enter, 1),
            (leave, -1)
        ])

    peak = 0

    for events in groups.values():
        current = 0

        for _, delta in sorted(
            events,
            key=lambda item: (item[0], item[1])
        ):
            current += delta
            peak = max(peak, current)

    return peak


def usage_statistics(rows):
    complete = [
        row for row in rows
        if str(row.get("usage_complete", "")).lower() == "true"
    ]

    totals = []

    for row in complete:
        input_tokens = number(row.get("tokens_in"))
        output_tokens = number(row.get("tokens_out"))

        if input_tokens is None or output_tokens is None:
            continue

        totals.append(input_tokens + output_tokens)

    return len(totals), mean_value(totals, 1)


def outcome_statistics(rows):
    total = len(rows)

    return {
        status: sum(
            row.get("status") == status
            for row in rows
        )
        for status in STATUS_ORDER
    }, total


def cost_statistics(rows):
    measured = [
        number(row.get("actual_cost_usd"))
        for row in rows
        if row.get("status") == "ok"
    ]

    measured = [
        value for value in measured
        if value is not None
    ]

    if not measured:
        return "not measured"

    return f"{sum(measured) / len(measured) * 1000:.4f}"


def experiment_summary(rows, label):
    total = len(rows)
    counts, _ = outcome_statistics(rows)

    successful = [
        row for row in rows
        if row.get("status") == "ok"
    ]

    retries = numeric(rows, "retries")
    usage_count, average_tokens = usage_statistics(rows)

    provider_rejections = sum(
        row.get("status") == "rate_limited"
        and row.get("rejection_source") == "provider_429"
        for row in rows
    )

    local_rejections = sum(
        row.get("status") == "rate_limited"
        and row.get("rejection_source") != "provider_429"
        for row in rows
    )

    durations = numeric(rows, "run_duration_s")
    offered = numeric(rows, "offered_rate_per_min")

    successful_latency = numeric(successful, "total_ms")

    return {
        "label": label,
        "total": total,
        "success": counts["ok"],
        "success_pct": percentage(counts["ok"], total),
        "rate_limited": counts["rate_limited"],
        "rate_limited_pct": percentage(
            counts["rate_limited"], total
        ),
        "timeouts": counts["timeout"],
        "timeout_pct": percentage(counts["timeout"], total),
        "errors": counts["error"],
        "error_pct": percentage(counts["error"], total),
        "average_retries": mean_value(retries),
        "latency_p50": percentile(successful_latency, (50,)),
        "latency_p95": percentile(successful_latency, (95,)),
        "latency_p99": percentile(successful_latency, (99,)),
        "first_p50_p95": percentile(
            numeric(successful, "first_token_ms"),
            (50, 95)
        ),
        "first_p50_p95_p99": percentile(
            numeric(successful, "first_token_ms"),
            (50, 95, 99)
        ),
        "provider_ttft": percentile(
            numeric(successful, "provider_ttft_ms"),
            (50, 95)
        ),
        "answer_release": percentile(
            numeric(successful, "answer_release_ms"),
            (50, 95)
        ),
        "validation_hold": percentile(
            numeric(successful, "validation_hold_ms"),
            (50, 95)
        ),
        "queue_wait": percentile(
            numeric(rows, "queue_wait_ms"),
            (50, 95)
        ),
        "budget_wait": percentile(
            numeric(rows, "budget_wait_ms"),
            (50, 95)
        ),
        "retry_wait": percentile(
            numeric(rows, "retry_wait_ms"),
            (50, 95)
        ),
        "peak_queue": peak_queue(rows),
        "provider_rejections": provider_rejections,
        "local_rejections": local_rejections,
        "usage_count": usage_count,
        "average_tokens": average_tokens,
        "cost": cost_statistics(rows),
        "duration": (
            f"{max(durations):.3f}"
            if durations else "not measured"
        ),
        "offered_rate": (
            f"{offered[0]:.1f}"
            if offered else "not measured"
        ),
    }


def generate_single_report(rows, output, limits=None, source_name="input"):
    groups = defaultdict(list)

    for row in rows:
        groups[
            (
                row.get("run_id", ""),
                row.get("scenario", ""),
                row.get("source", ""),
            )
        ].append(row)

    latency = []
    outcomes = []
    timing = []

    for (run, scenario, source), group_rows in groups.items():
        summary = experiment_summary(
            group_rows,
            f"{scenario} [{run}]"
        )

        label = summary["label"]

        latency.append([
            label,
            source,
            summary["total"],
            summary["duration"],
            summary["offered_rate"],
            summary["first_p50_p95_p99"],
            percentile(
                numeric(
                    [
                        r for r in group_rows
                        if r.get("status") == "ok"
                    ],
                    "total_ms"
                )
            ),
        ])

        outcomes.append([
            label,
            summary["success_pct"],
            summary["rate_limited_pct"],
            summary["timeout_pct"],
            summary["average_retries"],
            summary["peak_queue"],
            summary["average_tokens"],
            summary["cost"],
            summary["error_pct"],
            percentage(
                summary["provider_rejections"],
                summary["total"]
            ),
            percentage(
                summary["local_rejections"],
                summary["total"]
            ),
        ])

        timing.append([
            label,
            summary["first_p50_p95"],
            summary["provider_ttft"],
            summary["answer_release"],
            summary["validation_hold"],
        ])

    retrieval = []

    real_hashes = {
        row.get("question_set_sha256", "")
        for row in rows
        if row.get("source") == "real"
        and row.get("scenario") == "retrieval_eval"
        and row.get("question_set_sha256")
    }

    if len(real_hashes) > 1:
        raise ValueError(
            "Mixed question-set versions in real quality evaluation. "
            "Report them separately."
        )

    for setting in ["small", "medium", "large"]:
        selected = [
            row for row in rows
            if row.get("source") == "real"
            and row.get("scenario") == "retrieval_eval"
            and row.get("retrieval_setting") == setting
        ]

        if not selected:
            retrieval.append(
                [setting] + ["not measured"] * 8
            )
            continue

        total = len(selected)
        grades = [
            row for row in selected
            if row.get("answer_grade")
        ]

        def grade_percentage(grade):
            if len(grades) != total:
                return "not measured"

            return percentage(
                sum(
                    row.get("answer_grade") == grade
                    for row in selected
                ),
                total
            )

        _, average_tokens = usage_statistics(selected)

        successful = [
            row for row in selected
            if row.get("status") == "ok"
        ]

        retrieval.append([
            setting,
            total,
            grade_percentage("correct"),
            grade_percentage("wrong"),
            grade_percentage("refused_correctly"),
            average_tokens,
            percentile(
                numeric(successful, "first_token_ms"),
                (50, 95)
            ),
            percentile(
                numeric(successful, "total_ms"),
                (50, 95)
            ),
            grade_percentage("refused_wrongly"),
        ])

    text = "# Generated results\n\n"
    text += f"Input file: `{source_name}`\n\n"

    text += (
        "Latency percentiles use successful requests only; failures "
        "are reported separately. Times are milliseconds. "
        "Duration is the arrival window, not drain time. "
        "Burst rate is not interpreted as a finite RPM. "
        "Token averages use records with complete usage only. "
        "Synthetic stand-in costs are not real API cost measurements.\n\n"
    )

    if limits:
        limits_data = json.loads(
            Path(limits).read_text(encoding="utf-8")
        )
    else:
        limits_data = {}

    limit_rows = [
        limits_data.get(
            label,
            [
                label,
                "not measured",
                "Await real account and probe",
                "low"
            ]
        )
        for label in [
            "Requests/min",
            "Tokens/min",
            "Requests/day",
            "Tokens/day",
            "Requests in flight",
            "Limit response",
            "Recovery time",
        ]
    ]

    text += "## Table 1: Real limits\n"
    text += mdtable(
        ["Limit", "Value found", "How found", "Confidence"],
        limit_rows
    )

    text += "\n## Table 2a: Latency\n"
    text += mdtable(
        [
            "Scenario", "Source", "Requests", "Duration s",
            "Offered/min", "First p50/p95/p99",
            "Total p50/p95/p99"
        ],
        latency
    )

    text += "\n## Table 2b: Outcomes\n"
    text += mdtable(
        [
            "Scenario", "OK %", "Rate limited %", "Timeout %",
            "Retries/request", "Peak queue", "Tokens/request",
            "$/1000 successful answers", "Other error %",
            "Provider rejection %", "Local rejection %",
        ],
        outcomes
    )

    text += "\n## Table 3: Retrieval\n"
    text += mdtable(
        [
            "Setting", "Questions", "Correct+cited %", "Wrong %",
            "Correct refusal %", "Tokens/answer", "First p50/p95",
            "Total p50/p95", "Wrong refusal %",
        ],
        retrieval
    )

    text += (
        "\nSettings are whitespace words (not model tokens): "
        "small=180/overlap30/k3; medium=300/50/k4; "
        "large=420/70/k5; expansion adds two passages, fitted to TPM. "
        "No reranking.\n"
    )

    text += "\n## Additional timing\n"
    text += mdtable(
        [
            "Scenario",
            "End-to-end first token p50/p95",
            "Provider TTFT p50/p95",
            "Answer release p50/p95",
            "Validation hold p50/p95"
        ],
        timing
    )

    successful = [
        row for row in rows
        if row.get("status") == "ok"
    ]

    slow = max(
        successful,
        key=lambda row: number(row.get("total_ms")) or 0,
        default=None,
    )

    if slow:
        text += "\n## Slow successful request trace\n"

        total_value = number(slow.get("total_ms")) or 0

        text += (
            f"Request `{slow.get('request_id', 'unknown')}` "
            f"({slow.get('source')}, {slow.get('scenario')}): "
            f"total {total_value:.1f} ms; "
        )

        for field in [
            "queue_wait_ms",
            "budget_wait_ms",
            "working_ms",
            "retry_wait_ms",
            "first_token_ms",
            "provider_ttft_ms",
            "answer_release_ms",
            "validation_hold_ms",
        ]:
            value = number(slow.get(field))

            text += (
                f"{field}={value:.1f} ms; "
                if value is not None
                else f"{field}=not measured; "
            )

        measured = sum(
            number(slow.get(field)) or 0
            for field in [
                "queue_wait_ms",
                "budget_wait_ms",
                "working_ms",
                "retry_wait_ms",
            ]
        )

        text += (
            f"residual scheduling/validation overhead="
            f"{total_value - measured:.1f} ms. "
            "See matching events.jsonl records.\n"
        )

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(text, encoding="utf-8")

    print(f"Report written to: {output}")


def generate_comparison(
    first_rows,
    second_rows,
    first_name,
    second_name,
    output
):
    first = experiment_summary(first_rows, first_name)
    second = experiment_summary(second_rows, second_name)

    metrics = [
        ("Requests", "total"),
        ("Successful requests", "success"),
        ("Success rate (%)", "success_pct"),
        ("Rate-limited (%)", "rate_limited_pct"),
        ("Timeout (%)", "timeout_pct"),
        ("Other errors (%)", "error_pct"),
        ("Average retries/request", "average_retries"),
        ("Total latency p50 (ms)", "latency_p50"),
        ("Total latency p95 (ms)", "latency_p95"),
        ("Total latency p99 (ms)", "latency_p99"),
        ("First-token p50/p95 (ms)", "first_p50_p95"),
        ("Provider TTFT p50/p95 (ms)", "provider_ttft"),
        ("Answer release p50/p95 (ms)", "answer_release"),
        ("Validation hold p50/p95 (ms)", "validation_hold"),
        ("Semaphore queue wait p50/p95 (ms)", "queue_wait"),
        ("Budget wait p50/p95 (ms)", "budget_wait"),
        ("Retry wait p50/p95 (ms)", "retry_wait"),
        ("Peak queue", "peak_queue"),
        ("Provider rejections", "provider_rejections"),
        ("Local rejections", "local_rejections"),
        ("Complete usage records", "usage_count"),
        ("Average tokens/complete record", "average_tokens"),
        ("Cost per 1000 successful answers", "cost"),
    ]

    rows = [
        [label, first[key], second[key]]
        for label, key in metrics
    ]

    text = "# Retry experiment comparison\n\n"

    text += (
        "This report compares two experiment runs. "
        "The experiments are not request-paired causal trials. "
        "Random failure draws and request scheduling can differ. "
        "Stand-in results are synthetic and must not be presented "
        "as real API performance or quality measurements.\n\n"
    )

    text += "## Experiment summary\n"
    text += mdtable(
        ["Metric", first_name, second_name],
        rows
    )

    text += "\n## Interpretation notes\n\n"
    text += (
        "- Success rate uses all submitted requests as the denominator.\n"
        "- Latency percentiles use successful requests only.\n"
        "- Token averages exclude records with incomplete usage.\n"
        "- Provider rejections are identified by `provider_429`.\n"
        "- Other rate-limit rejections are classified as local/application "
        "rejections, including bounded queue rejection.\n"
        "- A zero stand-in cost is synthetic and is not a paid-equivalent "
        "estimate.\n"
        "- Retries can increase load and waiting even when they recover "
        "some errors.\n"
    )

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(text, encoding="utf-8")

    print(f"Comparison report written to: {output}")


def discover_repeated_runs(root):
    """Find all v4 retry experiment result files."""

    root = Path(root)

    if not root.exists():
        raise FileNotFoundError(
            f"Experiment directory not found: {root}"
        )

    discovered = []

    for path in sorted(root.glob("v4-retry-*-run-*")):
        if not path.is_dir():
            continue

        csv_path = path / "results.csv"
        metadata_path = path / "simulator_config.json"

        if not csv_path.exists():
            continue

        metadata = {}

        if metadata_path.exists():
            metadata = json.loads(
                metadata_path.read_text(encoding="utf-8")
            )

        name = path.name

        if name.startswith("v4-retry-0-"):
            retries = 0
        elif name.startswith("v4-retry-1-"):
            retries = 1
        else:
            continue

        repetition_text = name.rsplit("-run-", 1)[-1]

        try:
            repetition = int(repetition_text)
        except ValueError:
            continue

        seed = metadata.get("seed")

        if seed is None:
            raise ValueError(
                f"Missing seed in metadata: {metadata_path}"
            )

        rows = read_csv(csv_path)

        if not rows:
            raise ValueError(
                f"Experiment CSV is empty: {csv_path}"
            )

        if any(row.get("source") != "stand-in" for row in rows):
            raise ValueError(
                f"Non-stand-in source found in {csv_path}"
            )

        discovered.append({
            "retries": retries,
            "repetition": repetition,
            "seed": seed,
            "path": csv_path,
            "rows": rows,
        })

    return discovered


def repeated_run_summary(run):
    rows = run["rows"]
    summary = experiment_summary(rows, run["path"].parent.name)

    return {
        "retries": run["retries"],
        "repetition": run["repetition"],
        "seed": run["seed"],
        "requests": summary["total"],
        "success": summary["success"],
        "success_rate": (
            summary["success"] / summary["total"] * 100
            if summary["total"] else 0
        ),
        "rate_limited": summary["rate_limited"],
        "timeout": summary["timeouts"],
        "errors": summary["errors"],
        "average_retries": number(summary["average_retries"]),
        "latency_p50": number(summary["latency_p50"]),
        "latency_p95": number(summary["latency_p95"]),
        "queue_wait_p95": (
            np.percentile(
                numeric(rows, "queue_wait_ms"), 95
            )
            if numeric(rows, "queue_wait_ms") else None
        ),
        "budget_wait_p95": (
            np.percentile(
                numeric(rows, "budget_wait_ms"), 95
            )
            if numeric(rows, "budget_wait_ms") else None
        ),
        "retry_wait_p95": (
            np.percentile(
                numeric(rows, "retry_wait_ms"), 95
            )
            if numeric(rows, "retry_wait_ms") else None
        ),
        "tokens": (
            np.mean([
                number(row.get("tokens_in")) +
                number(row.get("tokens_out"))
                for row in rows
                if str(row.get("usage_complete", "")).lower() == "true"
                and number(row.get("tokens_in")) is not None
                and number(row.get("tokens_out")) is not None
            ])
            if any(
                str(row.get("usage_complete", "")).lower() == "true"
                and number(row.get("tokens_in")) is not None
                and number(row.get("tokens_out")) is not None
                for row in rows
            )
            else None
        ),
        "complete_usage": summary["usage_count"],
        "peak_queue": summary["peak_queue"],
    }


def repeated_report(root, output):
    runs = discover_repeated_runs(root)

    if not runs:
        raise ValueError(
            f"No repeated v4 experiment results found in {root}"
        )

    summaries = [
        repeated_run_summary(run)
        for run in runs
    ]

    by_retries = {
        retries: [
            item for item in summaries
            if item["retries"] == retries
        ]
        for retries in (0, 1)
    }

    for retries in (0, 1):
        if len(by_retries[retries]) != 5:
            raise ValueError(
                f"Expected 5 repetitions for retries={retries}, "
                f"but found {len(by_retries[retries])}. "
                "Check that all 10 runs completed."
            )

    if any(
        item["requests"] != 40
        for item in summaries
    ):
        raise ValueError(
            "Expected 40 requests in every run. "
            "Inspect the experiment CSV files before comparison."
        )

    seed_map = {
        retries: {
            item["seed"] for item in by_retries[retries]
        }
        for retries in (0, 1)
    }

    if seed_map[0] != seed_map[1]:
        raise ValueError(
            "Retry configurations do not contain matching seed sets."
        )

    text = "# Repeated synthetic retry experiment\n\n"

    text += (
        "**Source:** Synthetic stand-in only. "
        "These measurements are not real Groq API results.\n\n"
        "**Design:** Five repetitions per configuration, 40 requests "
        "per repetition, with matching seeds across configurations. "
        "Retries can change random draw order and request scheduling, "
        "so this is not request-level causal pairing.\n\n"
    )

    text += "## 1. Individual run results\n\n"

    run_rows = []

    for item in sorted(
        summaries,
        key=lambda value: (
            value["retries"],
            value["repetition"]
        )
    ):
        run_rows.append([
            item["retries"],
            item["repetition"],
            item["seed"],
            item["requests"],
            f'{item["success"]}/{item["requests"]}',
            f'{item["success_rate"]:.1f}%',
            item["rate_limited"],
            item["timeout"],
            item["errors"],
            (
                f'{item["latency_p95"]:.1f}'
                if item["latency_p95"] is not None
                else "not measured"
            ),
            (
                f'{item["queue_wait_p95"]:.1f}'
                if item["queue_wait_p95"] is not None
                else "not measured"
            ),
        ])

    text += mdtable(
        [
            "Retries", "Run", "Seed", "Requests", "Successes",
            "Success rate", "Rate limited", "Timeouts",
            "Errors", "Latency p95 ms", "Queue p95 ms"
        ],
        run_rows
    )

    text += "\n## 2. Aggregate results across five repetitions\n\n"

    aggregate_rows = []

    metric_definitions = [
        ("Success rate (%)", "success_rate"),
        ("Rate-limited requests", "rate_limited"),
        ("Timeouts", "timeout"),
        ("Other errors", "errors"),
        ("Average retries/request", "average_retries"),
        ("Successful latency p50 (ms)", "latency_p50"),
        ("Successful latency p95 (ms)", "latency_p95"),
        ("Semaphore queue wait p95 (ms)", "queue_wait_p95"),
        ("Budget wait p95 (ms)", "budget_wait_p95"),
        ("Retry wait p95 (ms)", "retry_wait_p95"),
        ("Average tokens/complete record", "tokens"),
        ("Peak queue", "peak_queue"),
    ]

    for label, field in metric_definitions:
        values = {}

        for retries in (0, 1):
            values[retries] = [
                item[field]
                for item in by_retries[retries]
                if item[field] is not None
            ]

        aggregate_rows.append([
            label,
            mean_std(values[0], 2),
            mean_std(values[1], 2),
        ])

    text += mdtable(
        [
            "Metric (mean ± sample SD)",
            "Retries disabled",
            "Retries enabled"
        ],
        aggregate_rows
    )

    text += "\n## 3. Pooled outcome totals\n\n"

    pooled_rows = []

    for retries in (0, 1):
        selected = by_retries[retries]

        total_requests = sum(
            item["requests"] for item in selected
        )

        total_success = sum(
            item["success"] for item in selected
        )

        total_rate_limited = sum(
            item["rate_limited"] for item in selected
        )

        total_timeout = sum(
            item["timeout"] for item in selected
        )

        total_errors = sum(
            item["errors"] for item in selected
        )

        pooled_rows.append([
            "Retries enabled" if retries else "Retries disabled",
            total_requests,
            total_success,
            f"{percentage(total_success, total_requests)}%",
            total_rate_limited,
            total_timeout,
            total_errors,
        ])

    text += mdtable(
        [
            "Configuration", "Requests", "Successful",
            "Success rate", "Rate limited", "Timeouts", "Errors"
        ],
        pooled_rows
    )

    text += "\n## 4. Seed-level comparison\n\n"

    seed_rows = []

    disabled_by_seed = {
        item["seed"]: item
        for item in by_retries[0]
    }

    enabled_by_seed = {
        item["seed"]: item
        for item in by_retries[1]
    }

    for seed in sorted(disabled_by_seed):
        disabled = disabled_by_seed[seed]
        enabled = enabled_by_seed[seed]

        difference = (
            enabled["success_rate"]
            - disabled["success_rate"]
        )

        seed_rows.append([
            seed,
            f'{disabled["success_rate"]:.1f}%',
            f'{enabled["success_rate"]:.1f}%',
            f'{difference:+.1f} percentage points',
        ])

    text += mdtable(
        [
            "Seed",
            "Retries disabled",
            "Retries enabled",
            "Difference (enabled - disabled)"
        ],
        seed_rows
    )

    disabled_rates = [
        item["success_rate"] for item in by_retries[0]
    ]

    enabled_rates = [
        item["success_rate"] for item in by_retries[1]
    ]

    average_difference = (
        np.mean(enabled_rates) - np.mean(disabled_rates)
    )

    text += "\n## 5. Interpretation\n\n"

    text += (
        f"- Mean success-rate difference (enabled minus disabled): "
        f"**{average_difference:+.2f} percentage points**.\n"
    )

    text += (
        f"- Retries disabled mean success rate: "
        f"**{np.mean(disabled_rates):.2f}%**.\n"
    )

    text += (
        f"- Retries enabled mean success rate: "
        f"**{np.mean(enabled_rates):.2f}%**.\n"
    )

    text += (
        "- The standard deviation describes variation across five runs; "
        "it is not a confidence interval.\n"
    )

    text += (
        "- Seed-level comparisons are operational comparisons, not "
        "request-paired causal estimates.\n"
    )

    text += (
        "- Retry behaviour must be assessed alongside timeouts, "
        "rate limits, latency, queue waiting and model calls.\n"
    )

    text += (
        "- A lower generic error count does not automatically mean "
        "a better outcome if timeouts or rate limits increase.\n"
    )

    text += (
        "- Synthetic stand-in results cannot establish real provider "
        "performance, real API cost, or answer quality.\n"
    )

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(text, encoding="utf-8")

    print(f"Repeated experiment report written to: {output}")
    print(f"Experiment runs analysed: {len(summaries)}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Relay experiment reports."
    )

    parser.add_argument(
        "csv",
        nargs="?",
        help="First results CSV for single or two-file comparison"
    )

    parser.add_argument(
        "--compare",
        help="Second results CSV for side-by-side comparison"
    )

    parser.add_argument(
        "--repeated-dir",
        help="Root directory containing v4 repeated experiment folders"
    )

    parser.add_argument(
        "--output",
        default="runs/tables.md",
        help="Markdown report output path"
    )

    parser.add_argument(
        "--limits",
        help="Reviewed JSON map: limit label -> four table cells"
    )

    args = parser.parse_args()

    if args.repeated_dir:
        if args.csv or args.compare:
            parser.error(
                "--repeated-dir cannot be combined with positional CSV "
                "or --compare."
            )

        repeated_report(
            args.repeated_dir,
            args.output
        )

        return

    if not args.csv:
        parser.error(
            "Provide a CSV file or use --repeated-dir."
        )

    first_rows = read_csv(args.csv)

    if args.compare:
        second_rows = read_csv(args.compare)

        generate_comparison(
            first_rows,
            second_rows,
            Path(args.csv).parent.name,
            Path(args.compare).parent.name,
            args.output,
        )

    else:
        generate_single_report(
            first_rows,
            args.output,
            args.limits,
            args.csv,
        )


if __name__ == "__main__":
    main()
