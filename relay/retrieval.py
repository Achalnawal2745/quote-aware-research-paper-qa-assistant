"""Deterministic BM25 retrieval with conservative technical-query expansion.

Chunk sizes are whitespace words (not model tokens). Scores are ranking signals,
not calibrated probabilities or evidence that a passage answers the question.
"""
import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

import httpx
from pypdf import PdfReader

PAPERS = {
    '1706.03762v7': 'Attention Is All You Need',
    '2410.00037v1': 'Moshi: a speech-text foundation model for real-time dialogue',
    '2507.07955v2': 'Dynamic Chunking for End-to-End Hierarchical Sequence Modeling',
}
SETTINGS = {'small': (180, 30, 3), 'medium': (300, 50, 4), 'large': (420, 70, 5)}
EXPAND_EXTRA = 2
STOPWORDS = set('a an and are as at be been being by can could did do does for from had has have how i in into is it its may might of on or our should that the their them then there these they this those to was were what when where which who why will with would you your'.split())
# Explicit, inspectable domain synonyms. These expand terms, not factual content.
SYNONYMS = {
    'masking': 'masked mask future look ahead causal attention decoder',
    'masked': 'masking future causal attention',
    'chunking': 'chunks chunk boundary segmentation hierarchical sequence',
    'latency': 'delay response time streaming real time',
    'streaming': 'stream incremental real time latency',
    'quantization': 'quantisation codebook codec residual vector quantizer',
    'moshi': 'speech text dialogue mimi inner monologue',
    'mimi': 'audio codec speech tokenizer quantization',
    'helium': 'language model pretrained',
    'palm': 'language model prior work related work',
    'routing': 'route routing expert selection dispatch',
    'smoothing': 'smooth boundary chunk transition',
}


def normalize(text):
    return ' '.join(text.split())


def _stem(token):
    """Small conservative suffix normalizer; avoids a runtime NLP dependency."""
    if len(token) > 5 and token.endswith('ies'):
        return token[:-3] + 'y'
    if len(token) > 5 and token.endswith('ing'):
        root = token[:-3]
        return root[:-1] if len(root) > 2 and root[-1] == root[-2] else root
    if len(token) > 4 and token.endswith('ed'):
        return token[:-2]
    if len(token) > 4 and token.endswith('es'):
        return token[:-2]
    if len(token) > 3 and token.endswith('s') and not token.endswith('ss'):
        return token[:-1]
    return token


def terms(text, remove_stopwords=True):
    raw = re.findall(r'[a-z][a-z0-9]+|[0-9]+', text.lower())
    return [_stem(t) for t in raw if not (remove_stopwords and t in STOPWORDS)]


def query_analysis(question, expand=False):
    """Return query terms; expansion is deterministic and deliberately bounded."""
    base = terms(question)
    if not expand:
        return base
    extra = []
    seen = set(base)
    for word in base:
        for candidate in terms(SYNONYMS.get(word, '')):
            if candidate not in seen:
                extra.append(candidate)
                seen.add(candidate)
    return base + extra[:12]


def fetch(root=Path('data')):
    root = Path(root)
    (root / 'papers').mkdir(parents=True, exist_ok=True)
    manifest, pages = [], []
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        for pid, title in PAPERS.items():
            path = root / 'papers' / f'{pid}.pdf'
            url = f'https://arxiv.org/pdf/{pid}'
            if not path.exists():
                r = client.get(url)
                r.raise_for_status()
                if not r.content.startswith(b'%PDF'):
                    raise ValueError(f'Not PDF: {url}')
                path.write_bytes(r.content)
            reader = PdfReader(path)
            for i, page in enumerate(reader.pages, 1):
                pages.append(dict(paper=pid, title=title, page=i,
                                  text=normalize(page.extract_text() or '')))
            manifest.append(dict(paper=pid, title=title, url=url,
                                 sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                 pages=len(reader.pages)))
    (root / 'pages.json').write_text(json.dumps(pages, indent=2))
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    return manifest


