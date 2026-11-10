import asyncio
import csv
import json
import os
import time
from pathlib import Path
from email.utils import formatdate
import httpx
import pytest
from relay.adapter import Adapter,CallError
from relay.budget import Budget,BudgetExceeded
from relay.common import Artifacts,FIELDS,load_dotenv,retry_after_seconds
from relay.pipeline import Pipeline
from relay.retrieval import Retriever,EXPAND_EXTRA,SETTINGS
from relay.limit_probe import recovery_delay

REFUSAL='{"refused":true,"claims":[]}'
class FakeRetriever:
    def __init__(self,n=1,words=50):self.n,self.words=n,words
    def search(self,q,expand=False):
        return [dict(id=f'p:p1:c{i}',text=('evidence '*self.words).strip()+f' {i}')
                for i in range(self.n+(EXPAND_EXTRA if expand else 0))]
class ScriptedAdapter:
    max_tokens=100
    def __init__(self,script,tpm=100000):
        self.script=list(script);self.budget=Budget(tpm=tpm);self.calls=0
    async def complete(self,*args,**kwargs):
        self.calls+=1;value=self.script.pop(0)
        if value=='sleep':await asyncio.sleep(1)
        if isinstance(value,Exception):raise value
        return value

def make(tmp_path,adapter,retriever=None,deadline=2,verifier='off'):
    a=Artifacts(tmp_path)
    return Pipeline(retriever or FakeRetriever(),adapter,a,concurrency=1,max_queue=2,
                    deadline_s=deadline,verifier=verifier),a

@pytest.mark.parametrize('error',[CallError('over TPM','rate_limited','local_budget'),CallError('network'),TimeoutError()])
def test_optional_expansion_preserves_refusal(tmp_path,error):
    async def run():
        ad=ScriptedAdapter([REFUSAL,error]);p,a=make(tmp_path,ad)
        r=await p.request('q','retrieval_eval','real','large');a.close()
        assert r['status']=='ok' and r['refused'] is True
        assert 'kept first-pass refusal' in r['expansion_note']
        assert ad.calls==2
    asyncio.run(run())

def test_optional_expansion_times_out_before_outer_deadline(tmp_path):
    async def run():
        ad=ScriptedAdapter([REFUSAL,'sleep']);p,a=make(tmp_path,ad,deadline=.12)
        r=await p.request('q','x','real','small');a.close()
        assert r['status']=='ok' and r['refused']
        assert r['total_ms']<150
    asyncio.run(run())

def test_optional_verifier_failure_preserves_refusal(tmp_path):
    async def run():
        claim=json.dumps({'refused':False,'claims':[{'text':'claim','quote':'evidence evidence evidence evidence evidence','chunk_id':'p:p1:c0'}]})
        ad=ScriptedAdapter([REFUSAL,claim,CallError('verifier down')]);p,a=make(tmp_path,ad,verifier='always')
        r=await p.request('q','x','real','small');a.close()
        assert r['status']=='ok' and r['refused']
        assert 'verifier failed' in r['expansion_note']
    asyncio.run(run())

def test_first_draft_failure_propagates(tmp_path):
    async def run():
        ad=ScriptedAdapter([CallError('boom')]);p,a=make(tmp_path,ad)
        r=await p.request('q','x','real','small');a.close()
        assert r['status']=='error'
    asyncio.run(run())

def test_trim_all_when_single_passage_too_large(tmp_path):
    p,a=make(tmp_path,ScriptedAdapter([],tpm=200),FakeRetriever(words=2000))
    assert p._fit_to_tpm('q',p.retriever.search('q',expand=True))==[]
    a.close()

def test_daily_reply_has_sources_without_model_call(tmp_path):
    async def run():
        ad=ScriptedAdapter([]);ad.budget.day_requests=ad.budget.rpd
        p,a=make(tmp_path,ad);r=await p.request('q','x','real','small');a.close()
        assert r['status']=='rate_limited' and r['rejection_source']=='local_daily_block'
        assert 'NOT an answer' in r['answer'] and 'p:p1:c0' in r['answer']
        assert ad.calls==0
    asyncio.run(run())

def test_known_request_reset_does_not_clear_token_day_spend():
    b=Budget();b.day_requests=b.rpd;b.day_tokens=1234
    b.daily_block=True;b.daily_block_kind='requests';b.request_reset=time.time()-1
    assert not b.daily_exhausted()
    assert b.day_tokens==1234 and b.day_requests==0

def test_header_disabled_budget_really_ignores_learning():
    async def run():
        b=Budget(tpm=100000,observe_headers=False)
        await b.observe({'x-ratelimit-limit-tokens':'1','retry-after':'60'},429,'minute quota')
        assert b.tpm==100000 and b.blocked_until==0
    asyncio.run(run())

