import argparse
import asyncio
import hashlib
import json
import os
import time
import uuid
from pathlib import Path
import httpx
from .adapter import Adapter
from .budget import Budget
from .common import Artifacts, load_dotenv
from .pipeline import Pipeline
from .retrieval import Retriever, SETTINGS

DEFAULT_URL={'real':'https://api.groq.com/openai/v1/',
             'stand-in':'http://127.0.0.1:8001/openai/v1/'}

def reasoning_effort_for(args):
    choice=getattr(args,'reasoning_effort','auto')
    if choice=='none': return None
    if choice=='auto': return 'low' if 'gpt-oss' in args.model else None
    return choice

def suite_scenarios(base,args):
    k=args.scale
    return [
        ('steady',8*k,20,{},None),
        ('burst',12*k,0,{},None),
        ('sustained_overload',40*k,3,{},None),
        ('per_minute_limit_halved',12*k,15,
         {'rpm':max(1,base['rpm']//2),'tpm':max(1,base['tpm']//2)},None),
        ('daily_budget_exhausted',20*k,1.5,{'rpm':10000,'tpm':10_000_000,'rpd':10},
         dict(rpm=10000,tpm=10_000_000,rpd=args.rpd,tpd=args.tpd)),
        ('overload_limiter_off',40*k,3,{},
         dict(rpm=10**6,tpm=10**9,rpd=10**6,tpd=10**9,observe_headers=False)),
    ]

async def main(args):
    load_dotenv()
    if not getattr(args,'model',None):
        args.model=os.environ.get('RELAY_MODEL') or 'openai/gpt-oss-20b'
    source=args.source
    if args.mode=='suite' and source!='stand-in':
        raise SystemExit('suite is stand-in only; use eval/probe for modest real calls')
    key=os.environ.get('GROQ_API_KEY','') if source=='real' else 'synthetic'
    if source=='real' and not key:
        raise SystemExit('GROQ_API_KEY is not set. Use your shell or a private .env; no calls made.')
    if source=='real' and not args.confirm_real:
        raise SystemExit('Real calls consume shared quota; inspect relay.budget_plan then add --confirm-real.')
    chosen=list(SETTINGS) if args.mode=='eval' else [args.setting]
    if args.mode=='eval' and getattr(args,'settings',None):
        chosen=[s.strip() for s in args.settings.split(',') if s.strip()]
        if not chosen or len(set(chosen))!=len(chosen) or any(s not in SETTINGS for s in chosen):
            raise SystemExit('Choose unique settings from small,medium,large')
    url=args.base_url or DEFAULT_URL[source]
    qpath=Path(args.questions)
    question_hash=hashlib.sha256(qpath.read_bytes()).hexdigest()
    questions=json.loads(qpath.read_text())
    if args.mode=='ask':
        questions=[{'id':'interactive','question':args.question}]
        question_hash=hashlib.sha256(args.question.encode()).hexdigest()
    directory=Path(args.output)
    config_path=directory/'config.json'
    if getattr(args,'append',False) and config_path.exists():
        previous=json.loads(config_path.read_text())
        if previous.get('source')!=source or previous.get('model')!=args.model:
            raise SystemExit('Append requires the same source and model; choose a fresh output directory')
    artifacts=Artifacts(directory,append=getattr(args,'append',False))
    settings=dict(vars(args),question_set_sha256=question_hash,session_id=artifacts.session_id,
                  resolved_reasoning_effort=reasoning_effort_for(args))
    (directory/'sessions').mkdir(exist_ok=True)
    (directory/'sessions'/f'{artifacts.session_id}.json').write_text(json.dumps(settings,indent=2))
    if not config_path.exists():
        config_path.write_text(json.dumps(settings,indent=2))
    budget=Budget(args.rpm,args.tpm,args.rpd,args.tpd,args.ledger if source=='real' else None)
    adapter=Adapter(url,key,args.model,budget,artifacts,args.retries,args.seed,
                    getattr(args,'max_tokens',700),reasoning_effort_for(args))
    run_id=uuid.uuid4().hex[:10]
    try:
        if args.mode=='suite':
            from .standin import Config
            base=vars(Config())
            base.update(rpm=args.rpm,tpm=args.tpm,rpd=args.rpd,tpd=args.tpd,
                        refusal_probability=.15,
                        provenance='ASSUMED service timings; quota flags based on documentation, not observed account')
            if args.calibration:
                calibrated=json.loads(Path(args.calibration).read_text())['simulator_parameters']
                base.update({k:v for k,v in calibrated.items() if v is not None})
            scenarios=suite_scenarios(base,args)
            only={x.strip() for x in (getattr(args,'only',None) or '').split(',') if x.strip()}
            unknown=only-{s[0] for s in scenarios}
            if unknown: raise SystemExit(f'Unknown scenarios: {sorted(unknown)}')
            async with httpx.AsyncClient(timeout=20) as admin:
                for scenario,n,interval,changes,client in scenarios:
                    if only and scenario not in only: continue
                    cfg={**base,**changes,'seed':args.seed}
                    r=await admin.post(url.split('/openai/')[0]+'/admin/config',json=cfg,
                                       headers={'x-admin-token':os.environ.get('RELAY_ADMIN_TOKEN','')})
                    r.raise_for_status()
                    artifacts.event('run','scenario_config',scenario=scenario,config=cfg,
                                    client_budget=client or dict(rpm=args.rpm,tpm=args.tpm,rpd=args.rpd,tpd=args.tpd))
                    adapter.budget=Budget(**(client or dict(rpm=args.rpm,tpm=args.tpm,rpd=args.rpd,tpd=args.tpd)))
                    pipe=Pipeline(Retriever(setting=args.setting),adapter,artifacts,args.concurrency,
                                  args.queue,args.deadline,args.verifier)
                    await load(pipe,questions,scenario,n,interval,source,args.setting,run_id,question_hash)
        else:
            for setting in chosen:
                pipe=Pipeline(Retriever(setting=setting),adapter,artifacts,args.concurrency,
                              args.queue,args.deadline,args.verifier)
                if args.mode=='eval':
                    for i,q in enumerate(questions):
                        result=await pipe.request(q['question'],'retrieval_eval',source,setting,
                                                  question_id=q['id'],run_id=run_id,
                                                  question_set_sha256=question_hash)
                        print(q['id'],setting,result['status'],result['error'][:100],flush=True)
                        if i<len(questions)-1: await asyncio.sleep(args.interval)
                else:
                    n=1 if args.mode=='ask' else args.n
                    await load(pipe,questions,getattr(args,'scenario',None) or args.mode,n,args.interval,
                               source,setting,run_id,question_hash)
    finally:
        await adapter.close();artifacts.close()
    print(f'Artifacts: {directory}/results.csv, events.jsonl, calls.jsonl',flush=True)

async def load(pipe,questions,scenario,n,interval,source,setting,run_id,question_hash=''):
    start=time.perf_counter()
    async def one(i):
        target=i*interval
        await asyncio.sleep(max(0,start+target-time.perf_counter()))
        q=questions[i%len(questions)]
        result=await pipe.request(q['question'],scenario,source,setting,question_id=q['id'],
                                  offered_offset_ms=target*1000,run_id=run_id,
                                  offered_rate_per_min=(60/interval if interval else ''),
                                  run_duration_s=max(interval*(n-1),0),question_set_sha256=question_hash)
        if n==1: print(result['answer'] or result['error'],flush=True)
        return result
    results=await asyncio.gather(*(one(i) for i in range(n)))
    print(scenario,{s:sum(r['status']==s for r in results)
                    for s in ['ok','rate_limited','timeout','error']},flush=True)
    return results

def build_parser():
    load_dotenv()  # Before resolving environment-based CLI defaults.
    p=argparse.ArgumentParser(description='Real/stand-in QA and open-loop experiments')
    p.add_argument('mode',choices=['ask','probe','eval','suite'])
    p.add_argument('--scenario')
    p.add_argument('--source',choices=['real','stand-in'],default='stand-in')
    p.add_argument('--base-url')
    p.add_argument('--model',default=os.environ.get('RELAY_MODEL') or 'openai/gpt-oss-20b')
    p.add_argument('--output',default='runs/demo')
    p.add_argument('--questions',default='data/questions.json')
    p.add_argument('--question',default='How does decoder masking prevent attending to future tokens?')
    p.add_argument('--setting',choices=SETTINGS,default='small')
    p.add_argument('--settings',help='eval only: comma-separated retrieval settings')
    p.add_argument('--append',action='store_true')
    p.add_argument('--only',help='suite only: comma-separated scenario names')
    p.add_argument('--scale',type=int,default=1)
    p.add_argument('--n',type=int,default=12)
    p.add_argument('--interval',type=float,default=.3)
    p.add_argument('--concurrency',type=int,default=3)
    p.add_argument('--queue',type=int,default=8)
    p.add_argument('--deadline',type=float,default=30)
    p.add_argument('--retries',type=int,default=1)
    p.add_argument('--verifier',choices=['off','always','audit'],default='off')
    p.add_argument('--max-tokens',type=int,default=700)
    p.add_argument('--reasoning-effort',choices=['auto','none','low','medium','high'],default='auto')
    p.add_argument('--rpm',type=int,default=30)
    p.add_argument('--tpm',type=int,default=8000)
    p.add_argument('--rpd',type=int,default=1000)
    p.add_argument('--tpd',type=int,default=200000)
    p.add_argument('--ledger',default='runs/private-budget.json')
    p.add_argument('--calibration')
    p.add_argument('--seed',type=int,default=7)
    p.add_argument('--confirm-real',action='store_true')
    return p

if __name__=='__main__':
    parser=build_parser();a=parser.parse_args()
    if min(a.n,a.scale,a.concurrency,a.deadline,a.max_tokens,a.rpm,a.tpm,a.rpd,a.tpd)<=0 or min(a.interval,a.queue,a.retries)<0:
        parser.error('Counts, limits, deadline and output cap must be positive; interval/queue/retries nonnegative')
    asyncio.run(main(a))
