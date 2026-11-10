"""Paired synthetic runs. Same seed/config, but retries change random draw order;
this is an operational comparison, not a request-paired causal experiment."""
import asyncio
import json
import os
from argparse import Namespace
from pathlib import Path
import httpx
from .run import main

async def experiment():
    from .standin import Config
    base=vars(Config())
    base.update(rpm=10000,tpm=10000000,rpd=100000,tpd=10000000,
                failure_probability=.35,slow_probability=.15,base_s=.12,seed=31,
                provenance='ASSUMED retry stress test, not real calibration')
    for retries in [0,1]:
        async with httpx.AsyncClient() as c:
            r=await c.post('http://127.0.0.1:8001/admin/config',json=base,
                          headers={'x-admin-token':os.environ.get('RELAY_ADMIN_TOKEN','')})
            r.raise_for_status()
        out=f'runs/v2-retry-{retries}'
        args=Namespace(mode='probe',scenario=('retry_disabled' if retries==0 else 'retry_enabled'),source='stand-in',base_url=None,model='synthetic',
                       output=out,questions='data/questions.json',question='',setting='small',
                       n=40,interval=.08,concurrency=2,queue=6,deadline=2,retries=retries,
                       verifier='off',rpm=10000,tpm=10000000,rpd=100000,tpd=10000000,
                       ledger=None,seed=31,confirm_real=False,calibration=None,
                       max_tokens=700,reasoning_effort="none",append=False,settings=None)
        await main(args)
        Path(out,'simulator_config.json').write_text(json.dumps(base,indent=2))
if __name__=='__main__':
    asyncio.run(experiment())
