import asyncio
import json
import time
import httpx
from relay.standin import app
from relay.adapter import Adapter
from relay.budget import Budget
from relay.common import Artifacts


def test_standin_headers_daily_and_stream(monkeypatch):
    monkeypatch.setenv('RELAY_ADMIN_TOKEN','test-only')
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            h={'x-admin-token':'test-only'}
            r=await c.post('/admin/config',json={'failure_probability':0,'slow_probability':0,'base_s':.001},headers=h)
            assert r.status_code==200
            payload={'messages':[{'role':'user','content':'hi'}],'stream':True}
            r=await c.post('/openai/v1/chat/completions',json=payload)
            assert r.status_code==200 and '[DONE]' in r.text
            assert r.headers['x-ratelimit-limit-requests']=='10000'
            assert r.headers['x-ratelimit-limit-tokens']=='100000'
            await c.post('/admin/config',json={'daily_exhausted':True},headers=h)
            r=await c.post('/openai/v1/chat/completions',json=payload)
            assert r.status_code==429 and 'retry-after' in r.headers
            assert 'daily quota' in r.text
    asyncio.run(run())


def test_retry_records_all_usage(tmp_path):
    async def run():
        a=Artifacts(tmp_path); b=Budget(tpm=100000)
        adapter=Adapter('https://test/openai/v1/','unused','model',b,a,max_retries=1)
        attempts=0
        def respond(request):
            nonlocal attempts
            attempts+=1
            if attempts==1:
                return httpx.Response(503,json={'error':'temporary'})
            return httpx.Response(200,text='data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
                'data: {"choices":[],"usage":{"prompt_tokens":2,"completion_tokens":1}}\n\n'
                'data: [DONE]\n\n')
        await adapter.client.aclose()
        adapter.client=httpx.AsyncClient(base_url='https://test/openai/v1/',transport=httpx.MockTransport(respond))
        s=dict(request_id='r',deadline=time.perf_counter()+3,model_calls=0,working_ms=0.,queue_wait_ms=0.,
               retry_wait_ms=0.,tokens_in=0,tokens_out=0,usage_complete=True,rate_limit_hits=0,retries=0)
        assert await adapter.complete([{'role':'user','content':'q'}],s)=='ok'
        assert s['retries']==1 and s['model_calls']==2
        assert s['usage_complete'] is False  # Failed attempt's billing is unknown.
        assert s['retry_wait_ms']>=250
        await adapter.close();a.close()
        assert len((tmp_path/'calls.jsonl').read_text().splitlines())==2
    asyncio.run(run())