class Retriever:
    def __init__(self, pages_path='data/pages.json', setting='medium', rerank=True):
        if setting not in SETTINGS:
            raise ValueError(f'Unknown retrieval setting: {setting}')
        size, overlap, self.k = SETTINGS[setting]
        self.setting = setting
        self.rerank = rerank
        self.chunks = []
        for p in json.loads(Path(pages_path).read_text(encoding='utf-8')):
            words = p['text'].split()
            for n, start in enumerate(range(0, len(words), size - overlap)):
                text = ' '.join(words[start:start + size])
                if not text:
                    continue
                self.chunks.append(dict(id=f"{p['paper']}:p{p['page']}:c{n}",
                                        paper=p['paper'], page=p['page'],
                                        title=p.get('title', PAPERS.get(p['paper'], '')),
                                        text=text))
                if start + size >= len(words):
                    break
        self.counts = [Counter(terms(c['text'])) for c in self.chunks]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.avg = sum(self.lengths) / max(len(self.lengths), 1)
        self.df = Counter(t for c in self.counts for t in c)
        self.n = len(self.chunks)

    def _bm25(self, query, tf, length):
        score = 0.0
        for term, qweight in query.items():
            f = tf[term]
            if not f:
                continue
            df = self.df[term]
            idf = math.log(1 + (self.n - df + .5) / (df + .5))
            denom = f + 1.5 * (.25 + .75 * length / max(self.avg, 1))
            score += qweight * idf * (f * 2.5 / denom)
        return score

    @staticmethod
    def _phrase_bonus(question, text):
        """Reward exact multiword concepts without making them a hard filter."""
        q = [t for t in terms(question) if len(t) > 2]
        if len(q) < 2:
            return 0.0
        haystack = terms(text)
        if not haystack:
            return 0.0
        # Adjacent query-token pairs are a cheap phrase/proximity signal.
        pairs = list(zip(q, q[1:]))
        positions = {}
        for i, token in enumerate(haystack):
            positions.setdefault(token, []).append(i)
        hits = 0
        for left, right in pairs:
            if left in positions and right in positions:
                if any(0 < b - a <= 4 for a in positions[left] for b in positions[right]):
                    hits += 1
        return min(1.5, .35 * hits)

    def search(self, question, expand=False, top_k=None):
        # Original terms carry full weight; added synonyms carry lower weight.
        original = terms(question)
        expanded = query_analysis(question, expand=expand)
        query = Counter(original)
        for token in expanded[len(original):]:
            query[token] += .45
        if not query:
            return []
        scored = []
        for i, chunk in enumerate(self.chunks):
            bm25 = self._bm25(query, self.counts[i], self.lengths[i])
            phrase = self._phrase_bonus(question, chunk['text'])
            title_terms = set(terms(chunk.get('title', '')))
            title_bonus = .25 * sum(1 for t in set(original) if t in title_terms)
            score = bm25 + phrase + title_bonus
            if score > 0:
                scored.append((score, bm25, phrase, title_bonus, i))
        # Stable ordering makes repeated runs and audits reproducible.
        scored.sort(key=lambda x: (-x[0], self.chunks[x[4]]['paper'],
                                   self.chunks[x[4]]['page'], self.chunks[x[4]]['id']))
        limit = top_k if top_k is not None else self.k + (EXPAND_EXTRA if expand else 0)
        candidates = scored[:max(limit * 4, limit)]
        selected, used = [], set()
        for item in candidates:
            chunk = self.chunks[item[4]]
            # Avoid returning adjacent overlapping chunks from the same page when
            # another strong passage is available. This is a mild diversity rule.
            page_key = (chunk['paper'], chunk['page'])
            if page_key in used and len(candidates) - len(selected) > 1:
                continue
            selected.append(item)
            used.add(page_key)
            if len(selected) >= limit:
                break
        if len(selected) < limit:
            selected_ids = {x[4] for x in selected}
            selected.extend(x for x in candidates if x[4] not in selected_ids)  # fill remaining slots
            selected = selected[:limit]
        output = []
        for score, bm25, phrase, title_bonus, i in selected:
            output.append(dict(self.chunks[i], score=round(score, 4),
                               score_bm25=round(bm25, 4),
                               score_phrase=round(phrase, 4),
                               score_title=round(title_bonus, 4)))
        return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--query')
    parser.add_argument('--setting', choices=SETTINGS, default='medium')
    parser.add_argument('--expand', action='store_true')
    parser.add_argument('--top-k', type=int)
    args = parser.parse_args()
    if args.fetch:
        print(json.dumps(fetch(), indent=2))
    if args.query:
        print(json.dumps(Retriever(setting=args.setting).search(
            args.query, expand=args.expand, top_k=args.top_k), indent=2))
