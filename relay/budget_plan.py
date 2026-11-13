import argparse
import json
from .common import estimate_tokens
from .pipeline import DRAFT_SYSTEM
from .retrieval import Retriever,SETTINGS

def plan(questions,max_tokens=700,tpm=8000):
    output=[]
    for setting in SETTINGS:
        r=Retriever(setting=setting);first=[];expanded=[]
        for q in questions:
            for expand,bucket in [(False,first),(True,expanded)]:
                ev=json.dumps([{'id':c['id'],'text':c['text']} for c in r.search(q['question'],expand=expand)])
                messages=[{'role':'system','content':DRAFT_SYSTEM},
                          {'role':'user','content':f"Question: {q['question']}\nEvidence: {ev}"}]
                bucket.append(estimate_tokens(json.dumps(messages))+max_tokens)
        output.append(dict(setting=setting,first_pass=sum(first),largest_first=max(first),
                           refusal_expansion_plan=sum(first)+sum(expanded[i] for i,q in enumerate(questions) if q['expected_refusal']),
                           every_question_expands=sum(first)+sum(expanded),
                           expansions_over_tpm=sum(v>tpm for v in expanded)))
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--questions',default='data/questions.json')
    p.add_argument('--max-tokens',type=int,default=700);p.add_argument('--tpm',type=int,default=8000)
    p.add_argument('--rpd',type=int,default=1000);p.add_argument('--tpd',type=int,default=200000)
    a=p.parse_args();qs=json.load(open(a.questions, encoding='utf-8'));rows=plan(qs,a.max_tokens,a.tpm)
    for row in rows:print(json.dumps(row))
    print('Refusal-expansion planning estimate:',sum(r['refusal_expansion_plan'] for r in rows),'; token/day limit entered:',a.tpd)
    print('Every-question-expands estimate:',sum(r['every_question_expands'] for r in rows))
    print('Planned calls if only expected refusals expand:',len(qs)*3+3*sum(q['expected_refusal'] for q in qs),'; request/day limit entered:',a.rpd)
    print('Not a usage prediction or upper bound. Actual model refusals can differ. Bytes/3 estimates may over- or underestimate tokens; fitted expansions may be smaller. Probes, verifier calls, retries and reruns are EXTRA. Keep a reserve; split across days if necessary.')
