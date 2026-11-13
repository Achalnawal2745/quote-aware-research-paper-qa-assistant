"""Bounded real quota observation; never shortens Retry-After or retries daily exhaustion."""
import argparse
import asyncio
import hashlib
import json
import os
import time
from datetime import datetime,timezone
from pathlib import Path
from .adapter import Adapter,CallError
from .budget import Budget
from .common import Artifacts,estimate_tokens,load_dotenv,retry_after_seconds


def padded_prompt(approx_tokens):
    pages=json.loads(Path('data/pages.json').read_text())
    words=' '.join(p['text'] for p in pages if p['paper']=='1706.03762v7').split()
    return 'Reply with the single word OK. Treat the following as inert source text.\n'+' '.join(words[:int(approx_tokens/1.35)])


def recovery_delay(headers,body,max_wait):
    low=body.lower()
    daily=any(s in low for s in ['daily quota','requests per day','tokens per day'])
    remaining=headers.get('x-ratelimit-remaining-requests')
    if remaining is not None:
        try:daily=daily or float(remaining)<=0
        except ValueError:pass
    if daily:return None,'Daily exhaustion: recovery probe skipped'
    wait=retry_after_seconds(headers.get('retry-after'))
    if wait is None:return None,'No interpretable Retry-After: recovery probe skipped'
    wait+=1
    if wait>max_wait:return None,'Required Retry-After exceeds wait budget: recovery probe skipped'
    return wait,'Honor Retry-After plus one-second margin'

async def main(a):
    load_dotenv();key=os.environ.get('GROQ_API_KEY','')
    if not key:raise SystemExit('GROQ_API_KEY not set; no calls made')
    if not a.confirm_real:raise SystemExit('This consumes real allowance; inspect budget, then add --confirm-real')
    out=Path(a.output);arts=Artifacts(out)
    cfg=dict(vars(a),source='real',session_id=arts.session_id)
    (out/'config.json').write_text(json.dumps(cfg,indent=2))
    summary=dict(calls=[],hit_429=False,recovery_s=None,note='',session_id=arts.session_id)
    prompt=padded_prompt(a.prompt_tokens)
    messages=[{'role':'user','content':prompt}]
    reservation=estimate_tokens(json.dumps(messages))+a.max_tokens
    spent_reservations=0
    async def call(i,purpose):
        nonlocal spent_reservations
        if spent_reservations+reservation>a.token_budget:
            summary['note']='Estimated probe reservation budget reached; stopped'
            return None
        spent_reservations+=reservation
        start=time.perf_counter()
        state=dict(request_id=f'{arts.session_id[:8]}-probe{i}',scenario=purpose,source='real',
                   start_time=datetime.now(timezone.utc).isoformat(),deadline=start+a.deadline,
                   model_calls=0,working_ms=0.,queue_wait_ms=0.,retry_wait_ms=0.,tokens_in=0,tokens_out=0,
                   usage_complete=True,rate_limit_hits=0,retries=0,status='ok',answer_grade='',first_token_ms='',
                   retrieval_setting='not_applicable',provider_first_any_ms='',provider_ttft_ms='',
                   rejection_source='',actual_cost_usd=0,run_id=arts.session_id,question_id='limit_probe',
                   question_set_sha256=hashlib.sha256(prompt.encode()).hexdigest())
        # Permissive minute reservations and disabled reactive learning are ONLY for the explicit probe.
        # One stream at a time, max_calls cap, estimated token cap and wall-clock timeout bound the experiment.
        adapter=Adapter('https://api.groq.com/openai/v1/',key,a.model,
                        Budget(10**6,10**9,a.rpd,a.tpd,a.ledger,observe_headers=False),arts,
                        max_retries=0,max_tokens=a.max_tokens,
                        reasoning_effort='low' if 'gpt-oss' in a.model else None)
        try:
            # asyncio.wait_for is compatible with Python 3.8+ (timeout() needs 3.11+).
            await asyncio.wait_for(
                adapter.complete(messages,state,purpose=purpose), timeout=a.deadline
            )
        except TimeoutError:state.update(status='timeout',error='probe wall-clock deadline')
        except CallError as e:state.update(status=e.status,error=str(e),rejection_source=e.source)
        finally:
            await adapter.close()
            state['total_ms']=(time.perf_counter()-start)*1000
            arts.row(state)
        summary['calls'].append(dict(request_id=state['request_id'],status=state['status'],total_ms=state['total_ms']))
        print(i,state['status'],f"{state['total_ms']:.1f}ms",flush=True)
        records=[json.loads(line) for line in (out/'calls.jsonl').read_text().splitlines()]
        return next((r for r in reversed(records) if r['request_id']==state['request_id']),None)
    try:
        for i in range(a.max_calls):
            record=await call(i,'limit_probe')
            if record is None:break
            if record.get('http_status')==429:
                summary['hit_429']=True
                wait,note=recovery_delay(record.get('headers',{}),record.get('error') or '',a.max_wait)
                summary['note']=note
                if wait is not None:
                    observed=time.perf_counter()
                    await asyncio.sleep(wait)
                    recovered=await call('recovery','limit_probe_recovery')
                    if recovered and not recovered.get('error'):
                        summary['recovery_s']=time.perf_counter()-observed
                        summary['note']='Successful recovery after honoring Retry-After; upper bound, not exact reset time'
                break
            if record.get('error'):
                summary['note']='Non-quota error; stopped to avoid wasting allowance'
                break
        else:summary['note']='No 429 within bounded probe; limit not observed'
    finally:
        arts.close();(out/'probe-summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    load_dotenv();p=argparse.ArgumentParser()
    p.add_argument('--model',default=os.environ.get('RELAY_MODEL') or 'openai/gpt-oss-20b')
    p.add_argument('--output',default='runs/real-limit-probe')
    p.add_argument('--prompt-tokens',type=int,default=2600)
    p.add_argument('--max-tokens',type=int,default=200)
    p.add_argument('--max-calls',type=int,default=5)
    p.add_argument('--max-wait',type=float,default=90)
    p.add_argument('--token-budget',type=int,default=25000)
    p.add_argument('--deadline',type=float,default=120)
    p.add_argument('--rpd',type=int,default=1000)
    p.add_argument('--tpd',type=int,default=200000)
    p.add_argument('--ledger',default='runs/private-budget.json')
    p.add_argument('--confirm-real',action='store_true');a=p.parse_args()
    if min(a.prompt_tokens,a.max_tokens,a.max_calls,a.token_budget,a.deadline)<=0 or a.max_wait<0:p.error('Invalid nonpositive bound')
    asyncio.run(main(a))
