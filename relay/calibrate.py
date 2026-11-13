"""Estimate timing parameters from successful REAL calls; never from synthetic rows."""
import argparse
import json
from pathlib import Path
import numpy as np

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('run_dir'); p.add_argument('--output',default='runs/calibration.json')
    a=p.parse_args(); root=Path(a.run_dir)
    cfg=json.loads((root/'config.json').read_text())
    if cfg['source']!='real':
        raise SystemExit('Refusing to calibrate from stand-in data')
    calls=[json.loads(s) for s in (root/'calls.jsonl').read_text().splitlines()]
    good=[r for r in calls if not r['error'] and r.get('usage') and r.get('provider_ttft_ms') is not None]
    if len(good)<5:
        raise SystemExit('Need at least 5 successful real streaming calls with usage')
    x=np.array([r['usage']['prompt_tokens'] for r in good]); y=np.array([r['provider_ttft_ms']/1000 for r in good])
    if np.ptp(x)>100:
        slope,intercept=np.polyfit(x,y,1); slope=max(0,float(slope)); intercept=max(.001,float(intercept))
    else:
        slope=0.; intercept=float(np.median(y))
    rates=[r['usage']['completion_tokens']/max(.001,(r['total_ms']-(r.get('provider_first_any_ms') or r['provider_ttft_ms']))/1000) for r in good]
    med=float(np.median(y)); threshold=max(med*3,float(np.percentile(y,95)))
    slow=[t for t in y if t>threshold]
    result={'real_sample_n':len(good),'simulator_parameters':{
        'base_s':intercept,'prefill_s_per_token':slope,'output_tokens_per_s':float(np.median(rates)),
        'slow_probability':len(slow)/len(good),
        'slow_multiplier':float(np.median(slow)/max(med,.001)) if slow else 1.,
        'failure_probability':sum(bool(r['error']) for r in calls)/len(calls),
        'provenance':f'Estimated from {len(good)} real successful calls; see calibration caveats'},
        'assumptions':['Concurrency slowdown NOT identified: retain explicit stress-test assumption.',
                       'RPM/TPM/RPD/TPD must be set from documented/account-observed limits separately.',
                       'Small-sample tails unstable; threshold=max(3*median,p95).',
                       'TTFT linear fit is clipped nonnegative, not a causal model.',
                       'Failed/abandoned calls may have unknown provider token usage.',
                       'Reasoning latency is folded into content TTFT; not separately identified.']}
    Path(a.output).write_text(json.dumps(result,indent=2)); print(a.output)
