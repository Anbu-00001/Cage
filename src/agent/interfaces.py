"""Structural interfaces the agent loop depends on, but does not implement.

This is what keeps ``src/agent`` a pure, host-and-transport-agnostic "brain"
package: it never imports ``src.orchestrator``. Instead it defines the two
capabilities it needs as ``typing.Protocol``s, and the orchestrator package
supplies concrete classes that satisfy them structurally (duck typing, no
inheritance required):

- ``CompletionClient``  -- src/orchestrator/llm_client.py
    ``LlamaServerClient`` (real, HTTP via httpx) and ``FakeLLMClient``
    (scripted, for tests / no-model smoke runs).
- ``ActionChannel``     -- src/orchestrator/channel.py
    ``SSHChannel`` / ``VsockChannel`` (stubbed transports to the guest) and
    ``LocalMockChannel`` (in-memory, for tests).

Why this split matters for this project specifically: the design docs are
explicit that the model and the orchestrator live on the host and the VM is
reached only through a narrow, logged channel (Architecture C). Encoding
that as two Protocols means ``AgentLoop`` can be constructed and unit
tested with zero model weights and zero QEMU process running -- which is
exactly what ``tests/test_smoke.py`` does.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.agent.models import ToolResult


@runtime_checkable
class ActionChannel(Protocol):
    """Whatever transport carries one action to the cage and returns its
    result. Implementations MUST NOT raise on a failed *guest-side*
    command (non-zero exit, timeout, etc.) -- that is a normal
    ``ToolResult(ok=False, ...)``. Raising is reserved for transport-level
    failures (channel not connected, guest unreachable)."""

    def execute(self, command: str, timeout_s: float = 10.0) -> ToolResult:
        """Run ``command`` in the cage and return a bounded, timed result."""
        ...


@runtime_checkable
class CompletionClient(Protocol):
    """Whatever can turn a prompt into a raw text completion.

    Deliberately the narrowest possible surface (one method, plain string
    in and out) so swapping the real llama-server HTTP client for a
    scripted fake in tests requires no adapter layer.
    """

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        seed: int | None = None,
        max_tokens: int = 512,
        json_schema: dict | None = None,
    ) -> str:
        """Return the model's raw completion text for ``prompt``.

        ``json_schema`` (optional): a JSON Schema the completion MUST
        conform to. A real llama.cpp-backed client turns this into a GBNF
        grammar and *constrained-decodes*, so malformed JSON is never
        emitted in the first place (see docs/DE-RISKING.md §3) -- this is
        what lets the agent loop treat tool calls as reliable rather than
        parse-retrying. Clients that cannot constrain output (e.g. the
        scripted fake) accept and ignore it.
        """
        ...
