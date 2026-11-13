
import asyncio
import json
import random
import time

import httpx

from .budget import BudgetExceeded
from .common import estimate_tokens, retry_after_seconds


class CallError(Exception):
    def __init__(self, message, status="error", source=""):
        super().__init__(message)
        self.status = status
        self.source = source


class Adapter:

    def __init__(
        self,
        base_url,
        key,
        model,
        budget,
        artifacts,
        max_retries=1,
        seed=7,
        max_tokens=700,
        reasoning_effort=None
    ):
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            headers={
                "Authorization": f"Bearer {key}"
            },
            timeout=None
        )

        self.model = model
        self.budget = budget
        self.a = artifacts

        self.max_retries = max_retries
        self.rng = random.Random(seed)

        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort

    async def close(self):
        await self.client.aclose()

    async def complete(
        self,
        messages,
        state,
        purpose="draft",
        max_tokens=None
    ):
        max_tokens = (
            self.max_tokens
            if max_tokens is None
            else max_tokens
        )

        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

        rid = state["request_id"]

        reservation = (
            estimate_tokens(json.dumps(messages))
            + max_tokens
        )

        for attempt in range(self.max_retries + 1):

            # Local quota waits are scheduling, not API retries.
            while True:
                try:
                    ticket = await self.budget.reserve(
                        reservation
                    )
                    break

                except BudgetExceeded as e:

                    if e.daily or not e.wait:
                        raise CallError(
                            e.reason,
                            "rate_limited",
                            "local_daily"
                            if e.daily
                            else "local_budget"
                        )

                    remaining = (
                        state["deadline"]
                        - time.perf_counter()
                    )

                    if e.wait >= remaining:
                        raise CallError(
                            e.reason
                            + "; cannot recover before deadline",
                            "rate_limited",
                            "local_budget"
                        )

                    t = time.perf_counter()

                    self.a.event(
                        rid,
                        "budget_wait_start",
                        seconds=e.wait,
                        reason=e.reason
                    )

                    try:
                        await asyncio.sleep(e.wait)

                    finally:
                        state["budget_wait_ms"] = (
                            state.get("budget_wait_ms", 0.0)
                            + (time.perf_counter() - t) * 1000
                        )

                        self.a.event(
                            rid,
                            "budget_wait_end"
                        )

            started = time.perf_counter()

            record = dict(
                request_id=rid,
                purpose=purpose,
                attempt=attempt,
                max_tokens=max_tokens,
                reasoning_effort=self.reasoning_effort,
                dispatch_ms=(
                    started - self.a.origin
                ) * 1000,
                model=self.model,
                messages=messages,
                reservation_tokens=reservation,
                headers={},
                http_status=None,
                provider_ttft_ms=None,
                usage=None,
                response="",
                error=None
            )

            state["model_calls"] += 1

            self.a.event(
                rid,
                "model_start",
                purpose=purpose,
                attempt=attempt
            )

            text = ""
            first = None
            first_any = None
            finish = None
            usage = None
            retry_wait = None
            retryable = False

            try:
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0,
                    "max_completion_tokens": max_tokens,
                    "stream": True,
                    "stream_options": {
                        "include_usage": True
                    }
                }

                if self.reasoning_effort:
                    payload["reasoning_effort"] = (
                        self.reasoning_effort
                    )

                async with self.client.stream(
                    "POST",
                    "chat/completions",
                    json=payload
                ) as response:

                    record["http_status"] = (
                        response.status_code
                    )

                    record["headers"] = {
                        k: v
                        for k, v in response.headers.items()
                        if (
                            k.startswith("x-ratelimit")
                            or k == "retry-after"
                        )
                    }

                    if response.status_code >= 400:

                        body = (
                            await response.aread()
                        ).decode(errors="replace")

                        record["error"] = body

                        await self.budget.observe(
                            response.headers,
                            response.status_code,
                            body
                        )

                        if response.status_code == 429:

                            state["rate_limit_hits"] += 1

                            retryable = (
                                not self.budget.daily_block
                            )

                            retry_wait = (
                                retry_after_seconds(
                                    response.headers.get(
                                        "retry-after"
                                    )
                                )
                                or 1
                            )

                            raise CallError(
                                body,
                                "rate_limited",
                                "provider_429"
                            )

                        retryable = (
                            response.status_code
                            in (408, 500, 502, 503, 504)
                        )

                        raise CallError(
                            f"HTTP {response.status_code}: {body}"
                        )

                    await self.budget.observe(
                        response.headers,
                        response.status_code
                    )

                    done = False

                    async for line in response.aiter_lines():

                        if not line.startswith("data:"):
                            continue

                        data = line[5:].strip()

                        if data == "[DONE]":
                            done = True
                            break

                        chunk = json.loads(data)

                        # Support OpenAI and Groq usage formats.
                        groq_data = chunk.get("x_groq") or {}

                        usage = (
                            chunk.get("usage")
                            or groq_data.get("usage")
                            or usage
                        )

                        choices = chunk.get("choices", [])

                        delta = (
                            choices[0].get("delta", {})
                            if choices
                            else {}
                        )

                        content = delta.get("content") or ""

                        reasoning = (
                            delta.get("reasoning")
                            or delta.get("reasoning_content")
                            or ""
                        )

                        if choices and choices[0].get(
                            "finish_reason"
                        ):
                            finish = choices[0][
                                "finish_reason"
                            ]

                        # First provider output, including reasoning.
                        if (
                            content or reasoning
                        ) and first_any is None:

                            first_any = time.perf_counter()

                            record["provider_first_any_ms"] = (
                                first_any - started
                            ) * 1000

                            if (
                                purpose == "draft"
                                and state.get(
                                    "provider_first_any_ms"
                                ) in (None, "")
                            ):
                                state["provider_first_any_ms"] = (
                                    record[
                                        "provider_first_any_ms"
                                    ]
                                )

                        # First user-visible content token.
                        if content:

                            if first is None:

                                first = time.perf_counter()

                                record["provider_ttft_ms"] = (
                                    first - started
                                ) * 1000

                                if (
                                    purpose == "draft"
                                    and not state.get(
                                        "draft_first_at"
                                    )
                                ):
                                    state["draft_first_at"] = first

                                    state["provider_ttft_ms"] = (
                                        record[
                                            "provider_ttft_ms"
                                        ]
                                    )

                                self.a.event(
                                    rid,
                                    "provider_first_token",
                                    purpose=purpose,
                                    attempt=attempt
                                )

                            text += content

                    if not done:
                        retryable = True

                        raise CallError(
                            "stream ended without [DONE]"
                        )

                    if finish == "length":
                        raise CallError(
                            f"output truncated at max_tokens={max_tokens}; "
                            "raise --max-tokens or lower --reasoning-effort"
                        )

                    if not text:
                        raise CallError(
                            "empty content stream; reasoning may "
                            "have consumed the output cap"
                        )

                return text

            except (
                httpx.TransportError,
                json.JSONDecodeError
            ) as e:

                retryable = True
                error = CallError(str(e))
                record["error"] = str(e)

            except CallError as e:

                error = e
                record["error"] = str(e)

            except asyncio.CancelledError:

                record["error"] = (
                    "cancelled at user deadline; "
                    "provider may continue working"
                )

                raise

            finally:

                end = time.perf_counter()

                record["response"] = text
                record["usage"] = usage
                record["finish_reason"] = finish

                record["total_ms"] = (
                    end - started
                ) * 1000

                state["working_ms"] += (
                    record["total_ms"]
                )

                # Reconcile only when actual usage is available.
                if (
                    usage
                    and "prompt_tokens" in usage
                    and "completion_tokens" in usage
                ):

                    tin = usage["prompt_tokens"]
                    tout = usage["completion_tokens"]

                    state["tokens_in"] += tin
                    state["tokens_out"] += tout

                    await self.budget.reconcile(
                        ticket,
                        tin + tout
                    )

                else:

                    # Keep reservation for safety.
                    # Never report estimates as measured usage.
                    state["usage_complete"] = False

                self.a.call(record)

                self.a.event(
                    rid,
                    "model_end",
                    purpose=purpose,
                    attempt=attempt,
                    duration_ms=record["total_ms"],
                    error=record["error"]
                )

            if (
                not retryable
                or attempt >= self.max_retries
            ):
                raise error

            delay = (
                max(
                    retry_wait or 0,
                    0.25 * (2 ** attempt)
                )
                + self.rng.uniform(0, 0.15)
            )

            if (
                self.budget.daily_block
                or time.perf_counter() + delay
                >= state["deadline"]
            ):
                raise error

            state["retries"] += 1

            self.a.event(
                rid,
                "retry_wait_start",
                seconds=delay
            )

            t = time.perf_counter()

            try:
                await asyncio.sleep(delay)

            finally:
                state["retry_wait_ms"] += (
                    time.perf_counter() - t
                ) * 1000

                self.a.event(
                    rid,
                    "retry_wait_end"
                )
