"""Offline lexical evidence coverage, NOT answer correctness or a guaranteed recall bound."""
import argparse
import json
from .common import estimate_tokens
from .pipeline import DRAFT_SYSTEM
from .retrieval import Retriever,SETTINGS,normalize

def audit(questions,max_tokens=700):
    out=[]
    for setting in SETTINGS:
        r=Retriever(setting=setting); first_hits=expanded_hits=n=0
        contexts=[];reservations=[];misses=[]
        for q in questions:
            if q['expected_refusal']:continue
            n+=1
            first=r.search(q['question']); expanded=r.search(q['question'],expand=True)
            def hit(chunks):
                text=normalize(' '.join(c['text'] for c in chunks)).lower()
                return bool(q.get('evidence_terms')) and all(normalize(t).lower() in text for t in q['evidence_terms'])
            first_hits+=hit(first);expanded_hits+=hit(expanded)
            if not hit(first):misses.append(q['id'])
            contexts.append(estimate_tokens(' '.join(c['text'] for c in first)))
            ev=json.dumps([{'id':c['id'],'text':c['text']} for c in first])
            reservations.append(estimate_tokens(json.dumps([
                {'role':'system','content':DRAFT_SYSTEM},
                {'role':'user','content':f"Question: {q['question']}\nEvidence: {ev}"}]))+max_tokens)
        out.append(dict(setting=setting,answerable=n,first_pass_hit=first_hits,
                        after_expansion_hit=expanded_hits,mean_context_tokens_est=round(sum(contexts)/max(1,n)),
                        max_reservation_est=max(reservations,default=0),misses=misses))
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--questions',default='data/questions.json')
    p.add_argument('--max-tokens',type=int,default=700);a=p.parse_args()
    print('| Setting | Answerable | First-pass phrase hits | After +2 passages | Mean context estimate | Max reservation estimate | Missed |')
    print('|---|---|---|---|---|---|---|')
    for r in audit(json.load(open(a.questions)),a.max_tokens):
        print('| '+' | '.join(str(v) for v in [r['setting'],r['answerable'],r['first_pass_hit'],r['after_expansion_hit'],r['mean_context_tokens_est'],r['max_reservation_est'],','.join(r['misses']) or '-'])+' |')
    print('\nPhrase coverage is a lexical proxy, not semantic support or a quality grade. Bytes/3 token estimates can over- or underestimate actual usage. Expansion fitting may remove passages counted here.')
