import asyncio
import csv
import json
from pathlib import Path
import httpx
import pytest
from relay.budget import Budget,BudgetExceeded
from relay.common import parse_duration,Artifacts
from relay.pipeline import validate,Pipeline
from relay.adapter import Adapter
from relay.retrieval import Retriever


def test_durations():
    assert parse_duration('2m59.56s')==pytest.approx(179.56)
    assert parse_duration('12ms')==.012
    assert parse_duration('nonsense') is None


def test_quote_validation_not_entailment():
    chunks=[{'id':'paper:p1:c0','text':'the model uses a masked attention mechanism'}]
    d={'refused':False,'claims':[{'text':'claim','chunk_id':'paper:p1:c0','quote':'the model uses a masked attention mechanism'}]}
    assert validate(d,chunks)[0]
    d['claims'][0]['chunk_id']='invented'
    assert not validate(d,chunks)[0]
    d['claims'][0]['chunk_id']='paper:p1:c0';d['claims'][0]['quote']='invented span with five or more words'
    assert not validate(d,chunks)[0]
    assert validate({'refused':True,'claims':[]},chunks)[0]
    assert not validate({'refused':True,'claims':[{}]},chunks)[0]


def test_budget_reserve_reconcile_and_limits(tmp_path):
    async def run():
        b=Budget(rpm=1,tpm=100,rpd=2,tpd=500,ledger=tmp_path/'ledger.json')
        t=await b.reserve(80)
        await b.reconcile(t,30)
        assert b.day_tokens==30
        with pytest.raises(BudgetExceeded) as e:
            await b.reserve(20)
        assert e.value.wait>0 and not e.value.daily
        await b.observe({'x-ratelimit-remaining-requests':'0','retry-after':'2'},429,'requests per day exceeded')
        with pytest.raises(BudgetExceeded) as e:
            await b.reserve(1)
        assert e.value.daily
        assert Budget(ledger=tmp_path/'ledger.json').daily_block
    asyncio.run(run())


def test_retriever(tmp_path):
    path=tmp_path/'pages.json'
    path.write_text(json.dumps([{'paper':'p','page':1,'text':'decoder masking prevents attending to future positions'},
                               {'paper':'p','page':2,'text':'audio codec vector quantization'}]))
    r=Retriever(path,'small')
    assert r.search('decoder future masking')[0]['page']==1
    assert r.search('xyzunlikely')==[]


def test_deadline_and_queue_bound(tmp_path):
    class R:
        def search(self,*a,**k):
            return [{'id':'p:p1:c0','text':'some evidence with at least five words'}]
    class A:
        budget=Budget(tpm=100000)
        async def complete(self,*a,**k):
            await asyncio.sleep(2)
    async def run():
        a=Artifacts(tmp_path)
        p=Pipeline(R(),A(),a,concurrency=1,max_queue=0,deadline_s=.03)
        results=await asyncio.gather(*(p.request('q','test','stand-in','small') for _ in range(3)))
        assert sorted(r['status'] for r in results)==['rate_limited','rate_limited','timeout']
        assert p.active==p.waiting==0
        assert all(r['first_token_ms']=='' for r in results)
        a.close()
    asyncio.run(run())


def test_real_and_standin_share_sse_adapter(tmp_path):
    async def run():
        a=Artifacts(tmp_path)
        b=Budget(tpm=100000)
        adapter=Adapter('https://example.test/openai/v1/','not-a-secret','model',b,a)
        def respond(req):
            assert req.url.path=='/openai/v1/chat/completions'
            return httpx.Response(200,content=(
                'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
                'data: {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":2}}\n\n'
                'data: [DONE]\n\n'),headers={'content-type':'text/event-stream'})
        await adapter.client.aclose()
        adapter.client=httpx.AsyncClient(base_url='https://example.test/openai/v1/',transport=httpx.MockTransport(respond))
        s=dict(request_id='r',deadline=999999999,model_calls=0,working_ms=0.,queue_wait_ms=0.,
               retry_wait_ms=0.,tokens_in=0,tokens_out=0,usage_complete=True,rate_limit_hits=0,retries=0)
        assert await adapter.complete([{'role':'user','content':'q'}],s)=='hello'
        assert s['tokens_in']==10 and s['tokens_out']==2
        assert b.day_tokens==12
        assert s['provider_ttft_ms']>=0
        await adapter.close(); a.close()
    asyncio.run(run())


def test_retriever_expansion_and_explanatory_scores(tmp_path):
    path = tmp_path / 'pages.json'
    path.write_text(json.dumps([
        {'paper': 'moshi', 'page': 4, 'title': 'Moshi speech-text dialogue',
         'text': 'Mimi is an audio codec using residual vector quantization for speech tokens.'},
        {'paper': 'attention', 'page': 2, 'title': 'Attention Is All You Need',
         'text': 'Masked attention prevents a decoder position from attending to future positions.'}
    ]))
    r = Retriever(path, 'small')
    baseline = r.search('Mimi audio codec')
    expanded = r.search('Moshi quantisation speech', expand=True)
    assert baseline and baseline[0]['paper'] == 'moshi'
    assert expanded and expanded[0]['paper'] == 'moshi'
    assert {'score_bm25', 'score_phrase', 'score_title'} <= set(expanded[0])


def test_retriever_empty_and_top_k(tmp_path):
    path = tmp_path / 'pages.json'
    path.write_text(json.dumps([{'paper': 'p', 'page': 1, 'text': 'alpha beta gamma delta'}]))
    r = Retriever(path, 'large')
    assert r.search('the and is') == []
    assert len(r.search('alpha beta gamma', top_k=1)) == 1
