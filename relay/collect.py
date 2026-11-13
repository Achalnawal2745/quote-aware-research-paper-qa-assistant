import argparse
import csv
from pathlib import Path
from .common import FIELDS

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('files',nargs='+'); p.add_argument('--output',default='results.csv')
    a=p.parse_args(); seen=set(); rows=[]
    for path in a.files:
        for r in csv.DictReader(open(path, encoding='utf-8-sig', newline='')):
            if r['request_id'] in seen: raise SystemExit('Duplicate request ID')
            if r['source']=='stand-in' and r['answer_grade']: raise SystemExit('Synthetic row has quality grade')
            seen.add(r['request_id']);rows.append(r)
    with open(a.output,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    print(f'{len(rows)} requests -> {a.output}')