def state():
    return dict(request_id='r',deadline=time.perf_counter()+5,model_calls=0,working_ms=0.,queue_wait_ms=0.,
                retry_wait_ms=0.,tokens_in=0,tokens_out=0,usage_complete=True,rate_limit_hits=0,retries=0,
                provider_first_any_ms='')
async def mock_adapter(tmp_path,respond,**kwargs):
    arts=Artifacts(tmp_path)
    ad=Adapter('https://test/openai/v1/','unused','m',Budget(tpm=100000),arts,max_retries=0,**kwargs)
    await ad.client.aclose()
    ad.client=httpx.AsyncClient(base_url='https://test/openai/v1/',transport=httpx.MockTransport(respond))
    return ad,arts

def test_reasoning_tokens_and_configurable_payload(tmp_path):
    async def run():
        payload={}
        def respond(req):
            payload.update(json.loads(req.content))
            return httpx.Response(200,text='data: {"choices":[{"delta":{"reasoning":"thinking"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"hi"},"finish_reason":"stop"}]}\n\n'
                'data: {"choices":[],"usage":{"prompt_tokens":5,"completion_tokens":3}}\n\ndata: [DONE]\n\n')
        ad,a=await mock_adapter(tmp_path,respond,reasoning_effort='low',max_tokens=321);s=state()
        assert await ad.complete([{'role':'user','content':'q'}],s)=='hi'
        await ad.close();a.close()
        assert payload['reasoning_effort']=='low' and payload['max_completion_tokens']==321
        assert 0<=s['provider_first_any_ms']<=s['provider_ttft_ms']
        record=json.loads((tmp_path/'calls.jsonl').read_text())
        assert record['finish_reason']=='stop' and record['session_id']
        assert record['dispatch_unix_ms']>0
    asyncio.run(run())

@pytest.mark.parametrize('body,expected',[
    ('data: {"choices":[{"delta":{"content":"partial"},"finish_reason":"length"}]}\n\ndata: [DONE]\n\n','truncated'),
    ('data: {"choices":[{"delta":{"reasoning":"thinking"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n','empty content'),
    ('data: {"choices":[{"delta":{"content":"partial"}}]}\n\n','without [DONE]')])
def test_stream_failures_are_not_silently_accepted(tmp_path,body,expected):
    async def run():
        ad,a=await mock_adapter(tmp_path,lambda req:httpx.Response(200,text=body))
        with pytest.raises(CallError,match=expected.replace('[',r'\[').replace(']',r'\]')):
            await ad.complete([{'role':'user','content':'q'}],state())
        await ad.close();a.close()
    asyncio.run(run())

def test_provider_429_attribution(tmp_path):
    async def run():
        ad,a=await mock_adapter(tmp_path,lambda req:httpx.Response(429,headers={'retry-after':'3'},json={'error':'minute quota'}))
        with pytest.raises(CallError) as e:await ad.complete([{'role':'user','content':'q'}],state())
        assert e.value.source=='provider_429'
        await ad.close();a.close()
    asyncio.run(run())

def test_dotenv_shell_wins_and_model_default_loaded_early(tmp_path,monkeypatch):
    from relay.run import build_parser
    monkeypatch.chdir(tmp_path);monkeypatch.setenv('RELAY_TEST_B','shell')
    monkeypatch.delenv('RELAY_MODEL',raising=False)
    (tmp_path/'.env').write_text('RELAY_MODEL="test-model"\nRELAY_TEST_B=file\n')
    p=build_parser()
    assert p.parse_args(['ask']).model=='test-model'
    assert os.environ['RELAY_TEST_B']=='shell'
    monkeypatch.delenv('RELAY_MODEL')

def test_missing_key_makes_no_artifacts(tmp_path,monkeypatch):
    from relay.run import main,build_parser
    monkeypatch.chdir(tmp_path);monkeypatch.delenv('GROQ_API_KEY',raising=False)
    args=build_parser().parse_args(['ask','--source','real','--confirm-real','--output','out'])
    with pytest.raises(SystemExit,match='GROQ_API_KEY'):asyncio.run(main(args))
    assert not (tmp_path/'out').exists()

def test_append_has_distinct_sessions_and_preserves_rows(tmp_path):
    first=Artifacts(tmp_path);first.row({'request_id':'one'});sid=first.session_id;first.close()
    second=Artifacts(tmp_path,append=True);second.row({'request_id':'two'});assert second.session_id!=sid;second.close()
    rows=list(csv.DictReader(open(tmp_path/'results.csv')))
    assert len(rows)==2 and len({r['session_id'] for r in rows})==2
    events=[json.loads(x) for x in (tmp_path/'events.jsonl').read_text().splitlines()]
    assert all(e['unix_ms']>0 and e['session_id'] for e in events)
    with pytest.raises(ValueError,match='already contains'):Artifacts(tmp_path)

