"""Reviewed Table 1 evidence: real-call observations plus explicitly labeled doc fallbacks."""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
PAT=re.compile(r'on (?:requests|tokens) per (?:minute|day)\s*\((RPM|TPM|RPD|TPD)\)\s*:\s*Limit\s*([\d,]+)',re.I)
LABEL={'RPM':'Requests/min','TPM':'Tokens/min','RPD':'Requests/day','TPD':'Tokens/day'}

def main(dirs,out):
    calls=[];recovery=[];models=set()
    for directory in dirs:
        d=Path(directory);cfg=json.loads((d/'config.json').read_text())
        if cfg.get('source')!='real':raise ValueError(f'Refusing non-real source: {d}')
        models.add(cfg.get('model'))
        for line in (d/'calls.jsonl').read_text().splitlines():
            r=json.loads(line)
            # Never compare reset monotonic clocks from unrelated sessions/directories.
            r['_clock']=(str(d.resolve()),r.get('session_id','legacy-single-session'))
            calls.append(r)
        if (d/'probe-summary.json').exists():
            value=json.loads((d/'probe-summary.json').read_text()).get('recovery_s')
            if value is not None:recovery.append(value)
    if len(models)>1:raise ValueError('Cannot combine real limits for different or unknown model identities')
    model=next(iter(models),None)
    docs=json.loads(Path('docs/documented-limits.json').read_text());result={}
    for c in calls:
        if c.get('http_status')!=429:continue
        for m in PAT.finditer(c.get('error') or ''):
            label=LABEL[m.group(1).upper()]
            result[label]=[label,m.group(2).replace(',',''),f'Real 429 body; request {c["request_id"]}','high']
    for c in calls:
        for header,label in [('x-ratelimit-limit-requests','Requests/day'),('x-ratelimit-limit-tokens','Tokens/min')]:
            value=c.get('headers',{}).get(header)
            if value:result.setdefault(label,[label,value,f'Real {header} header; request {c["request_id"]}','medium'])
    for key,label in [('rpm','Requests/min'),('tpm','Tokens/min'),('rpd','Requests/day'),('tpd','Tokens/day')]:
        result.setdefault(label,[label,f'{docs[key]} (documented, not observed)' if model==docs['model'] else 'not measured',
                                 f'Public documentation for {docs["model"]}, not account measurement' if model==docs['model'] else 'No observed value or matching-model documentation','low'])
    groups=defaultdict(list)
    for c in calls:
        if c.get('http_status')==200 and c.get('total_ms') is not None:
            groups[c['_clock']].extend([(c['dispatch_ms'],1),(c['dispatch_ms']+c['total_ms'],-1)])
    peak=0
    for events in groups.values():
        current=0
        for _,delta in sorted(events,key=lambda x:(x[0],x[1])):
            current+=delta;peak=max(peak,current)
    result['Requests in flight']=['Requests in flight',f'>= {peak} overlapping accepted calls (not a provider cap)' if peak else 'not measured',
                                  'Accepted-call spans compared only within a single clock session','low']
    errors=[c for c in calls if c.get('http_status')==429]
    result['Limit response']=['Limit response',f'HTTP 429; Retry-After={errors[0]["headers"].get("retry-after","absent")}' if errors else 'not measured',
                              f'{len(errors)} observed real 429s; raw bodies preserved','high' if errors else 'low']
    result['Recovery time']=['Recovery time',f'<= {max(recovery):.2f} s observed recovery bound' if recovery else 'not measured',
                             'Successful recovery probe includes response time; not an exact reset measurement','medium' if recovery else 'low']
    Path(out).parent.mkdir(parents=True,exist_ok=True)
    Path(out).write_text(json.dumps(result,indent=2));print(out)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('dirs',nargs='+');p.add_argument('--output',default='runs/limits.json')
    a=p.parse_args();main(a.dirs,a.output)
