
"""Repeated synthetic retry experiments.

Runs five independent seed pairs:
- retries=0: retry disabled
- retries=1: retry enabled

Both configurations use the same seed within each pair.
Retries can change random draw order, so this is an operational
comparison, not a request-paired causal experiment.

All results are synthetic stand-in results, not real API measurements.
"""

import asyncio
import json
import os
from argparse import Namespace
from pathlib import Path

import httpx

from .common import load_dotenv
from .run import main


STANDIN_URL = "http://127.0.0.1:8001"

BASE_SEEDS = (31, 32, 33, 34, 35)
RETRY_CONFIGURATIONS = (0, 1)

REQUEST_COUNT = 40
OUTPUT_ROOT = Path("runs")


def build_config(seed):
    """Build the common synthetic server configuration."""

    from .standin import Config

    config = dict(vars(Config()))

    config.update(
        rpm=10000,
        tpm=10000000,
        rpd=100000,
        tpd=10000000,
        failure_probability=0.35,
        slow_probability=0.15,
        base_s=0.12,
        seed=seed,
        provenance=(
            "ASSUMED retry stress test; "
            "synthetic stand-in results, not real calibration"
        )
    )

    return config


async def configure_standin(client, config):
    """Check server availability and apply simulator configuration."""

    health_url = f"{STANDIN_URL}/health"

    try:
        health = await client.get(health_url)
        health.raise_for_status()

    except httpx.HTTPError as exc:
        raise RuntimeError(
            "Stand-in server is unavailable. "
            "Start it at http://127.0.0.1:8001 "
            "before running experiments."
        ) from exc

    config_url = f"{STANDIN_URL}/admin/config"

    response = await client.post(
        config_url,
        json=config,
        headers={
            "x-admin-token": os.environ.get(
                "RELAY_ADMIN_TOKEN",
                ""
            )
        }
    )

    response.raise_for_status()


def build_args(retries, seed, output):
    """Create arguments compatible with relay.run.main()."""

    return Namespace(
        mode="probe",
        scenario=(
            "retry_disabled"
            if retries == 0
            else "retry_enabled"
        ),
        source="stand-in",
        base_url=None,
        model="synthetic",
        output=str(output),
        questions="data/questions.json",
        question="",
        setting="small",
        n=REQUEST_COUNT,
        interval=0.08,
        concurrency=2,
        queue=6,
        deadline=2,
        retries=retries,
        verifier="off",
        rpm=10000,
        tpm=10000000,
        rpd=100000,
        tpd=10000000,
        ledger=None,
        seed=seed,
        confirm_real=False,
        calibration=None,
        max_tokens=700,
        reasoning_effort="none",
        append=False,
        settings=None
    )


def output_directory(retries, repetition):
    """Return a unique output directory for one experiment run."""

    return (
        OUTPUT_ROOT
        / f"v4-retry-{retries}-run-{repetition}"
    )


def prepare_output(output, config, retries, seed, repetition):
    """Create a fresh output directory and save experiment provenance."""

    directory = Path(output)

    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError(
            f"Output directory is not empty: {directory}\n"
            "Move the existing results or choose a new output name. "
            "Existing results will never be overwritten."
        )

    directory.mkdir(parents=True, exist_ok=True)

    metadata = {
        "experiment": "repeated_retry_comparison",
        "repetition": repetition,
        "retry_count": retries,
        "scenario": (
            "retry_disabled"
            if retries == 0
            else "retry_enabled"
        ),
        "source": "stand-in",
        "synthetic": True,
        "causal_pairing": False,
        "seed": seed,
        "requests": REQUEST_COUNT,
        "configuration": config
    }

    metadata_path = directory / "simulator_config.json"

    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8"
    )


async def run_one(
    client,
    retries,
    seed,
    repetition
):
    """Configure and execute one experiment."""

    config = build_config(seed)

    output = output_directory(
        retries,
        repetition
    )

    prepare_output(
        output,
        config,
        retries,
        seed,
        repetition
    )

    await configure_standin(
        client,
        config
    )

    args = build_args(
        retries,
        seed,
        output
    )

    print(
        "\n"
        + "=" * 60
        + f"\nStarting repetition {repetition}/5"
        + f"\nRetries: {retries}"
        + f"\nSeed: {seed}"
        + f"\nOutput: {output}"
        + "\n"
        + "=" * 60,
        flush=True
    )

    await main(args)

    print(
        f"Completed repetition {repetition}/5 "
        f"(retries={retries}, seed={seed})",
        flush=True
    )


async def experiment():
    """Run five repetitions for both retry configurations."""

    load_dotenv()

    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    print("\nREPEATED SYNTHETIC RETRY EXPERIMENT")
    print("Repetitions per configuration: 5")
    print("Requests per run:", REQUEST_COUNT)
    print("Retry configurations:", RETRY_CONFIGURATIONS)
    print("Seeds:", BASE_SEEDS)
    print("Total experiment runs: 10")
    print("Source: synthetic stand-in only\n")

    async with httpx.AsyncClient(timeout=20) as client:

        for retries in RETRY_CONFIGURATIONS:

            print(
                f"\n\nSTARTING CONFIGURATION: retries={retries}",
                flush=True
            )

            for repetition, seed in enumerate(
                BASE_SEEDS,
                start=1
            ):
                await run_one(
                    client,
                    retries,
                    seed,
                    repetition
                )

    print("\n" + "=" * 60)
    print("ALL 10 EXPERIMENT RUNS COMPLETED")
    print("=" * 60)

    print("\nGenerated output directories:")

    for retries in RETRY_CONFIGURATIONS:
        for repetition in range(1, 6):
            print(
                output_directory(
                    retries,
                    repetition
                )
            )


if __name__ == "__main__":
    asyncio.run(experiment())
