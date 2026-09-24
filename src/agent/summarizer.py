"""Context/state summarization.

Part 2 / Part 7: "as context grows, prefill cost grows with it, so late
steps are slower than early ones... aggressive context summarisation" and
"State summarizer -- essential, keeps context short = keeps prefill cheap,
non-negotiable on CPU."

Two implementations are provided behind one ``Summarizer`` protocol:

``HeuristicSummarizer`` (the default) folds the oldest facts/failures into
a bullet-joined ``state.summary`` string with **zero extra inference
calls** -- on a 2-P-core CPU budget, spending a whole model call just to
compress text is a bad trade when a deterministic heuristic does the job
for free and keeps the episode reproducible (same input state always
summarizes the same way).

``LLMSummarizer`` is included for completeness / future ablation work (the
design doc's "scaffolding vs scale" experiment, Part 16, explicitly wants
to compare cheap vs. expensive scaffolding) but costs one extra completion
call per invocation -- use only when char-budget pressure is rare, e.g. for
long L7 multi-stage episodes.
"""

from __future__ import annotations

from typing import Protocol

from src.agent.interfaces import CompletionClient
from src.agent.models import AgentState


class Summarizer(Protocol):
    def maybe_summarize(self, state: AgentState, char_budget: int) -> bool:
        """If ``state``'s rendered size would exceed ``char_budget``, fold
        the oldest facts/failures into ``state.summary`` in place and
        return True. Otherwise leave state untouched and return False."""
        ...


class HeuristicSummarizer:
    """Deterministic, zero-inference-cost summarizer (the default)."""

    def __init__(self, keep_recent_facts: int = 6, keep_recent_failures: int = 4) -> None:
        self.keep_recent_facts = keep_recent_facts
        self.keep_recent_failures = keep_recent_failures

    def maybe_summarize(self, state: AgentState, char_budget: int) -> bool:
        approx_len = self._approx_len(state)
        if approx_len <= char_budget:
            return False

        overflow_facts = state.facts[: -self.keep_recent_facts] if self.keep_recent_facts else state.facts[:]
        overflow_failures = (
            state.failures[: -self.keep_recent_failures] if self.keep_recent_failures else state.failures[:]
        )
        if not overflow_facts and not overflow_failures:
            return False  # nothing left to fold; caller must widen the budget or stop

        new_bits: list[str] = []
        if overflow_facts:
            new_bits.append(
                "facts: " + "; ".join(f.text for f in overflow_facts)
            )
        if overflow_failures:
            new_bits.append(
                "dead ends: "
                + "; ".join(f"{f.action_summary} (for '{f.hypothesis}')" for f in overflow_failures)
            )
        folded = " | ".join(new_bits)
        state.summary = (state.summary + " || " + folded).strip(" |") if state.summary else folded

        state.facts = state.facts[-self.keep_recent_facts :] if self.keep_recent_facts else []
        state.failures = state.failures[-self.keep_recent_failures :] if self.keep_recent_failures else []
        return True

    @staticmethod
    def _approx_len(state: AgentState) -> int:
        parts = [state.summary, *(f.text for f in state.facts), *(f.reason for f in state.failures)]
        return sum(len(p) for p in parts)


class LLMSummarizer:
    """Model-backed summarizer: trades one extra completion call for a
    (presumably) higher-quality compression than the heuristic. Not used
    by default -- see module docstring. Kept behind the same
    ``Summarizer`` protocol so ``AgentLoop`` can swap it in without any
    other change, for the scaffolding-vs-scale ablation (Part 16).
    """

    def __init__(self, llm: CompletionClient, keep_recent_facts: int = 6, keep_recent_failures: int = 4) -> None:
        self.llm = llm
        self.keep_recent_facts = keep_recent_facts
        self.keep_recent_failures = keep_recent_failures

    def maybe_summarize(self, state: AgentState, char_budget: int) -> bool:
        heuristic = HeuristicSummarizer(self.keep_recent_facts, self.keep_recent_failures)
        approx_len = heuristic._approx_len(state)
        if approx_len <= char_budget:
            return False

        overflow_facts = state.facts[: -self.keep_recent_facts] if self.keep_recent_facts else state.facts[:]
        overflow_failures = (
            state.failures[: -self.keep_recent_failures] if self.keep_recent_failures else state.failures[:]
        )
        if not overflow_facts and not overflow_failures:
            return False

        prompt = (
            "Summarize the following agent facts and dead ends into at most "
            "3 short bullet sentences, preserving anything a future step "
            "would need to avoid re-deriving or re-trying it:\n\n"
            "FACTS:\n" + "\n".join(f"- {f.text}" for f in overflow_facts) + "\n\n"
            "DEAD ENDS:\n" + "\n".join(f"- {f.action_summary}: {f.reason}" for f in overflow_failures)
        )
        # TODO(orchestrator wiring): this is a real inference call and
        # therefore costs tokens/wall-clock -- callers should rate-limit
        # how often LLMSummarizer runs relative to HeuristicSummarizer.
        completion = self.llm.complete(prompt, temperature=0.0, max_tokens=200)
        folded = completion.strip()
        state.summary = (state.summary + " || " + folded).strip(" |") if state.summary else folded

        state.facts = state.facts[-self.keep_recent_facts :] if self.keep_recent_facts else []
        state.failures = state.failures[-self.keep_recent_failures :] if self.keep_recent_failures else []
        return True
