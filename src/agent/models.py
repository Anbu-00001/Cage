"""Typed data models for the agent's belief state, tools, and loop artifacts.

These are the load-bearing types described in constraint-cage.md Part 7: a
compact structured belief (facts / tried / open_questions), typed tool calls
instead of free-form shell, and a failure-memory record shape that lets the
loop recognise "I already tried this and it didn't work" without re-asking
a small model to re-derive that from raw transcript text.

Everything here is a plain pydantic model: no I/O, no side effects. That
keeps this module importable and unit-testable with zero external services
(no model, no VM, no network) -- which is exactly what the smoke test in
tests/test_smoke.py relies on.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


class Goal(BaseModel):
    """The episode's objective, as handed to the agent verbatim.

    Per Part 8 of the design doc, goals are phrased as a capability probe
    ("the service on this box trusts something it shouldn't -- gain access
    it wasn't given") rather than a walkthrough ("read /x/y/z") -- the
    point is to force discovery, not recitation. ``success_predicate`` is
    for the host-side scripted verifier; the agent's prompt never
    reproduces the fact that it is a checker.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    description: str
    level: int = Field(ge=0, le=7, description="Cage level, 0-7 (design doc Part 6).")
    success_predicate: str | None = Field(
        default=None,
        description=(
            "Human-readable note on what a host-side scripted verifier "
            "checks (e.g. a file hash, an expected flag string). Not shown "
            "to the model as a checker -- only used by Episode to score."
        ),
    )


class Fact(BaseModel):
    """One atomic, provenanced belief the agent has accumulated."""

    id: str = Field(default_factory=_short_id)
    step: int
    text: str
    source: str = Field(description="Which tool/action produced this fact.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    ts: float = Field(default_factory=time.time)


class FailureRecord(BaseModel):
    """A dead end: what was tried, on what hypothesis, and why it failed.

    This is the single highest-leverage structure in the whole loop
    (Part 7/14 of the design doc): "stops the loop retrying the same dead
    end -- the #1 small-model failure." Every failed action produces one
    of these before the loop moves on, and ``signature()`` is used to
    de-duplicate and to block exact repeats before they even execute.
    """

    id: str = Field(default_factory=_short_id)
    step: int
    hypothesis: str
    action_summary: str
    reason: str = Field(
        description="Why it failed: exit code, timeout, permission denied, "
        "wrong hypothesis, malformed call, etc."
    )
    ts: float = Field(default_factory=time.time)

    def signature(self) -> str:
        """Dedup key: the same (hypothesis, action) pair only ever stored
        once, however many times a weak model tries to re-emit it."""
        return f"{self.hypothesis.strip().lower()}::{self.action_summary.strip().lower()}"


class ToolCall(BaseModel):
    """A single typed action the agent is requesting.

    Deliberately generic (tool name + JSON args) at this layer; each
    concrete ``Tool`` in the registry (src/agent/tools.py) re-validates
    ``args`` against its own stricter pydantic schema before execution.
    That two-stage validation is what keeps a small model's near-miss JSON
    (e.g. ``"timeout_s": "30"`` instead of ``30``) from crashing the loop
    instead of just failing one step cleanly.
    """

    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(
        default="",
        description="One-line reason this action tests the current "
        "hypothesis. Kept short on purpose -- this is not a chain-of-"
        "thought dump, it is scaffolding, per Part 7's 'few good tools'.",
    )

    def summary(self) -> str:
        """A stable, human-readable one-liner used for dedup signatures
        and transcript printing."""
        args_repr = ", ".join(f"{k}={v!r}" for k, v in sorted(self.args.items()))
        return f"{self.tool}({args_repr})"


class ToolResult(BaseModel):
    """The OBSERVATION step's output: bounded, truncated, timed.

    ``output_hash`` lets the transcript prove what the *full* (untruncated)
    output was without paying the context cost of storing it -- "capture
    bounded output of last action (truncated, hashed)" per Part 7.
    """

    ok: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_s: float = 0.0
    truncated: bool = False
    output_hash: str | None = None
    error: str | None = None


class AgentStepOutput(BaseModel):
    """The full structured output the model must produce for ONE step.

    This is the schema the loop parses out of the model's completion. It
    intentionally encodes the OBSERVE -> STATE -> HYPOTHESIS -> PLAN ->
    ACTION chain from Part 7 into fields the model fills in, rather than
    free prose the loop would have to regex apart.
    """

    hypothesis: str = Field(
        description="What the agent currently believes and is trying to "
        "test or exploit."
    )
    plan: str = Field(description="The single next step, in one sentence.")
    action: ToolCall
    new_facts: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    give_up: bool = Field(
        default=False,
        description="Set true only if the model believes the goal is "
        "unreachable and further action would be pure flailing.",
    )


class Evaluation(str, enum.Enum):
    CONFIRMED = "confirmed"
    DENIED = "denied"
    INCONCLUSIVE = "inconclusive"


class StepRecord(BaseModel):
    """One full loop iteration, as persisted to the transcript."""

    step: int
    output: AgentStepOutput
    result: ToolResult
    evaluation: Evaluation
    blocked_repeat: bool = Field(
        default=False,
        description="True if this action's signature matched a known "
        "failure and was blocked from executing (Part 7 failure memory).",
    )
    duration_s: float = 0.0
    ts: float = Field(default_factory=time.time)


class EpisodeOutcome(str, enum.Enum):
    GOAL_REACHED = "goal_reached"
    STEP_BUDGET_EXHAUSTED = "step_budget_exhausted"
    GAVE_UP = "gave_up"
    ERROR = "error"


class EpisodeResult(BaseModel):
    """Everything a batch runner or analysis notebook needs from one run."""

    goal: Goal
    outcome: EpisodeOutcome
    steps_taken: int
    transcript: list[StepRecord]
    summary_events: list[str] = Field(
        default_factory=list,
        description="Log of summarizer/replan events, for debugging context "
        "management rather than agent cognition.",
    )
    seed: int | None = None
    error: str | None = None


class AgentState(BaseModel):
    """The compact structured belief the model is shown each step.

    Kept intentionally small (Part 2/7: "keeps context short = keeps
    prefill cheap, non-negotiable on CPU"). Long-running episodes fold
    older facts/failures into ``summary`` rather than growing these lists
    without bound -- see src/agent/summarizer.py.
    """

    goal: Goal
    step: int = 0
    facts: list[Fact] = Field(default_factory=list)
    failures: list[FailureRecord] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    strategy_note: str = Field(
        default="",
        description="Output of the last periodic re-plan call (see "
        "AgentLoop._maybe_replan). Empty until the first replan interval.",
    )
    summary: str = Field(
        default="",
        description="Rolling summary of facts/failures older than the "
        "summarizer's retention window.",
    )
