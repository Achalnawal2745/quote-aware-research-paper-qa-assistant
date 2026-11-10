"""OpenAI-compatible HTTP/SSE stand-in. All output is synthetic, never quality evidence."""
import asyncio
import json
import os
import random
import time
from dataclasses import dataclass, asdict
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from .common import estimate_tokens

@dataclass
class Config:
    rpm:int=120
    tpm:int=100000
    rpd:int=10000
    tpd:int=2000000
    window_s:float=60
    day_s:float=86400
    base_s:float=.08
    prefill_s_per_token:float=.00001
    output_tokens_per_s:float=1500
    slowdown_per_inflight:float=.15
    slow_probability:float=.08
    slow_multiplier:float=8
    failure_probability:float=.03
    seed:int=7
    daily_exhausted:bool=False
    refusal_probability:float=0.0
    reasoning_chunks:int=0
    provenance:str='ASSUMED: synthetic smoke-test parameters, not real calibration'

app=FastAPI(title='Relay stand-in (synthetic only)')
config=Config()
rng=random.Random(config.seed)
window=[]
day_start=time.time()
day_requests=day_tokens=inflight=0
lock=asyncio.Lock()

def headers(now):
    used=sum(x[1] for x in window)
    minute_reset=max(0,config.window_s-(now-window[0][0])) if window else 0
    return {'x-ratelimit-limit-requests':str(config.rpd),
            'x-ratelimit-remaining-requests':str(max(0,config.rpd-day_requests)),
            'x-ratelimit-reset-requests':f'{max(0,config.day_s-(now-day_start)):.3f}s',
            'x-ratelimit-limit-tokens':str(config.tpm),
            'x-ratelimit-remaining-tokens':str(max(0,config.tpm-used)),
            'x-ratelimit-reset-tokens':f'{minute_reset:.3f}s',
            'x-relay-limit-requests-minute':str(config.rpm),
            'x-relay-remaining-requests-minute':str(max(0,config.rpm-len(window))),
            'x-relay-limit-requests-day':str(config.rpd),
            'x-relay-remaining-requests-day':str(max(0,config.rpd-day_requests)),
            'x-relay-limit-tokens-day':str(config.tpd),
            'x-relay-remaining-tokens-day':str(max(0,config.tpd-day_tokens)),
            'x-relay-source':'stand-in'}

@app.get('/health')
async def health():
    return {'source':'stand-in','inflight':inflight,'provenance':config.provenance}

@app.post('/admin/config')
async def configure(request:Request):
    global config,rng,window,day_start,day_requests,day_tokens
    token=os.environ.get('RELAY_ADMIN_TOKEN')
    if not token or request.headers.get('x-admin-token')!=token:
        raise HTTPException(403,'Set RELAY_ADMIN_TOKEN and supply x-admin-token')
    payload=await request.json()
    async with lock:
        if inflight:
            raise HTTPException(409,'Cannot reset while calls are in flight')
        config=Config(**payload); rng=random.Random(config.seed)
        window=[]; day_start=time.time(); day_requests=day_tokens=0
    return asdict(config)

def synthetic_answer(messages,refuse=False):
    content=messages[-1]['content']
    if messages[0]['content'].startswith('Judge whether'):
        return json.dumps({'supported':True})
    if refuse:
        return json.dumps({'refused':True,'claims':[]})
    try:
        evidence=json.loads(content.split('Evidence: ',1)[1])
        c=evidence[0]
        words=c['text'].split()[:22]
        quote=' '.join(words)
        # Extractive fixture only: not a semantic answer to the question.
        return json.dumps({'refused':False,'claims':[
            {'text':quote,'chunk_id':c['id'],'quote':quote}]})
    except (ValueError,IndexError,KeyError):
        return json.dumps({'refused':True,'claims':[]})

@app.post('/openai/v1/chat/completions')
async def complete(request:Request):
    global window,day_start,day_requests,day_tokens,inflight
    body=await request.json()
    messages=body.get('messages',[])
    refuse=config.refusal_probability>0 and rng.random()<config.refusal_probability
    text=synthetic_answer(messages,refuse)
    tin=estimate_tokens(json.dumps(messages)); tout=estimate_tokens(text)
    async with lock:
        now=time.time()
        if now-day_start>=config.day_s:
            day_start=now; day_requests=day_tokens=0
        window=[x for x in window if now-x[0]<config.window_s]
        reason=None
        if config.daily_exhausted or day_requests>=config.rpd or day_tokens+tin+tout>config.tpd:
            reason='daily quota exhausted'; wait=max(.01,config.day_s-(now-day_start))
        elif len(window)>=config.rpm or sum(x[1] for x in window)+tin+tout>config.tpm:
            reason='minute quota exhausted'
            wait=max(.01,config.window_s-(now-window[0][0])) if window else config.window_s
        if reason:
            h=headers(now); h['retry-after']=f'{wait:.3f}'
            return JSONResponse({'error':{'message':reason,'type':'rate_limit_error'}},429,headers=h)
        day_requests+=1; day_tokens+=tin+tout; window.append((now,tin+tout))
        h=headers(now)
        if rng.random()<config.failure_probability:
            return JSONResponse({'error':{'message':'synthetic transient failure'}},503,headers=h)
        inflight+=1
        factor=1+config.slowdown_per_inflight*(inflight-1)
        if rng.random()<config.slow_probability:
            factor*=config.slow_multiplier
        delay=(config.base_s+tin*config.prefill_s_per_token)*factor
        per_piece=factor/config.output_tokens_per_s
    async def stream():
        global inflight
        try:
            await asyncio.sleep(delay)
            for _ in range(config.reasoning_chunks):
                yield 'data: '+json.dumps({'choices':[{'index':0,'delta':{'reasoning':'thinking '},'finish_reason':None}]})+'\n\n'
                await asyncio.sleep(per_piece*3)
            # Small text pieces, not claimed to be the actual model tokenizer.
            for i in range(0,len(text),12):
                piece=text[i:i+12]
                yield 'data: '+json.dumps({'id':'synthetic','object':'chat.completion.chunk',
                    'choices':[{'index':0,'delta':{'content':piece},'finish_reason':None}]})+'\n\n'
                await asyncio.sleep(per_piece*estimate_tokens(piece))
            yield 'data: '+json.dumps({'choices':[{'index':0,'delta':{},'finish_reason':'stop'}]})+'\n\n'
            yield 'data: '+json.dumps({'choices':[], 'usage':{
                'prompt_tokens':tin,'completion_tokens':tout,'total_tokens':tin+tout}})+'\n\n'
            yield 'data: [DONE]\n\n'
        finally:
            async with lock:
                inflight-=1
    if not body.get('stream'):
        async with lock:
            inflight-=1
        return JSONResponse({'choices':[{'message':{'content':text}}],
                             'usage':{'prompt_tokens':tin,'completion_tokens':tout}},headers=h)
    return StreamingResponse(stream(),media_type='text/event-stream',headers=h)
