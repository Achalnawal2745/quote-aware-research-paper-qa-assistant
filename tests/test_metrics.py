import asyncio
import json
import time

import httpx

from relay.adapter import Adapter
from relay.budget import Budget, BudgetExceeded
from relay.common import Artifacts
from relay.pipeline import Pipeline


class OneWaitBudget:
    """Budget test double that forces one local scheduling wait."""

    def __init__(self):
        self.calls = 0

    async def reserve(self, tokens):
        self.calls += 1
        if self.calls == 1:
            raise BudgetExceeded("test token-window wait", wait=0.02)
        return {"tokens": tokens}

    async def observe(self, *args, **kwargs):
        return None

    async def reconcile(self, *args, **kwargs):
        return None


class OneChunkRetriever:
    def search(self, question, expand=False):
        return [{
            "id": "paper:p1:c0",
            "text": "The model uses a masked attention mechanism to process tokens."
        }]


class DelayedFirstTokenAdapter:
    def __init__(self):
        self.budget = Budget(tpm=100000)

    async def complete(self, messages, state, purpose="draft", max_tokens=None):
        # Simulate first visible content arriving, then later completion.
        state["draft_first_at"] = time.perf_counter()
        await asyncio.sleep(0.04)
        return json.dumps({
            "refused": False,
            "claims": [{
                "text": "The model uses masked attention.",
                "chunk_id": "paper:p1:c0",
                "quote": "The model uses a masked attention mechanism to process tokens."
            }]
        })


def test_budget_wait_is_not_counted_as_queue_wait(tmp_path):
    async def run():
        artifacts = Artifacts(tmp_path)
        budget = OneWaitBudget()
        adapter = Adapter(
            "https://example.test/openai/v1/",
            "test-key",
            "test-model",
            budget,
            artifacts,
            max_retries=0,
        )

        def respond(request):
            return httpx.Response(
                200,
                content=(
                    'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
                    'data: {"choices":[],"usage":{"prompt_tokens":2,"completion_tokens":1}}\n\n'
                    'data: [DONE]\n\n'
                ),
                headers={"content-type": "text/event-stream"},
            )

        await adapter.client.aclose()
        adapter.client = httpx.AsyncClient(
            base_url="https://example.test/openai/v1/",
            transport=httpx.MockTransport(respond),
        )

        state = {
            "request_id": "budget-wait-test",
            "deadline": time.perf_counter() + 3,
            "model_calls": 0,
            "working_ms": 0.0,
            "queue_wait_ms": 0.0,
            "budget_wait_ms": 0.0,
            "retry_wait_ms": 0.0,
            "tokens_in": 0,
            "tokens_out": 0,
            "usage_complete": True,
            "rate_limit_hits": 0,
            "retries": 0,
        }

        answer = await adapter.complete(
            [{"role": "user", "content": "hello"}],
            state,
        )

        assert answer == "hello"
        assert state["budget_wait_ms"] >= 15
        assert state["queue_wait_ms"] == 0

        await adapter.close()
        artifacts.close()

    asyncio.run(run())


def test_first_token_and_answer_release_are_separate(tmp_path):
    async def run():
        artifacts = Artifacts(tmp_path)
        pipeline = Pipeline(
            OneChunkRetriever(),
            DelayedFirstTokenAdapter(),
            artifacts,
            concurrency=1,
            max_queue=1,
            deadline_s=2,
            verifier="off",
        )

        result = await pipeline.request(
            "What does the model use?",
            "metrics-test",
            "stand-in",
            "small",
        )

        assert result["status"] == "ok"
        assert result["first_token_ms"] > 0
        assert result["answer_release_ms"] > result["first_token_ms"]
        assert result["total_ms"] >= result["answer_release_ms"]
        assert result["validation_hold_ms"] >= 0

        artifacts.close()

    asyncio.run(run())
