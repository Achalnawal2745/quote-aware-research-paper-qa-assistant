import csv
import json
import math
import os
import uuid
from datetime import datetime, timezone
import re
import time
from pathlib import Path

FIELDS = ['request_id','scenario','source','start_time','first_token_ms','total_ms','status',
          'retries','tokens_in','tokens_out','retrieval_setting','answer_grade',
          'provider_ttft_ms','validation_hold_ms','queue_wait_ms','working_ms','retry_wait_ms',
          'rate_limit_hits','queue_enter_ms','queue_exit_ms','queue_depth','offered_offset_ms',
          'run_id','run_duration_s','offered_rate_per_min','actual_cost_usd','usage_complete',
          'retrieved_chunks','context_est_tokens','retrieval_degraded','verification_policy',
          'model_calls','refused','answer','error','question_id',
          'rejection_source','provider_first_any_ms','expansion_note','session_id','question_set_sha256']

def estimate_tokens(text):
    # Heuristic only, not a guaranteed upper bound; reconcile with server usage.
    return max(1, math.ceil(len(text.encode('utf-8')) / 3))

def parse_duration(value):
    if not value:
        return None
    try:
        return max(0., float(value))
    except ValueError:
        units = {'ms': .001, 's': 1, 'm': 60, 'h': 3600, 'd': 86400}
        matches = re.findall(r'(\d+(?:\.\d+)?)(ms|s|m|h|d)', value)
        return sum(float(n)*units[u] for n, u in matches) if matches else None

class Artifacts:
    def __init__(self, directory, append=False):
        self.path = Path(directory)
        self.path.mkdir(parents=True, exist_ok=True)
        csv_path = self.path/'results.csv'
        fresh = not csv_path.exists() or csv_path.stat().st_size == 0
        orphaned=any((self.path/name).exists() and (self.path/name).stat().st_size>0 for name in ['events.jsonl','calls.jsonl'])
        if not append and (not fresh or orphaned):
            raise ValueError('Output already contains results; choose a new directory or use --append')
        if append and not fresh:
            with csv_path.open(newline='', encoding='utf-8') as f:
                existing = next(csv.reader(f))
            if existing != FIELDS:
                raise ValueError('Cannot append: CSV schema differs; use a fresh output directory')
        self.session_id = uuid.uuid4().hex
        self.origin = time.perf_counter()
        self.origin_unix_ms = time.time()*1000
        mode = 'a' if append else 'w'
        self.csv = csv_path.open(mode, newline='', encoding='utf-8')
        self.writer = csv.DictWriter(self.csv, fieldnames=FIELDS)
        if fresh:
            self.writer.writeheader()
        self.trace = (self.path/'events.jsonl').open(mode, encoding='utf-8')
        self.calls = (self.path/'calls.jsonl').open(mode, encoding='utf-8')
        self.event('session', 'session_start', origin_unix_ms=self.origin_unix_ms)

    def event(self, rid, name, **extra):
        self.trace.write(json.dumps(dict(request_id=rid, event=name, session_id=self.session_id,
                                        unix_ms=time.time()*1000,
                                        monotonic_ms=(time.perf_counter()-self.origin)*1000,
                                        **extra))+'\n')
        self.trace.flush()

    def call(self, record):
        record = dict(record, session_id=self.session_id,
                      dispatch_unix_ms=self.origin_unix_ms+record['dispatch_ms'])
        self.calls.write(json.dumps(record)+'\n')
        self.calls.flush()

    def row(self, row):
        self.writer.writerow({k: (self.session_id if k=='session_id' else row.get(k, '')) for k in FIELDS})
        self.csv.flush()

    def close(self):
        for f in (self.csv,self.trace,self.calls):
            f.close()


def load_dotenv(path='.env'):
    """Minimal KEY=VALUE loader. Shell variables win. No key values are logged."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        if line.startswith('export '):
            line = line[7:].strip()
        k, v = line.split('=', 1)
        k, v = k.strip(), v.strip()
        if len(v)>=2 and v[0]==v[-1] and v[0] in ('"', "'"):
            v=v[1:-1]
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',k) and k not in os.environ:
            os.environ[k]=v


def retry_after_seconds(value, now=None):
    """HTTP Retry-After: delta seconds or an HTTP date. Never shorten a requested delay."""
    if not value:
        return None
    try:
        return max(0., float(value))
    except (ValueError, TypeError):
        from email.utils import parsedate_to_datetime
        try:
            return max(0., parsedate_to_datetime(value).timestamp()-(time.time() if now is None else now))
        except (ValueError, TypeError, OverflowError):
            return None
