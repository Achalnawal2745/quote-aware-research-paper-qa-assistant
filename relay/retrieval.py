
"""Deterministic BM25 retrieval for the paper-QA project.

Chunk sizes are measured in whitespace-delimited words, not model tokens.
The first-pass search uses only the user's original query. Optional lexical
expansion is applied only when expand=True.
"""

import argparse
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

import httpx
from pypdf import PdfReader


PAPERS = {
    "1706.03762v7": "Attention Is All You Need",
    "2410.00037v1": "Moshi: a speech-text foundation model for real-time dialogue",
    "2507.07955v2": "Dynamic Chunking for End-to-End Hierarchical Sequence Modeling",
}

EXPAND_EXTRA = 2

SETTINGS = {
    "small": (180, 30, 3),
    "medium": (300, 50, 4),
    "large": (420, 70, 5),
}

QUERY_EXPANSIONS = (
    (
        (
            "subsequent", "future position", "future token",
            "decoder masking", "masked attention",
            "causal mask", "attend to future"
        ),
        "masking masked attention decoder future subsequent positions causal"
    ),
    (
        (
            "dot-product", "dot product", "key dimension",
            "square root", "softmax gradient", "scaled attention"
        ),
        "scaling scaled attention square root dk key dimension softmax gradients"
    ),
    (
        (
            "positional encoding", "positional encodings",
            "position information", "sequence order", "order information"
        ),
        "positional encodings position representations sequence order recurrence convolution"
    ),
    (
        ("label smoothing", "label-smoothing"),
        "label smoothing perplexity accuracy bleu 0.1"
    ),
    (
        (
            "latency", "real-time", "real time",
            "response delay", "first token"
        ),
        "latency delay streaming real time theoretical practical 160ms 200ms"
    ),
    (
        (
            "inner monologue", "time-aligned text",
            "text prefix", "speech tokens"
        ),
        "inner monologue time aligned text prefix audio tokens linguistic quality"
    ),
    (
        (
            "mimi", "audio codec",
            "vector quantization", "discrete audio tokens"
        ),
        "mimi neural audio codec discrete tokens residual vector quantization"
    ),
    (
        ("frame rate", "frames per second", "12.5 hz"),
        "frame rate frames 12.5 hz training hyperparameters sample rate"
    ),
    (
        ("dynamic chunk", "chunk boundary", "chunking", "boundary prediction"),
        "dynamic chunking chunk boundary boundaries hierarchical sequence"
    ),
    (
        (
            "routing", "smoothing",
            "boundary probability", "cosine similarity"
        ),
        "routing smoothing cosine similarity adjacent encoder outputs boundary probability"
    ),
    (
        ("palm", "helium", "pretrained", "pre-trained", "from scratch"),
        "palm audiopalm helium pretrained initialization from scratch related work"
    ),
    (
        (
            "attention head", "attention heads",
            "multi-head", "number of heads", "7b", "parameters"
        ),
        "attention heads multi head h 8 helium 7b parameters text language model"
    ),
)


def terms(text):
    """Return normalized alphanumeric terms."""
    normalized = unicodedata.normalize(
        "NFKC", str(text or "")
    ).casefold()

    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", normalized)


def normalize(text):
    """Collapse multiple whitespace characters."""
    return " ".join(str(text or "").split())


def query_analysis(question):
    """Expand a query using vocabulary from the research papers."""
    original = normalize(question)
    lowered = original.casefold()

    additions = []

    for triggers, expansion in QUERY_EXPANSIONS:
        if any(trigger in lowered for trigger in triggers):
            additions.append(expansion)

    if not additions:
        return original

    return original + " " + " ".join(additions)