def test_append_rejects_schema_change(tmp_path):
    (tmp_path/'results.csv').write_text('wrong,header\na,b\n')
    with pytest.raises(ValueError,match='schema'):Artifacts(tmp_path,append=True)

def test_retry_after_and_recovery_policy():
    assert retry_after_seconds('3')==3
    now=1700000000
    assert retry_after_seconds(formatdate(now+60,usegmt=True),now=now)==60
    assert recovery_delay({'retry-after':'100'},'minute quota',90)[0] is None
    assert recovery_delay({'retry-after':'3'},'daily quota exhausted',90)[0] is None
    assert recovery_delay({'retry-after':'3','x-ratelimit-remaining-requests':'0'},'quota',90)[0] is None
    assert recovery_delay({},'minute quota',90)[0] is None
    assert recovery_delay({'retry-after':'3'},'minute quota',90)[0]==4

def test_limit_evidence_separates_clock_sessions_and_rejects_synthetic(tmp_path):
    from relay.limits_from_calls import main
    d=tmp_path/'calls';d.mkdir();(d/'config.json').write_text('{"source":"real"}')
    records=[dict(request_id=str(i),http_status=200,dispatch_ms=0,total_ms=10,session_id=str(i),headers={}) for i in range(3)]
    records.append(dict(request_id='429',http_status=429,dispatch_ms=20,total_ms=1,session_id='0',headers={'retry-after':'12'},error='on tokens per minute (TPM): Limit 8000, Used 6000'))
    (d/'calls.jsonl').write_text('\n'.join(json.dumps(r) for r in records))
    result=main([d],tmp_path/'limits.json')
    assert result['Tokens/min'][1]=='8000'
    assert result['Requests in flight'][1].startswith('>= 1 ')
    (d/'config.json').write_text('{"source":"stand-in"}')
    with pytest.raises(ValueError,match='non-real'):main([d],tmp_path/'out.json')

def test_expansion_adds_two_passages():
    for setting in SETTINGS:
        r=Retriever(setting=setting)
        assert len(r.search('transformer attention',expand=True))<=r.k+2

def test_report_queue_sessions_not_summed():
    from relay.report import peak_queue
    assert peak_queue([dict(queue_enter_ms='1',queue_exit_ms='10',session_id='a'),
                       dict(queue_enter_ms='1',queue_exit_ms='10',session_id='b')])==1


def test_probe_wall_clock_timeout_without_network(tmp_path,monkeypatch):
    from argparse import Namespace
    from relay import limit_probe
    class BlockingAdapter:
        def __init__(self,*args,**kwargs):pass
        async def complete(self,*args,**kwargs):await asyncio.sleep(1)
        async def close(self):pass
    monkeypatch.setenv('GROQ_API_KEY','test-placeholder-not-a-real-key')
    monkeypatch.setattr(limit_probe,'Adapter',BlockingAdapter)
    args=Namespace(confirm_real=True,model='mock',output=str(tmp_path/'probe'),prompt_tokens=20,
                   max_tokens=10,token_budget=10000,max_calls=1,max_wait=2,deadline=.03,
                   rpd=1000,tpd=200000,ledger=None)
    asyncio.run(limit_probe.main(args))
    rows=list(csv.DictReader(open(tmp_path/'probe/results.csv')))
    assert rows[0]['status']=='timeout'
    assert float(rows[0]['total_ms'])<200


def test_calibration_uses_reasoning_generation_interval(tmp_path):
    import subprocess,sys
    d=tmp_path/'real';d.mkdir();(d/'config.json').write_text('{"source":"real"}')
    recs=[dict(error=None,usage=dict(prompt_tokens=1000+400*i,completion_tokens=300),
               provider_ttft_ms=900+100*i,provider_first_any_ms=100+10*i,total_ms=1400+100*i) for i in range(6)]
    (d/'calls.jsonl').write_text('\n'.join(json.dumps(r) for r in recs))
    output=tmp_path/'calibration.json'
    command=[sys.executable,'-m','relay.calibrate',str(d),'--output',str(output)]
    p=__import__('subprocess').run(command,capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    assert 150<json.loads(output.read_text())['simulator_parameters']['output_tokens_per_s']<400
    (d/'config.json').write_text('{"source":"stand-in"}')
    assert __import__('subprocess').run(command,capture_output=True).returncode!=0
