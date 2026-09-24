"""Completion clients: the real llama-server HTTP client, and a fake one
for tests / no-model smoke runs.

Both satisfy ``src.agent.interfaces.CompletionClient`` structurally (one
``complete(prompt, ...) -> str`` method) -- ``AgentLoop`` never imports
this module, it only receives an object shaped like this.

Design-doc grounding: Part 3/24 settle Architecture C -- the model runs on
the HOST via llama.cpp, reached over HTTP, not inside the guest. Part 18
wants the inference stack (llama.cpp commit, threads, ctx, sampling)
pinned per run; ``LlamaServerClient`` takes exactly those knobs from
``ModelConfig``/``SamplingConfig`` rather than hardcoding them.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field
from typing import Callable

import httpx

logger = logging.getLogger(__name__)


@dataclass
class LlamaServerClient:
    """Talks to a running ``llama-server`` instance over its OpenAI-
    compatible ``/v1/chat/completions`` endpoint.

    TODO(before real runs): llama-server must be started separately (see
    scripts/build_llama_cpp.sh and config/example.yaml's `model.server_url`
    / `model.threads`) -- this client does not spawn or manage that
    process, it only talks to it. Keeping process lifecycle out of this
    class is deliberate: it lets telemetry (src.telemetry) and the agent
    loop both observe an already-running server without racing to start
    it.
    """

    base_url: str
    timeout_s: float = 120.0
    client: httpx.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.client = httpx.Client(base_url=self.base_url, timeout=self.timeout_s)

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        seed: int | None = None,
        max_tokens: int = 512,
        json_schema: dict | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if seed is not None:
            payload["seed"] = seed
        if json_schema is not None:
            # llama-server's OpenAI-compatible endpoint accepts
            # response_format with a json_schema; internally it compiles
            # the schema to a GBNF grammar and masks any token that would
            # break conformance, so the returned content is guaranteed
            # parseable (docs/DE-RISKING.md §3). We pay ~5-8% throughput
            # for it and delete the speculative parse-retry loop's reason
            # to exist against a real model.
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "agent_step", "schema": json_schema, "strict": True},
            }
        try:
            resp = self.client.post("/v1/chat/completions", json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            # TODO(retry policy): a transient connection error here should
            # probably retry with backoff before surfacing to the loop as
            # a parse failure; left as a TODO to keep this class's
            # behaviour easy to reason about for the smoke test.
            raise RuntimeError(f"llama-server request failed: {exc}") from exc
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def close(self) -> None:
        self.client.close()


@dataclass
class FakeLLMClient:
    """Deterministic, scripted completion client for tests and the
    no-model smoke run (``python -m tests.test_smoke``,
    ``run.sh --smoke``).

    Two modes:

    - ``script``: a fixed list of raw completion strings, returned in
      order (cycling if exhausted). This is what the smoke test uses --
      fully deterministic, no LLM-shaped guesswork.
    - ``responder``: an optional ``Callable[[str], str]`` that receives
      the rendered prompt and returns a completion, for tests that want
      prompt-dependent behaviour (e.g. "solve on the Nth call").
    """

    script: list[str] = field(default_factory=list)
    responder: Callable[[str], str] | None = None
    calls: list[str] = field(default_factory=list, repr=False)
    _cycle: itertools.cycle | None = field(default=None, init=False, repr=False)

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        seed: int | None = None,
        max_tokens: int = 512,
        json_schema: dict | None = None,
    ) -> str:
        # A scripted fake cannot constrain decoding; it just returns its
        # next canned line. json_schema is accepted (to satisfy the
        # CompletionClient Protocol) and ignored -- the scripts are
        # already valid JSON by construction.
        self.calls.append(prompt)
        if self.responder is not None:
            return self.responder(prompt)
        if not self.script:
            raise RuntimeError("FakeLLMClient has no script and no responder configured")
        if self._cycle is None:
            self._cycle = itertools.cycle(self.script)
        return next(self._cycle)


def build_completion_client(server_url: str | None, *, fake_script: list[str] | None = None):
    """Convenience factory used by the CLI/episode wiring: real client if
    a server URL is configured and reachable-in-intent, else the fake
    one. Kept separate from ``RunConfig`` so tests can construct either
    client directly without going through YAML.
    """
    if fake_script is not None:
        return FakeLLMClient(script=fake_script)
    if not server_url:
        raise ValueError("no llama-server URL configured and no fake_script provided")
    return LlamaServerClient(base_url=server_url)
