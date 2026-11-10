import csv
from pathlib import Path
from relay.common import FIELDS
from relay.report import peak_queue


def test_bundled_results_are_honest_and_consistent():
    rows=list(csv.DictReader(open('results.csv')))
    assert len(rows)>0
    assert len({r['request_id'] for r in rows})==len(rows)
    assert set(FIELDS)==set(rows[0])
    for r in rows:
        assert r['source'] in ('real','stand-in')
        if r['source']=='stand-in':
            assert r['answer_grade']==''
        else:
            assert r['answer_grade'] in ('','correct','wrong','refused_correctly','refused_wrongly')
        assert r['status'] in ['ok','rate_limited','timeout','error']
        if r['status']=='ok':
            assert 0<=float(r['first_token_ms'])<=float(r['total_ms'])
        else:
            assert r['first_token_ms']==''
        assert float(r['total_ms'])>=0
        assert sum(float(r[x]) for x in ['queue_wait_ms','working_ms','retry_wait_ms'])<=float(r['total_ms'])+1


def test_peak_queue_spans():
    assert peak_queue([{'queue_enter_ms':'1','queue_exit_ms':'5'},
                       {'queue_enter_ms':'2','queue_exit_ms':'6'},
                       {'queue_enter_ms':'7','queue_exit_ms':'7.1'}])==2