def fetch(root=Path("data")):
    """Download missing PDFs and extract their page text."""
    root = Path(root)
    papers_dir = root / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    pages = []

    with httpx.Client(
        follow_redirects=True,
        timeout=120
    ) as client:

        for paper_id, title in PAPERS.items():

            pdf_path = papers_dir / f"{paper_id}.pdf"
            url = f"https://arxiv.org/pdf/{paper_id}"

            if not pdf_path.exists():

                response = client.get(url)
                response.raise_for_status()

                if not response.content.startswith(b"%PDF"):
                    raise ValueError(
                        f"Downloaded content is not a PDF: {url}"
                    )

                pdf_path.write_bytes(response.content)

            reader = PdfReader(pdf_path)

            for page_number, page in enumerate(
                reader.pages, start=1
            ):

                page_text = normalize(
                    page.extract_text() or ""
                )

                pages.append({
                    "paper": paper_id,
                    "title": title,
                    "page": page_number,
                    "text": page_text,
                })

            manifest.append({
                "paper": paper_id,
                "title": title,
                "url": url,
                "sha256": hashlib.sha256(
                    pdf_path.read_bytes()
                ).hexdigest(),
                "pages": len(reader.pages),
            })

    (root / "pages.json").write_text(
        json.dumps(
            pages,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    (root / "manifest.json").write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    return manifest


class Retriever:
    """BM25 retriever with optional lexical query expansion."""

    def __init__(
        self,
        pages_path="data/pages.json",
        setting="medium"
    ):

        if setting not in SETTINGS:
            raise ValueError(
                f"Unknown retrieval setting {setting!r}; "
                f"choose one of {', '.join(SETTINGS)}"
            )

        size, overlap, self.k = SETTINGS[setting]

        if size <= 0 or overlap < 0 or overlap >= size:
            raise ValueError(
                "Chunk size must be positive and overlap "
                "smaller than size"
            )

        self.setting = setting
        self.chunk_size = size
        self.overlap = overlap
        self.chunks = []

        source_path = Path(pages_path)

        page_records = json.loads(
            source_path.read_text(encoding="utf-8")
        )

        for page_record in page_records:

            words = normalize(
                page_record.get("text", "")
            ).split()

            step = size - overlap

            for chunk_number, start in enumerate(
                range(0, len(words), step)
            ):

                chunk_text = " ".join(
                    words[start:start + size]
                )

                if not chunk_text:
                    continue

                self.chunks.append({
                    "id": (
                        f"{page_record['paper']}:"
                        f"p{page_record['page']}:c{chunk_number}"
                    ),
                    "paper": page_record["paper"],
                    "page": page_record["page"],
                    "text": chunk_text,
                })

                if start + size >= len(words):
                    break

        self.counts = [
            Counter(terms(chunk["text"]))
            for chunk in self.chunks
        ]

        self.lengths = [
            sum(count.values())
            for count in self.counts
        ]

        self.avg_length = (
            sum(self.lengths) / len(self.lengths)
            if self.lengths else 0.0
        )

        self.document_frequency = Counter(
            term
            for count in self.counts
            for term in count.keys()
        )

    def _score(self, query_terms):
        """Calculate BM25 scores for all chunks."""

        number_of_chunks = len(self.chunks)

        if not number_of_chunks or not query_terms:
            return []

        scored = []

        k1 = 1.5
        b = 0.75

        for index, term_counts in enumerate(self.counts):

            score = 0.0
            document_length = self.lengths[index]

            length_normalizer = (
                1.0 - b
                + b * document_length / max(self.avg_length, 1.0)
            )

            for term in query_terms:

                frequency = term_counts.get(term, 0)

                if frequency == 0:
                    continue

                document_frequency = (
                    self.document_frequency[term]
                )

                inverse_document_frequency = math.log(
                    1.0
                    + (
                        number_of_chunks
                        - document_frequency
                        + 0.5
                    ) / (document_frequency + 0.5)
                )

                denominator = (
                    frequency + k1 * length_normalizer
                )

                score += (
                    inverse_document_frequency
                    * frequency
                    * (k1 + 1.0)
                    / denominator
                )

            if score > 0:

                scored.append((
                    score,
                    self.chunks[index]["id"],
                    index
                ))

        scored.sort(
            key=lambda item: (-item[0], item[1])
        )

        return scored

    def search(self, question, expand=False):
        """Retrieve relevant evidence chunks."""

        if not isinstance(question, str) or not question.strip():
            return []

        if expand:
            query = query_analysis(question)
        else:
            query = question

        query_terms = set(terms(query))

        limit = self.k + (
            EXPAND_EXTRA if expand else 0
        )

        ranked = self._score(query_terms)

        results = []
        seen_ids = set()

        for score, chunk_id, index in ranked:

            if chunk_id in seen_ids:
                continue

            seen_ids.add(chunk_id)

            result = dict(self.chunks[index])
            result["score"] = round(score, 4)

            results.append(result)

            if len(results) >= limit:
                break

        return results


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--fetch",
        action="store_true"
    )

    parser.add_argument(
        "--query"
    )

    parser.add_argument(
        "--setting",
        choices=SETTINGS,
        default="medium"
    )

    parser.add_argument(
        "--expand",
        action="store_true"
    )

    args = parser.parse_args()

    if args.fetch:

        print(json.dumps(
            fetch(),
            indent=2,
            ensure_ascii=False
        ))

    if args.query:

        retriever = Retriever(
            setting=args.setting
        )

        print(json.dumps(
            retriever.search(
                args.query,
                expand=args.expand
            ),
            indent=2,
            ensure_ascii=False
        ))
