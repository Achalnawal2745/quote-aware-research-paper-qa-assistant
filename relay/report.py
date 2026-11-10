"""Tables are calculated, never handwritten. Missing observations stay missing."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
import numpy as np


def numeric(rows,field):
    return [float(r[field]) for r in rows if r.get(field) not in ('',None)]

def pct(values,ps=(50,95,99)):
    return ' / '.join(f'{x:.1f}' for x in np.percentile(values,ps)) if values else 'not measured'

def mdtable(headers,rows):
    return '| '+' | '.join(headers)+' |\n|'+'|'.join(['---']*len(headers))+'|\n'+''.join(
        '| '+' | '.join(str(x).replace('|','/') for x in r)+' |\n' for r in rows)

def peak_queue(rows):
    groups=defaultdict(list)
    for r in rows:
        if r.get('queue_enter_ms') and r.get('queue_exit_ms'):
            a,b=float(r['queue_enter_ms']),float(r['queue_exit_ms'])
            if b-a>=1:
                groups[r.get('session_id') or r.get('run_id','legacy')].extend([(a,1),(b,-1)])
    peak=0
    for events in groups.values():
        current=0
        for _,delta in sorted(events,key=lambda x:(x[0],x[1])):
            current+=delta;peak=max(peak,current)
    return peak

def generate(path,output,limits=None):
    rows=list(csv.DictReader(open(path, encoding='utf-8', errors='replace')))
    groups=defaultdict(list)
    for r in rows:
        groups[(r['run_id'],r['scenario'],r['source'])].append(r)
    latency=[]; outcomes=[]; timing=[]
    for (run,scenario,source),rs in groups.items():
        n=len(rs); ok=[r for r in rs if r['status']=='ok']
        durations=numeric(rs,'run_duration_s')
        duration=max(durations) if durations else 0
        rate=numeric(rs,'offered_rate_per_min')
        display=f"{scenario} [{run}]"
        latency.append([display,source,n,f'{duration:.3f}',f'{rate[0]:.1f}' if rate else 'instantaneous batch',
                        pct(numeric(ok,'first_token_ms')),pct(numeric(ok,'total_ms'))])
        complete=[r for r in ok if r['usage_complete']=='True']
        token=f"{np.mean([float(r['tokens_in'])+float(r['tokens_out']) for r in complete]):.1f}" if complete else 'not measured'
        cost=f"{sum(numeric(rs,'actual_cost_usd'))/len(ok)*1000:.4f}" if ok else 'not measured'
        outcomes.append([display,f"{len(ok)/n*100:.1f}",
                         f"{sum(r['status']=='rate_limited' for r in rs)/n*100:.1f}",
                         f"{sum(r['status']=='timeout' for r in rs)/n*100:.1f}",
                         f"{np.mean(numeric(rs,'retries')):.2f}",peak_queue(rs),token,cost,
                         f"{sum(r['status']=='error' for r in rs)/n*100:.1f}",
                         f"{sum(r['status']=='rate_limited' and r.get('rejection_source')=='provider_429' for r in rs)/n*100:.1f}",
                         f"{sum(r['status']=='rate_limited' and r.get('rejection_source')!='provider_429' for r in rs)/n*100:.1f}"])
        timing.append([display,pct(numeric(ok,'provider_ttft_ms'),(50,95)),
                       pct(numeric(ok,'validation_hold_ms'),(50,95))])
    retrieval=[]
    hashes={r.get('question_set_sha256','') for r in rows if r['source']=='real' and r['scenario']=='retrieval_eval'}
    if len(hashes)>1:
        raise ValueError('Mixed question-set versions in real quality evaluation; report separately')
    for setting in ['small','medium','large']:
        rs=[r for r in rows if r['source']=='real' and r['scenario']=='retrieval_eval' and r['retrieval_setting']==setting]
        if not rs:
            retrieval.append([setting]+['not measured']*8)
            continue
        n=len(rs); graded=[r for r in rs if r['answer_grade']]
        fraction=lambda grade: f"{sum(r['answer_grade']==grade for r in rs)/n*100:.1f}" if len(graded)==n else 'not measured'
        complete=[r for r in rs if r['usage_complete']=='True' and r['status']=='ok']
        retrieval.append([setting,n,fraction('correct'),fraction('wrong'),fraction('refused_correctly'),
                          f"{np.mean([float(r['tokens_in'])+float(r['tokens_out']) for r in complete]):.1f}" if complete else 'not measured',
                          pct(numeric([r for r in rs if r['status']=='ok'],'first_token_ms'),(50,95)),pct(numeric([r for r in rs if r['status']=='ok'],'total_ms'),(50,95)),
                          fraction('refused_wrongly')])
    text='# Generated results\n\n'
    text+='Latency percentiles use successful requests only; failures are in outcomes. Times are ms. '
    text+='Duration is the arrival window, not drain time. Burst rate is intentionally not a finite RPM. '
    text+='Tokens/answer include measured input and output across attempts; incomplete-usage requests are excluded. '
    text+='Cost is actual free-tier cash charge (or synthetic zero), not a paid-equivalent estimate. '
    text+='Peak queue counts waits of at least 1 ms from CSV spans. Independent runs are calculated separately. Provider/local rejection columns use all scenario requests as denominator; recovered 429s are logged separately as rate_limit_hits.\n\n'
    text+='## Table 1: Real limits\n'+mdtable(['Limit','Value found','How found','Confidence'],[
        (json.loads(Path(limits).read_text()).get(x,[x,'not measured','No observation','low']) if limits else [x,'not measured','Await real account and probe','low']) for x in
        ['Requests/min','Tokens/min','Requests/day','Tokens/day','Requests in flight','Limit response','Recovery time']])
    text+='\n## Table 2a: Latency\n'+mdtable(['Scenario','Source','Requests','Duration s','Offered/min','First p50/p95/p99','Total p50/p95/p99'],latency)
    text+='\n## Table 2b: Outcomes\n'+mdtable(['Scenario','OK %','Rate limited %','Timeout/given up %','Retries/request','Peak queue','Tokens/answer','$/1000 successful answers','Other error %','Provider rejection % of all','Local rejection % of all'],outcomes)
    text+='\n## Table 3: Retrieval\n'+mdtable(['Setting','Questions','Correct+cited %','Wrong %','Correct refusal %','Tokens/answer','First p50/p95','Total p50/p95','Wrong refusal %'],retrieval)
    text+='\nSettings are whitespace words (not model tokens): small=180/overlap30/k3; medium=300/50/k4; large=420/70/k5; expansion adds two passages, fitted to TPM. No reranking.\n'
    text+='\n## Additional timing\n'+mdtable(['Scenario','Provider TTFT p50/p95','Validation hold p50/p95'],timing)
    slow=max((r for r in rows if r['status']=='ok'),key=lambda r:float(r['total_ms']),default=None)
    if slow:
        text+='\n## Slow request trace\n'
        text+=f"Request `{slow['request_id']}` ({slow['source']}, {slow['scenario']}): total {float(slow['total_ms']):.1f} ms; "
        for f in ['queue_wait_ms','working_ms','retry_wait_ms','first_token_ms','provider_ttft_ms','validation_hold_ms']:
            text+=f"{f}={float(slow[f]):.1f} ms; " if slow[f] else f'{f}=not measured; '
        residual=float(slow['total_ms'])-sum(float(slow[f]) for f in ['queue_wait_ms','working_ms','retry_wait_ms'])
        text+=f'residual scheduling/validation overhead={residual:.1f} ms. '
        text+='Since release follows validation, almost all user delay is before the first answer token. See matching events.jsonl records.\n'
    Path(output).write_text(text)
    print(output)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('csv'); p.add_argument('--output',default='runs/tables.md'); p.add_argument('--limits',help='Reviewed JSON map: limit label -> four table cells')
    a=p.parse_args(); generate(a.csv,a.output,a.limits)
