"""Structured memory + failure memory.

Part 7: "Structured memory / scratchpad -- essential, compensates for a
small model; external memory > long context" and "Failure memory --
essential, stops the loop retrying the same dead end, the #1 small-model
failure." This module is the concrete implementation of both, wrapping an
``AgentState`` and providing the operations the loop needs each step:
record a fact, record (and de-duplicate) a failure, check whether a
proposed action is a known dead end, and render the state compactly for
the prompt.
"""

from __future__ import annotations

from src.agent.models import (
    AgentState,
    Fact,
    FailureRecord,
    Goal,
    ToolCall,
)


class StructuredMemory:
    """Owns one episode's ``AgentState`` and enforces the failure-memory
    invariant: the same (hypothesis, action) pair is never silently
    retried."""

    def __init__(self, goal: Goal) -> None:
        self.state = AgentState(goal=goal)
        self._failure_signatures: set[str] = set()
        # Signatures of actions actually EXECUTED (regardless of outcome), to
        # catch *unproductive repeats* -- a small model re-issuing a command
        # that already succeeded but taught it nothing (observed live: a 0.5B
        # looping on `ls` after it had already found the target file). This is
        # distinct from _failure_signatures, which only tracks dead ends.
        self._executed_action_sigs: set[str] = set()

    # -- writes -----------------------------------------------------------

    def add_fact(self, text: str, source: str) -> Fact:
        fact = Fact(step=self.state.step, text=text, source=source)
        self.state.facts.append(fact)
        return fact

    def add_failure(self, hypothesis: str, action_summary: str, reason: str) -> FailureRecord | None:
        """Record a dead end. Returns ``None`` (and records nothing new)
        if this exact (hypothesis, action) pair is already known -- the
        signature set is the de-dup mechanism, so a small model re-issuing
        the same wrong call doesn't bloat the transcript with duplicates."""
        record = FailureRecord(
            step=self.state.step,
            hypothesis=hypothesis,
            action_summary=action_summary,
            reason=reason,
        )
        sig = record.signature()
        if sig in self._failure_signatures:
            return None
        self._failure_signatures.add(sig)
        self.state.failures.append(record)
        return record

    def add_open_questions(self, questions: list[str]) -> None:
        for q in questions:
            q = q.strip()
            if q and q not in self.state.open_questions:
                self.state.open_questions.append(q)

    def set_strategy_note(self, note: str) -> None:
        self.state.strategy_note = note

    def advance_step(self) -> None:
        self.state.step += 1

    # -- reads --------------------------------------------------------

    def signature_of(self, hypothesis: str, call: ToolCall) -> str:
        return f"{hypothesis.strip().lower()}::{call.summary().strip().lower()}"

    def has_tried(self, hypothesis: str, call: ToolCall) -> bool:
        """True if this exact (hypothesis, action) pair already failed."""
        return self.signature_of(hypothesis, call) in self._failure_signatures

    def action_signature(self, call: ToolCall) -> str:
        """Signature of an ACTION alone (tool + meaningful args), ignoring
        ``timeout_s`` and the hypothesis -- so the same command counts as the
        same action however the model narrates or times it."""
        args = {k: v for k, v in call.args.items() if k != "timeout_s"}
        args_repr = ", ".join(f"{k}={v!r}" for k, v in sorted(args.items()))
        return f"{call.tool}({args_repr})".strip().lower()

    def record_execution(self, call: ToolCall) -> None:
        """Note that an action actually ran (called after dispatch)."""
        self._executed_action_sigs.add(self.action_signature(call))

    def is_unproductive_repeat(self, call: ToolCall) -> bool:
        """True if this exact action already executed once. Terminal actions
        (submit_flag) are exempt -- re-submitting is handled by goal scoring,
        not treated as an exploration loop."""
        if call.tool == "submit_flag":
            return False
        return self.action_signature(call) in self._executed_action_sigs

    def render(self, max_facts: int = 12, max_failures: int = 8) -> str:
        """Compact, prompt-ready text rendering of the current belief
        state. Older entries are expected to already have been folded into
        ``state.summary`` by the summarizer before this is called (see
        summarizer.py) -- this method only bounds *this* render, it does
        not itself discard state."""
        s = self.state
        lines: list[str] = []
        if s.summary:
            lines.append(f"SUMMARY OF EARLIER STEPS:\n{s.summary}")
        lines.append(f"STEP: {s.step}")
        if s.strategy_note:
            lines.append(f"CURRENT STRATEGY: {s.strategy_note}")
        recent_facts = s.facts[-max_facts:]
        if recent_facts:
            lines.append("FACTS:")
            lines.extend(f"  - [{f.step}] {f.text} (via {f.source})" for f in recent_facts)
        recent_failures = s.failures[-max_failures:]
        if recent_failures:
            lines.append("KNOWN DEAD ENDS (do not repeat these):")
            lines.extend(
                f"  - tried {f.action_summary} for hypothesis '{f.hypothesis}': failed ({f.reason})"
                for f in recent_failures
            )
        if s.open_questions:
            lines.append("OPEN QUESTIONS:")
            lines.extend(f"  - {q}" for q in s.open_questions)
        return "\n".join(lines)

    def approx_char_len(self) -> int:
        """Cheap proxy for "how much context does this state cost". A real
        tokenizer would be more accurate; on CPU, a char-count heuristic
        (~4 chars/token for English) is free and good enough to trigger
        summarization before prefill cost actually spikes (Part 2)."""
        return len(self.render(max_facts=10_000, max_failures=10_000))
