"""Build a stand-in timing profile from successful REAL streaming calls only.

This is a small-sample engineering estimate, not a provider capacity model.
Concurrency slowdown and quota values are intentionally not inferred here.
"""
import argparse
import json
from pathlib import Path
import numpy as np


def build_profile(run_dir):
    root = Path(run_dir)
    cfg_path, calls_path = root / 'config.json', root / 'calls.jsonl'
    if not cfg_path.exists() or not calls_path.exists():
        raise SystemExit(f'Expected {cfg_path} and {calls_path}')
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    if cfg.get('source') != 'real':
        raise SystemExit('Refusing to calibrate from stand-in data')
    calls = [json.loads(line) for line in calls_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    good = [r for r in calls if not r.get('error') and isinstance(r.get('usage'), dict)
            and r.get('provider_ttft_ms') is not None
            and r['usage'].get('prompt_tokens') is not None
            and r['usage'].get('completion_tokens') is not None]
    if len(good) < 5:
        raise SystemExit(f'Need at least 5 successful real streaming calls with usage; found {len(good)}')

    prompt = np.asarray([float(r['usage']['prompt_tokens']) for r in good])
    ttft = np.asarray([float(r['provider_ttft_ms']) / 1000 for r in good])
    # Estimate only a linear prompt-size effect when there is enough spread.
    if np.ptp(prompt) >= 100:
        slope, intercept = np.polyfit(prompt, ttft, 1)
        slope = max(0.0, float(slope))
        intercept = max(0.001, float(intercept))
    else:
        slope = 0.0
        intercept = max(0.001, float(np.median(ttft)))

    rates = []
    for r in good:
        first = r.get('provider_first_any_ms') or r.get('provider_ttft_ms')
        generation_s = (float(r['total_ms']) - float(first)) / 1000
        completion = int(r['usage']['completion_tokens'])
        if generation_s > 0 and completion > 0:
            rates.append(completion / generation_s)
    if not rates:
        raise SystemExit('Cannot estimate output token rate: no positive generation intervals')

    median_ttft = float(np.median(ttft))
    p95_ttft = float(np.percentile(ttft, 95))
    # Label slow samples explicitly. With <20 calls this is descriptive only.
    threshold = max(3 * median_ttft, p95_ttft)
    slow = ttft[ttft > threshold]
    failures = [r for r in calls if r.get('error')]
    params = {
        'base_s': round(intercept, 6),
        'prefill_s_per_token': round(slope, 9),
        'output_tokens_per_s': round(float(np.median(rates)), 3),
        'slow_probability': round(float(len(slow) / len(good)), 4),
        'slow_multiplier': round(float(np.median(slow) / max(median_ttft, .001)), 3) if len(slow) else 1.0,
        'failure_probability': round(float(len(failures) / max(len(calls), 1)), 4),
        'provenance': f'MEASURED estimate from {len(good)} successful real calls in {root.as_posix()}; small sample'
    }
    return {
        'source': 'real', 'model': cfg.get('model'), 'run_directory': root.as_posix(),
        'real_sample_n': len(good), 'all_call_n': len(calls),
        'observed': {
            'ttft_ms_p50': round(float(np.percentile(ttft, 50)) * 1000, 1),
            'ttft_ms_p95': round(float(np.percentile(ttft, 95)) * 1000, 1),
            'ttft_ms_p99': round(float(np.percentile(ttft, 99)) * 1000, 1),
            'output_tokens_per_s_p50': round(float(np.median(rates)), 2),
            'failed_calls': len(failures), 'all_calls': len(calls)
        },
        'simulator_parameters': params,
        'not_inferred': {
            'slowdown_per_inflight': 'ASSUMPTION: requires controlled concurrent-load experiment',
            'rpm_tpm_rpd_tpd': 'Use documented or separately observed account limits; not inferred from latency samples',
            'daily_reset_seconds': 'ASSUMPTION unless reset observed',
            'provider_error_distribution': 'Small sample; do not treat as stable probability'
        },
        'caveats': [
            'At least five successful calls are required; more are strongly preferred.',
            'TTFT includes provider queueing, prefill and any hidden reasoning; these are not separately identified.',
            'The linear prompt-size fit is descriptive, not a causal model.',
            'Output rate is estimated from completion tokens divided by time after first provider output.',
            'Small-sample p95/p99 and slow-event probabilities are unstable.',
            'Concurrency slowdown is not identifiable from sequential probes.'
        ]
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run_dir')
    parser.add_argument('--output', default='runs/calibration.json')
    args = parser.parse_args()
    result = build_profile(args.run_dir)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(output), 'real_sample_n': result['real_sample_n'],
                      'simulator_parameters': result['simulator_parameters'],
                      'not_inferred': result['not_inferred']}, indent=2))
