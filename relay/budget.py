"""Single-process rolling-window reservations; persistent day spend across runs.
Provider headers can tighten local availability. No guessed UTC reset.
"""
import asyncio
import json
import time
from pathlib import Path
from .common import parse_duration, retry_after_seconds

class BudgetExceeded(Exception):
    def __init__(self, reason, wait=0, daily=False):
        self.reason, self.wait, self.daily = reason, wait, daily
        super().__init__(reason)

class Budget:
    def __init__(self, rpm=30, tpm=8000, rpd=1000, tpd=200000, ledger=None, observe_headers=True):
        self.observe_headers=observe_headers
        self.rpm,self.tpm,self.rpd,self.tpd = rpm,tpm,rpd,tpd
        self.window=[]
        self.day_requests=0
        self.day_tokens=0
        self.blocked_until=0.
        self.daily_block=False
        self.daily_block_kind=None
        self.lock=asyncio.Lock()
        self.ledger=Path(ledger) if ledger else None
        self.token_remaining=None
        self.token_reset=0.
        self.request_reset=None
        if self.ledger and self.ledger.exists():
            d=json.loads(self.ledger.read_text())
            self.day_requests=d['day_requests']; self.day_tokens=d['day_tokens']
            self.daily_block=d.get('daily_block',False)
            self.daily_block_kind=d.get('daily_block_kind')
            self.request_reset=d.get('request_reset')

    def save(self):
        if self.ledger:
            self.ledger.parent.mkdir(parents=True,exist_ok=True)
            temp=self.ledger.with_suffix('.tmp')
            temp.write_text(json.dumps(dict(day_requests=self.day_requests,day_tokens=self.day_tokens,
                                            daily_block=self.daily_block,daily_block_kind=self.daily_block_kind,request_reset=self.request_reset)))
            temp.replace(self.ledger)

    def daily_exhausted(self):
        if self.request_reset and time.time()>=self.request_reset:
            self.day_requests=0
            if self.daily_block_kind=='requests':
                self.daily_block=False; self.daily_block_kind=None
            self.request_reset=None
            self.save()
        return self.daily_block or self.day_requests>=self.rpd or self.day_tokens>=self.tpd

    async def reserve(self, tokens):
        async with self.lock:
            now=time.time()
            # Only clear daily spend after an observed request-reset time, not local midnight.
            if self.request_reset and now>=self.request_reset:
                self.day_requests=0
                if self.daily_block_kind=='requests':
                    self.daily_block=False; self.daily_block_kind=None
                self.request_reset=None
            self.window=[x for x in self.window if now-x['at']<60]
            if self.daily_block or self.day_requests>=self.rpd or self.day_tokens+tokens>self.tpd:
                raise BudgetExceeded('daily budget unavailable',daily=True)
            if tokens>self.tpm:
                raise BudgetExceeded('one prompt reservation exceeds TPM')
            if now<self.blocked_until:
                raise BudgetExceeded('provider cooldown',self.blocked_until-now)
            if self.token_remaining is not None and now<self.token_reset and tokens>self.token_remaining:
                raise BudgetExceeded('provider token availability',self.token_reset-now)
            if len(self.window)>=self.rpm or sum(x['tokens'] for x in self.window)+tokens>self.tpm:
                wait=max(.01,60-(now-self.window[0]['at'])) if self.window else 60
                raise BudgetExceeded('local minute budget',wait)
            ticket={'at':now,'tokens':tokens}
            self.window.append(ticket); self.day_requests+=1; self.day_tokens+=tokens
            if self.token_remaining is not None and now<self.token_reset:
                self.token_remaining=max(0,self.token_remaining-tokens)
            self.save()
            return ticket

    async def reconcile(self,ticket,actual):
        async with self.lock:
            delta=actual-ticket['tokens']
            ticket['tokens']=actual; self.day_tokens+=delta
            self.save()

    async def observe(self,headers,status,body=''):
        if not self.observe_headers:
            return
        async with self.lock:
            now=time.time()
            # Documented request headers refer to RPD, token headers to TPM.
            for key,attr in [('x-ratelimit-limit-requests','rpd'),('x-ratelimit-limit-tokens','tpm')]:
                if headers.get(key):
                    setattr(self,attr,min(getattr(self,attr),int(float(headers[key]))))
            if headers.get('x-ratelimit-remaining-tokens'):
                self.token_remaining=int(float(headers['x-ratelimit-remaining-tokens']))
                reset=parse_duration(headers.get('x-ratelimit-reset-tokens'))
                self.token_reset=now+(reset if reset is not None else 60)
            rem=headers.get('x-ratelimit-remaining-requests')
            reset=parse_duration(headers.get('x-ratelimit-reset-requests'))
            if reset is not None:
                self.request_reset=now+reset
            if rem is not None:
                self.day_requests=max(self.day_requests,self.rpd-int(float(rem)))
            if status==429:
                delay=retry_after_seconds(headers.get('retry-after')) or 1
                self.blocked_until=max(self.blocked_until,now+delay)
                lower=body.lower()
                if (rem is not None and float(rem)<=0) or any(t in lower for t in ['tokens per day','requests per day','daily quota']):
                    self.daily_block=True
                    self.daily_block_kind=('tokens' if 'tokens per day' in lower else
                                           'requests' if ((rem is not None and float(rem)<=0) or 'requests per day' in lower) else 'unknown')
            self.save()
