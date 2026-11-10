"""Export manual review sheet or apply evidence-checked human grades without altering source CSV."""
import argparse
import csv
from pathlib import Path

VALID={'correct','wrong','refused_correctly','refused_wrongly'}
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('csv'); p.add_argument('--grades'); p.add_argument('--output',required=True)
    a=p.parse_args(); rows=list(csv.DictReader(open(a.csv, encoding='utf-8', errors='replace')))
    if a.grades:
        grades={r['request_id']:r for r in csv.DictReader(open(a.grades, encoding='utf-8', errors='replace'))}
        for row in rows:
            g=grades.get(row['request_id'])
            if not g or not g['answer_grade']: continue
            if row['source']!='real': raise SystemExit('Cannot quality-grade stand-in output')
            if g['answer_grade'] not in VALID or not g.get('review_notes','').strip():
                raise SystemExit('Each applied grade needs valid label and evidence review_notes')
            row['answer_grade']=g['answer_grade']
        with open(a.output,'w',newline='', encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    else:
        with open(a.output,'w',newline='', encoding='utf-8') as f:
            keys=['request_id','question_id','retrieval_setting','source','status','answer','answer_grade','review_notes']
            w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore'); w.writeheader()
            w.writerows(r for r in rows if r['source']=='real')
    print(a.output)
